import os
from datetime import date
from typing import Any

import streamlit as st

from frontend.api_client import APIClient, APIError

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
STATUSES = ["Applied", "Interview", "Offer", "Rejected", "Withdrawn"]
EMPLOYMENT_TYPES = [
    "Full-time",
    "Part-time",
    "Contract",
    "Internship",
    "Temporary",
    "Other",
]
PAGE_SIZE_OPTIONS = [10, 20, 50, 100]


def get_api_client() -> APIClient:
    return APIClient(API_BASE_URL)


def clear_authentication() -> None:
    for key in ("access_token", "current_user", "job_filters", "job_page"):
        st.session_state.pop(key, None)


def api_call(
    method: str,
    path: str,
    *,
    authenticated: bool = True,
    **kwargs: Any,
) -> Any | None:
    token = st.session_state.get("access_token") if authenticated else None
    try:
        return get_api_client().request(method, path, token=token, **kwargs)
    except APIError as exc:
        if authenticated and exc.authentication_failed:
            clear_authentication()
            st.error(exc.message)
            st.rerun()
        st.error(exc.message)
        return None


def render_authentication() -> None:
    st.title("AI-Powered Job Application Tracker")
    st.caption("Keep your search organized. Your account and applications stay yours.")
    login_tab, register_tab = st.tabs(["Sign in", "Create account"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", autocomplete="email")
            password = st.text_input(
                "Password",
                type="password",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            result = api_call(
                "POST",
                "/auth/login",
                authenticated=False,
                json={"email": email, "password": password},
            )
            if result is not None:
                st.session_state["access_token"] = result["access_token"]
                user = api_call("GET", "/auth/me")
                if user is not None:
                    st.session_state["current_user"] = user
                    st.rerun()
                clear_authentication()

    with register_tab:
        with st.form("register_form"):
            name = st.text_input("Name", autocomplete="name")
            register_email = st.text_input("Email address", autocomplete="email")
            register_password = st.text_input(
                "Password (at least 8 characters)",
                type="password",
                autocomplete="new-password",
            )
            submitted = st.form_submit_button("Create account", type="primary")
        if submitted:
            result = api_call(
                "POST",
                "/auth/register",
                authenticated=False,
                json={
                    "name": name,
                    "email": register_email,
                    "password": register_password,
                },
            )
            if result is not None:
                st.success("Account created. Sign in to continue.")


def render_dashboard() -> None:
    st.title("Your dashboard")
    stats = api_call("GET", "/dashboard/stats")
    if stats is None:
        return

    metrics = st.columns(4)
    metrics[0].metric("Applications", stats["total_applications"])
    metrics[1].metric("Interviews", stats["interview_count"])
    metrics[2].metric("Offers", stats["offer_count"])
    metrics[3].metric("Rejected", stats["rejection_count"])

    rates = st.columns(2)
    rates[0].metric("Interview conversion", f'{stats["interview_conversion_rate"]:.2f}%')
    rates[1].metric("Offer conversion", f'{stats["offer_conversion_rate"]:.2f}%')

    left, right = st.columns(2)
    with left:
        st.subheader("Applications by status")
        status_rows = stats["applications_by_status"]
        st.bar_chart(
            {
                "Status": [row["status"] for row in status_rows],
                "Applications": [row["count"] for row in status_rows],
            },
            x="Status",
            y="Applications",
        )
    with right:
        st.subheader("Applications over time")
        timeline = stats["applications_over_time"]
        if timeline:
            st.line_chart(
                {
                    "Date": [row["applied_date"] for row in timeline],
                    "Applications": [row["count"] for row in timeline],
                },
                x="Date",
                y="Applications",
            )
        else:
            st.info("Application activity will appear here.")

    left, right = st.columns(2)
    for column, title, key in (
        (left, "By employment type", "applications_by_employment_type"),
        (right, "By location", "applications_by_location"),
    ):
        with column:
            st.subheader(title)
            categories = stats[key]
            if categories:
                st.bar_chart(
                    {
                        "Category": [
                            row["category"] or "Not specified" for row in categories
                        ],
                        "Applications": [row["count"] for row in categories],
                    },
                    x="Category",
                    y="Applications",
                )
            else:
                st.info("No application data yet.")


def _render_job_form() -> None:
    st.subheader("Add an application")
    with st.form("create_job_form", clear_on_submit=True):
        company = st.text_input("Company name *")
        title = st.text_input("Job title *")
        url = st.text_input("Job URL")
        location = st.text_input("Location")
        employment = st.selectbox("Employment type", ["Not specified", *EMPLOYMENT_TYPES])
        status_value = st.selectbox("Status", STATUSES)
        applied_date = st.date_input("Applied date", value=date.today())
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save application", type="primary")
    if submitted:
        result = api_call(
            "POST",
            "/jobs",
            json={
                "company_name": company,
                "job_title": title,
                "job_url": url or None,
                "location": location or None,
                "employment_type": None if employment == "Not specified" else employment,
                "status": status_value,
                "applied_date": applied_date.isoformat(),
                "notes": notes or None,
            },
        )
        if result is not None:
            st.success("Application saved.")
            st.session_state["job_page"] = 0
            st.rerun()


def _job_label(job: dict[str, Any]) -> str:
    return f'{job["company_name"]} — {job["job_title"]} (#{job["id"]})'


def render_applications() -> list[dict[str, Any]]:
    st.title("Job applications")
    _render_job_form()
    st.divider()
    st.subheader("Your applications")

    with st.form("job_filters_form"):
        search = st.text_input("Search company or job title")
        selected_status = st.selectbox("Filter by status", ["All", *STATUSES])
        sort_by = st.selectbox(
            "Sort by",
            ["created_at", "applied_date", "company_name", "job_title", "status"],
        )
        sort_order = st.selectbox("Sort order", ["desc", "asc"])
        page_size = st.selectbox("Applications per page", PAGE_SIZE_OPTIONS, index=1)
        apply_filters = st.form_submit_button("Apply filters")
    if apply_filters:
        st.session_state["job_filters"] = {
            "search": search,
            "status": None if selected_status == "All" else selected_status,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "limit": page_size,
        }
        st.session_state["job_page"] = 0

    filters = st.session_state.get(
        "job_filters",
        {"search": "", "status": None, "sort_by": "created_at", "sort_order": "desc", "limit": 20},
    )
    page = st.session_state.get("job_page", 0)
    params = {
        "skip": page * filters["limit"],
        "limit": filters["limit"],
        "sort_by": filters["sort_by"],
        "sort_order": filters["sort_order"],
    }
    if filters["search"].strip():
        params["search"] = filters["search"].strip()
    if filters["status"]:
        params["status"] = filters["status"]
    page_data = api_call("GET", "/jobs", params=params)
    if page_data is None:
        return []

    jobs = page_data["items"]
    st.caption(f'{page_data["total"]} application(s)')
    if jobs:
        st.dataframe(
            [
                {
                    "Company": job["company_name"],
                    "Job title": job["job_title"],
                    "Location": job["location"] or "—",
                    "Type": job["employment_type"] or "—",
                    "Status": job["status"],
                    "Applied": job["applied_date"],
                    "Job ID": job["id"],
                }
                for job in jobs
            ],
            width="stretch",
            hide_index=True,
        )
        _render_edit_delete(jobs)
    else:
        st.info("No applications match these filters.")

    page_count = max(1, (page_data["total"] + filters["limit"] - 1) // filters["limit"])
    previous, page_label, next_button = st.columns([1, 2, 1])
    with previous:
        if st.button("Previous", disabled=page <= 0):
            st.session_state["job_page"] = page - 1
            st.rerun()
    with page_label:
        st.caption(f"Page {page + 1} of {page_count}")
    with next_button:
        if st.button("Next", disabled=page + 1 >= page_count):
            st.session_state["job_page"] = page + 1
            st.rerun()
    return jobs


def _render_edit_delete(jobs: list[dict[str, Any]]) -> None:
    selected = st.selectbox("Select an application to edit or delete", jobs, format_func=_job_label)

    with st.expander("Edit application"):
        with st.form(f"edit_job_{selected['id']}"):
            company = st.text_input("Company name", value=selected["company_name"])
            title = st.text_input("Job title", value=selected["job_title"])
            url = st.text_input("Job URL", value=selected["job_url"] or "")
            location = st.text_input("Location", value=selected["location"] or "")
            employment_options = ["Not specified", *EMPLOYMENT_TYPES]
            employment_current = selected["employment_type"] or "Not specified"
            employment_index = (
                employment_options.index(employment_current)
                if employment_current in employment_options
                else 0
            )
            employment = st.selectbox(
                "Employment type",
                employment_options,
                index=employment_index,
            )
            status_index = STATUSES.index(selected["status"])
            status_value = st.selectbox("Status", STATUSES, index=status_index)
            applied_date = st.date_input(
                "Applied date",
                value=date.fromisoformat(selected["applied_date"]),
            )
            notes = st.text_area("Notes", value=selected["notes"] or "")
            submitted = st.form_submit_button("Save changes")
        if submitted:
            result = api_call(
                "PATCH",
                f'/jobs/{selected["id"]}',
                json={
                    "company_name": company,
                    "job_title": title,
                    "job_url": url or None,
                    "location": location or None,
                    "employment_type": None if employment == "Not specified" else employment,
                    "status": status_value,
                    "applied_date": applied_date.isoformat(),
                    "notes": notes or None,
                },
            )
            if result is not None:
                st.success("Application updated.")
                st.rerun()

    with st.expander("Delete application"):
        confirmed = st.checkbox(
            f'Confirm deletion of {_job_label(selected)}',
            key=f'confirm_delete_{selected["id"]}',
        )
        if st.button("Delete application", disabled=not confirmed, type="secondary"):
            deleted = api_call("DELETE", f'/jobs/{selected["id"]}')
            if deleted:
                st.success("Application deleted.")
                st.rerun()


def render_resume_analysis() -> None:
    st.title("Resume analysis")
    st.caption("Your text is sent to the configured local Ollama service for this request.")
    with st.form("resume_analysis_form"):
        resume_text = st.text_area("Resume text", height=240)
        job_description = st.text_area("Job description", height=240)
        submitted = st.form_submit_button("Analyze match", type="primary")
    if not submitted:
        return
    result = api_call(
        "POST",
        "/ai/analyze-resume",
        json={"resume_text": resume_text, "job_description": job_description},
    )
    if result is None:
        return

    st.subheader("Resume summary")
    st.write(result["resume_summary"])
    st.subheader("Job-match summary")
    st.write(result["job_match_summary"])
    matching, missing = st.columns(2)
    with matching:
        st.subheader("Matching skills")
        if result["matching_skills"]:
            for skill in result["matching_skills"]:
                st.markdown(f'- **{skill["skill"]}** — {"; ".join(skill["evidence"])}')
        else:
            st.info("No matching skills were identified.")
    with missing:
        st.subheader("Missing or underrepresented")
        if result["missing_or_underrepresented_skills"]:
            for skill in result["missing_or_underrepresented_skills"]:
                st.markdown(
                    f'- **{skill["skill"]}** — {("; ".join(skill["job_description_evidence"]))}'
                )
        else:
            st.info("No skill gaps were identified.")
    st.subheader("Relevant experience")
    for item in result["relevant_experience_highlights"]:
        st.markdown(f'- {item["claim"]} — {"; ".join(item["evidence"])}')
    st.subheader("Improvement suggestions")
    for item in result["actionable_improvement_suggestions"]:
        st.markdown(f'- {item["suggestion"]} — {"; ".join(item["evidence"])}')


def render_application_assistance(jobs: list[dict[str, Any]] | None = None) -> None:
    st.title("Application assistance")
    st.caption("Get local AI suggestions based on one of your saved applications.")
    if jobs is None:
        page_data = api_call("GET", "/jobs", params={"skip": 0, "limit": 100})
        if page_data is None:
            return
        jobs = page_data["items"]
    if not jobs:
        st.info("Add a job application before requesting application assistance.")
        return

    selected = st.selectbox(
        "Choose an application",
        jobs,
        format_func=_job_label,
        key="assistance_job",
    )
    if st.button("Summarize and suggest next steps", type="primary"):
        result = api_call("POST", f'/ai/jobs/{selected["id"]}/assistance')
        if result is None:
            return
        st.subheader("Application summary")
        st.write(result["summary"])
        st.subheader("Suggested next steps")
        for step in result["next_steps"]:
            st.markdown(f'- {step["suggestion"]} — {"; ".join(step["evidence"])}')


def main() -> None:
    st.set_page_config(
        page_title="AI Job Application Tracker",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container {max-width: 1280px; padding-top: 2rem; padding-bottom: 3rem;}
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, rgba(59,130,246,.10), rgba(99,102,241,.08));
            border: 1px solid rgba(100,116,139,.18);
            padding: 1rem; border-radius: 14px;
        }
        div.stButton > button[kind="primary"] {border-radius: 9px;}
        @media (max-width: 700px) {
            .block-container {padding-left: 1rem; padding-right: 1rem;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.get("access_token"):
        render_authentication()
        return

    user = st.session_state.get("current_user", {})
    with st.sidebar:
        st.title("Application tracker")
        st.caption(user.get("name", "Signed in"))
        page_name = st.radio(
            "Navigate",
            ["Dashboard", "Applications", "Resume analysis", "Application assistance"],
            label_visibility="collapsed",
        )
        if st.button("Log out", use_container_width=True):
            clear_authentication()
            st.rerun()
        st.divider()
        st.caption("AI requests use your configured local Ollama service.")

    if page_name == "Dashboard":
        render_dashboard()
    elif page_name == "Applications":
        render_applications()
    elif page_name == "Resume analysis":
        render_resume_analysis()
    else:
        render_application_assistance()


if __name__ == "__main__":
    main()
