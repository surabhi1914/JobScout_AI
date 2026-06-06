"""
Backward-compatible import layer.

Old notebook imports can keep using:
    from src.fetchers import ...

Actual implementation is now split across:
    src/shared_helpers.py
    src/date_helpers.py
    src/job_fetchers.py
"""

from .shared_helpers import *
from .date_helpers import *
from .job_fetchers import *

from typing import Any, Dict, List, Optional, Callable

# ============================================================
# Registry / router
# ============================================================

def normalize_company_key(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(company).lower())


ATS_TYPE_FETCHERS: Dict[str, Callable[..., List[Dict[str, Any]]]] = {
    "custom_netflix": fetch_netflix_jobs,
    "custom_google": fetch_google_jobs,
    "custom_microsoft": fetch_microsoft_jobs,
    "custom_meta": fetch_meta_jobs,
    "custom_amazon": fetch_amazon_jobs,
    "custom_apple": fetch_apple_jobs,
    "custom_mckinsey": fetch_mckinsey_jobs,
    "custom_bcg": fetch_bcg_jobs,
    "custom_accenture": fetch_accenture_jobs,
    "custom_deloitte": fetch_deloitte_jobs,
    "custom_epic": fetch_epic_systems_jobs,
    "custom_astrazeneca": fetch_astrazeneca_jobs,
    "custom_palantir": fetch_palantir_jobs,
    "custom_salesforce": fetch_salesforce_jobs,
    "custom_uber": fetch_uber_jobs,
    "custom_bloomberg": fetch_bloomberg_jobs,   
    "custom_atlassian": fetch_atlassian_jobs,
}


def fetch_jobs_for_company(row: Any, query: str = "") -> List[Dict[str, Any]]:
    """
    Route one row from companies.csv to the correct fetcher.

    Supported columns:
    - company
    - ats_type
    - career_url
    - ats_slug
    - workday_tenant
    - workday_site
    - workday_server
    - workday_host
    - max_pages
    - limit
    """
    company = str(row_get(row, "company", "")).strip()
    ats_type = str(row_get(row, "ats_type", "")).lower().strip()
    career_url = str(row_get(row, "career_url", "")).strip()
    # print(f"Company: {company} | ATS type: {ats_type} | Career URL: {career_url}")

    if ats_type == "greenhouse":
        return fetch_greenhouse(
            company=company,
            ats_slug=str(row_get(row, "ats_slug")),
            query=query,
        )

    if ats_type == "ashby":
        return fetch_ashby(
            company=company,
            ats_slug=str(row_get(row, "ats_slug")),
            query=query,
        )

    if ats_type == "lever":
        return fetch_lever(
            company=company,
            ats_slug=str(row_get(row, "ats_slug")),
            query=query,
        )

    if ats_type == "workday":
        max_pages = int(row_get(row, "max_pages", 1) or 1)
        limit = int(row_get(row, "limit", 20) or 20)

        return fetch_workday(
            company=company,
            tenant=str(row_get(row, "workday_tenant", "")).strip(),
            site=str(row_get(row, "workday_site", "")).strip(),
            server=str(row_get(row, "workday_server", "")).strip(),
            host=str(row_get(row, "workday_host", "")).strip(),
            career_url=career_url,
            query=query,
            max_pages=max_pages,
            limit=limit,
        )

    if ats_type in ATS_TYPE_FETCHERS:
        print(f"Using custom fetcher for {company} with ATS type '{ats_type}'")
        fetcher = ATS_TYPE_FETCHERS[ats_type]
        kwargs = {"query": query}

        if career_url:
            kwargs["career_url"] = career_url

        return fetcher(**kwargs)



    print(f"Skipping {company} because ATS type '{ats_type}' is not supported yet.")
    return []


def fetch_jobs_from_registry(companies_df: pd.DataFrame, query: str = "") -> pd.DataFrame:
    """
    Run all company rows in companies.csv and return a DataFrame.
    """
    all_jobs: List[Dict[str, Any]] = []

    for _, row in companies_df.iterrows():
        company = row_get(row, "company", "Unknown")
        print(f"Fetching jobs for {company}...")

        try:
            jobs = fetch_jobs_for_company(row, query=query)
            print(f"Found {len(jobs)} jobs")
            all_jobs.extend(jobs)

        except requests.exceptions.HTTPError as exc:
            print(f"HTTP error for {company}: {exc}")

            if getattr(exc, "response", None) is not None:
                print("Response text:", exc.response.text[:500])

        except Exception as exc:
            print(f"Error fetching {company}: {exc}")

    jobs_df = pd.DataFrame(dedupe_jobs(all_jobs))

    if not jobs_df.empty and query:
        jobs_df["search_query"] = query

    return jobs_df