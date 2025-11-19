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
JINA_TIMEOUT: Final[int] = 30
CONTENT_LIMIT: Final[int] = 3000
MIN_CONTENT_LENGTH: Final[int] = 300


def scrape_direct(url: str) -> str:
    """Direct scraping using requests + BeautifulSoup.
    
    Fast but may fail on JavaScript-heavy sites.
    Returns extracted text or empty string on failure.
    """
    if not url:
        return ""

    try:
        response = requests.get(
            url,
            timeout=SCRAPE_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"⚠ Direct scrape failed for {url}: {exc}")
        return ""

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
        print(f"Direct scraping status: {response.status_code}, Length: {len(combined)}")

        return combined
    except Exception as exc:
        print(f"⚠ Failed to parse competitor content for {url}: {exc}")
        return ""


def scrape_via_jina(url: str) -> str:
    """Fallback scraping using Jina Reader API.
    
    Handles JavaScript-heavy sites by using Jina's proxy service.
    Returns extracted text or empty string on failure.
    """
    if not url:
        return ""

    try:
        jina_url = f"https://r.jina.ai/{url}"
        response = requests.get(
            jina_url,
            timeout=JINA_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        
        # Jina returns clean text content directly
        text = response.text.strip()
        text = text[:CONTENT_LIMIT]
        print(f"Jina scraping status: {response.status_code}, Length: {len(text)}")
        
        return text
    except requests.RequestException as exc:
        print(f"⚠ Jina scrape failed for {url}: {exc}")
        return ""
    except Exception as exc:
        print(f"⚠ Jina parsing failed for {url}: {exc}")
        return ""


def scrape_url(url: str) -> str:
    """Fetch and summarize key text blocks from a URL.

    Uses a two-tier strategy:
    1. First tries direct scraping (fast, works for most sites)
    2. Falls back to Jina Reader API if direct fails or returns insufficient content

    Returns up to the first 3,000 characters collected.
    If both methods fail, a safe fallback string is returned so callers
    can continue gracefully.
    """
    if not url:
        return "Scraping failed. Please extract insights manually."

    # Try direct scraping first
    try:
        direct_result = scrape_direct(url)
        
        # Check if direct scraping succeeded and has sufficient content
        if direct_result and len(direct_result) >= MIN_CONTENT_LENGTH:
            return direct_result
        
        # Direct scrape failed or returned insufficient content
        if direct_result:
            print(f"Direct scrape returned only {len(direct_result)} chars (< {MIN_CONTENT_LENGTH}), switching to Jina Proxy...")
        else:
            print("Direct scrape failed/empty, switching to Jina Proxy...")
    except Exception as exc:
        print(f"⚠ Direct scrape exception: {exc}, switching to Jina Proxy...")
        direct_result = ""

    # Fallback to Jina Reader API
    try:
        jina_result = scrape_via_jina(url)
        
        if jina_result:
            trimmed = jina_result[:CONTENT_LIMIT]
            if len(trimmed) < 500:
                trimmed = "[WARNING: The website blocked most content, analysis may be limited based on meta-tags only]\n" + trimmed
            print(f"Jina scraping status: length={len(trimmed)}")
            return trimmed

        print("Jina scrape also failed/empty")
    except Exception as exc:
        print(f"⚠ Jina scrape exception: {exc}")

    # Both methods failed
    return "Scraping failed. Please extract insights manually."

