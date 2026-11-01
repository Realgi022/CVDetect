"""Opt-in localhost-only launcher; never use this module as a production ASGI app."""
import ipaddress
import hashlib
import hmac
import json
import os
import secrets
import socket
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool
import uvicorn

from .main import app as normal_app

PATH = "/api/experimental/writing-diagnostic"
MAX_BODY_BYTES = 64 * 1024
RESEARCH_PAGE = "/research"
RESEARCH_API = "/research/analyze"
RESEARCH_JS = "/research/app.js"
RESEARCH_CSS = "/research/style.css"
ORIGIN = "http://127.0.0.1:8001"
SESSION_SECONDS = 600
ASSETS = Path(__file__).parent / "research_ui"
FORWARDING = ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-real-ip")
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"


def _browser_local(request: Request) -> bool:
    server, client = request.scope.get("server"), request.scope.get("client")
    return bool(server and client and _loopback(server[0]) and _loopback(client[0])
                and request.headers.getlist("host") == ["127.0.0.1:8001"]
                and not any(h in request.headers for h in FORWARDING))


class ResearchSessions:
    """Short-lived signed random session IDs and independently keyed CSRF tokens."""
    def __init__(self):
        self._key = secrets.token_bytes(32)

    def _mac(self, purpose: str, value: str) -> str:
        return hmac.new(self._key, f"{purpose}:{value}".encode("ascii"), hashlib.sha256).hexdigest()

    def issue(self):
        value = f"{int(time.time())}.{secrets.token_hex(32)}"
        return f"{value}.{self._mac('session', value)}", self._mac("csrf", value)

    def valid(self, cookie: str, token: str) -> bool:
        try:
            issued, nonce, signature = cookie.split(".")
            if not (issued.isascii() and issued.isdecimal() and len(issued) <= 12 and len(nonce) == 64 and len(signature) == 64 and len(token) == 64):
                return False
            if any(c not in "0123456789abcdef" for c in nonce + signature + token):
                return False
            age = time.time() - int(issued)
            value = f"{issued}.{nonce}"
            return (0 <= age < SESSION_SECONDS and hmac.compare_digest(signature, self._mac("session", value))
                    and hmac.compare_digest(token, self._mac("csrf", value)))
        except (ValueError, TypeError):
            return False


async def _diagnostic(request: Request):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "Expected application/json.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(413, "Request exceeds the local research limit.")
        body.extend(chunk)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise HTTPException(400, "Invalid JSON request.") from None
    if not isinstance(payload, dict) or set(payload) != {"text"} or not isinstance(payload["text"], str):
        raise HTTPException(400, "Provide only a text string.")
    try:
        from ml.dev_inference import infer
        return await run_in_threadpool(infer, payload["text"])
    except ValueError:
        raise HTTPException(400, "Invalid text or research model configuration.") from None
    except Exception:
        raise HTTPException(503, "Local research model unavailable.") from None


def _loopback(address):
    try:
        return ipaddress.ip_address(address).is_loopback
    except (ValueError, TypeError):
        return False


def _local_request(request: Request) -> bool:
    # ASGI socket information must be supplied by the server, not forwarded
    # headers. Reject browsers and proxies entirely; CORS cannot enable this.
    server = request.scope.get("server")
    client = request.scope.get("client")
    host = request.headers.get("host", "").lower()
    return bool(server and client and _loopback(server[0]) and _loopback(client[0])
                and host in ("127.0.0.1", "127.0.0.1:8001")
                and not any(h in request.headers for h in ("origin", "forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-real-ip")))


def create_development_app() -> FastAPI:
    if os.environ.get("CVDETECT_ENV") != "development" or os.environ.get("CVDETECT_EXPERIMENTAL_INFERENCE") != "1":
        raise RuntimeError("Experimental server requires explicit local development opt-in.")
    dev_app = FastAPI(title="CVDetect local research", docs_url=None, redoc_url=None, openapi_url=None)
    sessions = ResearchSessions()

    @dev_app.middleware("http")
    async def gate_experiment(request: Request, call_next):
        if request.url.path in (RESEARCH_PAGE, RESEARCH_API, RESEARCH_JS, RESEARCH_CSS):
            origins = request.headers.getlist("origin")
            allowed_origin = origins == [ORIGIN] if request.url.path == RESEARCH_API else (not origins or origins == [ORIGIN])
            if not _browser_local(request) or not allowed_origin:
                response = JSONResponse({"detail": "Not found."}, status_code=404)
            else:
                response = await call_next(request)
            response.headers.update({"Cache-Control": "no-store", "Content-Security-Policy": CSP,
                                     "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
            return response
        if request.url.path == PATH:
            if not _local_request(request):
                return JSONResponse({"detail": "Not found."}, status_code=404, headers={"Cache-Control": "no-store"})
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        return await call_next(request)

    @dev_app.post(PATH, include_in_schema=False)
    async def experimental(request: Request):
        return await _diagnostic(request)

    @dev_app.get(RESEARCH_PAGE, include_in_schema=False)
    async def research_page():
        cookie, token = sessions.issue()
        html = (ASSETS / "index.html").read_text(encoding="utf-8").replace("{{CSRF_TOKEN}}", token)
        response = HTMLResponse(html)
        response.set_cookie("research_session", cookie, max_age=SESSION_SECONDS, httponly=True, samesite="strict", path="/research")
        return response

    @dev_app.get(RESEARCH_JS, include_in_schema=False)
    async def research_js():
        return Response((ASSETS / "app.js").read_text(encoding="utf-8"), media_type="text/javascript")

    @dev_app.get(RESEARCH_CSS, include_in_schema=False)
    async def research_css():
        return Response((ASSETS / "style.css").read_text(encoding="utf-8"), media_type="text/css")

    @dev_app.post(RESEARCH_API, include_in_schema=False)
    async def research_analyze(request: Request):
        tokens = request.headers.getlist("x-csrf-token")
        if len(tokens) != 1 or not sessions.valid(request.cookies.get("research_session", ""), tokens[0]):
            raise HTTPException(403, "Session expired or invalid; reload the research page.")
        return await _diagnostic(request)

    dev_app.mount("/", normal_app)
    return dev_app


def main():
    app = create_development_app()
    # Own the socket rather than accepting a configurable/public bind address.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 8001))
        listener.listen(128)
        config = uvicorn.Config(app, host="127.0.0.1", port=8001, proxy_headers=False, access_log=False)
        uvicorn.Server(config).run(sockets=[listener])


if __name__ == "__main__":
    main()
