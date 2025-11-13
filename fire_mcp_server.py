# fire_mcp_server.py

from typing import Any
import httpx
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
import asyncio
import os

# ---------------------------------------------
# Initialize MCP server
# ---------------------------------------------
mcp = FastMCP("firefighter")

# ---------------------------------------------
# Tools
# ---------------------------------------------
@mcp.tool()
def get_weather(city: str) -> Any:
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            headers={"User-Agent": "firefighter-mcp/1.0"},
            timeout=20.0,
        ).json()

        if not geo:
            return {"error": f"City '{city}' not found."}

        lat, lon = geo[0]["lat"], geo[0]["lon"]

        weather = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            headers={"User-Agent": "firefighter-mcp/1.0"},
            timeout=20.0,
        ).json().get("current_weather", {})

        return {
            "city": city,
            "latitude": lat,
            "longitude": lon,
            "temperature": weather.get("temperature"),
            "windspeed": weather.get("windspeed"),
            "winddirection": weather.get("winddirection"),
            "source": "Open-Meteo API",
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_nearest_station(city: str) -> Any:
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            headers={"User-Agent": "firefighter-mcp/1.0"},
            timeout=20.0,
        ).json()

        if not geo:
            return {"error": f"City '{city}' not found."}

        lat, lon = geo[0]["lat"], geo[0]["lon"]

        query = f"""
        [out:json];
        node["amenity"="fire_station"](around:8000,{lat},{lon});
        out;
        """
        data = httpx.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            headers={"User-Agent": "firefighter-mcp/1.0"},
            timeout=30.0,
        ).json()

        if not data.get("elements"):
            return {"message": f"No fire stations found near {city}."}

        st = data["elements"][0]

        return {
            "city": city,
            "station_name": st.get("tags", {}).get("name", "Unknown Station"),
            "latitude": st.get("lat"),
            "longitude": st.get("lon"),
            "source": "OpenStreetMap Overpass API",
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------
# FastAPI + MCP Background Runner
# ---------------------------------------------
app = FastAPI(title="Firefighter MCP Server")


@app.on_event("startup")
async def start_mcp():
    """Start the MCP server in the background once FastAPI starts."""
    asyncio.create_task(mcp.run(transport="streamable-http"))


@app.get("/")
def root():
    return {"status": "🔥 Firefighter MCP server is running"}


# ---------------------------------------------
# Run Uvicorn
# ---------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
