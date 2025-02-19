import logging
import os
import sys
from typing import Any, Dict, Generator
from dotenv import load_dotenv
import streamlit as st
from config import suggestions
from services import OpenAIService, SemanticRouterService, WaybackService

# Setup path and environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Streamlit page
st.set_page_config(
    page_title="Wayback Machine Copilot",
    page_icon="assets/favicon.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def initialize_app_services():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OpenAI API key is missing. Please set the OPENAI_API_KEY environment variable.")
        st.stop()

    try:
        return OpenAIService(api_key), WaybackService(), SemanticRouterService()
    except Exception as exc:
        st.error(f"Failed to initialize services: {exc}")
        st.stop()


openai_svc, wayback_svc, semantic_router_svc = initialize_app_services()


def render_sidebar_suggestions():
    with st.sidebar.expander("Explore Example Queries"):
        for suggestion in suggestions:
            st.markdown(f"- {suggestion}")


def execute_tool_call(function_name: str, args: Dict[str, Any]) -> str:
    url = args.get("url")
    logger.info(f"Executing tool call: {function_name} on {url}")

    if function_name == "fetch_cdx_data":
        return str(wayback_svc.fetch_cdx_data(url, args.get("limit")))
    elif function_name == "fetch_data_wayback":
        return str(wayback_svc.fetch_data_wayback(url, args.get("timestamp")))
    elif function_name == "get_trend_analysis":
        return str(wayback_svc.get_trend_analysis(url))
    elif function_name == "fetch_and_extract_text":
        return str(wayback_svc.fetch_and_extract_text(url))
    else:
        logger.error(f"Unrecognized tool function: {function_name}")
        raise ValueError(f"Unknown function: {function_name}")


def stream_response_text(text: str) -> Generator[str, None, None]:
    if not text:
        yield "No response generated."
    else:
        for char in text:
            yield char


def handle_user_prompt(user_input: str):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    intent = semantic_router_svc.get_intent(user_input)
    logger.info(f"Detected query intent: {intent}")

    messages_payload = st.session_state.messages.copy()
    if intent:
        messages_payload.append(
            {
                "role": "system",
                "content": f"The detected intent for the user's last message is: {intent}. Consider using the {intent} function if appropriate.",
            }
        )

    try:
        completion = openai_svc.get_completion(messages_payload)
        if not completion:
            st.error("Received an empty response from AI service.")
            return

        if completion.function_call:
            fn_name = completion.function_call.name
            fn_args = openai_svc.get_function_args(completion.function_call)

            if "url" in fn_args:
                fn_args["url"] = str(fn_args["url"])

            tool_result = execute_tool_call(fn_name, fn_args)

            st.session_state.messages.append(
                {
                    "role": "function",
                    "name": str(fn_name),
                    "content": str(tool_result),
                }
            )

            followup_completion = openai_svc.get_completion(st.session_state.messages)
            assistant_reply = followup_completion.content if followup_completion else "No response generated."
        else:
            assistant_reply = completion.content if completion else "No response generated."

    except Exception as exc:
        logger.error(f"Error handling query: {exc}")
        st.error(f"Error processing request: {exc}")
        return

    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
    with st.chat_message("assistant", avatar="assets/favicon.ico"):
        st.write_stream(stream_response_text(assistant_reply))


# Main Application Interface
st.title("Wayback Machine AI Copilot")
render_sidebar_suggestions()

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Hello! How can I assist you in exploring the Wayback Machine archives today?"}
    ]

# Render conversation history
for msg in st.session_state.messages:
    if msg["role"] in ["user", "assistant"]:
        avatar = "assets/favicon.ico" if msg["role"] == "assistant" else None
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["role"] == "assistant":
                st.write_stream(stream_response_text(msg["content"]))
            else:
                st.write(msg["content"])

# Chat input bar
prompt = st.chat_input("Type your message here...", key="chat_input")
if prompt:
    handle_user_prompt(prompt)
