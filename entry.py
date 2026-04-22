import sys
import traceback

# Global cache for the app
_cached_app = None

async def on_fetch(request, env):
    global _cached_app
    
    try:
        # Load the server ONLY when the first request arrives
        # This bypasses Cloudflare's strict build-time scripts
        if _cached_app is None:
            import server
            _cached_app = server.app
            
        import worker
        return await worker.asgi.fetch(_cached_app, request, env)
        
    except Exception:
        # Diagnostic fallback that uses standard worker bridge
        # so we can see the error in the browser if it still crashes
        import js
        error_info = traceback.format_exc()
        return js.Response.new(f"BOOT ERROR:\n\n{error_info}")
