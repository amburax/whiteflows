# Minimal Entry Point for Debugging
# No project imports allowed yet

async def on_fetch(request, env):
    try:
        # Check if we can even import worker
        import worker
        return worker.types.Response("ENTRY POINT IS WORKING! If you see this, the code is stable.", headers={"content-type": "text/plain"})
    except Exception as e:
        # Fallback to a very primitive response
        return f"CRITICAL PLATFORM ERROR: {str(e)}".encode('utf-8')
