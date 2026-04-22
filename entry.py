# Diagnostic Path-Finder
import sys
import os
from js import Response

async def on_fetch(request, env):
    try:
        # Show all paths Python is currently looking in
        paths = "\n".join(sys.path)
        
        # Try to find common hidden package directories
        hidden_dirs = []
        possible_spots = ["/requirements", "/site-packages", "/python-packages", "/app/requirements"]
        for spot in possible_spots:
            if os.path.exists(spot):
                hidden_dirs.append(f"FOUND: {spot}")
        
        found_info = "\n".join(hidden_dirs) if hidden_dirs else "No common package dirs found."

        return Response.new(f"DIAGNOSTIC INFO:\n\nSYS.PATH:\n{paths}\n\nPACKAGE SCAN:\n{found_info}")
    except Exception as e:
        return Response.new(f"DIAGNOSTIC CRASH: {str(e)}")
