import ast
from pathlib import Path

from ai.agents.workflow import invoke_agent_workflow


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_agent_workflow_uses_the_current_deterministic_flow():
    result = invoke_agent_workflow(
        {
            "client_identifier": "AZ-test",
            "frequency": 15,
            "total_spend": 85000.0,
            "incidents": 2,
            "incident_type": "Downgrade Involuntário",
            "tier": "",
            "churn_risk": 0.0,
            "value_at_risk": 0.0,
            "graph_rag_context": {},
            "decision_reasoning": "",
            "action_proposal": {},
            "audit_status": "",
        }
    )

    assert result["tier"] == "VIP World Legend"
    assert result["churn_risk"] == 0.6
    assert result["graph_rag_context"]["graph_relations"] == [
        "Downgrade Involuntário -> Resolução 400 ANAC -> Voucher Trust-First"
    ]
    assert result["action_proposal"]["voucher_value"] == 250.0
    assert result["audit_status"] == "PASSED_TRUST_FIRST_AUDIT"


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
