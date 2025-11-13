# ----------------------------------------------------------
# Firefighter MCP Server (Render-Ready, Pure MCP HTTP Server)
# ----------------------------------------------------------

from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("firefighter")


# ----------------------------------------------------------
# TOOL 1 — Get weather
# ----------------------------------------------------------
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
            timeout=20.0,
        ).json().get("current_weather", {})

        return {
            "city": city,
            "temperature": weather.get("temperature"),
            "windspeed": weather.get("windspeed"),
            "winddirection": weather.get("winddirection"),
        }

    except Exception as e:
        return {"error": str(e)}


# ----------------------------------------------------------
# TOOL 2 — Closest fire station
# ----------------------------------------------------------
@mcp.tool()
def get_nearest_station(city: str) -> Any:
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json"},
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
            timeout=20.0,
        ).json()

        if not data.get("elements"):
            return {"message": "No fire stations found."}

        st = data["elements"][0]

        return {
            "station_name": st.get("tags", {}).get("name", "Unknown"),
            "latitude": st.get("lat"),
            "longitude": st.get("lon"),
        }

    except Exception as e:
        return {"error": str(e)}


# ----------------------------------------------------------
# Run Pure MCP HTTP Server (NO FastAPI!)
# ----------------------------------------------------------
if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8000))

    # Run MCP HTTP server on given port
    mcp.run(transport="streamable-http", port=port, host="0.0.0.0")
