# ----------------------------------------------------------
# Firefighter MCP Server (Render-Ready)
# ----------------------------------------------------------

from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("firefighter")


# -------------------------
# TOOL: Weather
# -------------------------
@mcp.tool()
def get_weather(city: str) -> Any:
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json", "limit": 1},
            timeout=20.0
        ).json()
        if not geo:
            return {"error": f"City '{city}' not found."}

        lat = geo[0]["lat"]
        lon = geo[0]["lon"]

        weather = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            timeout=20.0
        ).json().get("current_weather", {})

        return {
            "city": city,
            "temperature": weather.get("temperature"),
            "windspeed": weather.get("windspeed"),
            "winddirection": weather.get("winddirection"),
        }

    except Exception as e:
        return {"error": str(e)}


# -------------------------
# TOOL: Nearest fire station
# -------------------------
@mcp.tool()
def get_nearest_station(city: str) -> Any:
    try:
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "format": "json"},
            timeout=20.0
        ).json()
        if not geo:
            return {"error": f"City '{city}' not found."}

        lat = geo[0]["lat"]
        lon = geo[0]["lon"]

        query = f"""
        [out:json];
        node["amenity"="fire_station"](around:8000,{lat},{lon});
        out;
        """

        data = httpx.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=20.0
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


# -------------------------
# Run MCP HTTP server
# -------------------------
if __name__ == "__main__":
    # DO NOT PASS host or port → MCP binds automatically to $PORT
    mcp.run(transport="streamable-http")
