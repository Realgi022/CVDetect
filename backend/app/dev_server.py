"""Opt-in localhost-only launcher; never use this module as a production ASGI app."""
import ipaddress
import json
import os
import socket

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
import uvicorn

from .main import app as normal_app

PATH = "/api/experimental/writing-diagnostic"
MAX_BODY_BYTES = 64 * 1024


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

    @dev_app.middleware("http")
    async def gate_experiment(request: Request, call_next):
        if request.url.path == PATH:
            if not _local_request(request):
                return JSONResponse({"detail": "Not found."}, status_code=404, headers={"Cache-Control": "no-store"})
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        return await call_next(request)

    @dev_app.post(PATH, include_in_schema=False)
    async def experimental(request: Request):
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
        # Import ML dependencies only for an opted-in request; the normal app
        # remains usable without scikit-learn installed.
        try:
            from ml.dev_inference import infer
            return await run_in_threadpool(infer, payload["text"])
        except ValueError:
            raise HTTPException(400, "Invalid text or research model configuration.") from None
        except Exception:
            # Do not log exceptions: they can contain input or sensitive paths.
            raise HTTPException(503, "Local research model unavailable.") from None

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
