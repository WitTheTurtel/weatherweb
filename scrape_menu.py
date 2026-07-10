import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

MENU_URL = "https://school.use.go.kr/hcu-h/M01080101/list?ymd={today}"
OUTPUT_PATH = Path("data/menu.json")
KOREA_TZ = ZoneInfo("Asia/Seoul")


def fetch_page(url: str) -> str:
    """Download the page HTML."""
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def find_todays_cell(soup: BeautifulSoup):
    today_num = str(datetime.now(KOREA_TZ).day)

    for cell in soup.find_all("div"):
        span = cell.find("span", recursive=False)
        if span and span.get_text(strip=True) == today_num:
            return cell
    return None


def parse_menu(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    meal_labels = {
        "조식": "breakfast",
        "중식": "lunch",
        "석식": "dinner",
    }

    menu = {
        "breakfast": "Not available",
        "lunch": "Not available",
        "dinner": "Not available",
    }

    today_cell = find_todays_cell(soup)
    search_scope = today_cell if today_cell is not None else soup

    if today_cell is None:
        print(
            "WARNING: could not find today's day-cell in the calendar. "
            "Falling back to scanning the whole page — results may be "
            "for the wrong date. See find_todays_cell() TODO.",
            file=sys.stderr,
        )

    for dl in search_scope.find_all("dl"):
        dt = dl.find("dt")
        if dt is None:
            continue

        meal_key = meal_labels.get(dt.get_text(strip=True))
        if meal_key is None:
            continue

        if menu[meal_key] != "Not available":
            continue

        items = [li.get_text(strip=True) for li in dl.select("dd ul li")]
        menu[meal_key] = ", ".join(items) if items else "Not available"

    menu["last_updated"] = datetime.now(timezone.utc).isoformat()
    return menu


def save_menu(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    try:
        html = fetch_page(MENU_URL)
        menu = parse_menu(html)
        save_menu(menu, OUTPUT_PATH)
        print(f"Menu saved to {OUTPUT_PATH}")
        print(json.dumps(menu, indent=2))
    except requests.RequestException as e:
        print(f"Failed to fetch menu page: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()