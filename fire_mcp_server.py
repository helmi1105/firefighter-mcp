# fire_mcp_server.py
# -----------------------------------------------------
# Firefighter MCP server — Streamable HTTP, Render-ready
# Works with:
#   - MCP Inspector (Transport: Streamable HTTP)
#   - OpenAI Realtime API (mcp_server.url = .../mcp)
# -----------------------------------------------------

from typing import Any
import os
import httpx
from mcp.server.fastmcp import FastMCP

# Create MCP server (stateless_http/json_response tuned for HTTP)
mcp = FastMCP(
    "firefighter",
    stateless_http=True,   # good for remote HTTP servers :contentReference[oaicite:2]{index=2}
    json_response=True
)

# -----------------------------------------------------
# TOOL 1 — Get weather
# -----------------------------------------------------
@mcp.tool()
def get_weather(city: str) -> Any:
    """
    Return temperature, windspeed, and wind direction for a city.
    """
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            headers={"User-Agent": "firefighter-mcp/1.0"},
            timeout=20.0,
        ).json()

        if not geo:
            return {"error": f"City '{city}' not found."}

        lat = geo[0]["lat"]
        lon = geo[0]["lon"]

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


# -----------------------------------------------------
# TOOL 2 — Find nearest fire station
# -----------------------------------------------------
@mcp.tool()
def get_nearest_station(city: str) -> Any:
    """
    Return the nearest fire station within ~8km using OpenStreetMap Overpass API.
    """
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            headers={"User-Agent": "firefighter-mcp/1.0"},
            timeout=20.0,
        ).json()

        if not geo:
            return {"error": f"City '{city}' not found."}

        lat = geo[0]["lat"]
        lon = geo[0]["lon"]

        query = f"""
        [out:json];
        node["amenity"="fire_station"](around:8000,{lat},{lon});
        out center;
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


# -----------------------------------------------------
# Main entrypoint — Streamable HTTP MCP server
# -----------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    # FastMCP v2 supports host / port / path for HTTP transports :contentReference[oaicite:3]{index=3}
    # This will expose your MCP server at:
    #   http://0.0.0.0:<PORT>/mcp
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        path="/mcp",
    )
