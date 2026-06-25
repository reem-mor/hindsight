from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)  # allow WebUI (in the browser) to call us

@app.route("/weather")
def weather():
    city = request.args.get("city", "Tel Aviv")
    geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}").json()
    if "results" not in geo or not geo["results"]:
        return jsonify({"error": "City not found"}), 404

    lat = geo["results"][0]["latitude"]
    lon = geo["results"][0]["longitude"]

    data = requests.get(
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}&current_weather=true"
    ).json()

    return jsonify(data["current_weather"])

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/openapi.json")
def openapi_spec():
    return jsonify({
        "openapi": "3.0.0",
        "info": {"title": "Local Weather Proxy", "version": "1.0.0"},
        "servers": [
            {"url": "http://localhost:5000", "description": "Browser / user tool server"},
            {"url": "http://host.docker.internal:5000", "description": "Open WebUI Docker backend"},
        ],
        "paths": {
            "/weather": {
                "get": {
                    "summary": "Get current weather for a city",
                    "parameters": [
                        {
                            "name": "city",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "City name (e.g. Tel Aviv)"
                        }
                    ],
                    "responses": {
                        "200": {"description": "OK"},
                        "404": {"description": "City not found"}
                    }
                }
            }
        }
    })

if __name__ == "__main__":
    # IMPORTANT: 0.0.0.0 so Docker can reach it
    app.run(host="0.0.0.0", port=5000)