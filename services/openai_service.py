import json
import logging
import os
from typing import Any, Dict, List
from dotenv import load_dotenv
from openai import OpenAI
from config.function_schemas import function_schemas

load_dotenv()
logger = logging.getLogger(__name__)


class OpenAIService:
    """
    Service wrapper for OpenAI chat completions and function calling.
    """

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.system_prompt = os.getenv(
            "SYSTEM_PROMPT",
            "You are Wayback Machine Copilot, a helpful AI assistant for exploring and analyzing web archives.",
        )

    def get_completion(self, messages: List[Dict[str, Any]]):
        """
        Sends conversation messages with functions to OpenAI.
        """
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=full_messages,
            functions=function_schemas,
            function_call="auto",
            temperature=0.7,
        )
        return response.choices[0].message

    def get_function_args(self, function_call: Any) -> Dict[str, Any]:
        """
        Parses JSON arguments from an OpenAI function call object.
        """
        if hasattr(function_call, "arguments"):
            return json.loads(function_call.arguments)
        if isinstance(function_call, dict) and "arguments" in function_call:
            return json.loads(function_call["arguments"])
        return {}
