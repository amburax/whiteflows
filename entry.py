# Step-by-step reintegration
from js import Response

async def on_fetch(request, env):
    try:
        # Try to import the server without using it yet
        import server
        return Response.new(f"IMPORT SUCCESS: server.py loaded! FastAPI version: {server.FastAPI.__module__ if hasattr(server, 'FastAPI') else 'unknown'}")
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        return Response.new(f"IMPORT FAILED:\n\n{error_info}")
