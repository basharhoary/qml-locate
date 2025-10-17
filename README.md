![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%2011-lightgrey.svg)
![Qt](https://img.shields.io/badge/Qt-PySide6-green.svg)
![Map](https://img.shields.io/badge/map-OpenStreetMap-blue.svg)

# 🗺️ QML Locate App

A small **Python + QML** application that detects your location (via Windows Location or IP fallback)  
and displays it on an **OpenStreetMap** view using **PySide6 / QtQuick**.  
You can type any destination address, and the app will calculate and visualize a route using the public **OSRM** routing service.

---

## ✨ Features

- 🌍 **Locate** automatically via Windows services or IP-based fallback  
- 🗺️ **Interactive map** with animated zoom, smooth pan & pinch support  
- 🧭 **Routing** using OSRM (driving profile)  
- 📏 Shows total distance (km) & duration (min)  
- 🚦 Non-blocking async networking (Qt NetworkAccessManager)  
- 🕓 Debounced actions & Busy indicator (never freezes)  
- ⚙️ Configurable via `config/settings.json` (timeouts, retry, tile server, etc.)

---

## 💻 Setup (virtual environment recommended)

### 1️⃣ Create and activate a virtual environment

```bash
# Create venv
python -m venv .venv

# Activate it (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate it (macOS/Linux)
source .venv/bin/activate


## Known limitations
- Uses public Nominatim/OSRM services (rate limits may apply).
- No offline tiles yet; network required for map/route.

## Next ideas
- Offline MBTiles pack for common areas.
- Vector tiles via MapLibre GL for crisper labels and smooth pitch/rotate.
- Waypoints (A → B → C) with draggable markers.
