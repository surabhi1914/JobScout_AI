from __future__ import annotations

import html as ihtml
import urllib.parse as up
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re
import json
import pandas as pd
import requests
from bs4 import BeautifulSoup, FeatureNotFound
from typing import Any, Dict, List, Optional, Callable
import asyncio


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36 JobScout/0.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ============================================================
# HTTP helpers
# ============================================================

def request_html(url: str, params: Optional[dict] = None, timeout: int = 25) -> str:
    response = SESSION.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.text


def request_json(
    method: str,
    url: str,
    params: Optional[dict] = None,
    payload: Optional[dict] = None,
    timeout: int = 25,
) -> dict:
    method = method.upper()

    if method == "POST":
        response = SESSION.post(url, params=params, json=payload, timeout=timeout)
    else:
        response = SESSION.get(url, params=params, timeout=timeout)

    response.raise_for_status()
    return response.json()


# ============================================================
# Shared cleaning / normalization helpers
# ============================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_html(html_text: Any) -> str:
    """
    Converts raw HTML into readable plain text.
    Works for Greenhouse, Ashby, Lever, Workday descriptions, and HTML pages.
    """
    if html_text is None:
        return ""

    html_text = ihtml.unescape(str(html_text))
    soup = BeautifulSoup(html_text, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    return " ".join(text.split()).strip()


def first_available(data: Dict[str, Any], keys: List[str], default: Any = "") -> Any:
    """
    Return the first non-empty value from a dictionary.
    """
    if not isinstance(data, dict):
        return default

    for key in keys:
        value = data.get(key)
        if value not in [None, "", [], {}]:
            return value

    return default


def normalize_location(value: Any) -> str:
    """
    Convert different location formats into a readable string.
    """
    if not value:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        return str(
            first_available(value, ["name", "location", "city", "text", "displayName"])
        ).strip()

    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(
                    str(first_available(item, ["name", "location", "city", "text", "displayName"]))
                )

        return ", ".join([p.strip() for p in parts if p and str(p).strip()])

    return str(value).strip()


def abs_url(base: str, href: str) -> str:
    return up.urljoin(base, href or "")


def row_get(row: Any, key: str, default: Any = "") -> Any:
    """
    Safe getter for pandas Series rows.
    Handles missing columns and NaN values cleanly.
    """
    try:
        value = row.get(key, default)
    except AttributeError:
        value = default

    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    return value


# ============================================================
# Standard JobScout row helpers
# ============================================================

def make_job(
    company: str,
    title: str,
    location: str,
    job_url: str,
    description: str = "",
    ats_type: str = "",
    external_job_id: str = "",
    posted_date: Any = "",
    **extra_fields: Any,
) -> Dict[str, Any]:
    """
    Standard JobScout job dictionary.
    Keep column names stable because later scoring/dashboard code depends on them.
    """
    job = {
        "company": company,
        "title": clean_html(title),
        "location": normalize_location(location),
        "job_url": job_url or "",
        "description": clean_html(description),
        "ats_type": ats_type,
        "external_job_id": str(external_job_id or "").strip(),
        "posted_date": str(posted_date or "").strip(),
        "date_found": utc_now_iso(),
    }

    job.update(extra_fields)
    return job


def matches_query(job: Dict[str, Any], query: str = "") -> bool:
    """
    Basic keyword filter. Empty query keeps everything.
    """
    query = str(query or "").strip().lower()
    if not query:
        return True

    haystack = " ".join(
        [
            str(job.get("company", "")),
            str(job.get("title", "")),
            str(job.get("location", "")),
            str(job.get("description", "")),
            str(job.get("ats_type", "")),
        ]
    ).lower()

    return query in haystack


def dedupe_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    output = []

    for job in jobs:
        key = (
            str(job.get("company", "")).lower(),
            str(job.get("external_job_id") or job.get("job_url") or job.get("title", "")).lower(),
            str(job.get("location", "")).lower(),
        )

        if key in seen:
            continue

        seen.add(key)
        output.append(job)

    return output


def summarize_job_quality(jobs_df: pd.DataFrame) -> pd.DataFrame:
    """
    Small helper for notebook inspection.
    """
    if jobs_df.empty:
        return pd.DataFrame()

    return jobs_df.groupby("ats_type").agg(
        job_count=("title", "count"),
        descriptions_present=("description", lambda x: (x.fillna("").str.len() > 0).sum()),
        posted_dates_present=("posted_date", lambda x: (x.fillna("") != "").sum()),
    ).reset_index()

def extract_json_array_after_key(text: str, key: str) -> Optional[str]:
    """
    Extracts a JSON array after a key like "positions": [...]
    Works with normal JSON, HTML-escaped JSON, and escaped script JSON.
    """
    if not text:
        return None

    text = ihtml.unescape(text)
    text = text.replace("\\u0022", '"')
    text = text.replace('\\"', '"')

    key_pattern = f'"{key}"'
    key_index = text.find(key_pattern)

    if key_index == -1:
        # fallback for loose HTML/search-result text
        match = re.search(
            rf'"{re.escape(key)}"\s*:\s*(\[.*?\])\s*,\s*"debug"',
            text,
            flags=re.DOTALL,
        )
        if match:
            return match.group(1)
        return None

    array_start = text.find("[", key_index)

    if array_start == -1:
        return None

    bracket_count = 0
    in_string = False
    escape = False

    for i in range(array_start, len(text)):
        char = text[i]

        if escape:
            escape = False
            continue

        if char == "\\":
            escape = True
            continue

        if char == '"':
            in_string = not in_string

        if not in_string:
            if char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1

                if bracket_count == 0:
                    return text[array_start : i + 1]

    return None


def extract_jsonld_jobs(
    html: str,
    company: str,
    base_url: str,
    ats_type: str,
    query: str = "",
) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: List[Dict[str, Any]] = []

    for script in soup.find_all("script", {"type": "application/ld+json"}):
        raw = script.string or script.get_text()

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        candidates = data if isinstance(data, list) else [data]
        queue = list(candidates)

        while queue:
            obj = queue.pop(0)

            if isinstance(obj, list):
                queue.extend(obj)
                continue

            if not isinstance(obj, dict):
                continue

            if isinstance(obj.get("@graph"), list):
                queue.extend(obj["@graph"])

            if obj.get("@type") != "JobPosting":
                continue

            loc = obj.get("jobLocation") or ""
            location_text = ""

            if isinstance(loc, list):
                parts = []

                for location_obj in loc:
                    if isinstance(location_obj, dict):
                        addr = location_obj.get("address") or {}

                        parts.append(
                            ", ".join(
                                filter(
                                    None,
                                    [
                                        addr.get("addressLocality", ""),
                                        addr.get("addressRegion", ""),
                                        addr.get("addressCountry", ""),
                                    ],
                                )
                            )
                        )

                location_text = "; ".join([p for p in parts if p])

            elif isinstance(loc, dict):
                addr = loc.get("address") or {}

                location_text = ", ".join(
                    filter(
                        None,
                        [
                            addr.get("addressLocality", ""),
                            addr.get("addressRegion", ""),
                            addr.get("addressCountry", ""),
                        ],
                    )
                )

            else:
                location_text = str(loc)

            identifier = obj.get("identifier", "")

            if isinstance(identifier, dict):
                identifier = first_available(identifier, ["value", "name"])

            job = make_job(
                company=company,
                title=obj.get("title", ""),
                location=location_text,
                job_url=abs_url(base_url, obj.get("url") or base_url),
                description=obj.get("description", ""),
                ats_type=ats_type,
                external_job_id=identifier,
                posted_date=obj.get("datePosted", ""),
            )

            if matches_query(job, query):
                jobs.append(job)

    return dedupe_jobs(jobs)


def parse_links_as_jobs(
    html: str,
    company: str,
    base_url: str,
    link_patterns: List[str],
    ats_type: str,
    query: str = "",
) -> List[Dict[str, Any]]:
    """
    Generic fallback for HTML-heavy career pages.
    This is less reliable than ATS APIs but useful for custom/company pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs: List[Dict[str, Any]] = []

    bad_titles = {
        "apply",
        "apply now",
        "view role",
        "view job",
        "view jobs",
        "learn more",
        "search",
        "saved jobs",
        "job search",
        "home",
        "careers",
        "jobs",
    }

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        full_url = abs_url(base_url, href)

        if not any(pattern in href or pattern in full_url for pattern in link_patterns):
            continue

        title = clean_html(a.get_text(" "))

        parent = a.find_parent(["li", "article", "section", "div"])
        parent_text = clean_html(parent.get_text(" ")) if parent else title

        if (not title or title.lower() in bad_titles) and parent_text:
            title = parent_text.split("  ")[0].strip()

        if not title or len(title) < 3 or title.lower() in bad_titles:
            continue

        if len(title) > 180:
            title = title[:180].strip()

        id_match = re.search(r"([A-Za-z]{1,5}\d{4,}|\d{4,})", full_url)
        external_id = id_match.group(1) if id_match else full_url

        job = make_job(
            company=company,
            title=title,
            location="",
            job_url=full_url,
            description=parent_text,
            ats_type=ats_type,
            external_job_id=external_id,
            posted_date="",
        )

        if matches_query(job, query):
            jobs.append(job)

    return dedupe_jobs(jobs)

def add_query_params(url: str, params: Dict[str, Any]) -> str:
    parsed = up.urlparse(url)
    existing = dict(up.parse_qsl(parsed.query))

    for key, value in params.items():
        if value not in [None, ""]:
            existing[key] = str(value)

    new_query = up.urlencode(existing)
    return up.urlunparse(parsed._replace(query=new_query))


def run_async(coro):
    """
    Run async Playwright code safely from Jupyter/Windows.

    Why:
    - Windows notebooks often use an asyncio loop that cannot launch subprocesses.
    - Playwright needs subprocess support to start Chromium.
    - So we run Playwright inside a separate thread with a ProactorEventLoop.
    """
    import sys
    import asyncio
    import threading
    import traceback

    result = {
        "value": None,
        "error": None,
        "traceback": None,
    }

    def runner():
        if sys.platform.startswith("win") and hasattr(asyncio, "ProactorEventLoop"):
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)

        try:
            result["value"] = loop.run_until_complete(coro)

        except Exception as exc:
            result["error"] = exc
            result["traceback"] = traceback.format_exc()

        finally:
            try:
                pending = asyncio.all_tasks(loop)

                for task in pending:
                    task.cancel()

                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass

            loop.close()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if result["error"] is not None:
        raise RuntimeError(result["traceback"]) from result["error"]

    return result["value"]


async def fetch_rendered_html_async(
    url: str,
    wait_ms: int = 6000,
    timeout_ms: int = 45000,
    max_scrolls: int = 4,
) -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1000},
        )

        page = await context.new_page()

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )

        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass

        await page.wait_for_timeout(wait_ms)

        for _ in range(max_scrolls):
            await page.mouse.wheel(0, 1800)
            await page.wait_for_timeout(1200)

        html = await page.content()

        await context.close()
        await browser.close()

        return html


def fetch_rendered_html(
    url: str,
    wait_ms: int = 6000,
    timeout_ms: int = 45000,
    max_scrolls: int = 4,
) -> str:
    return run_async(
        fetch_rendered_html_async(
            url=url,
            wait_ms=wait_ms,
            timeout_ms=timeout_ms,
            max_scrolls=max_scrolls,
        )
    )


def fetch_browser_link_jobs(
    company: str,
    career_url: str,
    ats_type: str,
    query: str = "",
    query_param: str = "q",
    link_patterns: Optional[List[str]] = None,
    extra_params: Optional[Dict[str, Any]] = None,
    wait_ms: int = 7000,
    max_scrolls: int = 5,
) -> List[Dict[str, Any]]:
    """
    Browser-rendered fallback for JS-heavy career pages.
    """
    if not career_url:
        return []

    params = extra_params.copy() if extra_params else {}

    if query_param and query:
        params[query_param] = query

    url = add_query_params(career_url, params)

    try:
        html = fetch_rendered_html(
            url=url,
            wait_ms=wait_ms,
            max_scrolls=max_scrolls,
        )
    except Exception as exc:
        print(f"{company} browser fetch failed:")
        print(repr(exc))
        return []

    jobs = extract_embedded_json_jobs(
        html=html,
        company=company,
        base_url=career_url,
        ats_type=ats_type,
        query=query,
    )

    if jobs:
        return dedupe_jobs(jobs)

    jobs = parse_links_as_jobs(
        html=html,
        company=company,
        base_url=career_url,
        link_patterns=link_patterns or ["/job/", "/jobs/", "/careers/"],
        ats_type=ats_type,
        query=query,
    )

    return dedupe_jobs(jobs)

def parse_detail_page_as_job(
    company: str,
    url: str,
    ats_type: str,
    query: str = "",
) -> Optional[Dict[str, Any]]:
    try:
        html = request_html(url, timeout=30)
    except Exception:
        return None

    jsonld_jobs = extract_jsonld_jobs(html, company, url, ats_type, query=query)

    if jsonld_jobs:
        return jsonld_jobs[0]

    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.find("h1")
    title = clean_html(h1.get_text(" ")) if h1 else ""

    if not title:
        title_tag = soup.find("title")
        title = clean_html(title_tag.get_text(" ")) if title_tag else ""

    main = soup.find("main") or soup.body
    description = clean_html(main.get_text(" ")) if main else ""

    if not title:
        return None

    id_match = re.search(r"([A-Za-z]{1,5}\d{4,}|\d{4,})", url)
    external_id = id_match.group(1) if id_match else url

    job = make_job(
        company=company,
        title=title,
        location="",
        job_url=url,
        description=description,
        ats_type=ats_type,
        external_job_id=external_id,
        posted_date="",
    )

    if not matches_query(job, query):
        return None

    return job


def collect_sitemap_urls(
    sitemap_url: str,
    include_substring: str,
    max_sitemaps: int = 40,
    max_urls: int = 1000,
) -> List[str]:
    queue = [sitemap_url]
    visited = set()
    matched_urls: List[str] = []

    while queue and len(visited) < max_sitemaps and len(matched_urls) < max_urls:
        url = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)

        try:
            xml = request_html(url, timeout=40)
        except Exception:
            continue

        try:
            soup = BeautifulSoup(xml, "xml")
        except FeatureNotFound:
            soup = BeautifulSoup(xml, "html.parser")

        loc_tags = soup.find_all("loc")

        # Fallback if XML parser is unavailable or loc tags are not parsed cleanly.
        if not loc_tags:
            loc_values = re.findall(r"<loc>(.*?)</loc>", xml, flags=re.DOTALL)
        else:
            loc_values = [tag.get_text() for tag in loc_tags]

        for loc_text in loc_values:
            loc_url = clean_html(loc_text)

            if not loc_url:
                continue

            if loc_url.endswith(".xml") and loc_url not in visited:
                queue.append(loc_url)
                continue

            if include_substring in loc_url:
                matched_urls.append(loc_url)

            if len(matched_urls) >= max_urls:
                break

    return matched_urls


def _find_first_jobs_list(obj: Any) -> List[dict]:
    if isinstance(obj, dict):
        for key in ("jobs", "jobResults", "results", "data"):
            val = obj.get(key)

            if isinstance(val, list) and val and isinstance(val[0], dict):
                return val

        for val in obj.values():
            found = _find_first_jobs_list(val)

            if found:
                return found

    elif isinstance(obj, list):
        for val in obj:
            found = _find_first_jobs_list(val)

            if found:
                return found

    return []

def _try_fetch_variants(
    fetch_calls: List[tuple[str, Callable[[], List[Dict[str, Any]]]]]
) -> List[Dict[str, Any]]:
    errors = []

    for label, fn in fetch_calls:
        try:
            jobs = fn()

            if jobs:
                return jobs

        except Exception as exc:
            errors.append(f"{label}: {exc}")

    if errors:
        print("Tried variants but none returned jobs:")

        for error in errors[:5]:
            print(" -", error)

    return []

def fetch_eightfold_embedded_jobs(
    company: str,
    career_url: str,
    query: str = "",
    ats_type: str = "eightfold_embedded",
) -> List[Dict[str, Any]]:
    """
    Generic Eightfold-style embedded jobs fetcher.

    Works for pages that embed a large JSON object containing:
        "positions": [...]
    """
    if not career_url:
        return []

    try:
        html = request_html(
            career_url,
            params={
                "query": query or "",
                "sort_by": "timestamp",
            },
            timeout=45,
        )
    except Exception as exc:
        print(f"{company} Eightfold page request failed: {exc}")
        return []

    positions_json = extract_json_array_after_key(html, "positions")

    if not positions_json:
        print(f"Could not find embedded positions data for {company}.")
        return []

    try:
        positions = json.loads(positions_json)
    except Exception as exc:
        print(f"Could not parse embedded positions JSON for {company}: {exc}")
        return []

    jobs: List[Dict[str, Any]] = []

    for item in positions:
        created_ts = first_available(item, ["t_create", "createdAt", "created_at"])
        updated_ts = first_available(item, ["t_update", "updatedAt", "updated_at"])

        posted_date = ""

        if created_ts:
            try:
                posted_date = datetime.fromtimestamp(int(created_ts), timezone.utc).isoformat()
            except Exception:
                posted_date = str(created_ts)

        updated_date = ""

        if updated_ts:
            try:
                updated_date = datetime.fromtimestamp(int(updated_ts), timezone.utc).isoformat()
            except Exception:
                updated_date = str(updated_ts)

        job_url = first_available(
            item,
            [
                "canonicalPositionUrl",
                "positionUrl",
                "position_url",
                "jobUrl",
                "url",
            ],
        )

        job = make_job(
            company=company,
            title=first_available(item, ["posting_name", "name", "title"]),
            location=normalize_location(first_available(item, ["locations", "location"])),
            job_url=abs_url(career_url, job_url),
            description=first_available(
                item,
                ["job_description", "description", "descriptionHtml", "descriptionPlain"],
            ),
            ats_type=ats_type,
            external_job_id=str(first_available(item, ["ats_job_id", "id", "jobId"])),
            posted_date=posted_date,
            updated_date=updated_date,
            department=first_available(item, ["department", "team"]),
            business_unit=first_available(item, ["business_unit", "businessUnit"]),
            work_location_option=first_available(item, ["work_location_option", "workLocationOption"]),
        )

        if matches_query(job, query):
            jobs.append(job)

    return dedupe_jobs(jobs)

def extract_job_like_objects(obj: Any) -> List[Dict[str, Any]]:
    """
    Recursively searches messy embedded JSON for job-like dictionaries.
    Helpful for Workday/Phenom/JS-heavy career pages.
    """
    found: List[Dict[str, Any]] = []

    if isinstance(obj, dict):
        keys = set(obj.keys())

        title_keys = {"title", "jobTitle", "job_title", "name", "postingTitle"}
        url_keys = {"url", "jobUrl", "job_url", "applyUrl", "externalApplyUrl", "canonicalPositionUrl"}

        has_title = bool(keys & title_keys)
        has_url = bool(keys & url_keys)

        if has_title and has_url:
            found.append(obj)

        for value in obj.values():
            found.extend(extract_job_like_objects(value))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(extract_job_like_objects(item))

    return found


def extract_embedded_json_jobs(
    html: str,
    company: str,
    base_url: str,
    ats_type: str,
    query: str = "",
) -> List[Dict[str, Any]]:
    """
    Finds job-like objects inside script JSON blocks.
    This is a generic fallback for JS-heavy pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs: List[Dict[str, Any]] = []

    scripts = soup.find_all("script")

    for script in scripts:
        raw = script.string or script.get_text()

        if not raw:
            continue

        raw = raw.strip()

        # Try direct JSON first.
        candidates = []

        try:
            candidates.append(json.loads(raw))
        except Exception:
            pass

        # Try extracting {...} blobs from scripts.
        if not candidates:
            for match in re.finditer(r"(\{.*?\})", raw, flags=re.DOTALL):
                blob = match.group(1)

                if len(blob) < 200:
                    continue

                try:
                    candidates.append(json.loads(blob))
                except Exception:
                    continue

        for candidate in candidates:
            job_objects = extract_job_like_objects(candidate)

            for item in job_objects:
                title = first_available(
                    item,
                    ["title", "jobTitle", "job_title", "name", "postingTitle"],
                )

                job_url = first_available(
                    item,
                    ["url", "jobUrl", "job_url", "applyUrl", "externalApplyUrl", "canonicalPositionUrl"],
                )

                location = normalize_location(
                    first_available(
                        item,
                        ["location", "locations", "jobLocation", "primaryLocation"],
                    )
                )

                description = first_available(
                    item,
                    ["description", "jobDescription", "descriptionHtml", "descriptionPlain"],
                )

                posted_date = first_available(
                    item,
                    ["postedDate", "datePosted", "posted_date", "createdAt", "updatedAt"],
                )

                external_id = first_available(
                    item,
                    ["id", "jobId", "job_id", "reqId", "requisitionId", "display_job_id"],
                    default=job_url,
                )

                job = make_job(
                    company=company,
                    title=title,
                    location=location,
                    job_url=abs_url(base_url, str(job_url)),
                    description=description,
                    ats_type=ats_type,
                    external_job_id=external_id,
                    posted_date=posted_date,
                )

                if matches_query(job, query):
                    jobs.append(job)

    return dedupe_jobs(jobs)