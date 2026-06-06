from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import pandas as pd


# ============================================================
# Date helpers
# ============================================================

def parse_posted_date(value: Any) -> Optional[datetime]:
    """
    Converts messy ATS posting dates into UTC datetime objects.
    Handles:
    - ISO dates
    - Unix timestamps
    - Workday strings like "Posted Today", "Posted Yesterday", "Posted 5 Days Ago"
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    value = str(value).strip()
    if not value:
        return None

    value_lower = value.lower()
    now = datetime.now(timezone.utc)

    if "posted today" in value_lower or value_lower in {"today", "just posted"}:
        return now

    if "posted yesterday" in value_lower or value_lower == "yesterday":
        return now - timedelta(days=1)

    match = re.search(r"(?:posted\s+)?(\d+)\s+(minute|hour|day|week|month)s?\s+ago", value_lower)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)

        if unit == "minute":
            return now - timedelta(minutes=amount)
        if unit == "hour":
            return now - timedelta(hours=amount)
        if unit == "day":
            return now - timedelta(days=amount)
        if unit == "week":
            return now - timedelta(weeks=amount)
        return now - timedelta(days=amount * 30)

    if "30+ days" in value_lower:
        return now - timedelta(days=30)

    if value.isdigit():
        timestamp = int(value)

        # milliseconds vs seconds
        if timestamp > 10**12:
            timestamp = timestamp / 1000

        try:
            return datetime.fromtimestamp(timestamp, timezone.utc)
        except Exception:
            return None

    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None

    return parsed.to_pydatetime()


def classify_freshness(posted_datetime: Optional[datetime], hours: int = 24) -> str:
    """
    Labels jobs as:
    - fresh: posted within last N hours
    - old: older than N hours
    - unknown: no parseable posted date
    """
    if posted_datetime is None:
        return "unknown"

    try:
        if pd.isna(posted_datetime):
            return "unknown"
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    age = now - posted_datetime

    if age <= timedelta(hours=hours):
        return "fresh"

    return "old"


def add_freshness_columns(jobs_df: pd.DataFrame, hours: int = 24) -> pd.DataFrame:
    """
    Adds posted_datetime and freshness_status columns.
    """
    jobs_df = jobs_df.copy()

    if jobs_df.empty:
        jobs_df["posted_datetime"] = pd.Series(dtype="object")
        jobs_df["freshness_status"] = pd.Series(dtype="object")
        return jobs_df

    if "posted_date" not in jobs_df.columns:
        jobs_df["posted_date"] = ""

    jobs_df["posted_datetime"] = jobs_df["posted_date"].apply(parse_posted_date)
    jobs_df["freshness_status"] = jobs_df["posted_datetime"].apply(
        lambda x: classify_freshness(x, hours=hours)
    )

    return jobs_df


def filter_recent_jobs(jobs_df: pd.DataFrame, hours: int = 24, keep_unknown: bool = True) -> pd.DataFrame:
    """
    Keeps jobs marked fresh. Optionally keeps unknown dates because some ATS pages hide posted dates.
    """
    jobs_df = add_freshness_columns(jobs_df, hours=hours)

    allowed = ["fresh"]
    if keep_unknown:
        allowed.append("unknown")

    return jobs_df[jobs_df["freshness_status"].isin(allowed)].copy()
