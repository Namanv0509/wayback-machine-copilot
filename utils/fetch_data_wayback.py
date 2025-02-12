from datetime import datetime, timedelta
from functools import lru_cache
import json
import logging
from typing import Any, Dict, Optional
from urllib.request import urlopen
from bs4 import BeautifulSoup
from mcmetadata import extract
import requests
import streamlit as st
import streamlit.components.v1 as components
from utils.cdxdata import fetch_cdx_data

logger = logging.getLogger(__name__)


@lru_cache(maxsize=100)
def get_latest_timestamp(url: str) -> str:
    """
    Fetches the latest snapshot timestamp for a given URL.
    """
    cdx_response = fetch_cdx_data(url=url, limit=100)

    if isinstance(cdx_response, dict) and "error" in cdx_response:
        raise ValueError(f"Error fetching CDX data: {cdx_response['error']}")

    cdx_records = json.loads(cdx_response) if isinstance(cdx_response, str) else cdx_response

    if not isinstance(cdx_records, list) or len(cdx_records) < 2:
        raise ValueError("No snapshot data available for this URL")

    return cdx_records[1][1]


def fetch_wayback_content(wayback_url: str) -> bytes:
    """
    Fetches raw HTML content from a Wayback Machine snapshot URL.
    """
    with urlopen(wayback_url, timeout=30) as response:
        if response.status != 200:
            raise requests.RequestException(
                f"HTTP Error {response.status}: {response.reason}"
            )
        return response.read()


def clean_text(text: str) -> str:
    """
    Cleans up whitespace and formatting in extracted webpage text.
    """
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)


def extract_metadata(url: str, text: str) -> Dict[str, Any]:
    """
    Extracts normalized title and article text content from HTML/text.
    """
    metadata = extract(url=url, html_text=text)
    return {
        "title": metadata.get("normalized_article_title", "") or "",
        "visible_text": metadata.get("text_content", "") or "",
    }


@st.cache_data(max_entries=100, show_spinner=False)
def get_snapshot_within_month(url: str, target_timestamp: str) -> str:
    """
    Fetches a snapshot timestamp closest to the target timestamp within a 30-day window.
    """
    target_date = datetime.strptime(target_timestamp, "%Y%m%d%H%M%S")
    from_date = (target_date - timedelta(days=15)).strftime("%Y%m%d%H%M%S")
    to_date = (target_date + timedelta(days=15)).strftime("%Y%m%d%H%M%S")

    logger.info(f"Querying snapshots between {from_date} and {to_date} for {url}")
    cdx_response = fetch_cdx_data(
        url=url, limit=100, from_timestamp=from_date, to_timestamp=to_date
    )

    if isinstance(cdx_response, dict) and "error" in cdx_response:
        raise ValueError(f"Error fetching CDX data: {cdx_response['error']}")

    if not cdx_response:
        raise ValueError("No snapshot data available for this URL")

    cdx_records = json.loads(cdx_response) if isinstance(cdx_response, str) else cdx_response

    if not isinstance(cdx_records, list) or len(cdx_records) < 2:
        raise ValueError("No snapshot data available for this URL")

    # Find closest snapshot to the target date (skipping header row at index 0 if header exists)
    data_rows = cdx_records[1:] if cdx_records[0][0] == "urlkey" else cdx_records
    closest_snapshot = min(
        data_rows,
        key=lambda row: abs(datetime.strptime(row[1], "%Y%m%d%H%M%S") - target_date),
    )

    return closest_snapshot[1]


def fetch_data_wayback(
    url: str, timestamp: Optional[str] = None, debug: bool = True
) -> str:
    """
    Fetches a webpage from the Wayback Machine and extracts its main textual content.
    """
    try:
        logger.info(f"Fetching archived page for {url} (timestamp: {timestamp})")

        resolved_timestamp = (
            get_snapshot_within_month(url, timestamp)
            if timestamp
            else get_latest_timestamp(url)
        )

        wayback_url = f"https://web.archive.org/web/{resolved_timestamp}id_/{url}"

        # Render preview in Streamlit chat if running in Streamlit context
        try:
            with st.chat_message("assistant", avatar="assets/favicon.ico"):
                st.write("Here's the Wayback Machine rendering of the page:")
                components.iframe(wayback_url, width=700, height=500, scrolling=True)
        except Exception:
            pass

        html_bytes = fetch_wayback_content(wayback_url)
        soup = BeautifulSoup(html_bytes, features="html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.extract()

        raw_text = clean_text(soup.get_text())
        metadata = extract_metadata(url, raw_text)
        text_content = "\n".join(
            part for part in [metadata["title"], metadata["visible_text"]] if part
        )

        if len(text_content.strip()) < 50:
            text_content = raw_text

        return text_content.strip()

    except (requests.RequestException, ValueError) as exc:
        logger.error(f"Error fetching Wayback data for {url}: {exc}")
        return ""
    except Exception as exc:
        logger.error(f"Unexpected error processing {url}: {exc}")
        return ""
