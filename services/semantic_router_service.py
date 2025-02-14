import logging
import os
from typing import Optional
from dotenv import load_dotenv
from semantic_router import Route, RouteLayer
from semantic_router.encoders import OpenAIEncoder
from config import router_schemas

load_dotenv()
logger = logging.getLogger(__name__)

routes = [
    Route(
        name="fetch_cdx_data",
        utterances=[
            "Get CDX data for URL",
            "Fetch Wayback Machine data for URL",
            "Historical data for URL",
            "Get historical data for URL",
            "Get CDX data",
            "Get Archive data",
            "Get Archive records",
        ],
        function_schemas=router_schemas,
    ),
    Route(
        name="get_trend_analysis",
        utterances=[
            "Analyze trends for URL",
            "Get resilience, fixity, and chaos metrics",
            "Trend analysis for website",
            "Show me the trend analysis of URL",
            "What are the trends for this URL?",
            "What are the resilience, fixity, and chaos metrics for this URL?",
            "What are the metrics for this URL?",
            "What are the trends for this website?",
            "How is this website doing?",
            "How is this URL doing?",
            "How has this URL been performing?",
            "How healthy is this URL?",
            "How resilient is this URL?",
            "How chaotic is this URL?",
            "How stable is this URL?",
            "How reliable is this URL?",
            "How trustworthy is this URL?",
            "How secure is this URL?",
            "How much has this URL changed?",
            "How much has this website changed?",
            "How much has this URL been modified?",
        ],
        function_schemas=router_schemas,
    ),
    Route(
        name="fetch_data_wayback",
        utterances=[
            "Fetch webpage snapshot",
            "Get webpage snapshot",
            "Get webpage snapshot from Wayback Machine",
            "Fetch webpage snapshot from Wayback Machine",
            "Fetch webpage from Wayback Machine",
            "What was the webpage like in the past?",
            "Show me the webpage snapshot",
            "What did the webpage look like in the past?",
            "What was shown on the webpage in the past?",
        ],
        function_schemas=router_schemas,
    ),
]


class SemanticRouterService:
    """
    Routes user prompt intents to appropriate backend functions using semantic embeddings.
    """

    def __init__(self):
        encoder = OpenAIEncoder()
        self.layer = RouteLayer(encoder=encoder, routes=routes)

    def get_intent(self, user_input: str) -> Optional[str]:
        """
        Evaluates input query and returns matching route name if confidence threshold met.
        """
        try:
            result = self.layer(user_input)
            return result.name if result and result.name else None
        except Exception as exc:
            logger.warning(f"Semantic routing error for '{user_input}': {exc}")
            return None
