import asyncio
from httpx import AsyncClient
from main import app

async def test():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/company/config")
        print(response.status_code)
        print(response.text)

asyncio.run(test())
