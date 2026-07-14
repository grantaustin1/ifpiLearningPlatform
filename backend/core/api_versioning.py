"""API versioning — `/api/v1/*` alias for `/api/*`.

Wraps the ASGI app so any incoming request whose path starts with
`/api/v1/` is rewritten to `/api/` BEFORE FastAPI routing runs. Every
existing endpoint is therefore reachable under both surfaces with zero
duplicate registration:

    /api/courses            → served
    /api/v1/courses         → also served (rewritten to /api/courses)

Rationale (why middleware, not `include_router` duplication):
- 30+ routers, each with dozens of endpoints. Cloning them would
  double the route table and require touching every router file.
- Middleware is a single, reversible seam. When we're ready to
  deprecate the unversioned `/api/*` alias, we flip a flag here.
- No behaviour change on the response side — clients see identical
  JSON, headers, and status codes.

Marker header (`X-API-Version: v1`) is added on the way out so ops can
see which prefix a client used without inspecting access logs.
"""
from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send


V1_PREFIX = "/api/v1/"
UNVERSIONED_PREFIX = "/api/"


class ApiV1AliasMiddleware:
    """Path-rewrite middleware. If the request path starts with
    `/api/v1/`, strip the `/v1` segment so downstream routing sees the
    canonical `/api/...` path. Otherwise pass through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        raw_path: bytes = scope.get("raw_path") or scope["path"].encode()
        path: str = scope["path"]
        used_v1 = path.startswith(V1_PREFIX)

        if used_v1:
            # Rewrite `/api/v1/xyz` → `/api/xyz`
            new_path = UNVERSIONED_PREFIX + path[len(V1_PREFIX):]
            scope = dict(scope)
            scope["path"] = new_path
            # `raw_path` mirrors `path` in bytes for downstream
            # compatibility (Starlette uses whichever is present).
            scope["raw_path"] = new_path.encode() + raw_path[len(path.encode()):] \
                if raw_path.startswith(path.encode()) else new_path.encode()

        if not used_v1:
            await self.app(scope, receive, send)
            return

        # Wrap `send` to stamp `X-API-Version: v1` on the response.
        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((b"x-api-version", b"v1"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
