# ---------------------------------------------------------
# Firefighter MCP + FastAPI unified service (Render-ready)
# ---------------------------------------------------------

import os
import httpx
from typing import Any
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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
        ).json()["current_weather"]

        return {
            "city": city,
            "temperature": weather["temperature"],
            "windspeed": weather["windspeed"],
            "wind_direction": weather["winddirection"],
        }

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# TOOL 2 — Nearest fire station
# ---------------------------------------------------------
@mcp.tool()
def get_nearest_station(city: str) -> Any:
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

        query = f"""
        [out:json];
        node["amenity"="fire_station"](around:8000,{lat},{lon});
        out center;
        """

        result = httpx.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=30,
        ).json()

        if not result.get("elements"):
            return {"message": f"No fire stations found near {city}"}

        st = result["elements"][0]

        return {
            "city": city,
            "station_name": st.get("tags", {}).get("name", "Unknown"),
            "latitude": st.get("lat"),
            "longitude": st.get("lon"),
            "source": "OpenStreetMap Overpass API"
        }

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# 2. Start MCP server in a background thread
# ---------------------------------------------------------
def start_mcp_server():
    mcp.run(transport="streamable-http")  # MCP automatically binds to port 8000


thread = Thread(target=start_mcp_server, daemon=True)
thread.start()


# ===========================
# 3. FASTAPI SERVER
# ===========================

app = FastAPI(title="Firefighter MCP API")

# Allow CORS (fix OPTIONS requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "status": "OK",
        "message": "FastAPI + MCP running",
        "mcp_endpoint": "/mcp",
    }


# ---------------------------------------------------------
# MCP CAPABILITIES ENDPOINT (HTTP GET)
# Required by MCP spec
# ---------------------------------------------------------
@app.get("/mcp")
def mcp_get():
    """Return MCP capabilities document."""
    return {
        "mcp_version": "1.0.0",
        "capabilities": {
            "tools": ["get_weather", "get_nearest_station"]
        }
    }


# ---------------------------------------------------------
# Allow CORS for preflight requests
# ---------------------------------------------------------
@app.options("/mcp")
def mcp_options():
    return Response(status_code=200)


# ---------------------------------------------------------
# Proxy POST to internal MCP server
# ---------------------------------------------------------
@app.post("/mcp")
async def proxy_mcp(request: Request):
    async with httpx.AsyncClient() as client:
        body = await request.body()
        headers = dict(request.headers)

        # Remove FastAPI "Accept-Encoding" because MCP transport doesn’t support it
        headers.pop("accept-encoding", None)

        # Send to internal MCP server
        result = await client.post(
            "http://127.0.0.1:8000/mcp",
            content=body,
            headers=headers,
            timeout=60
        )

        # If MCP returned JSON → forward it safely
        try:
            return JSONResponse(
                status_code=result.status_code,
                content=result.json()
            )
        except Exception:
            # Force JSON even when it's plain text or errors
            return JSONResponse(
                status_code=result.status_code,
                content={
                    "error": "MCP server returned invalid JSON",
                    "raw": result.text
                }
            )



# ===========================
# 4. Run FastAPI
# ===========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
