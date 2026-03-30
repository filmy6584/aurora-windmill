# Aurora Windmill

Real-time dashboard for photographing the Northern Lights with Dutch windmills in the Netherlands.

Built to solve a personal problem: I kept driving an hour north from Amsterdam only to find cloudy skies. This tool combines space weather data with cloud forecasts and a map of 24,000 windmills so you can make a go/no-go decision before leaving the house.

## What it does

- **Live aurora conditions** — Kp index, OVATION aurora probability, DSCOVR solar wind (Bz, Bt, speed, density) from NOAA SWPC
- **Cloud cover forecasts** — Hourly cloud data for each windmill location from Open-Meteo
- **Go/no-go engine** — Scores Kp, cloud cover, and aurora probability into a clear recommendation
- **Windmill map** — Interactive Leaflet map with ~24,000 mills scraped from allemolenskaart.nl
- **Light pollution overlay** — 2024 World Atlas (Falchi/Lorenz) Bortle-class layer to find dark skies
- **Camera settings** — Suggested exposure, ISO, aperture, and white balance for aurora photography
- **Navigation** — One-click Google Maps routing from Amsterdam to any windmill

## Quick start

Open the dashboard directly in a browser (needs a local server for the map data):

```bash
python3 -m http.server 8080
# Open http://localhost:8080/aurora_dashboard.html
```

Or use the CLI tool for a quick terminal check:

```bash
python3 aurora_check.py
```

## Files

| File | Description |
|------|-------------|
| `aurora_dashboard.html` | Main dashboard — all-in-one HTML with live API fetches |
| `aurora_map.html` | Standalone windmill map with filters |
| `aurora_check.py` | CLI tool — prints Kp, cloud cover, and recommendation |
| `scrape_molens.py` | Scrapes windmill data from allemolenskaart.nl (decodes base64 obfuscation) |
| `data/` | Pre-scraped windmill coordinates (JSON) |

## Data sources

| Source | Data | API |
|--------|------|-----|
| [NOAA SWPC](https://www.swpc.noaa.gov/) | Kp index, OVATION, DSCOVR solar wind | Free, no auth |
| [Open-Meteo](https://open-meteo.com/) | Hourly cloud cover by location | Free, no auth |
| [allemolenskaart.nl](https://www.allemolenskaart.nl/) | 23,933 Dutch windmill records | Scraped |
| [D. Lorenz / Falchi et al.](https://djlorenz.github.io/astronomy/lp/) | Light pollution atlas 2024 | Tile overlay |

## Key locations

| Location | Distance from Amsterdam | Why |
|----------|------------------------|-----|
| Schermerhorn | 45 km N | Iconic polder mills (1635), flat horizon, water reflections |
| De Wicher, Kalenberg | 120 km E | Weerribben-Wieden National Park, darkest skies, clear until late |
| De Grebmolen, Warmenhuizen | 35 km N | Quick drive, isolated polder mill (1547) |

## No dependencies

The entire dashboard is a single HTML file with vanilla JS. The Python scripts use only stdlib (`urllib`, `json`, `base64`, `csv`). The only external library loaded via CDN is Leaflet.js for the map.

## License

MIT
