from __future__ import annotations

from typing import Final

import requests
from bs4 import BeautifulSoup

USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
SCRAPE_TAGS: Final[tuple[str, ...]] = ("h1", "h2", "h3", "p", "li")
SCRAPE_TIMEOUT: Final[int] = 10
CONTENT_LIMIT: Final[int] = 3000


def scrape_competitor_text(url: str) -> str:
    """Fetch and summarize key text blocks from a competitor page.

    Returns up to the first 3,000 characters collected from headline and body tags.
    If fetching or parsing fails, a safe fallback string is returned so callers
    can continue gracefully.
    """

    if not url:
        return "Unable to scrape content."

    try:
        response = requests.get(
            url,
            timeout=SCRAPE_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"⚠ Competitor scrape failed for {url}: {exc}")
        return "Unable to scrape content."

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        collected: list[str] = []

        for element in soup.find_all(SCRAPE_TAGS):  # type: ignore[arg-type]
            text = element.get_text(separator=" ", strip=True)
            if text:
                collected.append(text)

        combined = " ".join(collected).strip()

        if len(combined) < 100:
            meta_description = soup.find("meta", attrs={"name": "description"})
            meta_text = meta_description.get("content", "").strip() if meta_description else ""
            title_tag = soup.find("title")
            title_text = title_tag.get_text(strip=True) if title_tag else ""
            fallback = " ".join(filter(None, [title_text, meta_text])).strip()
            combined = f"{combined} {fallback}".strip()

        combined = combined[:CONTENT_LIMIT]
        print(f"Scraping status: {response.status_code}, Length: {len(combined)}")

        if not combined:
            return "Scraping failed. Please extract insights manually."

        return combined
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"⚠ Failed to parse competitor content for {url}: {exc}")
        return "Scraping failed. Please extract insights manually."

