# Gold Standard Minimal Entry
from js import Response

async def on_fetch(request, env):
    return Response.new("PLATFORM STABLE: js.Response is working!")
