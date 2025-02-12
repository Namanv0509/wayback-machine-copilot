import logging
import requests

logger = logging.getLogger(__name__)

WAYBACK_BASE_URL = "https://web.archive.org/web"


def get_snapshot_data(url: str, timestamp: str, job_id: str = "") -> str:
    """
    Retrieves the raw HTML/data for a specific Wayback Machine snapshot.

    :param url: Webpage URL.
    :param timestamp: Snapshot timestamp formatted as YYYYMMDDhhmmss.
    :param job_id: Optional job ID identifier.
    :return: Snapshot content string or error message.
    """
    job_part = f"id_{job_id}" if job_id else "id_"
    snapshot_url = f"{WAYBACK_BASE_URL}/{timestamp}{job_part}/{url}"

    try:
        response = requests.get(snapshot_url, timeout=30)
        if response.status_code == 200:
            return response.text
        return f"Error: {response.status_code} - {response.reason}"
    except requests.exceptions.RequestException as exc:
        logger.error(f"Error retrieving snapshot for {url}: {exc}")
        return f"Error: {exc}"