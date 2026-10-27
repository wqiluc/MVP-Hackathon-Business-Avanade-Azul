import ast
from pathlib import Path
from unittest.mock import patch

from ai.agents.workflow import invoke_agent_workflow


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_agent_workflow_uses_the_current_deterministic_flow():
    result = invoke_agent_workflow(
        {
            "client_identifier": "AZ-test",
            "frequency": 15,
            "total_spend": 85000.0,
            "churn_score": 0.8,
            "flight_incidents": 2,
            "incident_type": "Downgrade Involuntário",
            "tier": "Diamante",
            "value_at_risk": 0.0,
            "graph_rag_context": {},
            "decision": {},
            "audit_status": "",
        }
    )

    assert result["tier"] == "Diamante"
    assert result["churn_score"] == 0.8
    assert result["value_at_risk"] == 88400.0
    assert result["graph_rag_context"]["graph_relations"] == [
        "Diamante -> categorias",
        "Downgrade Involuntário -> revisão humana necessária",
    ]
    assert result["decision"]["action_code"] == "recuperacao-servico"
    assert result["decision"]["proposal"]["voucher_value"] == 0.0
    assert result["graph_rag_context"]["policy_context"] in result["decision"]["evidence"]
    assert result["graph_rag_context"]["policies_verified"] is False
    assert result["audit_status"] == "WORKFLOW_COMPLETE"


def test_agent_keeps_graph_context_separate_and_uses_matching_policy_evidence():
    result = invoke_agent_workflow(
        {
            "client_identifier": "AZ-test",
            "frequency": 2,
            "total_spend": 1000.0,
            "churn_score": 0.1,
            "flight_incidents": 2,
            "incident_type": "Downgrade Involuntário",
            "tier": "Básico",
            "value_at_risk": 0.0,
            "graph_rag_context": {},
            "decision": {},
            "audit_status": "",
        }
    )

    assert result["graph_rag_context"]["graph_relations"]
    assert result["decision"]["action_code"] == "recuperacao-servico"
    assert result["graph_rag_context"]["policy_context"] in result["decision"]["evidence"]


def test_decision_routes_typed_incident_for_human_review():
    result = invoke_agent_workflow(
        {
            "client_identifier": "AZ-test",
            "frequency": 2,
            "total_spend": 1000.0,
            "churn_score": 0.1,
            "flight_incidents": 1,
            "incident_type": "Downgrade Involuntário",
            "tier": "Básico",
            "value_at_risk": 0.0,
            "graph_rag_context": {},
            "decision": {},
            "audit_status": "",
        }
    )

    assert result["decision"]["action_code"] == "recuperacao-servico"
    assert any(
        "Tipo de incidente informado: Downgrade Involuntário" in item
        for item in result["decision"]["evidence"]
    )


def test_policy_verification_status_changes_recommendation_strategy_and_proposal():
    def run_with_policy_status(policies_verified):
        with patch(
            "ai.agents.workflow.query_context",
            return_value={
                "tier": "Safira",
                "incident_type": None,
                "graph_relations": ["Safira -> categorias"],
                "policy_context": "Contexto de política de teste.",
                "policies_verified": policies_verified,
            },
        ):
            return invoke_agent_workflow(
                {
                    "client_identifier": "AZ-test",
                    "frequency": 2,
                    "total_spend": 1000.0,
                    "churn_score": 0.1,
                    "flight_incidents": 0,
                    "incident_type": None,
                    "tier": "Safira",
                    "value_at_risk": 0.0,
                    "graph_rag_context": {},
                    "decision": {},
                    "audit_status": "",
                }
            )["decision"]

    unverified = run_with_policy_status(False)
    verified = run_with_policy_status(True)

    assert "política não verificada" in unverified["strategy"]
    assert "Demonstração não verificada" in unverified["proposal"]["benefit"]
    assert any("não verificado" in item for item in unverified["evidence"])
    assert "política verificada" in verified["strategy"]
    assert "confirmar a elegibilidade individual" in verified["proposal"]["benefit"]
    assert any("marcado como verificado" in item for item in verified["evidence"])
    assert unverified["proposal"] != verified["proposal"]
    assert unverified["proposal"]["voucher_value"] == verified["proposal"]["voucher_value"] == 0
    assert unverified["proposal"]["bonus_points"] == verified["proposal"]["bonus_points"] == 0


def test_ai_modules_do_not_import_backend_or_infrastructure_layers():
    forbidden_roots = {
        "app",
        "backend",
        "data",
        "fastapi",
        "duckdb",
        "ml",
        "snowflake",
    }
    for source in (REPOSITORY_ROOT / "ai").rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])

        assert not (imported_roots & forbidden_roots), source


def test_ai_framework_dependencies_stay_in_their_modules():
    expected_modules = {
        "langgraph": "agents",
        "networkx": "graphrag",
        "langchain_community": "rag",
        "openai": "llm",
    }
    for source in (REPOSITORY_ROOT / "ai").rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])

        for dependency, module in expected_modules.items():
            if dependency in imported_roots:
                assert source.parent.name == module, source


def test_clients_route_delegates_agent_processing_to_application_service():
    source = REPOSITORY_ROOT / "backend" / "app" / "api" / "v1" / "clients.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert "app.services.agent_service" in imported_modules
    assert not any(module == "ai" or module.startswith("ai.") for module in imported_modules)
    assert not any(module == "langgraph" or module.startswith("langgraph.") for module in imported_modules)


def test_agent_service_adapts_backend_input_to_ai_workflow():
    source = REPOSITORY_ROOT / "backend" / "app" / "services" / "agent_service.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert "ai.agents.workflow" in imported_modules
    assert "app.core.security" in imported_modules
    assert "langgraph" not in imported_modules
    assert not any(module.startswith("ai.rag") for module in imported_modules)


def test_rag_service_adapts_ai_modules_without_duplicating_implementation():
    source = REPOSITORY_ROOT / "backend" / "app" / "services" / "rag_service.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert "ai.graphrag.context_retrieval" in imported_modules
    assert "ai.rag.embeddings" in imported_modules
    assert not any(module.startswith("langgraph") for module in imported_modules)
    assert not any(module.startswith("networkx") for module in imported_modules)
