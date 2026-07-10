"""
Scrapes today's breakfast, lunch, and dinner menu from the school's
monthly meal calendar page and saves it as JSON for f.html to display.

STILL TO DO:
1. Replace MENU_URL below with the real school menu page URL.
2. Run this locally first (see README/chat instructions) and check
   data/menu.json against the real site to confirm find_todays_cell()
   is grabbing the correct day before relying on the automated schedule.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# TODO: replace with the real menu page URL
MENU_URL = "https://school-website.example.com/menu"

# Where the scraped data gets written (relative to repo root)
OUTPUT_PATH = Path("data/menu.json")

# The school's local timezone, used to figure out "today" correctly.
# GitHub Actions runners use UTC, so without this, "today" could be
# off by a day around midnight in Korea.
KOREA_TZ = ZoneInfo("Asia/Seoul")


def fetch_page(url: str) -> str:
    """Download the page HTML."""
    # Korean government (.go.kr) sites often run firewalls that block
    # requests that don't look like they're coming from a real browser.
    # Sending browser-like headers reduces the chance of being blocked.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    # Korean sites sometimes don't correctly label their text encoding,
    # which makes 'requests' guess wrong and turn Korean characters into
    # garbled symbols (mojibake). Forcing UTF-8 fixes that in most cases.
    resp.encoding = "utf-8"
    return resp.text


def find_todays_cell(soup: BeautifulSoup):
    """
    Locate the HTML block for TODAY's specific date within the full
    month calendar (as opposed to grabbing whatever day happens to be
    first on the page).

    ASSUMPTION (based on your screenshot): each day is wrapped in a
    <div> that also contains a <span> holding just the day number,
    e.g. <span>5</span> for the 5th of the month.

    TODO / RISK: month calendars often pad the grid with a few days
    from the previous/next month (e.g. the last row might show "1, 2,
    3" belonging to next month). If this site does that, and one of
    those padding days shares today's day-of-month number, this could
    match the WRONG day. If you notice that happening, check whether
    those padding cells have a distinguishing class (often something
    like "other-month", "prev", "next", or a greyed-out style) and
    let me know — I'll add a filter to exclude them.
    """
    today_num = str(datetime.now(KOREA_TZ).day)

    for cell in soup.find_all("div"):
        span = cell.find("span", recursive=False)
        if span and span.get_text(strip=True) == today_num:
            return cell
    return None


def parse_menu(html: str) -> dict:
    """
    Parse the HTML and pull out breakfast/lunch/dinner text for TODAY.

    Matches this site's real structure:
        <dl>
          <dt>조식</dt>              <- meal name (조식/중식/석식)
          <dd>
            <ul>
              <li>food item</li>    <- one <li> per dish
              ...
            </ul>
          </dd>
        </dl>
    """
    soup = BeautifulSoup(html, "html.parser")

    # Maps the Korean meal labels on the page to our JSON keys
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
        # Fallback so the script doesn't crash — but this means it will
        # grab the FIRST 조식/중식/석식 found anywhere on the page, which
        # may be the wrong day. Printed so it shows up in the Action's
        # log if this ever happens.
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

        # Only fill this meal in once (first match wins), in case the
        # same meal label appears more than once within scope.
        if menu[meal_key] != "Not available":
            continue

        items = [li.get_text(strip=True) for li in dl.select("dd ul li")]
        menu[meal_key] = ", ".join(items) if items else "Not available"

    menu["last_updated"] = datetime.now(timezone.utc).isoformat()
    return menu


def save_menu(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False keeps Korean characters readable in the file
    # (e.g. 김치찌개) instead of converting them to \uXXXX escape codes.
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    try:
        html = fetch_page(MENU_URL)
        # TEMPORARY DEBUG LINE — prints the first 3000 characters of the
        # downloaded page so we can see its real structure in the Action
        # logs. Remove this once find_todays_cell() is confirmed working.
        print("----- RAW HTML PREVIEW (debug) -----", file=sys.stderr)
        print(html[:3000], file=sys.stderr)
        print("----- END PREVIEW -----", file=sys.stderr)

        menu = parse_menu(html)
        save_menu(menu, OUTPUT_PATH)
        print(f"Menu saved to {OUTPUT_PATH}")
        print(json.dumps(menu, indent=2))
    except requests.RequestException as e:
        print(f"Failed to fetch menu page: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
