from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.exceptions import ProviderUnavailableError
from app.main import provider_unavailable_handler


def test_provider_unavailable_error_returns_503():
    test_app = FastAPI()
    test_app.add_exception_handler(ProviderUnavailableError, provider_unavailable_handler)

    @test_app.get("/boom")
    def boom():
        raise ProviderUnavailableError("Gemini", "connection refused")

    client = TestClient(test_app)
    response = client.get("/boom")

    assert response.status_code == 503
    assert response.json() == {"detail": "Gemini is unavailable: connection refused"}
