import logging
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.exceptions import register_exception_handlers
from app.core.security import create_jwt_token
from app.services.datalake_service import DataLakeService
from run import app


@pytest.mark.parametrize("explicit_http_error", [True, False])
def test_internal_errors_are_not_exposed_or_logged_verbatim(caplog, explicit_http_error):
    private_details = "credential-value /private/internal.sql SELECT private_data"
    isolated_app = FastAPI()
    register_exception_handlers(isolated_app)
    isolated_app.add_middleware(
        CORSMiddleware, allow_origins=["https://app.example.test"], allow_credentials=True
    )

    @isolated_app.get("/failure")
    def failure():
        if explicit_http_error:
            raise HTTPException(500, detail={"message": private_details})
        raise RuntimeError(private_details)

    with caplog.at_level(logging.ERROR):
        response = TestClient(isolated_app).get(
            "/failure", headers={"Origin": "https://app.example.test"}
        )
    assert response.status_code == 500
    assert private_details not in response.text
    assert private_details not in caplog.text
    assert response.json()["message"] == "Erro interno do servidor."
    assert response.headers["Access-Control-Allow-Origin"] == "https://app.example.test"


def test_upload_parser_errors_do_not_expose_paths_or_data(monkeypatch, caplog):
    private_details = "credential-value /private/customer.csv personal-data"
    monkeypatch.setattr(
        DataLakeService, "process_ingestion", Mock(side_effect=ValueError(private_details))
    )
    response = TestClient(app).post(
        "/api/v1/ingestao/clientes",
        headers={"Authorization": f"Bearer {create_jwt_token({'sub': 'test-user'})}"},
        files={"arquivo": ("clients.csv", b"invalid data", "text/csv")},
    )
    assert response.status_code == 422
    assert private_details not in response.text
    assert private_details not in caplog.text


def test_upload_byte_limit_is_enforced_before_ingestion(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 4)
    ingest = Mock(side_effect=AssertionError("Oversized upload reached ingestion"))
    monkeypatch.setattr(DataLakeService, "process_ingestion", ingest)
    response = TestClient(app).post(
        "/api/v1/ingestao/clientes",
        headers={"Authorization": f"Bearer {create_jwt_token({'sub': 'test-user'})}"},
        files={"arquivo": ("clients.csv", b"12345", "text/csv")},
    )
    assert response.status_code == 413
    ingest.assert_not_called()
