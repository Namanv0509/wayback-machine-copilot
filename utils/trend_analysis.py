from copy import deepcopy
import logging
from math import exp
from typing import Any, Callable, Dict, Tuple
import pandas as pd
import requests
import streamlit as st
from utils.loadcdx import DailyRecord, PeriodicSamples, load_cdx

logger = logging.getLogger(__name__)

WAYBACK_BASE_URL = "https://web.archive.org/web"
CRLF = "\n"


def format_ymd_span(days: int) -> str:
    """Formats a span of days into years, months, days string representation."""
    years, rem_days = divmod(days, 365)
    months, rem_days = divmod(rem_days, 30)
    if years or months > 6:
        if rem_days > 15:
            months += 1
        rem_days = 0
    if months == 12:
        years += 1
        months = 0
    components = {"y": years, "m": months, "d": rem_days}
    return "".join(f"{v}{k}" for k, v in components.items() if v)


def sigmoid_inverse(x: float, shift: float, slope: float) -> float:
    return 1.0 + exp(shift - x / slope)


def sigmoid(x: float, shift: float = 5, slope: float = 1, spread: float = 1) -> float:
    return spread / sigmoid_inverse(x, shift, slope)


def fill_identical(records: Dict[str, DailyRecord], lk, lv, rk, rv, gap):
    if lv != rv:
        return
    for day in pd.date_range(lk, rk, inclusive="neither"):
        day_str = day.strftime("%Y-%m-%d")
        records[day_str] = DailyRecord(day_str, specimen=lv)


def fill_closest(records: Dict[str, DailyRecord], lk, lv, rk, rv, gap):
    mid = gap / 2
    for i, day in enumerate(pd.date_range(lk, rk, inclusive="neither")):
        day_str = day.strftime("%Y-%m-%d")
        records[day_str] = DailyRecord(day_str, specimen=lv) if i < mid else DailyRecord(day_str, specimen=rv)


def fill_forward(records: Dict[str, DailyRecord], lk, lv, rk, rv, gap):
    for day in pd.date_range(lk, rk, inclusive="neither"):
        day_str = day.strftime("%Y-%m-%d")
        records[day_str] = DailyRecord(day_str, specimen=lv)


def fill_backward(records: Dict[str, DailyRecord], lk, lv, rk, rv, gap):
    for day in pd.date_range(lk, rk, inclusive="neither"):
        day_str = day.strftime("%Y-%m-%d")
        records[day_str] = DailyRecord(day_str, specimen=rv)


FILL_POLICIES: Dict[str, Callable] = {
    "identical": fill_identical,
    "closest": fill_closest,
    "forward": fill_forward,
    "backward": fill_backward,
}


def fill_gap_records(
    date_records: Dict[str, DailyRecord], fill_limit: int, policy: str
) -> Dict[str, DailyRecord]:
    filled_records: Dict[str, DailyRecord] = {}
    record_items = iter(date_records.items())
    prev_key, prev_val = next(record_items)
    prev_specimen = prev_val.specimen
    prev_dt = pd.to_datetime(prev_key)

    for curr_key, curr_val in record_items:
        curr_specimen = curr_val.specimen
        curr_dt = pd.to_datetime(curr_key)
        gap = (curr_dt - prev_dt).days - 1
        if gap and (fill_limit == -1 or gap <= fill_limit):
            fill_func = FILL_POLICIES.get(policy, fill_identical)
            fill_func(filled_records, prev_dt, prev_specimen, curr_dt, curr_specimen, gap)
        prev_dt, prev_specimen = curr_dt, curr_specimen

    return filled_records


def load_trend_data(
    url: str, fill: int, policy: str, sigparams: Dict[str, Tuple[float, float, float]]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    date_records, psc = deepcopy(load_cdx(url))
    if not date_records:
        raise ValueError(f"Empty or malformed CDX API response for {url}")

    if fill != 0:
        date_records.update(fill_gap_records(date_records, fill, policy))

    results = []
    prev_status = "~"
    prev_content = "Unknown"
    prev_chaos = prev_chaosn = 0.0
    base_resilience = base_content = 0.5
    scale_resilience = scale_content = 0.5
    resilience_val = fixity_val = 0.5
    step_resilience = step_fixity = 0

    first_day = next(iter(date_records))
    for day in pd.date_range(first_day, pd.to_datetime("today")):
        day_str = day.strftime("%Y-%m-%d")
        record = date_records.get(day_str, DailyRecord(day_str))

        if record.chaos:
            prev_chaos = record.chaos
            prev_chaosn = record.chaosn
        else:
            record.chaos = prev_chaos
            record.chaosn = prev_chaosn

        specimen = record.specimen
        status_params = sigparams.get(specimen, (5, 1.0, 1.0))
        if specimen != prev_status:
            base_resilience = resilience_val
            scale_resilience = base_resilience if status_params[2] < 0 else 1 - base_resilience
            prev_status = specimen
            step_resilience = 0
        step_resilience += 1
        resilience_val = base_resilience + scale_resilience * sigmoid(step_resilience, *status_params)
        record.resilience = resilience_val

        content_status = record.content
        content_params = sigparams.get(content_status, (5, 1.0, 1.0))
        if content_status != prev_content:
            base_content = fixity_val
            scale_content = base_content if content_params[2] < 0 else 1 - base_content
            prev_content = content_status
            step_fixity = 0
        step_fixity += 1
        fixity_val = base_content + scale_content * sigmoid(step_fixity, *content_params)
        record.fixity = fixity_val

        results.append(record)

    df_records = pd.DataFrame(results)
    df_records.columns = [c[1:] if c.startswith("_") else c.title() for c in df_records.columns]
    df_records["URIM"] = df_records["Datetime"].apply(
        lambda x: f"{WAYBACK_BASE_URL}/{x}/{url}" if x != "~" else "#"
    )

    transitions = {
        "2xx": {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0},
        "3xx": {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0},
        "4xx": {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0},
        "5xx": {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0},
    }

    record_iter = iter(results)
    prev_rec = next(record_iter)
    for rec in record_iter:
        try:
            transitions[rec.specimen][prev_rec.specimen] += 1
            prev_rec = rec
        except KeyError:
            continue

    df_transitions = (
        pd.DataFrame(transitions)
        .reset_index()
        .rename(columns={"index": "Source"})
        .melt(
            id_vars=["Source"],
            value_vars=["2xx", "3xx", "4xx", "5xx"],
            var_name="Target",
            value_name="Count",
        )
    )

    df_samples = (
        pd.DataFrame.from_dict(psc, orient="index", columns=["Samples"])
        .reset_index()
        .rename(columns={"index": "Period"})
    )

    return df_records, df_transitions, df_samples


def analyze_trends(url: str) -> Dict[str, Any]:
    """
    Computes resilience, fixity, and chaos trend metrics for a given website URL.
    """
    fill_limit, policy = 0, "identical"
    sigparams = {
        "2xx": (4, 1.0, 1.0),
        "3xx": (5, 10.0, -0.5),
        "4xx": (5, 1.0, -1.0),
        "5xx": (5, 1.0, -1.0),
        "~": (10, 20.0, -0.5),
        "Changed": (6, 1.0, -1.0),
        "Unchanged": (4, 1.0, 1.0),
        "Unknown": (10, 30.0, -0.5),
    }

    df, _, _ = load_trend_data(url, fill_limit, policy, sigparams)

    # Render charts in Streamlit sidebar
    try:
        st.sidebar.subheader("Resilience Over Time")
        st.sidebar.line_chart(df.set_index("Day")["Resilience"])

        st.sidebar.subheader("Fixity Over Time")
        st.sidebar.line_chart(df.set_index("Day")["Fixity"])

        st.sidebar.subheader("Chaos Over Time")
        chaos_df = df.set_index("Day")[["Chaos", "Chaosn"]]
        chaos_df.columns = ["All", "Last 1000"]
        st.sidebar.line_chart(chaos_df)
    except Exception:
        pass

    return {
        "captures": int(df["All"].sum()),
        "span": len(df),
        "gaps": int((df["All"] == 0).sum()),
        "resilience": float(df["Resilience"].iloc[-1]),
        "resilience_trend": (
            float(df["Resilience"].iloc[-1] - df["Resilience"].iloc[-2])
            if len(df) > 1
            else 0.0
        ),
        "fixity": float(df["Fixity"].iloc[-1]),
        "fixity_trend": (
            float(df["Fixity"].iloc[-1] - df["Fixity"].iloc[-2]) if len(df) > 1 else 0.0
        ),
        "chaos": float(df["Chaos"].iloc[-1]),
        "chaos_trend": (
            float(df["Chaos"].iloc[-1] - df["Chaos"].iloc[-2]) if len(df) > 1 else 0.0
        ),
        "status_distribution": df[["2xx", "3xx", "4xx", "5xx"]].sum().to_dict(),
    }


def interpret_trend(metric: str, value: float, trend: float) -> str:
    interpretations = {
        "resilience": {
            "high": "The webpage is highly resilient, indicating good archival preservation.",
            "medium": "The webpage has moderate resilience, suggesting room for improvement in archival preservation.",
            "low": "The webpage has low resilience, indicating potential issues with archival preservation.",
        },
        "fixity": {
            "high": "The webpage content is highly stable over time.",
            "medium": "The webpage content shows moderate stability over time.",
            "low": "The webpage content is frequently changing or unstable.",
        },
        "chaos": {
            "high": "The webpage shows high variability in its HTTP status codes, indicating potential instability.",
            "medium": "The webpage shows moderate variability in its HTTP status codes.",
            "low": "The webpage shows low variability in its HTTP status codes, indicating stability.",
        },
    }

    level = "high" if value > 0.7 else "medium" if value > 0.3 else "low"
    trend_desc = "increasing" if trend > 0 else "decreasing" if trend < 0 else "stable"

    return f"{interpretations[metric][level]} The trend is {trend_desc}."


def get_trend_analysis(url: str) -> str:
    logger.info(f"Analyzing trends for {url}")
    summary = analyze_trends(url)

    return f"""
    Trend Analysis for {url}:

    1. Captures: {summary['captures']} total captures over {summary['span']} days, with {summary['gaps']} gaps.

    2. Resilience: {summary['resilience']:.5f} (Trend: {summary['resilience_trend']:.5f})
    {interpret_trend('resilience', summary['resilience'], summary['resilience_trend'])}

    3. Fixity: {summary['fixity']:.5f} (Trend: {summary['fixity_trend']:.5f})
    {interpret_trend('fixity', summary['fixity'], summary['fixity_trend'])}

    4. Chaos: {summary['chaos']:.5f} (Trend: {summary['chaos_trend']:.5f})
    {interpret_trend('chaos', summary['chaos'], summary['chaos_trend'])}

    5. Status Distribution:
    - 2xx: {summary['status_distribution']['2xx']}
    - 3xx: {summary['status_distribution']['3xx']}
    - 4xx: {summary['status_distribution']['4xx']}
    - 5xx: {summary['status_distribution']['5xx']}

    These metrics are for the understanding of LLM only. Try to simplify the explanation for the end-user. You'll have to explain in layman terms what these metrics mean for the website's health and stability. Don't include technical terms like fixity, chaos in the trend analysis result as user might not know of these.
    """
