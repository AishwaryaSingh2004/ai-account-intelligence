import importlib
import ipaddress
import re
from pathlib import Path

import streamlit as st

import src
from src import config, schema, validate, agents, report, ui

# Streamlit re-executes this script after a deploy but keeps already-imported
# modules in memory, so a new app.py could call an old src/agents.py (this
# caused "unexpected keyword argument 'on_step'" in production). Reload the
# project's own modules whenever their files change. Order matters:
# dependencies first.
_src_version = max(f.stat().st_mtime_ns for f in Path(src.__file__).parent.glob("*.py"))
if getattr(src, "_loaded_version", None) != _src_version:
    for _module in (config, schema, validate, agents, report, ui):
        importlib.reload(_module)
    src._loaded_version = _src_version

run_full_pipeline, run_qna = agents.run_full_pipeline, agents.run_qna
validate_intel = validate.validate_intel
build_pdf = report.build_pdf

st.set_page_config(page_title="AI Account Intelligence", page_icon="🛰️", layout="wide")

# ---------- CONFIG: driven by .env / Streamlit secrets, no customer-facing settings panel ----------
model_choice = config.GEMINI_MODEL

st.markdown(ui.CSS, unsafe_allow_html=True)
st.html(ui.hero_html())

# ---------- INPUT ----------
with st.container(key="input_panel"):
    st.html(ui.panel_head_html())
    with st.container(key="id_cols"):
        col1, col2 = st.columns(2)

        with col1:
            st.html(ui.col_head_html("01", "Known company", "Most accurate",
                                     "A name is all you need. The domain helps tell similar names apart."))
            company_name = st.text_input("Company name", placeholder="e.g. BrightPath Lending")
            partial_domain = st.text_input("Website or domain", placeholder="e.g. brightpathlending.com")

        with col2:
            st.html(ui.col_head_html("02", "Anonymous visitor", "Reverse-IP",
                                     "No name? The agents infer the likely company from where the visit came from.",
                                     alt=True))
            ip_address = st.text_input("IP address", placeholder="e.g. 34.201.112.55")
            location = st.text_input("Location", placeholder="e.g. Dallas, TX, USA")

    with st.expander("**Add visitor behavior** :gray[(optional, gives a sharper intent score)]", expanded=False):
        vcol1, vcol2 = st.columns(2, gap="large")
        with vcol1:
            pages_visited_raw = st.text_area(
                "Pages visited (one per line)",
                placeholder="/pricing\n/ai-sales-agent\n/case-studies",
            )
            referral_source = st.text_input("Referral source", placeholder="e.g. google_organic")
        with vcol2:
            time_on_site = st.number_input("Time on site (seconds)", min_value=0, value=0)
            visits_this_week = st.number_input("Visits this week", min_value=0, value=0)
            device = st.selectbox("Device", ["", "desktop", "mobile", "tablet", "unknown"])

    with st.container(key="go_row", horizontal=True):
        analyze_clicked = st.button("Run the agents  →", type="primary")
        st.html(ui.go_hint_html())

pages_visited = [p.strip() for p in pages_visited_raw.split("\n") if p.strip()] if pages_visited_raw else []


def observed_signals(ip: str) -> list:
    """The visitor inputs as short chips, captured at analysis time so editing
    the form afterwards doesn't change what an existing report shows."""
    out = []
    if ip:
        out.append(f"IP {ip}")
    if location.strip():
        out.append(f"Location: {location.strip()}")
    out += [f"Visited {p}" for p in pages_visited]
    if visits_this_week:
        out.append(f"{visits_this_week} visit(s) this week")
    if time_on_site:
        out.append(f"{time_on_site}s on site")
    if referral_source:
        out.append(f"Referral: {referral_source}")
    if device:
        out.append(f"Device: {device}")
    return out


def intent_explanation() -> str:
    parts = []
    if pages_visited:
        parts.append(f"{len(pages_visited)} page(s) visited ({', '.join(pages_visited)})")
    if visits_this_week:
        parts.append(f"{visits_this_week} visit(s) this week")
    if time_on_site:
        parts.append(f"{time_on_site} second(s) on site")
    if referral_source:
        parts.append(f"referred via {referral_source}")
    if device:
        parts.append(f"{device} device")
    if parts:
        return (
            "Calculated from this visitor's browsing behavior: " + "; ".join(parts) +
            ". More pages (especially pricing/demo), more visits this week, and more time on site "
            "push the score higher and move the stage further down the funnel."
        )
    return (
        "No visitor behavior was provided for this analysis, so this score is based on the "
        "company profile alone. Add pages visited, visits this week, and time on site "
        "for a behavior-based score."
    )


def friendly_error(e: Exception) -> str:
    """Plain-English message for the errors a user can actually hit."""
    if agents.is_overloaded(e):
        return "Gemini is overloaded right now (a temporary Google-side issue). Please try again in a minute."
    if agents.is_rate_limited(e):
        return "The Gemini rate limit was reached. Please wait 30 to 60 seconds and try again."
    if "API key" in str(e) or "GEMINI_API_KEY" in str(e):
        return f"Gemini API key problem: {e}"
    return f"Something went wrong: {e}"


# ---------- RUN ----------
if analyze_clicked:
    name = company_name.strip()
    domain = partial_domain.strip()
    ip = ip_address.strip()
    if not name and domain:
        name = agents.normalize_domain(domain) or domain  # a website alone is enough to identify a company
    has_identity_input = bool(name or ip or location.strip())

    ip_error = None
    if ip:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            ip_error = f"\"{ip}\" isn't a valid IP address. Use a format like 34.201.112.55 (IPv4) or 2001:db8::1 (IPv6)."

    if not has_identity_input:
        st.error("Enter a company name or website, OR an IP address / location for anonymous-visitor identification.")
    elif ip_error and not name:
        st.error(ip_error)
    else:
        if ip_error:
            st.warning(ip_error + " It was ignored; the analysis uses the company name.")
            ip = ""

        has_behavior_data = bool(pages_visited or time_on_site or visits_this_week or referral_source or device)

        visitor_signals = None
        if has_behavior_data:
            visitor_signals = {
                "pages_visited": pages_visited,
                "time_on_site_seconds": time_on_site,
                "visits_this_week": visits_this_week,
                "referral_source": referral_source or None,
                "device": device or None,
            }

        tracker = st.empty()
        try:
            raw_result = run_full_pipeline(
                company_name=name or None,
                partial_domain=domain or None,
                visitor_signals=visitor_signals,
                ip_address=ip or None,
                location=location.strip() or None,
                model=model_choice,
                on_step=lambda key: tracker.html(ui.tracker_html(key)),
            )
            tracker.empty()
            parsed, error = validate_intel(raw_result)

            if error:
                st.error(f"Model output did not match expected schema:\n\n{error}")
            else:
                st.session_state.parsed = parsed
                st.session_state.observed = observed_signals(ip)
                st.session_state.intent_help = intent_explanation()
                st.session_state.qna_history = {}
                st.session_state.qna_input = ""  # a new report starts with an empty question box
        # Catch-all error handling
        except Exception as e:
            tracker.empty()
            st.error(friendly_error(e))

# ---------- RESULTS + AI RESEARCH AGENT (persisted across reruns, e.g. when asking a question) ----------
if "parsed" in st.session_state:
    parsed = st.session_state.parsed
    if not hasattr(parsed, "risks"):
        del st.session_state["parsed"]  # stale object from before a schema change
        st.info("This app was updated since your last analysis. Please click \"Run the agents\" again.")
        st.stop()
    if not isinstance(st.session_state.get("qna_history"), dict):
        st.session_state.qna_history = {}  # heal stale sessions carrying the old list format
    observed = st.session_state.get("observed", [])
    intent_help = st.session_state.get("intent_help") or intent_explanation()

    hcol1, hcol2 = st.columns([4, 1], vertical_alignment="bottom")
    with hcol1:
        st.html(ui.results_head_html(parsed.company.name))
    with hcol2:
        st.download_button(
            "⬇  Download PDF",
            data=build_pdf(parsed),
            file_name=f"{re.sub(r'[^A-Za-z0-9._-]+', '_', parsed.company.name).strip('_') or 'account'}_account_intel.pdf",
            mime="application/pdf",
        )

    st.html(ui.company_and_intent_html(parsed, intent_help))
    st.html(ui.stack_and_people_html(parsed))
    st.html(ui.signals_html(parsed, observed))
    news = ui.news_html(parsed)
    if news:
        st.html(news)
    st.html(ui.strategy_html(parsed))

    # ---- AI Research Agent: ask free-form questions grounded in this account's data ----
    st.html(ui.qna_head_html())

    example_questions = [
        "What is this company's biggest challenge?",
        "How can we sell our product to them?",
        "Who should I contact first?",
        "What is the likelihood they'll buy?",
        "Summarize this company in 30 seconds.",
    ]
    example_clicked = None
    with st.container(key="examples", horizontal=True):
        for q in example_questions:
            if st.button(q, key=f"example_{q}"):
                example_clicked = q

    qcol1, qcol2 = st.columns([5, 1], vertical_alignment="bottom")
    with qcol1:
        custom_question = st.text_input(
            "Ask AI a question about this account",
            placeholder="e.g. What is this company's biggest challenge?",
            key="qna_input",
            label_visibility="collapsed",
        )
    with qcol2:
        ask_clicked = st.button("Ask AI", type="primary", key="ask_ai_button")

    question_to_ask = example_clicked or (custom_question.strip() if ask_clicked and custom_question.strip() else None)
    if ask_clicked and not question_to_ask:
        st.warning("Type a question first, or pick one of the examples above.")

    if question_to_ask:
        with st.spinner("Thinking..."):
            try:
                answer = run_qna(question_to_ask, parsed.model_dump(), model=model_choice)
                dedup_key = question_to_ask.strip().lower()
                st.session_state.qna_history.pop(dedup_key, None)  # re-asking replaces, not duplicates
                st.session_state.qna_history[dedup_key] = (question_to_ask.strip(), answer)
            except Exception as e:
                st.error(friendly_error(e))

    history = list(reversed(list(st.session_state.get("qna_history", {}).values())))
    qa = ui.qna_html(history)
    if qa:
        st.html(qa)
