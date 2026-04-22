import sys
import os

# ─── ASYNC BOOTLOADER ───────────────────────────────────────────────────────
# Explicitly using 'async def' to ensure Cloudflare registers the event handler.

async def on_fetch(request, env, ctx):
    """
    Surgical Entry Point with Lazy Initialization.
    """
    try:
        # 1. Setup Environment
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        LIBS_DIR = os.path.join(BASE_DIR, "libs")
        
        if LIBS_DIR not in sys.path:
            sys.path.insert(0, LIBS_DIR)
            
        # 2. Lazy Imports
        from api import app
        from worker import asgi
        
        # 3. Execution
        return await asgi(app, request, env, ctx)
        
    except Exception as e:
        # Fallback to js Response if things go south
        from js import Response
        return Response.new(f"WhiteFlows Runtime Error: {str(e)}", status=500)

# Optional: Export app for ASGI discovery if needed
app = None
