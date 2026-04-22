import asyncio
from typing import Any, Dict, Optional

async def asgi(app, request, env, ctx):
    """
    Surgical ASGI Bridge for Cloudflare Workers.
    Adapts the Cloudflare Worker request structure to a standard ASGI call.
    """
    # 1. Prepare the ASGI Scope
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": request.method,
        "scheme": "https",
        "path": request.url.path,
        "query_string": request.url.search.lstrip("?").encode("ascii"),
        "headers": [(k.lower().encode("ascii"), v.encode("ascii")) for k, v in request.headers.items()],
        "client": (request.headers.get("cf-connecting-ip", "127.0.0.1"), 0),
        "server": ("whiteflowsint.com", 443),
        "env": env,  # Pass the Worker environment (D1, etc.)
        "ctx": ctx,
    }

    # 2. Define the communication channel
    response_body = []
    response_headers = []
    response_status = 200
    response_started = asyncio.Event()

    async def receive() -> Dict[str, Any]:
        body = await request.arrayBuffer()
        return {
            "type": "http.request",
            "body": bytes(body),
            "more_body": False,
        }

    async def send(message: Dict[str, Any]) -> None:
        nonlocal response_status, response_headers
        if message["type"] == "http.response.start":
            response_status = message["status"]
            response_headers = [
                (k.decode("ascii"), v.decode("ascii")) 
                for k, v in message.get("headers", [])
            ]
            response_started.set()
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    # 3. Call the application
    await app(scope, receive, send)
    
    # 4. Construct the Cloudflare Response
    # Note: We import Response at runtime to avoid top-level issues
    from js import Response, Headers
    
    headers = Headers()
    for k, v in response_headers:
        headers.append(k, v)
        
    return Response.new(b"".join(response_body), status=response_status, headers=headers)
