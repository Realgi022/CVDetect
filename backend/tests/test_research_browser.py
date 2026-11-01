import re

import pytest
from fastapi.testclient import TestClient

import app.dev_server as server
from app.main import app
from ml import dev_inference


@pytest.fixture
def browser(monkeypatch):
    monkeypatch.setenv("CVDETECT_ENV", "development")
    monkeypatch.setenv("CVDETECT_EXPERIMENTAL_INFERENCE", "1")
    return TestClient(server.create_development_app(), base_url=server.ORIGIN, client=("127.0.0.1", 1234))


def session(client):
    page = client.get(server.RESEARCH_PAGE)
    assert page.status_code == 200
    return re.search(r'<meta name="csrf-token" content="([a-f0-9]{64})">', page.text).group(1), page


def headers(token, origin=server.ORIGIN):
    return {"origin": origin, "x-csrf-token": token}


def test_normal_app_has_no_research_routes():
    client = TestClient(app, base_url=server.ORIGIN, client=("127.0.0.1", 1234))
    for path in (server.RESEARCH_PAGE, server.RESEARCH_JS, server.RESEARCH_CSS, server.RESEARCH_API, server.PATH):
        assert client.get(path).status_code == 404
        assert client.post(path, json={"text": "fictional"}).status_code == 404


@pytest.mark.parametrize("env,optin", [(None, None), ("development", None), (None, "1"), ("production", "1")])
def test_requires_both_optins(monkeypatch, env, optin):
    for name, value in (("CVDETECT_ENV", env), ("CVDETECT_EXPERIMENTAL_INFERENCE", optin)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        server.create_development_app()


def test_page_assets_cookie_and_headers(browser):
    token, page = session(browser)
    cookie = page.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=600" in cookie and "path=/research" in cookie
    assert token not in cookie
    for response in (page, browser.get(server.RESEARCH_JS), browser.get(server.RESEARCH_CSS)):
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-security-policy"] == server.CSP
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
    assert "innerHTML" not in browser.get(server.RESEARCH_JS).text


@pytest.mark.parametrize("origin", [None, "null", "http://localhost:8001", "http://127.0.0.1", "http://127.0.0.1:8001.evil.test", "http://127.0.0.1:8001/", "https://127.0.0.1:8001", "http://evil.test"])
def test_post_requires_exact_origin(browser, origin):
    token, _ = session(browser)
    header = {"x-csrf-token": token}
    if origin is not None:
        header["origin"] = origin
    response = browser.post(server.RESEARCH_API, headers=header, json={"text": "fictional"})
    assert response.status_code == 404
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost:8001", "127.0.0.1:8002", "evil.test", "127.0.0.1:8001.evil.test"])
def test_exact_host_required(browser, host):
    token, _ = session(browser)
    assert browser.get(server.RESEARCH_PAGE, headers={"host": host}).status_code == 404
    assert browser.post(server.RESEARCH_API, headers={**headers(token), "host": host}, json={"text": "fictional"}).status_code == 404


@pytest.mark.parametrize("header", ["forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-real-ip"])
def test_forwarded_rejected(browser, header):
    token, _ = session(browser)
    assert browser.get(server.RESEARCH_PAGE, headers={header: "127.0.0.1"}).status_code == 404
    assert browser.post(server.RESEARCH_API, headers={**headers(token), header: "127.0.0.1"}, json={"text": "fictional"}).status_code == 404


def test_non_loopback_rejected(monkeypatch):
    monkeypatch.setenv("CVDETECT_ENV", "development")
    monkeypatch.setenv("CVDETECT_EXPERIMENTAL_INFERENCE", "1")
    local = server.create_development_app()
    for base, peer in [(server.ORIGIN, ("192.0.2.1", 42)), ("http://0.0.0.0:8001", ("127.0.0.1", 42))]:
        client = TestClient(local, base_url=base, client=peer)
        assert client.get(server.RESEARCH_PAGE, headers={"host": "127.0.0.1:8001"}).status_code == 404


def test_csrf_binding_missing_tampering_and_expiry(browser, monkeypatch):
    now = 1_700_000_000
    monkeypatch.setattr(server.time, "time", lambda: now)
    token1, page1 = session(browser)
    cookie1 = browser.cookies.get("research_session")
    token2, _ = session(browser)
    assert token1 != token2 and cookie1 != browser.cookies.get("research_session")
    assert browser.post(server.RESEARCH_API, headers=headers(token1), json={"text": "fictional"}).status_code == 403
    assert browser.post(server.RESEARCH_API, headers={"origin": server.ORIGIN}, json={"text": "fictional"}).status_code == 403
    assert browser.post(server.RESEARCH_API, headers=headers("0" * 64), json={"text": "fictional"}).status_code == 403
    assert browser.post(server.RESEARCH_API, headers={**headers(token2), "cookie": "research_session=bad"}, json={"text": "fictional"}).status_code == 403
    assert browser.post(server.RESEARCH_API, headers=headers(token2), json={"text": "fictional"}).status_code == 200
    monkeypatch.setattr(server.time, "time", lambda: now + server.SESSION_SECONDS)
    assert browser.post(server.RESEARCH_API, headers=headers(token2), json={"text": "fictional"}).status_code == 403
    assert page1.headers["cache-control"] == "no-store"


def test_browser_input_and_inference_do_not_train_on_request(browser):
    token, _ = session(browser)
    header = headers(token)
    assert browser.post(server.RESEARCH_API, headers=header, json={"text": ""}).status_code == 400
    assert browser.post(server.RESEARCH_API, headers=header, json={"text": "x" * 20001}).status_code == 400
    assert browser.post(server.RESEARCH_API, headers={**header, "content-type": "application/json"}, content="{").status_code == 400
    assert browser.post(server.RESEARCH_API, headers={**header, "content-type": "application/json"}, content=b"x" * (server.MAX_BODY_BYTES + 1)).status_code == 413
    text = "Fictional qzxresearchunseen project"
    response = browser.post(server.RESEARCH_API, headers=header, json={"text": text})
    assert response.status_code == 200 and response.json()["authorship_conclusion"] == "inconclusive"
    assert response.json()["status"] == "unvalidated_research_model" and text not in response.text
    assert "qzxresearchunseen" not in dev_inference._fictional_model().named_steps["tfidf"].vocabulary_
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("payload", [{"text": "   "}, [], {"text": None}, {"text": "fictional", "extra": 1}])
def test_browser_rejects_invalid_payloads_without_echo(browser, payload):
    token, _ = session(browser)
    response = browser.post(server.RESEARCH_API, headers=headers(token), json=payload)
    assert response.status_code == 400
    assert "fictional" not in response.text


def test_browser_character_limit_boundary(browser):
    token, _ = session(browser)
    assert browser.post(server.RESEARCH_API, headers=headers(token), json={"text": "x" * 20000}).status_code == 200
    assert browser.post(server.RESEARCH_API, headers=headers(token), json={"text": "x" * 20001}).status_code == 400


def test_page_accessible_structure(browser):
    _, page = session(browser)
    for expected in ('<label for="text">', 'aria-describedby="input-help"', 'role="status"',
                     'aria-live="polite"', 'id="limitations-title"', 'not an AI-authorship probability'):
        assert expected in page.text


def test_cli_still_rejects_browser_origin(browser):
    assert browser.post(server.PATH, headers={"origin": server.ORIGIN}, json={"text": "fictional"}).status_code == 404
