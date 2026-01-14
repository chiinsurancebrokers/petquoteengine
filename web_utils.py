"""
PETSHEALTH Quote Engine - Secure Web Scraping Utilities
Safe content fetching with validation, sanitization, and caching
"""
import logging
from urllib.parse import urljoin, urlparse
from typing import Optional

import requests
from bs4 import BeautifulSoup
import streamlit as st

from config import (
    WEB_SCRAPE_TIMEOUT,
    WEB_SCRAPE_MAX_ITEMS,
    WEB_SCRAPE_USER_AGENT,
)
from input_validators import validate_url, sanitize_scraped_text

logger = logging.getLogger(__name__)


class WebScrapingError(Exception):
    """Custom exception for web scraping errors"""
    pass


# --------------------------
# Safe HTTP Requests
# --------------------------

def safe_get_request(url: str, timeout: int = WEB_SCRAPE_TIMEOUT) -> requests.Response:
    """
    Make a safe HTTP GET request with validation and error handling.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Response object

    Raises:
        WebScrapingError: If request fails
    """
    # Validate URL
    if not validate_url(url):
        raise WebScrapingError(f"Invalid URL: {url}")

    # Security: Only allow HTTPS (except for localhost testing)
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http'):
        raise WebScrapingError(f"Invalid URL scheme: {parsed.scheme}")

    # Warn about HTTP
    if parsed.scheme == 'http' and not parsed.netloc.startswith('localhost'):
        logger.warning(f"Using insecure HTTP: {url}")

    headers = {
        'User-Agent': WEB_SCRAPE_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,el;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',  # Do Not Track
        'Connection': 'close',
    }

    try:
        logger.info(f"Fetching: {url}")
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            verify=True,  # Verify SSL certificates
        )
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            logger.warning(f"Unexpected content type: {content_type}")

        # Check size (prevent huge responses)
        content_length = len(response.content)
        if content_length > 10 * 1024 * 1024:  # 10MB
            raise WebScrapingError(f"Response too large: {content_length / 1024 / 1024:.1f}MB")

        logger.info(f"Fetched {content_length} bytes from {url}")
        return response

    except requests.exceptions.SSLError as e:
        logger.error(f"SSL error for {url}: {e}")
        raise WebScrapingError(f"SSL certificate validation failed for {url}") from e

    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout for {url}: {e}")
        raise WebScrapingError(f"Request timed out after {timeout}s") from e

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error for {url}: {e}")
        raise WebScrapingError(f"Could not connect to {url}") from e

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error for {url}: {e}")
        raise WebScrapingError(f"HTTP {response.status_code} error for {url}") from e

    except Exception as e:
        logger.error(f"Unexpected error for {url}: {e}")
        raise WebScrapingError(f"Failed to fetch {url}: {str(e)}") from e


# --------------------------
# Content Extraction
# --------------------------

@st.cache_data(show_spinner=False, ttl=3600)  # Cache for 1 hour
def fetch_highlights(url: str, max_items: int = WEB_SCRAPE_MAX_ITEMS) -> list[str]:
    """
    Fetch and extract text highlights from a webpage (CACHED).

    Args:
        url: URL to scrape
        max_items: Maximum number of items to return

    Returns:
        List of sanitized text snippets
    """
    try:
        response = safe_get_request(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove unwanted elements
        for tag in soup(['script', 'style', 'noscript', 'iframe', 'object', 'embed']):
            tag.decompose()

        candidates = []

        # Extract from headings and list items
        for tag in soup.find_all(['h1', 'h2', 'h3', 'li']):
            text = tag.get_text(' ', strip=True)
            text = sanitize_scraped_text(text, max_length=240)

            if 28 <= len(text) <= 240:
                candidates.append(text)

        # If not enough, extract from paragraphs
        if len(candidates) < max_items:
            for tag in soup.find_all('p'):
                text = tag.get_text(' ', strip=True)
                text = sanitize_scraped_text(text, max_length=300)

                if 60 <= len(text) <= 300:
                    candidates.append(text)

                if len(candidates) >= max_items * 3:
                    break

        # Deduplicate and filter
        seen = set()
        filtered = []

        for text in candidates:
            text_lower = text.lower()

            # Skip if duplicate
            if text_lower in seen:
                continue
            seen.add(text_lower)

            # Skip unwanted content
            unwanted = [
                'cookie', 'privacy policy', 'javascript',
                'newsletter', 'subscribe', '©', 'all rights reserved',
                'terms of service', 'disclaimer'
            ]
            if any(word in text_lower for word in unwanted):
                continue

            filtered.append(text)

            if len(filtered) >= max_items:
                break

        logger.info(f"Extracted {len(filtered)} highlights from {url}")
        return filtered

    except WebScrapingError as e:
        logger.error(f"Failed to fetch highlights: {e}")
        return []

    except Exception as e:
        logger.error(f"Unexpected error fetching highlights: {e}")
        return []


@st.cache_data(show_spinner=False, ttl=3600)  # Cache for 1 hour
def fetch_site_images(url: str, limit: int = WEB_SCRAPE_MAX_ITEMS) -> list[str]:
    """
    Fetch image URLs from a webpage (CACHED).

    Args:
        url: URL to scrape
        limit: Maximum number of images to return

    Returns:
        List of absolute image URLs
    """
    try:
        response = safe_get_request(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        image_urls = []

        for img in soup.find_all('img'):
            src = (img.get('src') or '').strip()
            if not src:
                continue

            # Convert to absolute URL
            full_url = urljoin(url, src)

            # Validate
            if not validate_url(full_url):
                continue

            # Check extension
            lower_url = full_url.lower()
            valid_exts = ['.png', '.jpg', '.jpeg', '.webp', '.gif']
            if not any(ext in lower_url for ext in valid_exts):
                continue

            # Skip common tracking/ad images
            if any(skip in lower_url for skip in ['tracking', 'pixel', 'analytics', '1x1']):
                continue

            image_urls.append(full_url)

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in image_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
            if len(unique_urls) >= limit:
                break

        logger.info(f"Found {len(unique_urls)} images from {url}")
        return unique_urls

    except WebScrapingError as e:
        logger.error(f"Failed to fetch images: {e}")
        return []

    except Exception as e:
        logger.error(f"Unexpected error fetching images: {e}")
        return []


@st.cache_data(show_spinner=False, ttl=3600)  # Cache for 1 hour
def download_image_bytes(url: str, max_size_mb: int = 10) -> Optional[bytes]:
    """
    Download image as bytes with validation (CACHED).

    Args:
        url: Image URL
        max_size_mb: Maximum file size in MB

    Returns:
        Image bytes or None if failed
    """
    try:
        # Use shorter timeout for images
        response = safe_get_request(url, timeout=15)

        # Check content type
        content_type = response.headers.get('Content-Type', '').lower()
        if not content_type.startswith('image/'):
            logger.warning(f"Invalid content type for image: {content_type}")
            return None

        # Check size
        size_mb = len(response.content) / (1024 * 1024)
        if size_mb > max_size_mb:
            logger.warning(f"Image too large: {size_mb:.1f}MB")
            return None

        logger.info(f"Downloaded image: {size_mb:.2f}MB")
        return response.content

    except WebScrapingError as e:
        logger.error(f"Failed to download image: {e}")
        return None

    except Exception as e:
        logger.error(f"Unexpected error downloading image: {e}")
        return None


# --------------------------
# Batch Operations
# --------------------------

def fetch_all_content(
        urls: dict[str, str],
        max_highlights: int = 8,
) -> dict[str, list[str]]:
    """
    Fetch content from multiple URLs efficiently.

    Args:
        urls: Dictionary of {name: url}
        max_highlights: Max highlights per URL

    Returns:
        Dictionary of {name: highlights_list}
    """
    results = {}

    for name, url in urls.items():
        logger.info(f"Fetching content for: {name}")
        try:
            highlights = fetch_highlights(url, max_items=max_highlights)
            results[name] = highlights
            logger.info(f"✅ Fetched {len(highlights)} highlights for {name}")
        except Exception as e:
            logger.error(f"❌ Failed to fetch {name}: {e}")
            results[name] = []

    return results
