"""
fetch_weather.py
Fetches 7-day weather forecast from CWA API (F-D0047-091) for Taiwan's
6 regions, parses temperature data, and saves to weather_data.csv.

Regions:
  北部 (Northern):  基隆市, 臺北市, 新北市, 桃園市, 新竹市, 新竹縣
  中部 (Central):   苗栗縣, 臺中市, 彰化縣, 南投縣, 雲林縣
  南部 (Southern):  嘉義市, 嘉義縣, 臺南市, 高雄市, 屏東縣
  東北部 (NE):      宜蘭縣
  東部 (Eastern):   花蓮縣
  東南部 (SE):      臺東縣

The original assignment references F-A0010-001 but that endpoint currently
returns 404.  F-D0047-091 provides equivalent 7-day county-level forecast
data that we aggregate into the six target regions.
"""

import requests
import pandas as pd
import urllib3
import json
import sys

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuration -----------------------------------------------------------
API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-091"
AUTH_KEY = "CWA-12A2AA9F-8E62-4939-AE88-40420B2C5152"

# Mapping: county name → region
COUNTY_TO_REGION = {
    "基隆市": "北部", "臺北市": "北部", "新北市": "北部",
    "桃園市": "北部", "新竹市": "北部", "新竹縣": "北部",
    "苗栗縣": "中部", "臺中市": "中部", "彰化縣": "中部",
    "南投縣": "中部", "雲林縣": "中部",
    "嘉義市": "南部", "嘉義縣": "南部", "臺南市": "南部",
    "高雄市": "南部", "屏東縣": "南部",
    "宜蘭縣": "東北部",
    "花蓮縣": "東部",
    "臺東縣": "東南部",
    # Islands — grouped into nearest region
    "澎湖縣": "南部", "金門縣": "中部", "連江縣": "北部",
}


def fetch_weather_data():
    """Fetch weather data from CWA API and return parsed records."""
    params = {
        "Authorization": AUTH_KEY,
    }

    print("Fetching 7-day forecast from CWA API (F-D0047-091) ...")
    try:
        resp = requests.get(API_URL, params=params, verify=False, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        sys.exit(1)

    data = resp.json()

    # Navigate: records → Locations[0] → Location[]
    try:
        locations = data["records"]["Locations"][0]["Location"]
    except (KeyError, IndexError):
        print("Unexpected API response structure.")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        sys.exit(1)

    # Collect per-county, per-date min/max values
    # Structure: { (date, region): { "min": [vals], "max": [vals] } }
    from collections import defaultdict
    region_day_data = defaultdict(lambda: {"mins": [], "maxs": []})

    for loc in locations:
        county = loc.get("LocationName", "")
        region = COUNTY_TO_REGION.get(county)
        if region is None:
            continue

        elems = loc.get("WeatherElement", [])
        elem_map = {e["ElementName"]: e.get("Time", []) for e in elems}

        # Find the min/max temperature element names
        min_key = max_key = None
        for name in elem_map:
            if "最低溫度" in name or "MinT" in name:
                min_key = name
            elif "最高溫度" in name or "MaxT" in name:
                max_key = name
        # Fallback
        if not min_key:
            min_key = next((n for n in elem_map if "最低" in n), None)
        if not max_key:
            max_key = next((n for n in elem_map if "最高" in n), None)

        if not min_key or not max_key:
            print(f"  Skipping {county}: cannot find min/max elements. "
                  f"Available: {list(elem_map.keys())}")
            continue

        # Collect daily min values
        for t in elem_map[min_key]:
            start = t.get("StartTime", "")
            date_str = start[:10]
            ev = t.get("ElementValue", [{}])
            val = ev[0] if isinstance(ev, list) and ev else ev
            temp = val.get("MinTemperature", val.get("Temperature",
                   val.get("value", val.get("measures", ""))))
            try:
                region_day_data[(date_str, region)]["mins"].append(float(temp))
            except (ValueError, TypeError):
                pass

        # Collect daily max values
        for t in elem_map[max_key]:
            start = t.get("StartTime", "")
            date_str = start[:10]
            ev = t.get("ElementValue", [{}])
            val = ev[0] if isinstance(ev, list) and ev else ev
            temp = val.get("MaxTemperature", val.get("Temperature",
                   val.get("value", val.get("measures", ""))))
            try:
                region_day_data[(date_str, region)]["maxs"].append(float(temp))
            except (ValueError, TypeError):
                pass

    # Aggregate: per (date, region) take min-of-mins and max-of-maxs
    records = []
    for (date_str, region), vals in sorted(region_day_data.items()):
        if not vals["mins"] or not vals["maxs"]:
            continue
        min_temp = round(min(vals["mins"]), 1)
        max_temp = round(max(vals["maxs"]), 1)
        avg_temp = round((min_temp + max_temp) / 2, 1)
        records.append({
            "date": date_str,
            "region": region,
            "min_temp": min_temp,
            "max_temp": max_temp,
            "avg_temp": avg_temp,
        })

    return records


def save_to_csv(records, filename="weather_data.csv"):
    """Save records to a CSV file."""
    df = pd.DataFrame(records)
    if df.empty:
        print("Warning: No records parsed. CSV will be empty.")
    else:
        df = df.sort_values(["date", "region"]).reset_index(drop=True)
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} records to {filename}")
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    records = fetch_weather_data()
    save_to_csv(records)
