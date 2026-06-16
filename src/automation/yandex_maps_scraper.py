"""Yandex Maps Moscow organization scraper.

This module intentionally uses visible browser automation instead of private APIs.
Yandex may show CAPTCHA/anti-bot challenges; in that case the scraper saves
progress and exits gracefully so it can be resumed later.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus

try:
    import pandas as pd
except ImportError:  # pragma: no cover - reported at runtime by CLI
    pd = None

try:
    from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright
except ImportError:  # pragma: no cover - reported at runtime by CLI
    async_playwright = None
    PlaywrightTimeoutError = TimeoutError
    Page = object  # type: ignore[assignment]

MOSCOW_CATEGORIES: dict[str, list[str]] = {
    "computer_clubs": ["Компьютерные клубы", "Киберарена"],
    "interior_design": ["Дизайн-студии интерьеров", "Архитектурное бюро"],
    "video_production": ["Студии видеомонтажа", "Видеопродакшн"],
}

DEFAULT_PROGRESS_PATH = Path("data/yandex_maps_progress.jsonl")
DEFAULT_CSV_PATH = Path("data/yandex_maps_progress.csv")
DEFAULT_EXCEL_PATH = Path("data/yandex_maps_moscow_organizations.xlsx")
DEFAULT_TARGET_PER_CATEGORY = 150
DEFAULT_STAGNATION_LIMIT = 6
MOSCOW_CENTER = "55.755864,37.617698"
SEARCH_URL = "https://yandex.ru/maps/213/moscow/search/{query}/?ll=37.617698%2C55.755864&z=11"


@dataclass(slots=True)
class Organization:
    name: str | None = None
    category_key: str | None = None
    query_source: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    yandex_maps_url: str | None = None
    rating: str | None = None
    reviews: str | None = None


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D+", "", phone)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits or None


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_text(value: str | None) -> str:
    return clean_text(value).casefold()


def dedupe_key(record: dict[str, str | None]) -> str:
    url = record.get("yandex_maps_url")
    if url:
        # Strip common volatile map state after the stable organization URL.
        return "url:" + url.split("?", 1)[0].split("&", 1)[0]
    phone = normalize_phone(record.get("phone"))
    if phone:
        return "phone:" + phone
    return "name_address:" + normalize_text(record.get("name")) + "|" + normalize_text(record.get("address"))


def load_existing_records(progress_path: Path) -> list[dict[str, str | None]]:
    records: list[dict[str, str | None]] = []
    if not progress_path.exists():
        return records
    with progress_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Skipping malformed progress line: {line[:120]}", file=sys.stderr)
    return records


def append_jsonl(path: Path, record: dict[str, str | None]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()


def export_csv(path: Path, records: Iterable[dict[str, str | None]]) -> None:
    rows = list(records)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(Organization()).keys())
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_excel(path: Path, records: Iterable[dict[str, str | None]]) -> None:
    rows = list(records)
    if pd is None:
        raise RuntimeError("pandas/openpyxl are required for Excel export. Install requirements.txt.")
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=list(asdict(Organization()).keys())).to_excel(path, index=False)


async def jitter(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


async def has_captcha(page: Page) -> bool:
    patterns = ["captcha", "smartcaptcha", "Введите символы", "Подтвердите, что вы не робот", "робот"]
    content = (await page.content()).casefold()
    return any(pattern.casefold() in content for pattern in patterns)


async def safe_text(locator) -> str | None:
    try:
        text = await locator.first.text_content(timeout=1500)
        return clean_text(text) or None
    except Exception:
        return None


async def extract_from_card(card, category_key: str, query_source: str) -> Organization:
    """Extract the fields that are visible in a Yandex Maps sidebar card."""
    name = await safe_text(card.locator(".search-business-snippet-view__title, .business-snippet-view__title, [class*=title]").first)
    address = await safe_text(card.locator(".search-business-snippet-view__address, .business-snippet-view__address, [class*=address]").first)
    rating = await safe_text(card.locator(".business-rating-badge-view__rating, [class*=rating]").first)
    reviews = await safe_text(card.locator(".business-rating-badge-view__text, [class*=review], [class*=rating]").nth(1))
    phone = await safe_text(card.locator("a[href^='tel:'], [class*=phone]").first)

    website = None
    try:
        website = await card.locator("a[href^='http']:not([href*='yandex'])").first.get_attribute("href", timeout=1000)
    except Exception:
        website = None

    yandex_url = None
    try:
        link = card.locator("a[href*='/org/'], a[href*='yandex.ru/maps/org']").first
        href = await link.get_attribute("href", timeout=1000)
        if href:
            yandex_url = href if href.startswith("http") else "https://yandex.ru" + href
    except Exception:
        yandex_url = None

    return Organization(
        name=name,
        category_key=category_key,
        query_source=query_source,
        address=address,
        phone=phone,
        website=website,
        yandex_maps_url=yandex_url,
        rating=rating,
        reviews=reviews,
    )


async def find_result_cards(page: Page):
    selectors = [
        ".search-snippet-view",
        ".business-snippet-view",
        "li[class*=search-snippet]",
        "div[class*=business-snippet]",
    ]
    for selector in selectors:
        loc = page.locator(selector)
        if await loc.count() > 0:
            return loc
    return page.locator("__no_matching_cards__")


async def scroll_results(page: Page) -> None:
    # Yandex changes class names periodically; try several likely scroll containers,
    # then fall back to mouse wheel over the page.
    for selector in [".scroll__container", ".sidebar-view__panel", "[class*=scroll__container]", "[class*=sidebar]"]:
        locator = page.locator(selector).first
        try:
            await locator.evaluate("el => { el.scrollTop = el.scrollHeight; }")
            return
        except Exception:
            continue
    await page.mouse.wheel(0, 1800)


async def click_more_if_present(page: Page) -> bool:
    labels = ["Показать ещё", "Показать еще", "Далее", "Ещё", "Еще"]
    for label in labels:
        try:
            button = page.get_by_text(label, exact=False).first
            if await button.is_visible(timeout=800):
                await button.click(timeout=1500)
                return True
        except Exception:
            continue
    return False


async def scrape_query(page: Page, category_key: str, query: str, args, seen: set[str], remaining_target: int) -> list[dict[str, str | None]]:
    url = SEARCH_URL.format(query=quote_plus(query + " Москва"))
    collected: list[dict[str, str | None]] = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=args.navigation_timeout * 1000)
    except PlaywrightTimeoutError:
        print(f"Navigation timeout for query {query!r}; continuing.", file=sys.stderr)
        return collected
    await jitter(args.min_delay, args.max_delay)

    if await has_captcha(page):
        print("CAPTCHA or anti-bot challenge detected. Progress is saved; stop and retry manually later.", file=sys.stderr)
        return collected

    unchanged_attempts = 0
    last_visible_count = 0
    while unchanged_attempts < args.stagnation_limit:
        if await has_captcha(page):
            print("CAPTCHA detected during scrolling; stopping this query.", file=sys.stderr)
            break
        cards = await find_result_cards(page)
        visible_count = await cards.count()
        if visible_count == 0:
            no_results = await page.get_by_text("Ничего не найдено", exact=False).count()
            if no_results:
                print(f"No results for {query!r}.")
                break

        for index in range(visible_count):
            org = await extract_from_card(cards.nth(index), category_key, query)
            record = asdict(org)
            key = dedupe_key(record)
            if not normalize_text(record.get("name")) or key in seen:
                continue
            seen.add(key)
            append_jsonl(args.progress_path, record)
            collected.append(record)
            if len(collected) >= remaining_target:
                return collected

        if visible_count <= last_visible_count:
            unchanged_attempts += 1
        else:
            unchanged_attempts = 0
            last_visible_count = visible_count

        if not await click_more_if_present(page):
            await scroll_results(page)
        await jitter(args.min_delay, args.max_delay)

    if unchanged_attempts >= args.stagnation_limit:
        print(f"Result count unchanged after {args.stagnation_limit} attempts for {query!r}; moving on.")
    return collected


def deduplicate(records: Iterable[dict[str, str | None]]) -> list[dict[str, str | None]]:
    unique: dict[str, dict[str, str | None]] = {}
    for record in records:
        key = dedupe_key(record)
        if key and key not in unique:
            unique[key] = record
    return list(unique.values())


async def run(args) -> int:
    if async_playwright is None:
        print("Playwright is not installed. Run: pip install -r requirements.txt && playwright install chromium", file=sys.stderr)
        return 2

    existing = load_existing_records(args.progress_path)
    seen = {dedupe_key(record) for record in existing}
    all_records = existing[:]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=args.headless, slow_mo=args.slow_mo)
        context = await browser.new_context(locale="ru-RU", timezone_id="Europe/Moscow")
        page = await context.new_page()
        page.set_default_timeout(args.action_timeout * 1000)

        for category_key, queries in MOSCOW_CATEGORIES.items():
            category_count = sum(1 for r in all_records if r.get("category_key") == category_key)
            if category_count >= args.target_per_category:
                continue
            for query in queries:
                if category_count >= args.target_per_category:
                    break
                remaining_target = max(args.target_per_category - category_count, 0)
                new_records = await scrape_query(page, category_key, query, args, seen, remaining_target)
                all_records.extend(new_records)
                category_count = sum(1 for r in all_records if r.get("category_key") == category_key)
                export_csv(args.csv_path, deduplicate(all_records))
        await browser.close()

    unique_records = deduplicate(all_records)
    export_csv(args.csv_path, unique_records)
    export_excel(args.excel_path, unique_records)
    print(f"Saved {len(unique_records)} deduplicated organizations to {args.excel_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape Moscow organizations from Yandex Maps with Playwright.")
    parser.add_argument("--target-per-category", type=int, default=DEFAULT_TARGET_PER_CATEGORY)
    parser.add_argument("--progress-path", type=Path, default=DEFAULT_PROGRESS_PATH)
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--excel-path", type=Path, default=DEFAULT_EXCEL_PATH)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-delay", type=float, default=2.0)
    parser.add_argument("--max-delay", type=float, default=5.0)
    parser.add_argument("--stagnation-limit", type=int, default=DEFAULT_STAGNATION_LIMIT)
    parser.add_argument("--navigation-timeout", type=int, default=45, help="Page navigation timeout in seconds.")
    parser.add_argument("--action-timeout", type=int, default=10, help="Default Playwright action timeout in seconds.")
    parser.add_argument("--slow-mo", type=int, default=0, help="Playwright slow_mo value in milliseconds.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.min_delay > args.max_delay:
        parser.error("--min-delay must be less than or equal to --max-delay")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
