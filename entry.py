import sys
import traceback

# Global cache for the app
_cached_app = None

async def on_fetch(request, env):
    global _cached_app
    
    try:
        import worker # Ensure worker is available for the response
        if _cached_app is None:
            # Lazy load the server module
            import server
            _cached_app = server.app
            
        return await worker.asgi.fetch(_cached_app, request, env)
        
    except Exception:
        error_info = traceback.format_exc()
        try:
            import worker
            return worker.types.Response(f"DEBUG ERROR:\n\n{error_info}", headers={"content-type": "text/plain"})
        except:
            # Absolute fallback if even worker fails
            return b"Fatal Error in Entry Point. Check Logs."
