# ---------------------------------------------------------
# Firefighter MCP + FastAPI server (Render-compatible)
# ---------------------------------------------------------

from fastapi import FastAPI
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
import anyio
import httpx
from typing import Any

# ---------------------------------------------------------
# Initialize MCP server
# ---------------------------------------------------------
mcp = FastMCP("firefighter")

# Tools
@mcp.tool()
def get_weather(city: str) -> Any:
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            timeout=20.0,
        ).json()
        if not geo:
            return {"error": f"City '{city}' not found."}

        lat, lon = geo[0]["lat"], geo[0]["lon"]
        weather = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
        ).json().get("current_weather", {})

        return {
            "city": city,
            "temperature": weather.get("temperature"),
            "windspeed": weather.get("windspeed"),
            "winddirection": weather.get("winddirection"),
        }

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# Lifespan event: Start MCP server in background
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with anyio.create_task_group() as tg:
        # run MCP server without blocking FastAPI
        tg.start_soon(mcp.run, "streamable-http")
        yield
        tg.cancel_scope.cancel()  # stop MCP server on shutdown


# ---------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------
app = FastAPI(title="Firefighter MCP Server", lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "🔥 Firefighter MCP server running (FastAPI + MCP)"}


# ---------------------------------------------------------
# Uvicorn Entry
# ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(app, host="0.0.0.0", port=port)
