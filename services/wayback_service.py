import logging
from typing import Any, Dict, Optional, Union
from utils.fetch_data_wayback import fetch_data_wayback
from utils.cdxdata import fetch_cdx_data
from utils.extract_text import fetch_and_extract_text
from utils.trend_analysis import get_trend_analysis

logger = logging.getLogger(__name__)


class WaybackService:
    """
    Unified service facade for Wayback Machine operations.
    """

    def fetch_cdx_data(
        self, url: str, limit: Optional[int] = None
    ) -> Union[str, Dict[str, str]]:
        logger.info(f"Fetching CDX data for {url} (limit: {limit})")
        return fetch_cdx_data(url=url, limit=limit)

    def fetch_and_extract_text(self, url: str) -> Optional[str]:
        logger.info(f"Fetching live text content from {url}")
        return fetch_and_extract_text(url=url)

    def get_trend_analysis(self, url: str) -> str:
        logger.info(f"Generating trend analysis for {url}")
        return get_trend_analysis(url=url)

    def fetch_data_wayback(self, url: str, time: Optional[str] = None) -> str:
        logger.info(f"Fetching Wayback snapshot text for {url} at time {time}")
        return fetch_data_wayback(url=url, timestamp=time)
