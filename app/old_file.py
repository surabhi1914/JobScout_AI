import os # File handing
import pandas as pd # Data handling
import streamlit as st #web app framework
from pathlib import Path
from dotenv import load_dotenv # handling environment variables
from sqlalchemy import create_engine, text #Data connection queries
from html import escape


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

# -------------------------------------------------
# Theme / styling
# -------------------------------------------------
def inject_css():
    bg = "#F5F7FB"
    card_bg = "#FFFFFF"
    text = "#17202A"
    muted = "#64748B"
    border = "#E2E8F0"
    accent = "#0E9F6E"
    accent_dark = "#057A55"
    soft_accent = "rgba(14, 159, 110, 0.10)"
    warning = "#F59E0B"
    danger = "#DC2626"
    blue = "#2563EB"

    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                radial-gradient(circle at top left, rgba(14,159,110,0.13), transparent 30%),
                radial-gradient(circle at top right, rgba(37,99,235,0.10), transparent 28%),
                {bg};
            color: {text};
        }}

        h1, h2, h3, h4, h5, h6, p, div {{
            color: {text};
        }}

        section[data-testid="stSidebar"] {{
            background: #FFFFFF;
            border-right: 1px solid {border};
        }}

        .hero-card {{
            background: linear-gradient(135deg, #FFFFFF 0%, #ECFDF5 55%, #EFF6FF 100%);
            padding: 30px;
            border-radius: 26px;
            border: 1px solid {border};
            margin-bottom: 22px;
            box-shadow: 0 18px 45px rgba(15,23,42,0.08);
        }}

        .hero-title {{
            font-size: 38px;
            font-weight: 900;
            margin-bottom: 8px;
            letter-spacing: -0.04em;
        }}

        .hero-subtitle {{
            color: {muted};
            font-size: 16px;
            max-width: 850px;
            line-height: 1.6;
        }}

        .metric-card {{
            background: {card_bg};
            padding: 18px 20px;
            border-radius: 20px;
            border: 1px solid {border};
            box-shadow: 0 10px 28px rgba(15,23,42,0.06);
        }}

        .metric-label {{
            color: {muted};
            font-size: 13px;
            margin-bottom: 6px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        .metric-value {{
            color: {text};
            font-size: 30px;
            font-weight: 900;
        }}

        .scout-job-card {{
            background: {card_bg};
            padding: 22px 24px;
            border-radius: 22px;
            border: 1px solid {border};
            margin-bottom: 18px;
            box-shadow: 0 12px 34px rgba(15,23,42,0.07);
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }}

        .scout-job-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 18px 44px rgba(15,23,42,0.10);
        }}

        .job-card-top {{
            display: flex;
            justify-content: space-between;
            gap: 18px;
            align-items: flex-start;
        }}

        .job-title {{
            font-size: 21px;
            font-weight: 900;
            margin-bottom: 6px;
            letter-spacing: -0.02em;
        }}

        .job-meta {{

            font-size: 14px;
            margin-bottom: 12px;
            line-height: 1.5;
        }}

        .score-pill {{
            min-width: 82px;
            text-align: center;
            background: {soft_accent};
            color: {accent_dark};
            border: 1px solid rgba(14,159,110,0.35);
            padding: 10px 12px;
            border-radius: 18px;
            font-weight: 900;
            font-size: 22px;
        }}

        .score-caption {{
            font-size: 11px;
            color: {muted};
            font-weight: 700;
            text-transform: uppercase;
            margin-top: 2px;
        }}

        .badge {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
            margin-right: 6px;
            margin-bottom: 7px;
            background: {soft_accent};
            color: {accent_dark};
            border: 1px solid rgba(14,159,110,0.35);
        }}

        .badge-blue {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
            margin-right: 6px;
            margin-bottom: 7px;
            background: rgba(37,99,235,0.10);
            color: {blue};
            border: 1px solid rgba(37,99,235,0.25);
        }}

        .badge-warning {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
            margin-right: 6px;
            margin-bottom: 7px;
            background: rgba(245,158,11,0.12);
            color: {warning};
            border: 1px solid rgba(245,158,11,0.35);
        }}

        .badge-danger {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
            margin-right: 6px;
            margin-bottom: 7px;
            background: rgba(220,38,38,0.10);
            color: {danger};
            border: 1px solid rgba(220,38,38,0.28);
        }}
        /* Scout Board action row */
        .scout-actions-label {{
            color: #64748B;
            font-size: 12px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-top: 14px;
            margin-bottom: 6px;
        }}

        /* Base style for Scout Board buttons */
        div[class*="st-key-btn_report_"] button,
        div[class*="st-key-btn_save_"] button,
        div[class*="st-key-btn_ignore_"] button,
        div[class*="st-key-btn_apply_"] a {{
            border-radius: 999px !important;
            height: 42px !important;
            font-weight: 900 !important;
            border: none !important;
            box-shadow: 0 8px 18px rgba(15,23,42,0.10) !important;
            transition: all 0.15s ease !important;
        }}

        div[class*="st-key-btn_report_"] button:hover,
        div[class*="st-key-btn_save_"] button:hover,
        div[class*="st-key-btn_ignore_"] button:hover,
        div[class*="st-key-btn_apply_"] a:hover {{
            transform: translateY(-1px);
            box-shadow: 0 12px 24px rgba(15,23,42,0.16) !important;
        }}

        /* Scout Report button */
        div[class*="st-key-btn_report_"] button {{
            background: linear-gradient(135deg, #BFBFFF, #A3A3FF) !important;
            color: #FFFFFF !important;
        }}

        /* Apply button */
        div[class*="st-key-btn_apply_"] a {{
            background: linear-gradient(135deg, #0E9F6E, #057A55) !important;
            color: #FFFFFF !important;
            text-decoration: none !important;
        }}

        /* Save button */
        div[class*="st-key-btn_save_"] button {{
            background: #ECFDF5 !important;
            color: #057A55 !important;
            border: 1px solid rgba(14,159,110,0.25) !important;
        }}

        /* Ignore button */
        div[class*="st-key-btn_ignore_"] button {{
            background: #FEF2F2 !important;
            color: #DC2626 !important;
            border: 1px solid rgba(220,38,38,0.22) !important;
        }}

        .mini-label {{
            color: {muted};
            font-size: 12px;
            font-weight: 800;
            text-transform: uppercase;
            margin-top: 10px;
            margin-bottom: 5px;
            letter-spacing: 0.04em;
        }}

        .desc-preview {{
            color: {muted};
            font-size: 14px;
            line-height: 1.55;
            margin-top: 8px;
            margin-bottom: 8px;
        }}

        .section-card {{
            background: {card_bg};
            padding: 20px;
            border-radius: 22px;
            border: 1px solid {border};
            margin-bottom: 18px;
            box-shadow: 0 10px 28px rgba(15,23,42,0.05);
        }}

        .detail-box {{
            background: #F8FAFC;
            border: 1px solid {border};
            padding: 16px;
            border-radius: 16px;
            margin-bottom: 12px;
        }}

        .description-box {{
            background: #FFFFFF;
            border: 1px solid {border};
            padding: 18px;
            border-radius: 18px;
            max-height: 360px;
            overflow-y: auto;
            line-height: 1.65;
            color: {text};
        }}

        div[data-testid="stMetric"] {{
            background: {card_bg};
            border: 1px solid {border};
            padding: 14px;
            border-radius: 16px;
            box-shadow: 0 8px 20px rgba(15,23,42,0.04);
        }}

        div[data-testid="stDialog"] div[role="dialog"] {{
            width: 82vw;
            max-width: 1200px;
        }}
        div[class*="st-key-scout_card_"] {{
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 22px;
            padding: 18px 20px;
            margin-bottom: 18px;
            box-shadow: 0 12px 34px rgba(15,23,42,0.07);
        }}

        div[class*="st-key-scout_card_"]:hover {{
            box-shadow: 0 18px 44px rgba(15,23,42,0.10);
            transform: translateY(-1px);
            transition: all 0.15s ease;
        }}
        
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------
# Data loading
# -------------------------------------------------
@st.cache_data(ttl=300)
def load_jobs():
    query = """
    SELECT
        jp.id AS job_id,
        jp.company,
        jp.title,
        jp.location,
        jp.job_url,
        jp.description,
        jp.ats_type,
        jp.posted_date,
        jp.posted_datetime,
        jp.freshness_status,
        jp.date_found,
        jp.first_seen,
        jp.last_seen,
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

# -------------------------------------------------
# Utility helpers
# -------------------------------------------------
def safe_text(value, fallback="Not available"):
    value = str(value).strip()
    if value.lower() in ["", "none", "nan", "null"]:
        return fallback
    return value

def clean_display_text(value, fallback="Not available"):
    value = safe_text(value, fallback="")
    value = " ".join(value.split())
    return value if value else fallback


def truncate_text(value, max_chars=280):
    value = clean_display_text(value, fallback="")
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rsplit(" ", 1)[0] + "..."

def render_badges(items, style="green", limit=10):
    if not items:
        return ""

    return " ".join(
        badge_html(escape(str(item)), style)
        for item in items[:limit]
    )

def badge_html(text, style="green"):
    class_map = {
        "green": "badge",
        "blue": "badge-blue",
        "warning": "badge-warning",
        "danger": "badge-danger"
    }
    cls = class_map.get(style, "badge")
    return f"<span class='{cls}'>{text}</span>"

def is_empty_flag(value):
    value = str(value).strip().lower()
    return value in ["", "none", "nan", "null", "[]"]


def split_semicolon_text(value):
    if is_empty_flag(value):
        return []
    return [x.strip() for x in str(value).split(";") if x.strip()]



def score_color(score):
    if score >= 80:
        return "🟢"
    if score >= 65:
        return "🟡"
    if score >= 50:
        return "🟠"
    return "🔴"


def make_metric_card(label, value):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------
# Job detail modal
# -------------------------------------------------
@st.dialog("JobScout Position Report", width="large")
def show_job_dialog(job):
    description = safe_text(job.get("description", ""), "No job description captured yet.")
    matched_skills = split_semicolon_text(job.get("matched_skills", ""))
    missing_keywords = split_semicolon_text(job.get("missing_keywords", ""))
    seniority_flags = split_semicolon_text(job.get("seniority_flags", ""))
    matched_roles = split_semicolon_text(job.get("matched_roles", ""))
    project_hits = split_semicolon_text(job.get("project_relevance_hits", ""))

    st.markdown(f"## {safe_text(job.get('title'))}")
    st.markdown(
        f"""
        {badge_html(safe_text(job.get('company')), "blue")}
        {badge_html("Score " + str(int(job.get("ats_match_score", 0))), "green")}
        {badge_html(safe_text(job.get("score_label")), "green")}
        {badge_html(safe_text(job.get("freshness_status")), "warning")}
        {badge_html(safe_text(job.get("ats_type")), "blue")}
        """,
        unsafe_allow_html=True
    )

    st.markdown("")

    top_left, top_right = st.columns([2, 1])

    with top_left:
        st.markdown(
            f"""
            <div class="detail-box">
                <b>Company:</b> {safe_text(job.get("company"))}<br>
                <b>Location:</b> {safe_text(job.get("location"))}<br>
                <b>Posted at:</b> {safe_text(job.get("posted_date"))}<br>
                <b>Found by JobScout:</b> {safe_text(job.get("date_found"))}<br>
                <b>First seen:</b> {safe_text(job.get("first_seen"))}<br>
                <b>Current status:</b> {safe_text(job.get("status"))}
            </div>
            """,
            unsafe_allow_html=True
        )

    with top_right:
        st.metric("ATS Match", int(job.get("ats_match_score", 0)))
        st.metric("Keyword Hits", int(job.get("keyword_match_count", 0) or 0))

    st.markdown("### Score Breakdown")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Role", int(job.get("role_score", 0)))
    c2.metric("Skills", int(job.get("skill_score", 0)))
    c3.metric("Project", int(job.get("project_score", 0)))
    c4.metric("Experience", int(job.get("experience_score", 0)))
    c5.metric("Freshness", int(job.get("freshness_score", 0)))

    st.markdown("### JobScout Analysis")
    st.write(safe_text(job.get("score_reason"), "No score reason available."))

    st.markdown("### Matched Role Signals")
    if matched_roles:
        st.markdown(" ".join([badge_html(x, "blue") for x in matched_roles[:20]]), unsafe_allow_html=True)
    else:
        st.caption("No role signals found.")

    st.markdown("### Matched Skills")
    if matched_skills:
        st.markdown(" ".join([badge_html(x, "green") for x in matched_skills[:30]]), unsafe_allow_html=True)
    else:
        st.caption("No matched skills found.")

    st.markdown("### Project Relevance Signals")
    if project_hits:
        st.markdown(" ".join([badge_html(x, "blue") for x in project_hits[:20]]), unsafe_allow_html=True)
    else:
        st.caption("No project relevance signals found.")

    st.markdown("### Seniority Warnings")
    if seniority_flags:
        st.markdown(" ".join([badge_html(x, "danger") for x in seniority_flags]), unsafe_allow_html=True)
    else:
        st.success("No seniority flags found.")

    st.markdown("### Missing Keywords")
    if missing_keywords:
        st.write(", ".join(missing_keywords[:30]))
    else:
        st.caption("No missing keywords listed.")

    st.markdown("### Job Description")
    st.markdown(
        f"""
        <div class="description-box">
            {description}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        st.link_button("Apply Now", job["job_url"], use_container_width=True)

    with a2:
        if st.button("Save Job", use_container_width=True):
            update_job_status(job["job_id"], "saved")
            st.toast("Saved job")
            st.rerun()

    with a3:
        if st.button("Mark Applied", use_container_width=True):
            update_job_status(job["job_id"], "applied")
            st.toast("Marked as applied")
            st.rerun()

    with a4:
        if st.button("Ignore", use_container_width=True):
            update_job_status(job["job_id"], "ignored")
            st.toast("Ignored job")
            st.rerun()

# -------------------------------------------------
# App start
# -------------------------------------------------
jobs_df = load_jobs()

if jobs_df.empty:
    st.warning("No jobs found yet. Run notebooks 02, 03, and 04 first.")
    st.stop()

# add helper boolean
jobs_df["has_seniority_flags"] = ~jobs_df["seniority_flags"].apply(is_empty_flag)

# # sidebar theme toggle
# st.sidebar.markdown("## Settings")
# dark_mode = st.sidebar.toggle("Dark mode", value=True)
# inject_css(dark_mode)

inject_css()


st.markdown(
    """
    <div class="hero-card">
        <div class="hero-title">🧭 JobScout AI</div>
        <div class="hero-subtitle">
            A personal career intelligence dashboard that scans company job boards,
            scores roles against your profile, flags seniority risks, and helps you focus
            on the positions most worth applying to.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------
# Global tabs
# -------------------------------------------------
career_tab, search_tab = st.tabs(
    [
        "📊 My Career Page",
        "🔎 Search Jobs"
    ]
)


# -------------------------------------------------
# Tab A: My Career Page
# -------------------------------------------------
with career_tab:
    total_jobs = len(jobs_df)
    total_applied = int((jobs_df["status"] == "applied").sum())
    strong_matches = int((jobs_df["ats_match_score"] >= 80).sum())
    relevant_jobs = int((jobs_df["is_relevant"] == True).sum())

    # filtered jobs here means default clean candidate pool:
    # relevant + no seniority flags
    filtered_jobs = jobs_df[
        (jobs_df["is_relevant"] == True)
        & (jobs_df["has_seniority_flags"] == False)
    ]

    st.subheader("Career Snapshot")

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        make_metric_card("Total Applied", total_applied)
    with m2:
        make_metric_card("Total Jobs", total_jobs)
    with m3:
        make_metric_card("Filtered Jobs", len(filtered_jobs))
    with m4:
        make_metric_card("Strong Matches", strong_matches)
    with m5:
        make_metric_card("Relevant Jobs", relevant_jobs)

    st.markdown("### Quick Analytics")

    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("#### Average ATS score by company")
        avg_score_df = (
            jobs_df.groupby("company")["ats_match_score"]
            .mean()
            .round(1)
            .reset_index()
            .sort_values("ats_match_score", ascending=False)
        )
        st.bar_chart(avg_score_df, x="company", y="ats_match_score")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("#### Jobs by application status")
        status_df = (
            jobs_df["status"]
            .value_counts()
            .reset_index()
        )
        status_df.columns = ["status", "count"]
        st.bar_chart(status_df, x="status", y="count")
        st.markdown("</div>", unsafe_allow_html=True)

    left2, right2 = st.columns(2)

    with left2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("#### Score label distribution")
        label_df = (
            jobs_df["score_label"]
            .value_counts()
            .reset_index()
        )
        label_df.columns = ["score_label", "count"]
        st.bar_chart(label_df, x="score_label", y="count")
        st.markdown("</div>", unsafe_allow_html=True)

    with right2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("#### Freshness distribution")
        freshness_df = (
            jobs_df["freshness_status"]
            .value_counts()
            .reset_index()
        )
        freshness_df.columns = ["freshness_status", "count"]
        st.bar_chart(freshness_df, x="freshness_status", y="count")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Top companies by strong matches")

    company_strong_df = (
        jobs_df[jobs_df["ats_match_score"] >= 80]
        .groupby("company")
        .size()
        .reset_index(name="strong_matches")
        .sort_values("strong_matches", ascending=False)
    )

    st.dataframe(
        company_strong_df,
        use_container_width=True,
        hide_index=True
    )


# -------------------------------------------------
# Tab B: Search Jobs
# -------------------------------------------------
with search_tab:
    st.subheader("Search Jobs")

    st.markdown("Use filters to find jobs worth applying to. The seniority filter is ON by default.")

    f1, f2, f3, f4 = st.columns([1, 1, 1, 1])

    with f1:
        min_score = st.slider(
            "Minimum ATS score",
            min_value=0,
            max_value=100,
            value=50,
            step=5
        )

    with f2:
        show_relevant_only = st.checkbox(
            "Relevant jobs only",
            value=True
        )

    with f3:
        hide_seniority_flags = st.checkbox(
            "Hide seniority flags",
            value=True
        )

    with f4:
        max_jobs_to_show = st.selectbox(
            "Jobs to show",
            options=[10, 25, 50, 100],
            index=1
        )

    companies = sorted(jobs_df["company"].dropna().unique().tolist())
    score_labels = sorted(jobs_df["score_label"].dropna().unique().tolist())
    freshness_options = sorted(jobs_df["freshness_status"].dropna().unique().tolist())
    status_options = sorted(jobs_df["status"].dropna().unique().tolist())

    c1, c2 = st.columns(2)

    with c1:
        selected_companies = st.multiselect(
            "Companies",
            options=companies,
            default=companies
        )

        selected_labels = st.multiselect(
            "Score labels",
            options=score_labels,
            default=score_labels
        )

    with c2:
        selected_freshness = st.multiselect(
            "Freshness",
            options=freshness_options,
            default=freshness_options
        )

        selected_statuses = st.multiselect(
            "Application status",
            options=status_options,
            default=status_options
        )

    keyword_search = st.text_input(
        "Search title/company/skills",
        placeholder="Try: machine learning, data scientist, python, computer vision..."
    )

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

    if hide_seniority_flags:
        filtered_df = filtered_df[filtered_df["has_seniority_flags"] == False]

    if keyword_search.strip():
        query = keyword_search.strip().lower()
        filtered_df = filtered_df[
            filtered_df.apply(
                lambda row: query in " ".join(
                    [
                        str(row.get("company", "")),
                        str(row.get("title", "")),
                        str(row.get("matched_skills", "")),
                        str(row.get("matched_keywords", "")),
                        str(row.get("score_reason", ""))
                    ]
                ).lower(),
                axis=1
            )
        ]

    filtered_df = filtered_df.sort_values(
        ["ats_match_score", "date_found"],
        ascending=[False, False]
    )

    st.markdown("### Applied filters summary")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Visible jobs", len(filtered_df))
    s2.metric("Min score", min_score)
    s3.metric("Strong visible", int((filtered_df["ats_match_score"] >= 80).sum()))
    s4.metric("No seniority flags", int((filtered_df["has_seniority_flags"] == False).sum()))

    st.markdown("### Scout Board")

    if filtered_df.empty:
        st.info("No jobs match your current filters.")
    else:
        display_df = filtered_df.head(max_jobs_to_show).copy()

        st.markdown(
            f"""
            <div class="section-card">
                <b>{len(filtered_df)}</b> jobs match your current filters. Showing top <b>{len(display_df)}</b>.
                Jobs are ranked by ATS match score, freshness, and your profile signals.
            </div>
                    """,
            unsafe_allow_html=True
        )

        for _, job in display_df.iterrows():
            job_dict = job.to_dict()

            seniority_flags = split_semicolon_text(job_dict.get("seniority_flags", ""))
            matched_skills = split_semicolon_text(job_dict.get("matched_skills", ""))
            matched_roles = split_semicolon_text(job_dict.get("matched_roles", ""))
            project_hits = split_semicolon_text(job_dict.get("project_relevance_hits", ""))

            score = int(job_dict.get("ats_match_score", 0))
            description_preview = escape(
                truncate_text(job_dict.get("description", ""), max_chars=360)
            )

            title = escape(safe_text(job_dict.get("title")))
            company = escape(safe_text(job_dict.get("company")))
            location = escape(safe_text(job_dict.get("location")))
            freshness = escape(safe_text(job_dict.get("freshness_status")))
            status = escape(safe_text(job_dict.get("status")))
            ats_type = escape(safe_text(job_dict.get("ats_type")))
            score_label = escape(safe_text(job_dict.get("score_label")))

            if score >= 80:
                score_style = "green"
            elif score >= 65:
                score_style = "warning"
            else:
                score_style = "blue"

            with st.container(border=False, key=f"scout_card_{job_dict['job_id']}"):
                st.markdown(
                    f"""
                    <div class="job-card-top">
                        <div>
                            <div class="job-title">{score_color(score)} {title}</div>
                            <div class="job-meta">
                                <b>{company}</b> · {location} · {freshness} · {status}
                            </div>
                            <div>
                                {badge_html(score_label, score_style)}
                                {badge_html(ats_type, "blue")}
                                {badge_html("Role " + str(int(job_dict.get("role_score", 0))), "blue")}
                                {badge_html("Skills " + str(int(job_dict.get("skill_score", 0))), "green")}
                                {badge_html("Exp " + str(int(job_dict.get("experience_score", 0))), "warning")}
                            </div>
                        </div>
                        <div>
                            <div class="score-pill">{score}</div>
                            <div class="score-caption">Match</div>
                        </div>
                    </div>

                    <div class="desc-preview">
                        {description_preview}
                    </div>
                    """,
                    unsafe_allow_html=True
                    )

                if matched_roles:
                    st.markdown(
                        f"""
                        <div cl`ass="mini-label">Role Signals</div>
                        <div>{render_badges(matched_roles, "blue", limit=6)}</div>
                                            """,
                                            unsafe_allow_html=True
                        )

                if matched_skills:
                    st.markdown(
                        f"""
                        <div class="mini-label">Matched Skills</div>
                        <div>{render_badges(matched_skills, "green", limit=10)}</div>
                                            """,
                                            unsafe_allow_html=True
                    )

                if project_hits:
                    st.markdown(
                        f"""
                        <div class="mini-label">Project Relevance</div>
                        <div>{render_badges(project_hits, "blue", limit=6)}</div>
                                            """,
                                            unsafe_allow_html=True
                    )

                if seniority_flags:
                    st.markdown(
                        f"""
                        <div class="mini-label">Seniority Flags</div>
                        <div>{render_badges(seniority_flags, "danger", limit=8)}</div>
                                            """,
                                            unsafe_allow_html=True
                    )

                st.markdown(
                    '<div class="scout-actions-label">Actions</div>',
                    unsafe_allow_html=True
                )

                b1, b2, b3, b4 = st.columns([1.25, 1, 1, 1])

                with b1:
                    with st.container(key=f"btn_report_{job_dict['job_id']}"):
                        if st.button(
                            "📋 Scout Report",
                            key=f"details_{job_dict['job_id']}",
                            use_container_width=True
                        ):
                            show_job_dialog(job_dict)

                with b2:
                    with st.container(key=f"btn_apply_{job_dict['job_id']}"):
                        st.link_button(
                            "🚀 Apply",
                            job_dict["job_url"],
                            use_container_width=True
                        )

                with b3:
                    with st.container(key=f"btn_save_{job_dict['job_id']}"):
                        if st.button(
                            "⭐ Save",
                            key=f"save_{job_dict['job_id']}",
                            use_container_width=True
                        ):
                            update_job_status(job_dict["job_id"], "saved")
                            st.toast("Saved job")
                            st.rerun()

                with b4:
                    with st.container(key=f"btn_ignore_{job_dict['job_id']}"):
                        if st.button(
                            "🙈 Ignore",
                            key=f"ignore_{job_dict['job_id']}",
                            use_container_width=True
                        ):
                            update_job_status(job_dict["job_id"], "ignored")
                            st.toast("Ignored job")
                            st.rerun()
            
