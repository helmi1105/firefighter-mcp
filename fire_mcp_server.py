# ---------------------------------------------------------
# Firefighter MCP + FastAPI unified service (Render-ready)
# ---------------------------------------------------------

import os
import httpx
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from threading import Thread
from mcp.server.fastmcp import FastMCP
import uvicorn

# ===========================
# 1. MCP SERVER SETUP
# ===========================

mcp = FastMCP("firefighter")

# ---------------------------------------------------------
# TOOL 1 — Weather
# ---------------------------------------------------------
@mcp.tool()
def get_weather(city: str) -> Any:
    """Get weather (temperature, windspeed, wind direction) for a city."""
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            timeout=20,
        ).json()

        if not geo:
            return {"error": f"City '{city}' not found"}

        lat = geo[0]["lat"]
        lon = geo[0]["lon"]

        weather = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            timeout=20,
        ).json().get("current_weather", {})

        return {
            "city": city,
            "temperature": weather.get("temperature"),
            "windspeed": weather.get("windspeed"),
            "wind_direction": weather.get("winddirection"),
        }

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# TOOL 2 — Nearest fire station
# ---------------------------------------------------------
@mcp.tool()
def get_nearest_station(city: str) -> Any:
    """Find nearest fire station within 8km using OSM Overpass API."""
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            timeout=20,
        ).json()

        if not geo:
            return {"error": f"City '{city}' not found"}

        lat = geo[0]["lat"]
        lon = geo[0]["lon"]

        overpass_query = f"""
        [out:json];
        node["amenity"="fire_station"](around:8000,{lat},{lon});
        out center;
        """

        result = httpx.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": overpass_query},
            timeout=30,
        ).json()

        if not result.get("elements"):
            return {"message": f"No fire stations found near {city}"}

        station = result["elements"][0]

        return {
            "city": city,
            "station_name": station.get("tags", {}).get("name", "Unknown"),
            "latitude": station.get("lat"),
            "longitude": station.get("lon"),
            "source": "OpenStreetMap Overpass API",
        }

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# 2. Start MCP server in a separate internal thread
# ---------------------------------------------------------

def start_mcp_server():
    """
    Runs MCP's HTTP server in standalone mode.
    MCP automatically binds to internal port 8000.
    """
    print("🔥 Starting internal MCP server on port 8000...")
    mcp.run(transport="streamable-http")

# start MCP
thread = Thread(target=start_mcp_server, daemon=True)
thread.start()


# ===========================
# 3. FASTAPI (public server)
# ===========================

app = FastAPI(title="🔥 Firefighter MCP API")

@app.get("/")
def home():
    return {"status": "OK", "message": "FastAPI + MCP are running"}


# ---------------------------------------------------------
# Proxy /mcp → internal MCP server
# ---------------------------------------------------------
@app.api_route("/mcp", methods=["GET", "POST"])
async def proxy_mcp(request: Request):
    """
    Realtime API uses POST /mcp.
    We proxy everything to the internal MCP server.
    """
    async with httpx.AsyncClient() as client:
        body = await request.body()
        headers = dict(request.headers)

        mcp_response = await client.request(
            request.method,
            "http://127.0.0.1:8000/mcp",
            content=body,
            headers=headers,
            timeout=30
        )

        return JSONResponse(
            status_code=mcp_response.status_code,
            content=mcp_response.json()
        )


# ===========================
# 4. Start FastAPI on Render port
# ===========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
