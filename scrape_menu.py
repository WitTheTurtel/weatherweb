import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

API_KEY = os.environ.get("NEIS_API_KEY", "")

OFFICE_CODE = "H10"
SCHOOL_CODE = "7480085"

KOREA_TZ = ZoneInfo("Asia/Seoul")
OUTPUT_PATH = Path("data/menu.json")

MEAL_CODE_NAMES = {
    "1": "breakfast",
    "2": "lunch",
    "3": "dinner",
}

def fetch_today_meals() -> list:
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
