import pytest

import app.dev_server as server
from test_extract import docx
from test_research_upload import artifact, browser, trust  # fixtures and trusted synthetic artifact
from test_research_browser import headers, session


def preflight(client, path, origin=server.VITE_ORIGIN, method="POST", names="x-csrf-token"):
    return client.options(path, headers={"origin": origin, "access-control-request-method": method, "access-control-request-headers": names})


def test_bridge_fails_closed_without_server_optin(browser):
    assert preflight(browser, server.VITE_SESSION, names="x-research-session").status_code == 404
    assert browser.post(server.VITE_SESSION, headers={"origin": server.VITE_ORIGIN, "x-research-session": "1"}).status_code == 404


@pytest.mark.parametrize("path", server.VITE_PATHS)
def test_exact_cors_host_and_forwarding(browser, monkeypatch, path):
    monkeypatch.setenv("CVDETECT_RESEARCH_VITE", "1")
    response = preflight(browser, path)
    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == server.VITE_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["cache-control"] == "no-store"
    for origin in ["http://localhost:5173", "http://127.0.0.1:5174", "null", "http://evil.test"]:
        denied = preflight(browser, path, origin=origin)
        assert denied.status_code == 404 and "access-control-allow-origin" not in denied.headers
    assert preflight(browser, path, method="GET").status_code == 404
    assert preflight(browser, path, names="x-untrusted").status_code == 404
    assert browser.post(path, headers={"origin": server.VITE_ORIGIN, "host": "localhost:8001"}).status_code == 404
    assert browser.post(path, headers={"origin": server.VITE_ORIGIN, "x-forwarded-for": "127.0.0.1"}).status_code == 404


def test_session_csrf_and_actual_fictional_inference(browser, monkeypatch, artifact):
    monkeypatch.setenv("CVDETECT_RESEARCH_VITE", "1")
    trust(monkeypatch, artifact)
    origin = {"origin": server.VITE_ORIGIN}
    assert browser.post(server.VITE_SESSION, headers=origin).status_code == 403
    bootstrap = browser.post(server.VITE_SESSION, headers={**origin, "x-research-session": "1"})
    assert bootstrap.status_code == 200
    assert "httponly" in bootstrap.headers["set-cookie"].lower() and "samesite=strict" in bootstrap.headers["set-cookie"].lower()
    token = bootstrap.json()["csrf_token"]
    assert browser.post(server.VITE_EXTRACT, headers=origin, files={"file": ("fictional.docx", docx())}).status_code == 403
    assert browser.post(server.VITE_EXTRACT, headers={**origin, "x-csrf-token": "0" * 64}, files={"file": ("fictional.docx", docx())}).status_code == 403
    valid = {**origin, "x-csrf-token": token}
    extraction = browser.post(server.VITE_EXTRACT, headers=valid, files={"file": ("fictional.docx", docx("Fictional project."))})
    assert extraction.status_code == 200
    result = browser.post(server.VITE_ARTIFACT, headers=valid, json={"text": extraction.json()["extracted_text"]})
    assert result.status_code == 200 and result.json()["authorship_conclusion"] == "inconclusive"
    assert isinstance(result.json()["model_diagnostic"]["raw_uncalibrated_decision_score"], float)
    assert result.json()["model_metadata"]["artifact_sha256"] == artifact[2]
    assert "Fictional project" not in result.text
    assert browser.post(server.RESEARCH_ARTIFACT, headers=valid, json={"text": "fictional"}).status_code == 404
    assert browser.post(server.VITE_EXTRACT, headers=valid, files={"file": ("bad.txt", b"x")}).status_code == 415
    assert browser.post(server.VITE_EXTRACT, headers=valid, files={"file": ("big.pdf", b"x" * (5 * 1024 * 1024 + 1))}).status_code == 413
    monkeypatch.delenv("CVDETECT_RESEARCH_TRUSTED_PICKLE")
    assert browser.post(server.VITE_ARTIFACT, headers=valid, json={"text": "fictional"}).status_code == 503


def test_session_bound_expired_and_normal_app_absent(browser, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("CVDETECT_RESEARCH_VITE", "1")
    now = 1_700_000_000
    monkeypatch.setattr(server.time, "time", lambda: now)
    h = {"origin": server.VITE_ORIGIN, "x-research-session": "1"}
    first = browser.post(server.VITE_SESSION, headers=h).json()["csrf_token"]
    second = browser.post(server.VITE_SESSION, headers=h).json()["csrf_token"]
    assert browser.post(server.VITE_ARTIFACT, headers={"origin": server.VITE_ORIGIN, "x-csrf-token": first}, json={"text": "fictional"}).status_code == 403
    monkeypatch.setattr(server.time, "time", lambda: now + server.SESSION_SECONDS)
    assert browser.post(server.VITE_ARTIFACT, headers={"origin": server.VITE_ORIGIN, "x-csrf-token": second}, json={"text": "fictional"}).status_code == 403
    client = TestClient(app, base_url=server.ORIGIN, client=("127.0.0.1", 42))
    for path in server.VITE_PATHS:
        assert client.post(path, headers=h).status_code == 404
    token, _ = session(browser)
    assert browser.post(server.RESEARCH_API, headers=headers(token, server.VITE_ORIGIN), json={"text": "fictional"}).status_code == 404
