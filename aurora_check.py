#!/usr/bin/env python3
"""
Aurora Dashboard for Northern Lights photography in the Netherlands.
Fetches real-time data from NOAA SWPC and Open-Meteo APIs.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

# Target location: Schermerhorn, Netherlands
TARGET_LAT = 52.59
TARGET_LON = 4.97
TARGET_NAME = "Schermerhorn"

# Alternative locations
LOCATIONS = {
    "Schermerhorn": (52.59, 4.97),
    "Marken": (52.46, 5.14),
    "Beemster": (52.55, 4.92),
}

NOAA_KP_FORECAST = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
NOAA_KP_CURRENT = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
NOAA_OVATION = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"
NOAA_WING_KP = "https://services.swpc.noaa.gov/products/wing-kp.json"


def fetch_json(url: str, timeout: int = 15) -> dict | list | None:
    """Fetch JSON from a URL."""
    try:
        req = Request(url, headers={"User-Agent": "AuroraDashboard/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  [!] Failed to fetch {url}: {e}")
        return None


def fetch_text(url: str, timeout: int = 15) -> str | None:
    """Fetch raw text from a URL."""
    try:
        req = Request(url, headers={"User-Agent": "AuroraDashboard/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode()
    except (URLError, TimeoutError) as e:
        print(f"  [!] Failed to fetch {url}: {e}")
        return None


def get_current_kp() -> tuple[float | None, str | None]:
    """Get the most recent estimated Kp value."""
    data = fetch_json(NOAA_KP_CURRENT)
    if not data or len(data) < 2:
        return None, None
    # Last row has the most recent value: [timestamp, kp, ...]
    last = data[-1]
    try:
        kp = float(last[1])
        ts = last[0]
        return kp, ts
    except (ValueError, IndexError):
        return None, None


def get_kp_forecast() -> list[tuple[str, str]]:
    """Get Kp forecast for upcoming periods."""
    data = fetch_json(NOAA_KP_FORECAST)
    if not data or len(data) < 2:
        return []
    # Skip header row, format: [time_tag, kp, observed/predicted, noaa_scale]
    results = []
    now = datetime.now(timezone.utc)
    for row in data[1:]:
        try:
            ts = row[0]
            kp = row[1]
            # Parse the timestamp to filter only future entries
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
            dt = dt.replace(tzinfo=timezone.utc)
            if dt >= now:
                results.append((ts, kp))
        except (ValueError, IndexError):
            continue
    return results[:8]  # Next 8 periods (24 hours)


def get_ovation_aurora_prob(target_lat: float, target_lon: float) -> float | None:
    """
    Get aurora probability from OVATION model for a specific lat/lon.
    The OVATION data contains coordinates and aurora probability values.
    """
    data = fetch_json(NOAA_OVATION)
    if not data:
        return None

    # OVATION data structure: {"Forecast Time": ..., "Data Input": ..., "coordinates": [...]}
    coords = data.get("coordinates")
    if not coords:
        return None

    # Find the closest grid point to our target
    best_prob = 0
    best_dist = float("inf")

    for entry in coords:
        # Each entry: [lon, lat, probability]
        try:
            lon, lat, prob = entry[0], entry[1], entry[2]
            # Simple distance (good enough for nearby grid points)
            dist = (lat - target_lat) ** 2 + (lon - target_lon) ** 2
            if dist < best_dist:
                best_dist = dist
                best_prob = prob
        except (IndexError, TypeError):
            continue

    return best_prob


def get_cloud_cover(lat: float, lon: float) -> list[tuple[str, int]]:
    """Get hourly cloud cover forecast from Open-Meteo."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high"
        f"&timezone=Europe/Amsterdam"
        f"&forecast_days=1"
    )
    data = fetch_json(url)
    if not data or "hourly" not in data:
        return []

    hourly = data["hourly"]
    times = hourly.get("time", [])
    covers = hourly.get("cloud_cover", [])
    covers_low = hourly.get("cloud_cover_low", [])
    covers_mid = hourly.get("cloud_cover_mid", [])
    covers_high = hourly.get("cloud_cover_high", [])

    results = []
    for i, t in enumerate(times):
        hour = int(t.split("T")[1].split(":")[0])
        # Only show evening/night hours (18:00 - 06:00)
        if 18 <= hour or hour <= 6:
            cc = covers[i] if i < len(covers) else "?"
            cl = covers_low[i] if i < len(covers_low) else "?"
            cm = covers_mid[i] if i < len(covers_mid) else "?"
            ch = covers_high[i] if i < len(covers_high) else "?"
            results.append((t, cc, cl, cm, ch))
    return results


def recommendation(kp: float | None, cloud_pct: int | None, aurora_prob: float | None) -> str:
    """Generate a go/no-go recommendation."""
    if kp is None:
        return "UNKNOWN - Could not fetch Kp data"

    score = 0

    # Kp scoring (for NL at ~52N, need Kp 5+ ideally)
    if kp >= 7:
        score += 3
    elif kp >= 6:
        score += 2
    elif kp >= 5:
        score += 1

    # Aurora probability scoring
    if aurora_prob is not None:
        if aurora_prob >= 20:
            score += 2
        elif aurora_prob >= 10:
            score += 1

    # Cloud penalty
    if cloud_pct is not None:
        if cloud_pct <= 20:
            score += 1
        elif cloud_pct >= 70:
            score -= 2

    if score >= 4:
        return "GO - Excellent conditions, get moving!"
    elif score >= 2:
        return "GO - Good conditions, worth the drive"
    elif score >= 1:
        return "MARGINAL - Possible but not guaranteed, check live Kp before driving"
    else:
        return "NO-GO - Conditions unfavorable"


def main():
    now = datetime.now(timezone.utc)
    local_now = datetime.now()

    print("=" * 60)
    print(f"  AURORA DASHBOARD - {local_now.strftime('%Y-%m-%d %H:%M')} local")
    print(f"  Target: {TARGET_NAME} ({TARGET_LAT}N, {TARGET_LON}E)")
    print("=" * 60)

    # Current Kp
    print("\n--- Current Kp Index ---")
    kp, kp_ts = get_current_kp()
    if kp is not None:
        bar = "#" * int(kp * 3)
        print(f"  Kp: {kp:.2f}  [{bar}]  (as of {kp_ts})")
        if kp >= 5:
            print(f"  >>> Kp {kp:.0f} is sufficient for aurora at NL latitude!")
        elif kp >= 4:
            print(f"  >>> Kp {kp:.0f} is borderline - aurora may be visible on camera but faint")
        else:
            print(f"  >>> Kp {kp:.0f} is below threshold for NL (need 5+)")
    else:
        print("  Could not retrieve current Kp")

    # Kp Forecast
    print("\n--- Kp Forecast (next 24h) ---")
    forecast = get_kp_forecast()
    if forecast:
        for ts, kp_val in forecast:
            try:
                kp_f = float(kp_val)
                bar = "#" * int(kp_f * 3)
                marker = " <<<" if kp_f >= 5 else ""
                print(f"  {ts}  Kp: {kp_f:.2f}  [{bar}]{marker}")
            except ValueError:
                print(f"  {ts}  Kp: {kp_val}")
    else:
        print("  Could not retrieve forecast")

    # OVATION Aurora Probability
    print("\n--- OVATION Aurora Probability ---")
    for name, (lat, lon) in LOCATIONS.items():
        prob = get_ovation_aurora_prob(lat, lon)
        if prob is not None:
            bar = "#" * int(prob / 2)
            print(f"  {name:15s}  {prob:5.1f}%  [{bar}]")
        else:
            print(f"  {name:15s}  unavailable")

    # Cloud Cover
    print(f"\n--- Cloud Cover at {TARGET_NAME} (evening/night) ---")
    clouds = get_cloud_cover(TARGET_LAT, TARGET_LON)
    if clouds:
        print(f"  {'Time':17s}  {'Total':>5s}  {'Low':>4s}  {'Mid':>4s}  {'High':>4s}  Status")
        print(f"  {'-'*17}  {'-'*5}  {'-'*4}  {'-'*4}  {'-'*4}  ------")
        evening_cloud = None
        for t, cc, cl, cm, ch in clouds:
            hour = int(t.split("T")[1].split(":")[0])
            status = ""
            if cc != "?" and int(cc) <= 20:
                status = "CLEAR"
            elif cc != "?" and int(cc) <= 50:
                status = "partial"
            elif cc != "?" and int(cc) > 50:
                status = "cloudy"
            print(f"  {t:17s}  {cc:>5}%  {cl:>4}%  {cm:>4}%  {ch:>4}%  {status}")
            # Track 21:00-23:00 cloud cover
            if hour in (21, 22) and cc != "?" and evening_cloud is None:
                evening_cloud = int(cc)
    else:
        print("  Could not retrieve cloud cover")
        evening_cloud = None

    # Recommendation
    print("\n" + "=" * 60)
    aurora_prob = get_ovation_aurora_prob(TARGET_LAT, TARGET_LON)
    rec = recommendation(kp, evening_cloud, aurora_prob)
    print(f"  RECOMMENDATION: {rec}")
    print("=" * 60)

    # Location info
    print(f"""
--- Top Location: Schermerhorn Polder Mills ---
  Address:  Noordervaart 2, 1636 VL Schermerhorn
  Coords:   52.59N, 4.97E
  Drive:    ~40 km north of Amsterdam (A7 > N244)
  Why:      11 historic windmills, open flat polder, dark skies
  Compose:  Mills along dike with water channels for reflections
  Horizon:  Unobstructed northern view across flat polder

--- Camera Settings ---
  Exposure:  15-25 seconds
  ISO:       1600-3200
  Aperture:  f/2.0 - f/2.8 (as wide as possible)
  WB:        3200-4000K (manual)
  Lens:      Wide angle (14-24mm)
  Focus:     Manual, on stars or distant lights

--- Live Monitoring ---
  SpaceWeatherLive:  https://www.spaceweatherlive.com/en/auroral-activity.html
  NOAA Aurora:       https://www.swpc.noaa.gov/products/aurora-30-minute-forecast
  Windy.com:         Check cloud movement in real-time
""")


if __name__ == "__main__":
    main()
