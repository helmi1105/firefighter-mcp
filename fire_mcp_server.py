# ---------------------------------------------------------
# Firefighter MCP + FastAPI server (Threaded MCP, no conflicts)
# ---------------------------------------------------------

from fastapi import FastAPI
from threading import Thread
from mcp.server.fastmcp import FastMCP
import httpx
from typing import Any
import os
import uvicorn

# ---------------------------------------------------------
# MCP server initialization
# ---------------------------------------------------------
mcp = FastMCP("firefighter")


@mcp.tool()
def get_weather(city: str) -> Any:
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1}
        ).json()

        if not geo:
            return {"error": "City not found"}

        lat, lon = geo[0]["lat"], geo[0]["lon"]

        weather = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True}
        ).json()["current_weather"]

        return weather

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# Run MCP server in a separate thread
# ---------------------------------------------------------
def start_mcp():
    # run MCP HTTP server on the same port OR different port
    mcp.run(transport="streamable-http")


mcp_thread = Thread(target=start_mcp, daemon=True)
mcp_thread.start()


# ---------------------------------------------------------
# FastAPI Server
# ---------------------------------------------------------
app = FastAPI()


@app.get("/")
def root():
    return {
        "status": "🔥 Firefighter server OK",
        "fastapi": True,
        "mcp": True
    }


# ---------------------------------------------------------
# Start Uvicorn (FastAPI)
# ---------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
