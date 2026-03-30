#!/usr/bin/env python3
"""
Scrape all 23,933 windmill records from allemolenskaart.nl
Decodes base64-obfuscated fields and exports to JSON + CSV.

Obfuscation: each base64 field has 2 random prefix chars + a 4-char
pattern injected. Pattern changes per request but is consistent within.
"""
from __future__ import annotations

import json
import re
import base64
import csv
import sys
import collections
from urllib.request import urlopen, Request
from pathlib import Path

URL = "https://www.allemolenskaart.nl"
OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)


def fetch_page() -> str:
    print("[1/5] Fetching allemolenskaart.nl...")
    req = Request(URL, headers={"User-Agent": "Mozilla/5.0 (MolenScraper)"})
    with urlopen(req, timeout=60) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    print(f"  Downloaded {len(html):,} bytes")
    return html


def extract_json(html: str) -> tuple[dict, str]:
    print("[2/5] Extracting data + obfuscation pattern...")

    # The page embeds: var stdk="XXXX"; which is the obfuscation key
    stdk_match = re.search(r'var\s+stdk\s*=\s*"([^"]+)"', html)
    pattern = stdk_match.group(1) if stdk_match else None
    if pattern:
        print(f"  Found stdk pattern: '{pattern}'")

    # Extract JSON block
    start = html.find('"count":')
    if start == -1:
        sys.exit("ERROR: Could not find data")
    brace = html.rfind("{", 0, start)

    # Find the closing of the photos array: ,\n]} or similar
    # Search for ]} after the last mln_id
    last_mln = html.rfind("mln_id", start)
    # From last record, find the closing }
    close_rec = html.find("}", last_mln)
    # Then find ]}
    close_arr = html.find("]", close_rec)
    close_obj = html.find("}", close_arr)
    raw = html[brace : close_obj + 1]

    # Fix trailing comma before ] (invalid JSON)
    raw = re.sub(r",\s*\]", "]", raw)

    data = json.loads(raw)
    print(f"  Count: {data['count']:,}, Records: {len(data['photos']):,}")

    # If stdk not found, detect pattern from data
    if not pattern:
        fields = re.findall(r'"vlo":\s*"([^"]+)"', html[:10000])
        counter = collections.Counter()
        for f in fields[:20]:
            for i in range(len(f) - 3):
                counter[f[i : i + 4]] += 1
        pattern = counter.most_common(1)[0][0]
        print(f"  Detected pattern (fallback): '{pattern}'")

    # Verify
    test_field = re.search(r'"vlo":\s*"([^"]+)"', html)
    if test_field:
        test = test_field.group(1)[2:].replace(pattern, "")
        pad = 4 - len(test) % 4
        if pad != 4:
            test += "=" * pad
        decoded = base64.b64decode(test).decode("utf-8", errors="replace")
        print(f"  Verify decode: {decoded}")

    return data, pattern


def decode(val: str, pattern: str) -> str:
    if not val or not isinstance(val, str) or len(val) < 3:
        return val
    cleaned = val[2:].replace(pattern, "")
    pad = 4 - len(cleaned) % 4
    if pad != 4:
        cleaned += "=" * pad
    try:
        return base64.b64decode(cleaned).decode("utf-8", errors="replace")
    except Exception:
        return val


def process_records(data: dict, pattern: str) -> list[dict]:
    print("[4/5] Decoding records...")
    photos = data["photos"]
    records = []

    for i, rec in enumerate(photos):
        name = decode(rec.get("vnm", ""), pattern)
        place = decode(rec.get("vpl", ""), pattern)
        ref = decode(rec.get("vnr", ""), pattern)
        lon_s = decode(rec.get("vlo", ""), pattern)
        lat_s = decode(rec.get("vla", ""), pattern)

        try:
            lon = float(lon_s)
        except (ValueError, TypeError):
            lon = None
        try:
            lat = float(lat_s)
        except (ValueError, TypeError):
            lat = None

        records.append({
            "id": rec.get("mln_id", i),
            "ref": ref.strip(),
            "name": name.strip(),
            "place": place.strip(),
            "status": rec.get("vst", ""),
            "year": rec.get("vbj", ""),
            "type": rec.get("vad", ""),
            "lat": lat,
            "lon": lon,
        })

        if (i + 1) % 5000 == 0:
            print(f"  {i + 1:,} / {len(photos):,}")

    print(f"  Total: {len(records):,}")
    return records


def save(records: list[dict]):
    print("[5/5] Saving...")

    # All records
    p = OUTPUT_DIR / "all_molens.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    print(f"  {p.name}: {len(records):,} records ({p.stat().st_size:,} bytes)")

    # CSV
    p = OUTPUT_DIR / "all_molens.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id","ref","name","place","status","year","type","lat","lon"])
        w.writeheader()
        w.writerows(records)
    print(f"  {p.name}")

    # Existing windmills
    existing = [r for r in records if r["status"] == "bestaand" and r["type"] == "windmolen"]
    p = OUTPUT_DIR / "existing_windmolens.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=1)
    print(f"  {p.name}: {len(existing):,} existing windmolens")

    # East of Amsterdam with coords (lon > 4.9, lat > 52.0)
    east = [r for r in existing if r["lon"] and r["lon"] > 4.9 and r["lat"] and r["lat"] > 52.0]
    east = sorted(east, key=lambda r: r["lon"] or 0)
    p = OUTPUT_DIR / "existing_east_of_amsterdam.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(east, f, ensure_ascii=False, indent=1)
    print(f"  {p.name}: {len(east):,} existing windmolens east of Amsterdam")

    # Stats
    statuses = collections.Counter(r["status"] for r in records)
    types = collections.Counter(r["type"] for r in records)
    print(f"\n  Status: {dict(statuses)}")
    print(f"  Types:  {dict(types)}")


if __name__ == "__main__":
    html = fetch_page()
    data, pattern = extract_json(html)
    records = process_records(data, pattern)
    save(records)
    print("\nDone!")
