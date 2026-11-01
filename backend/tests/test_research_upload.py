import hashlib
import json

import pytest
from fastapi.testclient import TestClient

import app.dev_server as server
from app.main import MAX_FILE_SIZE, app
from ml.research_training import fictional_records, run_comparison
from test_extract import docx, pdf
from test_research_browser import headers, session


@pytest.fixture(scope="module")
def artifact(tmp_path_factory):
    directory = tmp_path_factory.mktemp("fictional-artifact")
    (directory / ".gitignore").write_text("*\n", encoding="utf-8")
    run_comparison(fictional_records(), directory, evidence="synthetic")
    model = next(directory.glob("model-*.pkl"))
    report = next(directory.glob("report-*.json"))
    return model, report, hashlib.sha256(model.read_bytes()).hexdigest()


@pytest.fixture
def browser(monkeypatch):
    monkeypatch.setenv("CVDETECT_ENV", "development")
    monkeypatch.setenv("CVDETECT_EXPERIMENTAL_INFERENCE", "1")
    for key in ("CVDETECT_RESEARCH_TRUSTED_PICKLE", "CVDETECT_RESEARCH_MODEL_PATH", "CVDETECT_RESEARCH_MODEL_REPORT", "CVDETECT_RESEARCH_MODEL_SHA256"):
        monkeypatch.delenv(key, raising=False)
    return TestClient(server.create_development_app(), base_url=server.ORIGIN, client=("127.0.0.1", 1234))


def trust(monkeypatch, artifact):
    model, report, digest = artifact
    for key, value in (("CVDETECT_RESEARCH_TRUSTED_PICKLE", "1"), ("CVDETECT_RESEARCH_MODEL_PATH", str(model)),
                       ("CVDETECT_RESEARCH_MODEL_REPORT", str(report)), ("CVDETECT_RESEARCH_MODEL_SHA256", digest)):
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize("name,data", [("fictional.pdf", pdf("Fictional CV project qzxprivate")), ("fictional.docx", docx("Fictional CV project qzxprivate"))])
def test_upload_preview_and_explicit_trusted_inference(browser, monkeypatch, artifact, caplog, name, data):
    token, _ = session(browser)
    extracted = browser.post(server.RESEARCH_EXTRACT, headers=headers(token), files={"file": (name, data)})
    assert extracted.status_code == 200 and "qzxprivate" in extracted.json()["extracted_text"]
    assert extracted.headers["cache-control"] == "no-store" and extracted.headers["content-security-policy"] == server.CSP
    assert "filename" not in extracted.json()
    missing = browser.post(server.RESEARCH_ARTIFACT, headers=headers(token), json={"text": extracted.json()["extracted_text"]})
    assert missing.status_code == 503
    trust(monkeypatch, artifact)
    response = browser.post(server.RESEARCH_ARTIFACT, headers=headers(token), json={"text": extracted.json()["extracted_text"]})
    assert response.status_code == 200
    result = response.json()
    assert result["authorship_conclusion"] == "inconclusive" and result["model_metadata"]["evidence_status"] == "synthetic"
    assert result["model_metadata"]["artifact_sha256"] == artifact[2]
    assert "qzxprivate" not in response.text and "qzxprivate" not in caplog.text
    assert "probability" in json.dumps(result) and "false accusations" in json.dumps(result).lower()
    assert "%" not in response.text


@pytest.mark.parametrize("name,data,code", [("bad.txt", b"text", 415), ("bad.pdf", b"garbage", 422),
    ("bad.docx", b"garbage", 422), ("encrypted.pdf", pdf(encrypted=True), 422),
    ("encrypted.docx", bytes.fromhex("D0CF11E0A1B11AE1") + b"fictional", 422),
    ("big.pdf", b"x" * (MAX_FILE_SIZE + 1), 413), ("empty.pdf", b"", 422)])
def test_invalid_uploads(browser, name, data, code):
    token, _ = session(browser)
    assert browser.post(server.RESEARCH_EXTRACT, headers=headers(token), files={"file": (name, data)}).status_code == code


@pytest.mark.parametrize("path", [server.RESEARCH_EXTRACT, server.RESEARCH_ARTIFACT])
def test_security_and_public_isolation(browser, path):
    token, _ = session(browser)
    for header in ({}, {"origin": server.ORIGIN}, headers(token, "http://localhost:8001"), {**headers(token), "host": "localhost:8001"}, {**headers(token), "x-forwarded-for": "127.0.0.1"}):
        assert browser.post(path, headers=header, json={"text": "fictional"}).status_code in (403, 404)
    assert browser.post(path, headers=headers("0" * 64), json={"text": "fictional"}).status_code == 403
    public = TestClient(app, base_url=server.ORIGIN, client=("127.0.0.1", 1234))
    assert public.post(path, headers=headers(token), json={"text": "fictional"}).status_code == 404


def test_artifact_requires_explicit_trust_and_hash(browser, monkeypatch, artifact):
    token, _ = session(browser)
    trust(monkeypatch, artifact)
    monkeypatch.setenv("CVDETECT_RESEARCH_TRUSTED_PICKLE", "0")
    assert browser.post(server.RESEARCH_ARTIFACT, headers=headers(token), json={"text": "fictional"}).status_code == 503
    monkeypatch.setenv("CVDETECT_RESEARCH_TRUSTED_PICKLE", "1")
    monkeypatch.setenv("CVDETECT_RESEARCH_MODEL_SHA256", "0" * 64)
    assert browser.post(server.RESEARCH_ARTIFACT, headers=headers(token), json={"text": "fictional"}).status_code == 503


def test_no_unpickle_on_creation_or_bad_digest(browser, monkeypatch, artifact):
    from ml import artifact_inference
    calls = []
    monkeypatch.setattr(artifact_inference.pickle, "loads", lambda data: calls.append(True))
    trust(monkeypatch, artifact)
    monkeypatch.setenv("CVDETECT_RESEARCH_MODEL_SHA256", "0" * 64)
    token, _ = session(browser)
    assert calls == []
    assert browser.post(server.RESEARCH_ARTIFACT, headers=headers(token), json={"text": "fictional"}).status_code == 503
    assert calls == []


def test_extracted_text_research_limit(browser):
    token, _ = session(browser)
    response = browser.post(server.RESEARCH_EXTRACT, headers=headers(token), files={"file": ("fictional.docx", docx("x" * 20001))})
    assert response.status_code == 422 and "20,000" in response.json()["detail"]


def test_malformed_requests_are_safe(browser):
    token, _ = session(browser)
    assert browser.post(server.RESEARCH_EXTRACT, headers=headers(token), json={}).status_code == 400
    assert browser.post(server.RESEARCH_ARTIFACT, headers={**headers(token), "content-type": "application/json"}, content="{").status_code == 400
    assert browser.post(server.RESEARCH_ARTIFACT, headers=headers(token), json={"text": "fictional", "extra": 1}).status_code == 400


@pytest.mark.parametrize("path", [server.RESEARCH_EXTRACT, server.RESEARCH_ARTIFACT])
def test_research_post_expiration_and_remote_peers(browser, monkeypatch, path):
    now = 1_700_000_000
    monkeypatch.setattr(server.time, "time", lambda: now)
    token, _ = session(browser)
    monkeypatch.setattr(server.time, "time", lambda: now + server.SESSION_SECONDS)
    assert browser.post(path, headers=headers(token), json={"text": "fictional"}).status_code == 403
    remote = TestClient(browser.app, base_url=server.ORIGIN, client=("192.0.2.1", 42))
    assert remote.post(path, headers=headers(token), json={"text": "fictional"}).status_code == 404
