import logging
from typing import Optional
from mcmetadata import extract
import requests

logger = logging.getLogger(__name__)


def fetch_and_extract_text(url: str, timeout: int = 20) -> Optional[str]:
    """
    Fetches a webpage and extracts its main textual content and title.

    :param url: The target webpage URL.
    :param timeout: Request timeout in seconds.
    :return: Extracted text and title string or None on failure.
    """
    try:
        logger.info(f"Fetching webpage content from {url}")
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (Wayback Copilot Bot)"},
        )
        response.raise_for_status()

        encoding = response.encoding if response.encoding else "utf-8"
        html_content = response.content.decode(encoding, errors="replace")

        logger.info(f"Extracting metadata from {url}")
        metadata = extract(url=url, html_text=html_content)

        title = metadata.get("normalized_article_title", "") or ""
        visible_text = metadata.get("text_content", "") or ""

        text_content = "\n".join(part for part in [title, visible_text] if part)
        logger.info(f"Extracted {len(text_content)} characters from {url}")
        return text_content.strip() if text_content.strip() else None

    except requests.RequestException as exc:
        logger.error(f"Network error fetching {url}: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Error processing HTML from {url}: {exc}")
        return None
