import json
import logging
from typing import Any, Dict, List, Optional, Union
import requests

logger = logging.getLogger(__name__)

CDX_API_URL = "http://web.archive.org/cdx/search/cdx"


def fetch_cdx_data(
    url: str,
    match_type: str = "domain",
    limit: Optional[int] = 10,
    fields: Optional[List[str]] = None,
    filters: Optional[List[str]] = None,
    from_timestamp: Optional[str] = None,
    to_timestamp: Optional[str] = None,
) -> Union[str, Dict[str, str]]:
    """
    Fetches CDX (Capture Index) data from the Wayback Machine for a given URL.

    :param url: The target URL to fetch CDX historical records for.
    :param match_type: Match scope ('exact', 'prefix', 'host', 'domain').
    :param limit: Maximum number of capture records to return.
    :param fields: List of specific field names to return in the CDX response.
    :param filters: List of CDX filter rules.
    :param from_timestamp: Start timestamp filter (YYYYMMDDhhmmss format).
    :param to_timestamp: End timestamp filter (YYYYMMDDhhmmss format).
    :return: JSON-serialized list of 200-status captures, or dict with 'error'.
    """
    params: Dict[str, Any] = {
        "url": url,
        "output": "json",
        "matchType": match_type,
    }

    if limit is not None:
        params["limit"] = -limit
    else:
        params["limit"] = 10

    if fields:
        params["fl"] = ",".join(fields)
    if filters:
        params["filter"] = filters
    if from_timestamp:
        params["from"] = from_timestamp
    if to_timestamp:
        params["to"] = to_timestamp

    try:
        response = requests.get(CDX_API_URL, params=params, timeout=30)
        response.raise_for_status()

        cdx_data = response.json()
        if not cdx_data:
            return {"error": "No CDX data found for this URL."}

        # Filter out captures with HTTP status codes other than 200
        filtered_captures = [
            capture for capture in cdx_data if len(capture) > 4 and capture[4] == "200"
        ]

        if not filtered_captures:
            return {"error": "No CDX data found with status code 200 for this URL."}

        return json.dumps(filtered_captures)

    except requests.exceptions.RequestException as exc:
        logger.error(f"CDX request failed for {url}: {exc}")
        return {"error": str(exc)}
