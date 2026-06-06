# src/job_fetchers.py

from __future__ import annotations

# ============================================================
#Importing Libraries
# ============================================================

import json
import re
import html as ihtml
import urllib3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

import pandas as pd
import requests
from bs4 import BeautifulSoup, FeatureNotFound


from .shared_helpers import (
    abs_url,
    clean_html,
    dedupe_jobs,
    fetch_rendered_html,
    first_available,
    make_job,
    matches_query,
    normalize_location,
    request_html,
    request_json,
    row_get,
    extract_json_array_after_key,
    extract_jsonld_jobs,
    parse_links_as_jobs,
    parse_detail_page_as_job,
    collect_sitemap_urls,
    _find_first_jobs_list,
    _try_fetch_variants,
    fetch_eightfold_embedded_jobs,
    extract_job_like_objects,
    extract_embedded_json_jobs,
    fetch_browser_link_jobs,
)


# ============================================================
# Generic ATS fetchers
# ============================================================

def fetch_greenhouse(company: str, ats_slug: str, query: str = "") -> List[Dict[str, Any]]:
    """
    Generic Greenhouse fetcher.

    First tries the official Greenhouse board API.
    If that fails or returns 0 jobs, falls back to the newer job-boards.greenhouse.io page.
    """
    if not ats_slug:
        return []

    url = f"https://boards-api.greenhouse.io/v1/boards/{ats_slug}/jobs"

    try:
        data = request_json(
            "GET",
            url,
            params={"content": "true"},
        )
        rows = data.get("jobs", [])
    except requests.exceptions.HTTPError:
        return fetch_greenhouse_new_board_fallback(
            company=company,
            ats_slug=ats_slug,
            query=query,
        )

    if not rows:
        fallback_jobs = fetch_greenhouse_new_board_fallback(
            company=company,
            ats_slug=ats_slug,
            query=query,
        )
        if fallback_jobs:
            return fallback_jobs

    jobs: List[Dict[str, Any]] = []

    for item in rows:
        location = normalize_location(first_available(item, ["location", "offices"]))
        raw_description = first_available(item, ["content", "description"])

        posted_date = first_available(
            item,
            ["first_published", "published_at", "updated_at", "created_at"],
        )

        job = make_job(
            company=company,
            title=first_available(item, ["title"]),
            location=location,
            job_url=first_available(item, ["absolute_url"]),
            description=raw_description,
            ats_type="greenhouse",
            external_job_id=first_available(item, ["id"]),
            posted_date=posted_date,
            description_raw=raw_description,
        )

        if matches_query(job, query):
            jobs.append(job)

    return dedupe_jobs(jobs)


def fetch_greenhouse_new_board_fallback(
    company: str,
    ats_slug: str,
    query: str = "",
) -> List[Dict[str, Any]]:
    """
    Fallback for newer Greenhouse-hosted boards:
        https://job-boards.greenhouse.io/{ats_slug}
    """
    if not ats_slug:
        return []

    board_url = f"https://job-boards.greenhouse.io/{ats_slug}"

    try:
        html = request_html(board_url)
    except Exception:
        return []

    jobs = parse_links_as_jobs(
        html=html,
        company=company,
        base_url=board_url,
        link_patterns=[f"/{ats_slug}/jobs/", "/jobs/"],
        ats_type="greenhouse_new_board",
        query=query,
    )
    return dedupe_jobs(jobs)

def fetch_ashby(company: str, ats_slug: str, query: str = "") -> List[Dict[str, Any]]:
    """
    Generic Ashby fetcher.

    Example board:
        https://jobs.ashbyhq.com/companyname

    ats_slug:
        companyname
    """
    if not ats_slug:
        return []

    url = f"https://api.ashbyhq.com/posting-api/job-board/{ats_slug}"

    data = request_json(
        "GET",
        url,
        params={"includeCompensation": "true"},
    )

    jobs: List[Dict[str, Any]] = []

    for item in data.get("jobs", []):
        location = normalize_location(
            first_available(
                item,
                ["location", "locations", "locationName", "address", "office", "offices"],
            )
        )

        description = first_available(
            item,
            ["descriptionHtml", "descriptionPlain", "description", "jobDescription"],
        )

        posted_date = first_available(
            item,
            ["publishedAt", "publishedDate", "postedDate", "createdAt", "updatedAt"],
        )

        job = make_job(
            company=company,
            title=first_available(item, ["title", "name"]),
            location=location,
            job_url=first_available(item, ["jobUrl", "applyUrl", "url"]),
            description=description,
            ats_type="ashby",
            external_job_id=first_available(item, ["id", "jobId"]),
            posted_date=posted_date,
        )

        if matches_query(job, query):
            jobs.append(job)

    return dedupe_jobs(jobs)


def extract_lever_description(job: Dict[str, Any]) -> str:
    description_parts = [
        first_available(job, ["descriptionPlain", "description"]),
        first_available(job, ["additionalPlain", "additional"]),
    ]

    for section in job.get("lists", []):
        section_title = section.get("text", "")
        section_content = clean_html(section.get("content", ""))

        if section_title or section_content:
            description_parts.append(f"{section_title}: {section_content}")

    return " ".join([part for part in description_parts if part])


def fetch_lever(company: str, ats_slug: str, query: str = "") -> List[Dict[str, Any]]:
    """
    Generic Lever fetcher.

    Example board:
        https://jobs.lever.co/palantir

    ats_slug:
        palantir
    """
    if not ats_slug:
        return []

    url = f"https://api.lever.co/v0/postings/{ats_slug}"

    data = request_json(
        "GET",
        url,
        params={"mode": "json"},
    )

    jobs: List[Dict[str, Any]] = []

    for item in data:
        categories = item.get("categories", {}) or {}

        location_parts = [
            first_available(categories, ["location"]),
            first_available(item, ["country"]),
            first_available(item, ["workplaceType"]),
        ]

        location = " ".join(str(part) for part in location_parts if part)
        description = extract_lever_description(item)

        posted_date = first_available(
            item,
            ["createdAt", "updatedAt", "created_at", "updated_at"],
        )

        job = make_job(
            company=company,
            title=first_available(item, ["text", "title"]),
            location=location,
            job_url=first_available(item, ["hostedUrl", "applyUrl", "url"]),
            description=description,
            ats_type="lever",
            external_job_id=first_available(item, ["id"]),
            posted_date=posted_date,
        )

        if matches_query(job, query):
            jobs.append(job)

    return dedupe_jobs(jobs)

def workday_request_json(
    method: str,
    url: str,
    base_url: str,
    site: str,
    payload: Optional[dict] = None,
    timeout: int = 35,
) -> dict:
    """
    Workday is picky. It often behaves better when Origin, Referer,
    Accept, and Content-Type headers look browser-like.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": base_url,
        "Referer": f"{base_url}/{site}",
    }

    method = method.upper()

    if method == "POST":
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    else:
        response = requests.get(url, headers=headers, timeout=timeout)

    response.raise_for_status()
    return response.json()

def _workday_public_url(base_url: str, site: str, external_path: str) -> str:
    if not external_path:
        return ""

    if external_path.startswith("http"):
        return external_path

    if external_path.startswith(f"/{site}/"):
        return f"{base_url}{external_path}"

    if external_path.startswith("/"):
        return f"{base_url}/{site}{external_path}"

    return f"{base_url}/{site}/{external_path}"


def fetch_workday_detail(
    base_url: str,
    tenant: str,
    site: str,
    external_path: str,
) -> Dict[str, Any]:
    """
    Fetches full Workday detail using externalPath from the list API.
    """
    if not external_path:
        return {}

    if not external_path.startswith("/"):
        external_path = "/" + external_path

    detail_url = f"{base_url}/wday/cxs/{tenant}/{site}{external_path}"

    try:
        return workday_request_json(
            "GET",
            detail_url,
            base_url=base_url,
            site=site,
        )
    except Exception:
        return {}



def fetch_workday(
    company: str,
    tenant: str,
    site: str,
    server: str = "",
    host: str = "",
    career_url: str = "",
    query: str = "",
    limit: int = 20,
    max_pages: int = 1,
    sleep_seconds: float = 0.35,
) -> List[Dict[str, Any]]:
    """
    Generic Workday fetcher.

    Option A:
        tenant="accenture", server="wd103", site="AccentureCareers"

    Option B:
        host="accenture.wd103.myworkdayjobs.com", tenant="accenture", site="AccentureCareers"
    """
    if not tenant or not site:
        return []

    if host:
        base_url = f"https://{host}".rstrip("/")
    else:
        if not server:
            return []
        base_url = f"https://{tenant}.{server}.myworkdayjobs.com"

    endpoint = f"{base_url}/wday/cxs/{tenant}/{site}/jobs"

    jobs: List[Dict[str, Any]] = []

    for page in range(max_pages):
        payload = {
            "appliedFacets": {},
            "limit": limit,
            "offset": page * limit,
            "searchText": query or "",
        }

        try:
            data = workday_request_json(
                "POST",
                        endpoint,
                        base_url=base_url,
                        site=site,
                        payload=payload,
                    )
        except requests.exceptions.HTTPError as exc:
            print(f"{company} Workday API failed, trying HTML fallback: {exc}")

            fallback_url = career_url or f"{base_url}/{site}/"

            return fetch_workday_html_fallback(
                company=company,
                career_url=fallback_url,
                query=query,
            )
        postings = data.get("jobPostings", [])

        if not postings:
            break

        for item in postings:
            external_path = str(first_available(item, ["externalPath"]))
            job_url = _workday_public_url(base_url, site, external_path)

            title = first_available(item, ["title"])

            location = normalize_location(
                first_available(item, ["locationsText", "locations", "location"])
            )

            posted_date = first_available(
                item,
                ["postedOn", "postedDate", "startDate", "createdAt", "updatedAt"],
            )

            remote_type = first_available(item, ["remoteType"])

            bullet_fields = item.get("bulletFields", [])
            requisition_id = ""

            if isinstance(bullet_fields, list) and bullet_fields:
                requisition_id = str(bullet_fields[0])

            detail_data = fetch_workday_detail(base_url, tenant, site, external_path)
            job_info = detail_data.get("jobPostingInfo", {}) or detail_data

            raw_description = first_available(
                job_info,
                ["jobDescription", "description", "jobDescriptionText"],
            )

            title = first_available(job_info, ["title"], default=title)

            location = normalize_location(
                first_available(
                    job_info,
                    ["location", "locations", "locationsText"],
                    default=location,
                )
            )

            posted_date = first_available(
                job_info,
                ["postedOn", "postedDate", "startDate"],
                default=posted_date,
            )

            requisition_id = first_available(
                job_info,
                ["jobReqId", "jobRequisitionId", "requisitionId"],
                default=requisition_id,
            )

            job = make_job(
                company=company,
                title=title,
                location=location,
                job_url=job_url,
                description=raw_description,
                ats_type="workday",
                external_job_id=str(requisition_id or external_path),
                posted_date=posted_date,
                description_raw=raw_description,
                remote_type=remote_type,
            )

            if matches_query(job, query):
                jobs.append(job)

        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)

def fetch_workday_html_fallback(
    company: str,
    career_url: str,
    query: str = "",
) -> List[Dict[str, Any]]:
    """
    Fallback when Workday CXS API returns 400/422.
    First tries normal HTML. If that fails, tries browser-rendered HTML.
    """
    if not career_url:
        return []

    try:
        html = request_html(career_url, timeout=35)

        jobs = extract_embedded_json_jobs(
            html=html,
            company=company,
            base_url=career_url,
            ats_type="workday_html_fallback",
            query=query,
        )

        if jobs:
            return jobs

        jobs = parse_links_as_jobs(
            html=html,
            company=company,
            base_url=career_url,
            link_patterns=[
                "/job/",
                "/jobs/",
                "JobDetail",
                "jobdetail",
            ],
            ats_type="workday_html_fallback",
            query=query,
        )

        if jobs:
            return dedupe_jobs(jobs)

    except Exception as exc:
        print(f"{company} normal Workday fallback failed: {exc}")

    print(f"{company} trying browser-rendered Workday fallback...")

    return fetch_browser_link_jobs(
        company=company,
        career_url=career_url,
        ats_type="workday_browser_fallback",
        query=query,
        query_param="q",
        link_patterns=[
            "/job/",
            "/jobs/",
            "JobDetail",
            "jobdetail",
        ],
        wait_ms=9000,
        max_scrolls=5,
    )

def fetch_phenom_jobs(
    company: str,
    root_url: str,
    query: str = "",
    max_pages: int = 3,
    size: int = 50,
    sleep_seconds: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Generic Phenom-style widget fallback.
    Useful for BCG-style enterprise career sites.
    """
    jobs: List[Dict[str, Any]] = []
    endpoint = root_url.rstrip("/") + "/widgets"

    for page in range(max_pages):
        offset = page * size

        params = {
            "lang": "en_us",
            "deviceType": "desktop",
            "pageName": "search-results",
            "ddoKey": "refineSearch",
            "from": offset,
            "size": size,
            "jobs": "true",
            "counts": "true",
            "keyword": query or "",
            "keywords": query or "",
        }

        try:
            data = request_json("GET", endpoint, params=params)
        except Exception:
            break

        rows = _find_first_jobs_list(data)

        if not rows:
            break

        for item in rows:
            title = first_available(item, ["title", "jobTitle", "name"])

            location = normalize_location(
                first_available(item, ["location", "jobLocation", "locations"])
                or ", ".join(
                    filter(
                        None,
                        [
                            str(item.get("city", "")),
                            str(item.get("state", "")),
                            str(item.get("country", "")),
                        ],
                    )
                )
            )

            job_url = first_available(
                item,
                ["jobUrl", "url", "applyUrl", "externalApplyUrl"],
            )

            job_url = abs_url(root_url, job_url) if job_url else ""

            job = make_job(
                company=company,
                title=title,
                location=location,
                job_url=job_url,
                description=first_available(item, ["description", "jobDescription"]),
                ats_type="phenom_widget",
                external_job_id=first_available(item, ["jobId", "reqId", "id"]),
                posted_date=first_available(item, ["postedDate", "datePosted", "updatedDate"]),
            )

            if matches_query(job, query):
                jobs.append(job)

        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)

# def fetch_netflix_jobs(
#     query: str = "",
#     career_url: str = "https://explore.jobs.netflix.net/careers",
#     **kwargs,
# ) -> List[Dict[str, Any]]:
#     return fetch_eightfold_embedded_jobs(
#         company="Netflix",
#         career_url=career_url,
#         query=query,
#         ats_type="custom_netflix",
#     )

def fetch_netflix_jobs(
    query: str = "",
    career_url: str = "https://explore.jobs.netflix.net/careers",
) -> List[Dict[str, Any]]:
    html = request_html(career_url, params={"query": query or "", "sort_by": "new"})
    positions_json = extract_json_array_after_key(html, "positions")

    if not positions_json:
        print("Could not find Netflix positions data.")
        return []

    try:
        positions = json.loads(positions_json)
    except Exception:
        return []

    jobs: List[Dict[str, Any]] = []

    for item in positions:
        created_ts = item.get("t_create")
        updated_ts = item.get("t_update")

        posted_date = ""

        if created_ts:
            try:
                posted_date = datetime.fromtimestamp(int(created_ts), timezone.utc).isoformat()
            except Exception:
                posted_date = ""

        updated_date = ""

        if updated_ts:
            try:
                updated_date = datetime.fromtimestamp(int(updated_ts), timezone.utc).isoformat()
            except Exception:
                updated_date = ""

        job = make_job(
            company="Netflix",
            title=item.get("posting_name") or item.get("name", ""),
            location=normalize_location(item.get("locations") or item.get("location")),
            job_url=item.get("canonicalPositionUrl", ""),
            description=item.get("job_description", ""),
            ats_type="custom_netflix",
            external_job_id=str(item.get("ats_job_id") or item.get("id", "")),
            posted_date=posted_date,
            updated_date=updated_date,
            department=item.get("department", ""),
            business_unit=item.get("business_unit", ""),
            work_location_option=item.get("work_location_option", ""),
        )

        if matches_query(job, query):
            jobs.append(job)

    return dedupe_jobs(jobs)


def fetch_google_jobs(
    query: str = "",
    career_url: str = "https://www.google.com/about/careers/applications/jobs/results/",
    max_pages: int = 3,
    sleep_seconds: float = 0.3,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        html = request_html(career_url, params={"q": query or "", "page": page})

        page_jobs = extract_jsonld_jobs(
            html=html,
            company="Google",
            base_url=career_url,
            ats_type="google_html",
            query=query,
        )

        page_jobs += parse_links_as_jobs(
            html=html,
            company="Google",
            base_url=career_url,
            link_patterns=["/about/careers/applications/jobs/results/"],
            ats_type="google_html",
            query=query,
        )

        jobs.extend(page_jobs)
        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)


def fetch_microsoft_jobs(
    query: str = "",
    career_url: str = "https://jobs.careers.microsoft.com/global/en/search",
    **kwargs,
) -> List[Dict[str, Any]]:
    return fetch_browser_link_jobs(
        company="Microsoft",
        career_url=career_url,
        ats_type="custom_microsoft",
        query=query,
        query_param="q",
        link_patterns=[
            "/global/en/job/",
            "/careers/job/",
            "/us/en/job/",
            "/job/",
        ],
        wait_ms=9000,
        max_scrolls=5,
    )

def fetch_meta_jobs(
    query: str = "",
    career_url: str = "https://www.metacareers.com/jobs",
    **kwargs,
) -> List[Dict[str, Any]]:
    return fetch_browser_link_jobs(
        company="Meta",
        career_url=career_url,
        ats_type="custom_meta",
        query=query,
        query_param="q",
        link_patterns=[
            "/jobs/",
            "/job/",
        ],
        wait_ms=9000,
        max_scrolls=5,
    )


def fetch_amazon_jobs(
    query: str = "",
    career_url: str = "https://www.amazon.jobs/en/search",
    location: str = "",
    max_pages: int = 3,
    result_limit: int = 50,
    sleep_seconds: float = 0.3,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    endpoint = "https://www.amazon.jobs/en/search.json"

    for page in range(max_pages):
        params = {
            "base_query": query or "",
            "loc_query": location or "",
            "offset": page * result_limit,
            "result_limit": result_limit,
            "sort": "recent",
        }

        data = request_json("GET", endpoint, params=params)
        rows = data.get("jobs", [])

        if not rows:
            break

        for item in rows:
            job_path = first_available(item, ["job_path", "url_next_step"])
            job_url = abs_url("https://www.amazon.jobs", job_path)

            job = make_job(
                company="Amazon",
                title=first_available(item, ["title"]),
                location=first_available(item, ["normalized_location", "location"]),
                job_url=job_url,
                description=first_available(item, ["description", "basic_qualifications"]),
                ats_type="amazon_jobs",
                external_job_id=first_available(item, ["id", "job_id"]),
                posted_date=first_available(item, ["posted_date", "posted_date_iso", "updated_time"]),
            )

            if matches_query(job, query):
                jobs.append(job)

        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)


def fetch_apple_jobs(
    query: str = "",
    career_url: str = "https://jobs.apple.com/en-us/search",
    max_pages: int = 3,
    sleep_seconds: float = 0.3,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        html = request_html(career_url, params={"search": query or "", "page": page})

        page_jobs = extract_jsonld_jobs(
            html=html,
            company="Apple",
            base_url=career_url,
            ats_type="apple_html",
            query=query,
        )

        page_jobs += parse_links_as_jobs(
            html=html,
            company="Apple",
            base_url=career_url,
            link_patterns=["/en-us/details/"],
            ats_type="apple_html",
            query=query,
        )

        jobs.extend(page_jobs)
        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)


def fetch_mckinsey_jobs(
    query: str = "",
    career_url: str = "https://www.mckinsey.com/careers/search-jobs",
    **kwargs,
) -> List[Dict[str, Any]]:
    return fetch_browser_link_jobs(
        company="McKinsey & Company",
        career_url=career_url,
        ats_type="custom_mckinsey",
        query=query,
        query_param="query",
        link_patterns=[
            "/careers/search-jobs/jobs/",
            "/careers/search-jobs/",
        ],
        wait_ms=7000,
        max_scrolls=3,
    )

def fetch_bcg_jobs(
    query: str = "",
    career_url: str = "https://careers.bcg.com/global/en/search-results",
    max_pages: int = 2,
    sleep_seconds: float = 0.3,
    **kwargs,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []

    if "search-results" not in career_url:
        career_url = "https://careers.bcg.com/global/en/search-results"

    for page in range(max_pages):
        try:
            html = request_html(
                career_url,
                params={
                    "keywords": query or "",
                    "from": page * 10,
                },
                timeout=45,
            )
        except Exception as exc:
            print(f"BCG request failed: {exc}")
            return []

        page_jobs = extract_embedded_json_jobs(
            html=html,
            company="Boston Consulting Group",
            base_url=career_url,
            ats_type="custom_bcg",
            query=query,
        )

        page_jobs += parse_links_as_jobs(
            html=html,
            company="Boston Consulting Group",
            base_url=career_url,
            link_patterns=[
                "/global/en/job/",
                "/global/en/search-results/job/",
                "/job/",
            ],
            ats_type="custom_bcg",
            query=query,
        )

        jobs.extend(page_jobs)
        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)



def fetch_accenture_jobs(
    query: str = "",
    career_url: str = "https://www.accenture.com/us-en/careers/jobsearch",
    max_pages: int = 2,
) -> List[Dict[str, Any]]:
    """
    Accenture has used Workday-hosted boards.
    This tries likely Workday hosts first, then HTML fallback.
    """
    jobs = _try_fetch_variants(
        [
            (
                "accenture.wd103",
                lambda: fetch_workday(
                    company="Accenture",
                    host="accenture.wd103.myworkdayjobs.com",
                    tenant="accenture",
                    site="AccentureCareers",
                    query=query,
                    max_pages=max_pages,
                    limit=50,
                ),
            ),
            (
                "accenture.wd3",
                lambda: fetch_workday(
                    company="Accenture",
                    host="accenture.wd3.myworkdayjobs.com",
                    tenant="accenture",
                    site="AccentureCareers",
                    query=query,
                    max_pages=max_pages,
                    limit=50,
                ),
            ),
        ]
    )

    if jobs:
        return jobs

    html = request_html(career_url, params={"jk": query or ""})

    return parse_links_as_jobs(
        html=html,
        company="Accenture",
        base_url=career_url,
        link_patterns=["/us-en/careers/jobdetails", "jobdetails", "jobs/"],
        ats_type="accenture_html",
        query=query,
    )


def fetch_deloitte_jobs(
    query: str = "",
    career_url: str = "https://apply.deloitte.com/en_US/careers/SearchJobs",
    max_pages: int = 3,
    records_per_page: int = 30,
    sleep_seconds: float = 0.35,
) -> List[Dict[str, Any]]:
    """
    Deloitte's public landing page is different from its searchable job endpoint.
    If a landing URL is passed, this switches to the searchable endpoint.
    """
    if "SearchJobs" not in career_url:
        career_url = "https://apply.deloitte.com/en_US/careers/SearchJobs"

    jobs: List[Dict[str, Any]] = []

    for page in range(max_pages):
        offset = page * records_per_page

        html = request_html(
            career_url,
            params={
                "jobOffset": offset,
                "jobRecordsPerPage": records_per_page,
                "sort": "relevancy",
                "q": query or "",
            },
        )

        page_jobs = parse_links_as_jobs(
            html=html,
            company="Deloitte",
            base_url=career_url,
            link_patterns=["/en_US/careers/JobDetail", "JobDetail", "jobdetail"],
            ats_type="custom_deloitte",
            query=query,
        )

        jobs.extend(page_jobs)
        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)


def fetch_epic_systems_jobs(
    query: str = "",
    career_url: str = "https://careers.epic.com/jobs/",
) -> List[Dict[str, Any]]:
    html = request_html(career_url)

    jobs = parse_links_as_jobs(
        html=html,
        company="Epic Systems",
        base_url=career_url,
        link_patterns=["/jobs/"],
        ats_type="epic_static",
        query=query,
    )

    jobs = [
        job
        for job in jobs
        if job["job_url"].rstrip("/") != career_url.rstrip("/")
        and "life at epic" not in job["title"].lower()
        and "perks" not in job["title"].lower()
    ]

    return dedupe_jobs(jobs)


def fetch_astrazeneca_jobs(
    query: str = "",
    career_url: str = "https://careers.astrazeneca.com/search-jobs",
    max_pages: int = 2,
    sleep_seconds: float = 0.3,
    **kwargs,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []

    if "search-jobs" not in career_url:
        career_url = "https://careers.astrazeneca.com/search-jobs"

    for page in range(max_pages):
        try:
            html = request_html(
                career_url,
                params={
                    "keyword": query or "",
                    "from": page * 10,
                },
                timeout=45,
            )
        except Exception as exc:
            print(f"AstraZeneca request failed: {exc}")
            return []

        page_jobs = extract_embedded_json_jobs(
            html=html,
            company="AstraZeneca",
            base_url=career_url,
            ats_type="custom_astrazeneca",
            query=query,
        )

        page_jobs += parse_links_as_jobs(
            html=html,
            company="AstraZeneca",
            base_url=career_url,
            link_patterns=[
                "/job/",
                "/jobs/",
                "/search-jobs/",
            ],
            ats_type="custom_astrazeneca",
            query=query,
        )

        jobs.extend(page_jobs)
        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)


def fetch_palantir_jobs(
    query: str = "",
    career_url: str = "https://www.palantir.com/careers/",
) -> List[Dict[str, Any]]:
    return fetch_lever(
        company="Palantir",
        ats_slug="palantir",
        query=query,
    )


def fetch_salesforce_jobs(
    query: str = "",
    career_url: str = "https://careers.salesforce.com/en/jobs/",
    max_pages: int = 3,
    sleep_seconds: float = 0.3,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []

    if "careers.salesforce.com" not in career_url:
        career_url = "https://careers.salesforce.com/en/jobs/"

    for page in range(1, max_pages + 1):
        html = request_html(career_url, params={"page": page, "q": query or ""}, timeout=40)

        page_jobs = extract_jsonld_jobs(
            html=html,
            company="Salesforce",
            base_url=career_url,
            ats_type="custom_salesforce",
            query=query,
        )

        page_jobs += parse_links_as_jobs(
            html=html,
            company="Salesforce",
            base_url=career_url,
            link_patterns=["/en/jobs/jr", "/jobs/jr", "/en/jobs/"],
            ats_type="custom_salesforce",
            query=query,
        )

        jobs.extend(page_jobs)
        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)

def fetch_bloomberg_jobs(
    query: str = "",
    career_url: str = "https://bloomberg.avature.net/careers/SearchJobs",
    max_pages: int = 3,
    records_per_page: int = 50,
    sleep_seconds: float = 0.35,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []

    if "SearchJobs" not in career_url:
        career_url = "https://bloomberg.avature.net/careers/SearchJobs"

    for page in range(max_pages):
        offset = page * records_per_page

        html = request_html(
            career_url,
            params={
                "jobOffset": offset,
                "jobRecordsPerPage": records_per_page,
                "sort": "relevancy",
                "q": query or "",
            },
            timeout=40,
        )

        page_jobs = parse_links_as_jobs(
            html=html,
            company="Bloomberg",
            base_url=career_url,
            link_patterns=[
                "/careers/JobDetail",
                "JobDetail",
                "jobdetail",
            ],
            ats_type="custom_bloomberg",
            query=query,
        )

        jobs.extend(page_jobs)
        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)

def fetch_uber_jobs(
    query: str = "",
    career_url: str = "https://www.uber.com/us/en/careers/list/",
    max_jobs: int = 40,
    sleep_seconds: float = 0.1,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    Fast Uber fetcher:
    1. Try public careers list page.
    2. Only then try a tiny sitemap fallback.
    """
    jobs: List[Dict[str, Any]] = []

    try:
        html = request_html(career_url, params={"q": query or ""}, timeout=35)

        jobs = parse_links_as_jobs(
            html=html,
            company="Uber",
            base_url=career_url,
            link_patterns=["/careers/list/"],
            ats_type="custom_uber",
            query=query,
        )

        if jobs:
            return dedupe_jobs(jobs[:max_jobs])

    except Exception as exc:
        print(f"Uber careers page fallback failed: {exc}")

    print("Uber page returned no jobs. Trying tiny sitemap fallback...")

    try:
        urls = collect_sitemap_urls(
            sitemap_url="https://www.uber.com/sitemap.xml",
            include_substring="/careers/list/",
            max_sitemaps=3,
            max_urls=max_jobs,
        )
    except Exception as exc:
        print(f"Uber tiny sitemap fallback failed: {exc}")
        return []

    for url in urls[:max_jobs]:
        job = parse_detail_page_as_job(
            company="Uber",
            url=url,
            ats_type="custom_uber",
            query=query,
        )

        if job:
            jobs.append(job)

        time.sleep(sleep_seconds)

    return dedupe_jobs(jobs)

def fetch_atlassian_jobs(
    query: str = "",
    career_url: str = "https://www.atlassian.com/company/careers/all-jobs",
    **kwargs,
) -> List[Dict[str, Any]]:
    career_url = career_url.replace("all_jobs", "all-jobs")

    return fetch_browser_link_jobs(
        company="Atlassian",
        career_url=career_url,
        ats_type="custom_atlassian",
        query=query,
        query_param="search",
        link_patterns=[
            "/company/careers/details/",
            "/company/careers/all-jobs/",
            "/careers/details/",
            "/jobs/",
        ],
        wait_ms=9000,
        max_scrolls=5,
    )