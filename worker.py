from workers import WorkerEntrypoint
import asgi
from server import app

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # Bridge the Cloudflare Worker request to the FastAPI app
        # This handles the stateless execution and environment variable injection
        return await asgi.fetch(app, request, self.env)
