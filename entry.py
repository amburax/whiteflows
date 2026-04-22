import sys
import os
import traceback

# 1. FORCE THE PATH to prioritize our bundled pure-python libraries
# This ensures ModuleNotFoundError is impossible
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(BASE_DIR, "vendor")

if VENDOR_DIR not in sys.path:
    # Insert at index 0 to override any broken system packages
    sys.path.insert(0, VENDOR_DIR)

# Global cache for the app
_cached_app = None

async def on_fetch(request, env):
    global _cached_app
    
    try:
        # Load the server ONLY when the first request arrives
        if _cached_app is None:
            import server
            _cached_app = server.app
            
        import worker
        return await worker.asgi.fetch(_cached_app, request, env)
        
    except Exception:
        # Diagnostic fallback using standard JS bridge
        import js
        error_info = traceback.format_exc()
        return js.Response.new(f"BOOT ERROR (VENDORED):\n\n{error_info}")
