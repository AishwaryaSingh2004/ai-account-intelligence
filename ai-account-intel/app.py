import streamlit as st

from src import config
from src.agents import run_full_pipeline, run_qna
from src.validate import validate_intel
from src.report import build_pdf

st.set_page_config(page_title="AI Account Intelligence", layout="wide")

# ---------- CONFIG: driven by .env / Streamlit secrets, no customer-facing settings panel ----------
model_choice = config.GEMINI_MODEL

st.title("AI Account Intelligence")
st.caption("Enter a company name, OR an IP address with no name at all (simulated "
           "reverse-IP identification) — optionally add browsing behavior for a "
           "sharper intent score.")

# ---------- INPUT ----------
col1, col2 = st.columns(2)

with col1:
    company_name = st.text_input(
        "Company name (optional if IP address is provided below)",
        placeholder="e.g. BrightPath Lending",
    )
    partial_domain = st.text_input("Partial domain (optional)", placeholder="e.g. brightpathlending")

with col2:
    st.caption("Anonymous visitor? Leave company name blank and use IP/location "
               "below instead — simulates reverse-IP company identification.")
    ip_address = st.text_input("IP address (optional)", placeholder="e.g. 34.201.112.55")
    location = st.text_input("Location (optional)", placeholder="e.g. Dallas, TX, USA")

with st.expander("Add visitor behavior (optional)", expanded=False):
    vcol1, vcol2 = st.columns(2)
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

analyze_clicked = st.button("Analyze", type="primary")

pages_visited = [p.strip() for p in pages_visited_raw.split("\n") if p.strip()] if pages_visited_raw else []

# ---------- RUN + RENDER ----------
if analyze_clicked:
    has_identity_input = bool(company_name.strip()) or bool(ip_address.strip()) or bool(location.strip())

    if not has_identity_input:
        st.error("Enter a company name, OR an IP address / location for anonymous-visitor identification.")
    else:
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

        with st.spinner("Researching, scoring, and strategizing..."):
            try:
                raw_result = run_full_pipeline(
                    company_name=company_name.strip() or None,
                    partial_domain=partial_domain or None,
                    visitor_signals=visitor_signals,
                    ip_address=ip_address.strip() or None,
                    location=location.strip() or None,
                    model=model_choice,
                )
                parsed, error = validate_intel(raw_result)

                if error:
                    st.error(f"Model output did not match expected schema:\n\n{error}")
                else:
                    st.session_state.parsed = parsed
                    st.session_state.qna_history = {}
# Catch-all error handling
            except Exception as e:
                st.error(f"Something went wrong: {e}")
                st.caption("If this mentions a rate limit (429), wait ~30-60s, "
                           "or switch the model in the sidebar.")

# ---------- RESULTS + AI RESEARCH AGENT (persisted across reruns, e.g. when asking a question) ----------
if "parsed" in st.session_state:
    parsed = st.session_state.parsed
    if not hasattr(parsed, "risks"):
        del st.session_state["parsed"]  # stale object from before a schema change
        st.info("This app was updated since your last analysis — please click Analyze again.")
        st.stop()
    if not isinstance(st.session_state.get("qna_history"), dict):
        st.session_state.qna_history = {}  # heal stale sessions carrying the old list format
    st.divider()

    # ---- Company Name / Website / Domain / Industry / Company Size / Headquarters ----
    hcol1, hcol2 = st.columns([5, 1])
    hcol1.header(parsed.company.name)
    hcol2.download_button(
        "📄 Download PDF",
        data=build_pdf(parsed),
        file_name=f"{parsed.company.name.replace(' ', '_')}_account_intel.pdf",
        mime="application/pdf",
    )
    st.write(parsed.company.description)

    c1, c2, c3 = st.columns(3)
    c1.metric("Website / Domain", parsed.company.domain or "Unknown")
    c1.metric("Industry", parsed.company.industry)
    c2.metric("Company Size", f"{parsed.company.employee_count} employees" if parsed.company.employee_count else "Unknown")
    c2.metric("Headquarters", parsed.company.headquarters)
    c3.metric("Founded", parsed.company.founded_year or "Unknown")

    st.divider()

    # ---- Technology Stack (formatted, not JSON) ----
    st.subheader("Technology Stack")
    ts = parsed.tech_stack
    tcol1, tcol2 = st.columns(2)
    tcol1.write(f"**CRM:** {ts.crm or 'Unknown'}")
    tcol1.write(f"**Marketing Automation:** {ts.marketing_automation or 'Unknown'}")
    tcol2.write(f"**Website Platform:** {ts.website_platform or 'Unknown'}")
    tcol2.write(f"**Analytics:** {ts.analytics or 'Unknown'}")

    st.divider()

    # ---- Leadership (formatted, not JSON) ----
    st.subheader("Leadership")
    if parsed.leadership:
        for leader in parsed.leadership:
            st.write(f"- **{leader.name}** — {leader.title}")
    else:
        st.write("No leadership identified.")

    st.divider()

    # ---- Business Signals ----
    st.subheader("Business Signals")
    if parsed.business_signals:
        for signal in parsed.business_signals:
            st.write(f"- {signal}")
    else:
        st.write("No business signals identified.")

    sources = getattr(parsed, "sources", [])
    if sources:
        st.caption("Sources (to verify the above):")
        for src in sources:
            st.caption(f"- [{src.title}]({src.url})")

    st.divider()

    # ---- Recent News (useful for marketing/outreach) ----
    recent_news = getattr(parsed, "recent_news", [])
    if recent_news:
        st.subheader("📰 Recent News")
        st.caption("Live search results — useful for marketing and outreach.")
        for item in recent_news:
            date_suffix = f" ({item.date})" if item.date else ""
            st.write(f"**{item.headline}**{date_suffix}")
            st.write(item.summary)

        st.divider()

    # ---- Key Signals Observed (from whatever input you provided) ----
    st.subheader("Key Signals Observed")
    any_signal_shown = False
    if ip_address.strip():
        st.write(f"- IP address provided: {ip_address.strip()}")
        any_signal_shown = True
    if location.strip():
        st.write(f"- Location: {location.strip()}")
        any_signal_shown = True
    if pages_visited:
        st.write(f"- Visited: {', '.join(pages_visited)}")
        any_signal_shown = True
    if visits_this_week:
        st.write(f"- {visits_this_week} visit(s) this week")
        any_signal_shown = True
    if time_on_site:
        st.write(f"- {time_on_site} seconds on site")
        any_signal_shown = True
    if referral_source:
        st.write(f"- Referral source: {referral_source}")
        any_signal_shown = True
    if device:
        st.write(f"- Device: {device}")
        any_signal_shown = True
    if not any_signal_shown:
        st.write("No visitor signals provided — this result is based on company name only.")

    st.divider()

    # ---- Likely Persona / Intent Score / Intent Stage ----
    st.subheader("Intent")

    intent_signal_parts = []
    if pages_visited:
        intent_signal_parts.append(f"{len(pages_visited)} page(s) visited ({', '.join(pages_visited)})")
    if visits_this_week:
        intent_signal_parts.append(f"{visits_this_week} visit(s) this week")
    if time_on_site:
        intent_signal_parts.append(f"{time_on_site} second(s) on site")
    if referral_source:
        intent_signal_parts.append(f"referred via {referral_source}")
    if device:
        intent_signal_parts.append(f"{device} device")

    if intent_signal_parts:
        intent_help = (
            "Calculated from this visitor's browsing behavior — " + "; ".join(intent_signal_parts) +
            ". More pages (especially pricing/demo), more visits this week, and more time on site "
            "push the score higher and move the stage further down the funnel."
        )
    else:
        intent_help = (
            "No visitor behavior was provided for this analysis, so this score is based on the "
            "company profile alone. Add pages visited, visits this week, and time on site above "
            "for a behavior-based score."
        )

    icol1, icol2 = st.columns(2)
    icol1.metric("Intent Score", f"{parsed.intent.score} / 10", help=intent_help)
    icol2.metric("Intent Stage", parsed.intent.stage.value)
    st.write(
        f"Likely Persona: **{parsed.persona.likely_role}** "
        f"({round(parsed.persona.confidence * 100)}% confidence)"
    )

    st.divider()

    # ---- AI Summary ----
    st.subheader("AI Summary")
    st.write(parsed.ai_summary)

    # ---- Recommended Sales Action ----
    st.subheader("Recommended Sales Action")
    st.write(parsed.recommended_action.summary)
    for step in parsed.recommended_action.next_steps:
        st.write(f"- {step}")

    st.info(parsed.confidence_notes)

    st.divider()

    # ---- AI Research Agent: ask free-form questions grounded in this account's data ----
    st.subheader("🔎 AI Research Agent")
    st.caption("Instead of just displaying data, ask AI. Answers are grounded in the "
               "account intelligence above.")

    example_questions = [
        "What is this company's biggest challenge?",
        "How can we sell our product to them?",
        "Who should I contact first?",
        "What is the likelihood they'll buy?",
        "Summarize this company in 30 seconds.",
    ]
    example_clicked = None
    ex_cols = st.columns(len(example_questions))
    for col, q in zip(ex_cols, example_questions):
        if col.button(q, key=f"example_{q}"):
            example_clicked = q

    qcol1, qcol2 = st.columns([4, 1])
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

    if question_to_ask:
        with st.spinner("Thinking..."):
            try:
                answer = run_qna(question_to_ask, parsed.model_dump(), model=model_choice)
                dedup_key = question_to_ask.strip().lower()
                st.session_state.qna_history.pop(dedup_key, None)  # re-asking replaces, not duplicates
                st.session_state.qna_history[dedup_key] = (question_to_ask.strip(), answer)
            except Exception as e:
                st.error(f"Something went wrong answering that: {e}")

    for q, a in reversed(list(st.session_state.get("qna_history", {}).values())):
        st.markdown(f"**Q: {q}**")
        st.write(a)
        st.write("")