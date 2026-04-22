import sys

# Global cache for the app
_cached_app = None

async def on_fetch(request, env):
    global _cached_app
    
    if _cached_app is None:
        # Lazy load the server module only when a request arrives
        # This bypasses Cloudflare's build-time validation errors (10021)
        import server
        import worker
        
        # Initialize the app
        _cached_app = server.app
        
        # Store for the ASGI shim
        _asgi_shim = worker.asgi
        
    # Import inside fetch to ensure environment is ready
    import worker
    return await worker.asgi.fetch(_cached_app, request, env)
