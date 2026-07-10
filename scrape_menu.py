"""
Pulls today's breakfast, lunch, and dinner menu from the NEIS (National
Education Information System) Open API -- Korea's official public API
for school data -- instead of scraping the school website's HTML.

This avoids the web firewall blocking problem entirely, since it's a
real API meant for outside programs to use (not the human-facing page).

SETUP NEEDED BEFORE THIS WORKS:
1. Register for a free API key at https://open.neis.go.kr
   (Sign up -> "Open API 활용신청" -> search for "학교급식식단정보" /
   mealServiceDietInfo -> request access -> you'll get a KEY string)
2. Add that key as a GitHub Actions secret named NEIS_API_KEY:
   repo Settings -> Secrets and variables -> Actions -> New repository
   secret -> name: NEIS_API_KEY, value: (the key you got)
3. OFFICE_CODE and SCHOOL_CODE below were found via web search for
   "현대청운고등학교" (Hyundai Cheongun High School, Ulsan) -- DOUBLE
   CHECK these are correct by calling the schoolInfo endpoint yourself:
   https://open.neis.go.kr/hub/schoolInfo?KEY=YOUR_KEY&Type=json&SCHUL_NM=현대청운고등학교
   and confirming ATPT_OFCDC_SC_CODE and SD_SCHUL_CODE match what's below.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# Read from a GitHub Actions secret so the key isn't hardcoded in the repo
API_KEY = os.environ.get("NEIS_API_KEY", "")

OFFICE_CODE = "H10"       # 울산광역시교육청 (Ulsan Metropolitan Office of Education)
SCHOOL_CODE = "7480085"   # 현대청운고등학교 (Hyundai Cheongun High School) -- VERIFY THIS

KOREA_TZ = ZoneInfo("Asia/Seoul")
OUTPUT_PATH = Path("data/menu.json")

# NEIS meal-type codes -> our JSON keys
MEAL_CODE_NAMES = {
    "1": "breakfast",
    "2": "lunch",
    "3": "dinner",
}


def fetch_today_meals() -> list:
    """Call the NEIS API and return the raw list of meal rows for today."""
    today = datetime.now(KOREA_TZ).strftime("%Y%m%d")
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": API_KEY,
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": OFFICE_CODE,
        "SD_SCHUL_CODE": SCHOOL_CODE,
        "MLSV_YMD": today,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # NEIS reports errors (bad key, no data for that date, etc.) inside
    # a normal 200 response rather than an HTTP error code, so we have
    # to check for that ourselves.
    if "RESULT" in data:
        code = data["RESULT"].get("CODE", "")
        message = data["RESULT"].get("MESSAGE", "Unknown error")
        print(f"NEIS API message: {code} - {message}", file=sys.stderr)
        return []

    return data["mealServiceDietInfo"][1]["row"]


def parse_meals(rows: list) -> dict:
    """Turn NEIS's raw rows into our breakfast/lunch/dinner JSON shape."""
    menu = {
        "breakfast": "Not available",
        "lunch": "Not available",
        "dinner": "Not available",
    }

    for row in rows:
        meal_key = MEAL_CODE_NAMES.get(row.get("MMEAL_SC_CODE"))
        if meal_key is None:
            continue

        # NEIS separates dishes with <br/> and appends allergen numbers
        # directly onto each dish name, e.g. "쌀밥1.5.6.13."
        dishes_raw = row.get("DDISH_NM", "")
        dish_list = [d.strip() for d in dishes_raw.split("<br/>") if d.strip()]
        menu[meal_key] = ", ".join(dish_list) if dish_list else "Not available"

    menu["last_updated"] = datetime.now(timezone.utc).isoformat()
    return menu


def save_menu(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False keeps Korean characters readable in the file
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    try:
        rows = fetch_today_meals()
        menu = parse_meals(rows)
        save_menu(menu, OUTPUT_PATH)
        print(f"Menu saved to {OUTPUT_PATH}")
        print(json.dumps(menu, indent=2, ensure_ascii=False))
    except requests.RequestException as e:
        print(f"Failed to fetch menu data: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
