# fire_mcp_server.py
# ----------------------------------------------------------
# Firefighter MCP Server
# Provides:
#   🌦 get_weather(city): live weather + wind data
#   🚒 get_nearest_station(city): nearest fire station (OSM)
# ----------------------------------------------------------

from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("firefighter")

# ----------------------------------------------------------
# TOOL 1 — Get weather information
# ----------------------------------------------------------
@mcp.tool()
def get_weather(city: str) -> Any:
    """Return temperature, windspeed, and wind direction for a city."""
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            headers={"User-Agent": "firefighter-mcp/1.0"},
            timeout=20.0
        ).json()
        if not geo:
            return {"error": f"City '{city}' not found."}
        lat, lon = geo[0]["lat"], geo[0]["lon"]

        weather = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            headers={"User-Agent": "firefighter-mcp/1.0"},
            timeout=20.0
        ).json().get("current_weather", {})

        return {
            "city": city,
            "latitude": lat,
            "longitude": lon,
            "temperature": weather.get("temperature"),
            "windspeed": weather.get("windspeed"),
            "winddirection": weather.get("winddirection"),
            "source": "Open-Meteo API"
        }

    except Exception as e:
        return {"error": str(e)}

# ----------------------------------------------------------
# TOOL 2 — Find nearest fire station
# ----------------------------------------------------------
@mcp.tool()
def get_nearest_station(city: str) -> Any:
    """Return the nearest fire station within 8km using OpenStreetMap Overpass API."""
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            headers={"User-Agent": "firefighter-mcp/1.0"},
            timeout=20.0
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
            timeout=30.0
        ).json()

        if not data.get("elements"):
            return {"message": f"No fire stations found near {city}."}
        st = data["elements"][0]

        return {
            "city": city,
            "station_name": st.get("tags", {}).get("name", "Unknown Station"),
            "latitude": st.get("lat"),
            "longitude": st.get("lon"),
            "source": "OpenStreetMap Overpass API"
        }

    except Exception as e:
        return {"error": str(e)}

# ----------------------------------------------------------
# Run the MCP Server (STDIO transport)
# ----------------------------------------------------------
if __name__ == "__main__":
    import sys, logging
    # Only log to STDERR (never stdout)
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    mcp.run(transport="streamable-http")
