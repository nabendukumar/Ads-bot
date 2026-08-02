"""
Simple HTTP health check for Render keep-alive.
"""
import asyncio
import logging
from aiohttp import web
from config import PORT

logger = logging.getLogger(__name__)


async def handle_health(request):
    return web.Response(text="OK", status=200)


async def start_health_server():
    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health server running on port {PORT} ✅")
