import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.dev_server import MAX_BODY_BYTES, PATH, create_development_app
from app.main import app
from ml import dev_inference
from test_extract import docx


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("CVDETECT_ENV", "development")
    monkeypatch.setenv("CVDETECT_EXPERIMENTAL_INFERENCE", "1")
    return TestClient(create_development_app(), base_url="http://127.0.0.1:8001", client=("127.0.0.1", 1234))


def test_normal_app_never_exposes_route_even_if_opted_in(monkeypatch):
    monkeypatch.setenv("CVDETECT_ENV", "development")
    monkeypatch.setenv("CVDETECT_EXPERIMENTAL_INFERENCE", "1")
    with TestClient(app, base_url="http://127.0.0.1:8001", client=("127.0.0.1", 1234)) as client:
        assert client.post(PATH, json={"text": "fictional text"}).status_code == 404
        assert PATH not in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("environment,optin", [(None, None), ("development", None), (None, "1"), ("production", "1"), ("test", "1"), ("development", "true")])
def test_configuration_fails_closed(monkeypatch, environment, optin):
    for key, value in [("CVDETECT_ENV", environment), ("CVDETECT_EXPERIMENTAL_INFERENCE", optin)]:
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        create_development_app()


@pytest.mark.parametrize("headers", [
    {"origin": "http://localhost:5173"}, {"x-forwarded-for": "127.0.0.1"},
    {"forwarded": "for=127.0.0.1"}, {"x-real-ip": "127.0.0.1"}, {"host": "evil.example"},
])
def test_browser_proxy_and_untrusted_host_rejected(enabled, headers):
    response = enabled.post(PATH, headers=headers, json={"text": "fictional"})
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_cannot_enable_route(enabled):
    response = enabled.options(PATH, headers={"origin": "http://localhost:5173", "access-control-request-method": "POST"})
    assert response.status_code == 404
    assert "access-control-allow-origin" not in response.headers


def test_remote_socket_and_wildcard_server_rejected(monkeypatch):
    monkeypatch.setenv("CVDETECT_ENV", "development")
    monkeypatch.setenv("CVDETECT_EXPERIMENTAL_INFERENCE", "1")
    local = create_development_app()
    for base, peer in [("http://127.0.0.1:8001", ("192.0.2.1", 42)), ("http://0.0.0.0:8001", ("127.0.0.1", 42))]:
        client = TestClient(local, base_url=base, client=peer)
        assert client.post(PATH, headers={"host": "127.0.0.1:8001"}, json={"text": "fictional"}).status_code == 404


@pytest.mark.parametrize("payload", [{}, {"text": ""}, {"text": "!!!"}, {"text": 42}, {"text": "valid", "other": 1}, {"text": "x" * 20001}, {"text": "\ud800"}])
def test_invalid_input(enabled, payload):
    response = enabled.post(PATH, content=json.dumps(payload), headers={"content-type": "application/json"})
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_invalid_content_and_size(enabled):
    assert enabled.post(PATH, content="x", headers={"content-type": "text/plain"}).status_code == 415
    assert enabled.post(PATH, content="{", headers={"content-type": "application/json"}).status_code == 400
    assert enabled.post(PATH, content=b"x" * (MAX_BODY_BYTES + 1), headers={"content-type": "application/json"}).status_code == 413


def test_deterministic_research_output_and_no_personal_echo(enabled):
    text = "Fictional text uniquerequesttoken person@example.com"
    first = enabled.post(PATH, json={"text": text})
    second = enabled.post(PATH, json={"text": text})
    assert first.status_code == 200 and first.json() == second.json()
    assert first.headers["cache-control"] == "no-store"
    result = first.json()
    assert result["status"] == "unvalidated_research_model"
    assert result["authorship_conclusion"] == "inconclusive"
    assert "raw_uncalibrated_decision_score" in result["model_diagnostic"]
    assert "not a probability" in json.dumps(result)
    assert "research only" in json.dumps(result).lower()
    assert "probability" not in result["model_diagnostic"]
    assert text not in first.text and "person@example.com" not in first.text


def test_request_text_never_changes_training_state(enabled):
    dev_inference._fictional_model.cache_clear()
    assert enabled.post(PATH, json={"text": "Unique request content qzxtrainingprobe"}).status_code == 200
    model = dev_inference._fictional_model()
    vocabulary = dict(model.named_steps["tfidf"].vocabulary_)
    coefficients = model.named_steps["classifier"].coef_.copy()
    assert "qzxtrainingprobe" not in vocabulary
    assert enabled.post(PATH, json={"text": "Another content qzxsecondprobe"}).status_code == 200
    assert model is dev_inference._fictional_model()
    assert model.named_steps["tfidf"].vocabulary_ == vocabulary
    np.testing.assert_array_equal(model.named_steps["classifier"].coef_, coefficients)


def test_training_receives_only_fixed_smoke_partition(monkeypatch):
    observed = []
    original = dev_inference.train
    def spy(training, test):
        observed.append(([r["source_id"] for r in training], [r["source_id"] for r in test]))
        return original(training, test)
    monkeypatch.setattr(dev_inference, "train", spy)
    dev_inference._fictional_model.cache_clear()
    try:
        dev_inference.infer("Fictional request does not belong in training.")
        dev_inference.infer("Another fictional request.")
        assert observed == [([f"fiction-{i:02d}" for i in range(1, 9)], [f"fiction-{i:02d}" for i in range(9, 13)])]
    finally:
        dev_inference._fictional_model.cache_clear()


def test_original_api_identical_in_development_app(enabled):
    document = docx("Summary\nHardworking team player\nProjects\n- Responsible for tasks")
    files = {"file": ("cv.docx", document)}
    normal = TestClient(app).post("/api/cv/analyze", files=files)
    development = enabled.post("/api/cv/analyze", files=files)
    assert normal.status_code == development.status_code == 200
    assert normal.json() == development.json()
    assert development.headers["cache-control"] == "no-store"


def test_safe_internal_failure(enabled, monkeypatch):
    def broken(_):
        raise RuntimeError("sensitive detail")
    monkeypatch.setattr(dev_inference, "infer", broken)
    response = enabled.post(PATH, json={"text": "fictional"})
    assert response.status_code == 503 and "sensitive detail" not in response.text
