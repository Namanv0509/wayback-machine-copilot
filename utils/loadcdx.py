from dataclasses import dataclass, field
from typing import Dict, Generator, Tuple
from urllib.parse import quote_plus
import requests
import streamlit as st

CDX_API_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
MAX_CDX_PAGES = 2000


@dataclass
class DailyRecord:
    day: str
    datetime: str = "~"
    _2xx: int = 0
    _3xx: int = 0
    _4xx: int = 0
    _5xx: int = 0
    resilience: float = 0.0
    digest: str = "~"
    content: str = "Unknown"
    fixity: float = 0.0
    chaos: float = 0.0
    chaosn: float = 0.0
    _specimen: str = "~"

    @property
    def all(self) -> int:
        return self._2xx + self._3xx + self._4xx + self._5xx

    @property
    def specimen(self) -> str:
        if self._specimen != "~":
            return self._specimen
        for status_key in ("_2xx", "_4xx", "_5xx", "_3xx"):
            if getattr(self, status_key):
                return status_key[1:]
        return self._specimen

    @specimen.setter
    def specimen(self, val: str):
        self._specimen = val if isinstance(val, str) else "~"

    @property
    def filled(self) -> bool:
        return self.specimen != "~" and not self.all

    def incr(self, status: str, count: int = 1):
        attr_name = f"_{status}"
        if hasattr(self, attr_name):
            setattr(self, attr_name, getattr(self, attr_name) + count)


class PeriodicSamples:
    PERIODS = {"Second": 14, "Minute": 12, "Hour": 10, "Day": 8, "Month": 6, "Year": 4}

    def __init__(self):
        self.count = 0
        self.sample = {p: 0 for p in self.PERIODS}
        self._prev = {p: "~" for p in self.PERIODS}

    def __call__(self, dt: str):
        self.count += 1
        for k, length in self.PERIODS.items():
            if dt[:length] == self._prev[k]:
                break
            self._prev[k] = dt[:length]
            self.sample[k] += 1

    def __str__(self) -> str:
        return "\t".join([str(self.count)] + [str(v) for v in self.sample.values()])


def load_cdx_pages(url: str) -> Generator[bytes, None, None]:
    session = requests.Session()
    progress_bar = st.progress(0)
    page = 0
    while page < MAX_CDX_PAGES:
        page_url = f"{url}&page={page}"
        response = session.get(page_url, stream=True, timeout=30)
        if not response.ok:
            progress_bar.empty()
            raise ValueError(
                f"CDX API returned {response.status_code} status code for {url}"
            )
        response.raw.decode_content = True
        for line in response.raw:
            yield line
        page += 1
        max_pages = int(response.headers.get("x-cdx-num-pages", 1))
        progress_bar.progress(min(page / max_pages, 1.0))
        if page >= max_pages:
            progress_bar.empty()
            break


@st.cache_data(persist=True, show_spinner=False)
def load_cdx(url: str) -> Tuple[Dict[str, DailyRecord], Dict[str, int]]:
    digest_status: Dict[str, str] = {}
    date_records: Dict[str, DailyRecord] = {}
    psc = PeriodicSamples()
    status_priority = {"2xx": 4, "4xx": 3, "5xx": 2, "3xx": 1}
    sliding_window_size = 1000
    sliding_window = ["~"] * sliding_window_size
    current_priority = -1
    daily_rec: DailyRecord = None
    prev_day = ""
    prev_digest = "~"
    prev_status = "~"
    total_records = unique_statuses = window_unique_statuses = 0

    query_url = f"{CDX_API_ENDPOINT}?fl=timestamp,statuscode,digest&url={quote_plus(url)}"
    for line in load_cdx_pages(query_url):
        raw_parts = line.decode().split()
        if len(raw_parts) < 3:
            continue
        ts, status, digest = raw_parts[0], raw_parts[1], raw_parts[2]
        psc(ts)
        day_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        status_bucket = f"{status[:1]}xx" if "200" <= status <= "599" else status
        if status_bucket == "-":
            status_bucket = digest_status.get(digest, "~")
        else:
            digest_status[digest] = status_bucket

        short_digest = digest[:8]
        if day_str != prev_day:
            if prev_day and daily_rec is not None:
                prev_digest = daily_rec.digest
                daily_rec.chaos = unique_statuses / total_records if total_records else 0.0
                daily_rec.chaosn = window_unique_statuses / min(sliding_window_size, total_records) if total_records else 0.0
                date_records[prev_day] = daily_rec

            daily_rec = DailyRecord(day_str)
            current_priority = -1
            prev_day = day_str

        if daily_rec is not None:
            daily_rec.incr(status_bucket)
            priority = status_priority.get(status_bucket, 0)
            if priority > current_priority:
                daily_rec.specimen = status_bucket
                daily_rec.datetime = ts
                daily_rec.digest = short_digest
                daily_rec.content = "Unchanged" if short_digest == prev_digest else "Changed"
                current_priority = priority

        window_pos = total_records % sliding_window_size
        total_records += 1
        if status_bucket != prev_status:
            prev_status = status_bucket
            unique_statuses += 1
            window_unique_statuses += 1
        if sliding_window[window_pos] != sliding_window[window_pos - sliding_window_size + 1]:
            window_unique_statuses -= 1
        sliding_window[window_pos] = status_bucket

    if prev_day and daily_rec is not None:
        daily_rec.chaos = unique_statuses / total_records if total_records else 0.0
        daily_rec.chaosn = window_unique_statuses / min(sliding_window_size, total_records) if total_records else 0.0
        date_records[prev_day] = daily_rec

    return date_records, psc.sample
