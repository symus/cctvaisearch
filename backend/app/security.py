"""Protection for a localhost API against other websites in the same browser.

* Host header allow-list (blocks DNS-rebinding attacks).
* CORS limited to the configured frontend origins.
* State-changing requests carrying a foreign ``Origin`` are rejected, which
  blocks cross-site form posts that CORS alone would not stop.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import Settings
from .errors import error_response

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class OriginCheckMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: list[str], port: int):
        self.app = app
        self.allowed = set(allowed_origins) | {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS:
            headers = dict(scope.get("headers") or [])
            origin = headers.get(b"origin")
            if origin is not None and origin.decode("latin-1") not in self.allowed:
                resp = error_response(403, "forbidden_origin", "Cross-origin request rejected")
                await resp(scope, receive, send)
                return
        await self.app(scope, receive, send)


def install_security(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.allowed_origins, port=settings.port)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
