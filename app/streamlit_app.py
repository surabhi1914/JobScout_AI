import os # File handing
import pandas as pd # Data handling
import streamlit as st #web app framework
from pathlib import Path
from dotenv import load_dotenv # handling environment variables
from sqlalchemy import create_engine, text #Data connection queries


# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="JobScout AI Dashboard",
    page_icon="🧭",
    layout="wide"
)


# -----------------------------
# Paths and DB connection
# -----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH) # gets my db credentials

DATABASE_URL = os.getenv("DATABASE_URL")


@st.cache_resource # Cache the database connection to avoid reconnecting on every interaction
def get_engine():
    return create_engine(DATABASE_URL)


engine = get_engine()


# -----------------------------
# Data loading
# -----------------------------
@st.cache_data(ttl=300)
def load_jobs():
    query = """
    SELECT
        jp.id AS job_id,
        jp.company,
        jp.title,
        jp.location,
        jp.job_url,
        jp.ats_type,
        jp.posted_date,
        jp.posted_datetime,
        jp.freshness_status,
        jp.date_found,
        js.keyword_match_count,
        js.matched_keywords,
        js.role_score,
        js.skill_score,
        js.project_score,
        js.experience_score,
        js.freshness_score,
        js.ats_match_score,
        js.score_label,
        js.matched_roles,
        js.matched_skills,
        js.project_relevance_hits,
        js.missing_keywords,
        js.seniority_flags,
        js.good_level_hits,
        js.score_reason,
        js.is_relevant,
        ast.status,
        ast.resume_version,
        ast.notes
    FROM job_postings jp
    JOIN job_scores js
        ON jp.id = js.job_id
    JOIN application_status ast
        ON jp.id = ast.job_id
    ORDER BY js.ats_match_score DESC, jp.date_found DESC;
    """

    return pd.read_sql(query, engine)


def update_job_status(job_id, new_status):
    with engine.begin() as conn: 
        conn.execute(
            text("""
                UPDATE application_status
                SET status = :status,
                    applied_at = CASE
                        WHEN :status = 'applied' THEN NOW()
                        ELSE applied_at
                    END,
                    updated_at = NOW()
                WHERE job_id = :job_id;
            """),
            {
                "job_id": int(job_id),
                "status": new_status
            }
        )

    st.cache_data.clear() #refreshes dashboard data after status update


# -----------------------------
# Header
# -----------------------------
st.title("🧭 JobScout AI")
st.caption("Multi-agent job tracking, ATS scoring, and application dashboard")

jobs_df = load_jobs()

if jobs_df.empty:
    st.warning("No jobs found in PostgreSQL yet. Run notebooks 02, 03, and 04 first.")
    st.stop()


# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.header("Filters")

min_score = st.sidebar.slider(
    "Minimum ATS score",
    min_value=0,
    max_value=100,
    value=50,
    step=5
)

companies = sorted(jobs_df["company"].dropna().unique().tolist())
selected_companies = st.sidebar.multiselect(
    "Companies",
    options=companies,
    default=companies
)

score_labels = sorted(jobs_df["score_label"].dropna().unique().tolist())
selected_labels = st.sidebar.multiselect(
    "Score labels",
    options=score_labels,
    default=score_labels
)

freshness_options = sorted(jobs_df["freshness_status"].dropna().unique().tolist())
selected_freshness = st.sidebar.multiselect(
    "Freshness",
    options=freshness_options,
    default=freshness_options
)

status_options = sorted(jobs_df["status"].dropna().unique().tolist())
selected_statuses = st.sidebar.multiselect(
    "Application status",
    options=status_options,
    default=status_options
)

show_relevant_only = st.sidebar.checkbox(
    "Show relevant jobs only",
    value=True
)


# -----------------------------
# Apply filters
# -----------------------------
filtered_df = jobs_df.copy()

filtered_df = filtered_df[
    (filtered_df["ats_match_score"] >= min_score)
    & (filtered_df["company"].isin(selected_companies))
    & (filtered_df["score_label"].isin(selected_labels))
    & (filtered_df["freshness_status"].isin(selected_freshness))
    & (filtered_df["status"].isin(selected_statuses))
]

if show_relevant_only:
    filtered_df = filtered_df[filtered_df["is_relevant"] == True]


# -----------------------------
# Summary metrics
# -----------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total jobs", len(jobs_df))
col2.metric("Filtered jobs", len(filtered_df))
col3.metric("Strong matches", int((jobs_df["ats_match_score"] >= 80).sum()))
col4.metric("Relevant jobs", int((jobs_df["is_relevant"] == True).sum()))


# -----------------------------
# Main table
# -----------------------------
st.subheader("Top job matches")

display_columns = [
    "company",
    "title",
    "location",
    "ats_match_score",
    "score_label",
    "freshness_status",
    "matched_skills",
    "seniority_flags",
    "status",
    "job_url"
]

table_df = filtered_df[display_columns].copy()

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "job_url": st.column_config.LinkColumn("Apply link"),
        "ats_match_score": st.column_config.ProgressColumn(
            "ATS score",
            min_value=0,
            max_value=100
        )
    }
)


# -----------------------------
# Job detail panel
# -----------------------------
st.subheader("Job detail")

if filtered_df.empty:
    st.info("No jobs match the current filters.")
    st.stop()

filtered_df["job_label"] = (
    filtered_df["company"].astype(str)
    + " | "
    + filtered_df["title"].astype(str)
    + " | Score: "
    + filtered_df["ats_match_score"].astype(str)
)

selected_label = st.selectbox(
    "Select a job",
    filtered_df["job_label"].tolist()
)

selected_job = filtered_df[
    filtered_df["job_label"] == selected_label
].iloc[0]


left, right = st.columns([2, 1])

with left:
    st.markdown(f"### {selected_job['title']}")
    st.markdown(f"**Company:** {selected_job['company']}")
    st.markdown(f"**Location:** {selected_job['location']}")
    st.markdown(f"**ATS:** {selected_job['ats_type']}")
    st.markdown(f"**Freshness:** {selected_job['freshness_status']}")
    st.markdown(f"**Current status:** `{selected_job['status']}`")

    st.markdown("#### Score reason")
    st.write(selected_job["score_reason"])

    st.markdown("#### Matched skills")
    st.write(selected_job["matched_skills"])

    st.markdown("#### Missing keywords")
    st.write(selected_job["missing_keywords"])

    st.markdown("#### Seniority flags")
    st.write(selected_job["seniority_flags"])

with right:
    st.metric("ATS Match Score", int(selected_job["ats_match_score"]))
    st.metric("Role Score", int(selected_job["role_score"]))
    st.metric("Skill Score", int(selected_job["skill_score"]))
    st.metric("Project Score", int(selected_job["project_score"]))
    st.metric("Experience Score", int(selected_job["experience_score"]))
    st.metric("Freshness Score", int(selected_job["freshness_score"]))

    st.link_button("Apply", selected_job["job_url"])

    st.markdown("#### Update status")

    if st.button("Save job"):
        update_job_status(selected_job["job_id"], "saved")
        st.rerun()

    if st.button("Mark applied"):
        update_job_status(selected_job["job_id"], "applied")
        st.rerun()

    if st.button("Ignore"):
        update_job_status(selected_job["job_id"], "ignored")
        st.rerun()


# -----------------------------
# Analytics section
# -----------------------------
st.subheader("Quick analytics")

analytics_col1, analytics_col2 = st.columns(2)

with analytics_col1:
    st.markdown("#### Average score by company")
    avg_score_df = (
        jobs_df.groupby("company")["ats_match_score"]
        .mean()
        .reset_index()
        .sort_values("ats_match_score", ascending=False)
    )

    st.dataframe(
        avg_score_df,
        use_container_width=True,
        hide_index=True
    )

with analytics_col2:
    st.markdown("#### Jobs by status")
    status_df = (
        jobs_df["status"]
        .value_counts()
        .reset_index()
    )

    status_df.columns = ["status", "count"]

    st.dataframe(
        status_df,
        use_container_width=True,
        hide_index=True
    )