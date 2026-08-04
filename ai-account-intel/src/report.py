from fpdf import FPDF

_UNICODE_REPLACEMENTS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "•": "-",
}


def _sanitize(text) -> str:
    """PDF core fonts only support latin-1; Gemini output often includes
    smart punctuation (em dashes, curly quotes) that would otherwise crash
    PDF generation, so normalize known cases and replace anything else
    unencodable rather than failing."""
    text = str(text) if text is not None else ""
    for src, dst in _UNICODE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


RISK_LABELS = {
    "employee_turnover": "High employee turnover",
    "funding_slowdown": "Funding slowdown",
    "negative_news": "Negative news",
    "declining_hiring": "Declining hiring",
    "low_buying_intent": "Low buying intent",
}


def build_pdf(parsed) -> bytes:
    """Renders one AccountIntel result into a downloadable PDF report."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def heading(text, size=13):
        pdf.set_font("Helvetica", "B", size)
        pdf.multi_cell(0, 8, _sanitize(text))
        pdf.ln(1)

    def body(text):
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _sanitize(text))
        pdf.ln(2)

    def bullet(text):
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _sanitize(f"- {text}"))
        pdf.ln()  # multi_cell defaults to leaving x at the right edge; reset to left margin

    c = parsed.company
    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 10, _sanitize(c.name))
    pdf.ln(1)
    body(c.description)
    body(f"Industry: {c.industry}   |   Employees: {c.employee_count or 'Unknown'}")
    body(f"Headquarters: {c.headquarters}   |   Founded: {c.founded_year or 'Unknown'}   |   Domain: {c.domain or 'Unknown'}")

    heading("Technology Stack")
    ts = parsed.tech_stack
    body(f"CRM: {ts.crm or 'Unknown'}   |   Marketing Automation: {ts.marketing_automation or 'Unknown'}")
    body(f"Website Platform: {ts.website_platform or 'Unknown'}   |   Analytics: {ts.analytics or 'Unknown'}")

    heading("Leadership")
    if parsed.leadership:
        for leader in parsed.leadership:
            bullet(f"{leader.name} - {leader.title}")
    else:
        body("No leadership identified.")
    pdf.ln(2)

    heading("Business Signals")
    if parsed.business_signals:
        for signal in parsed.business_signals:
            bullet(signal)
    else:
        body("No business signals identified.")
    pdf.ln(2)

    heading("Intent")
    body(f"Intent Score: {parsed.intent.score} / 10   |   Stage: {parsed.intent.stage.value}")
    body(f"Likely Persona: {parsed.persona.likely_role} ({round(parsed.persona.confidence * 100)}% confidence)")

    heading("Risk Analysis")
    for field, label in RISK_LABELS.items():
        risk = getattr(parsed.risks, field)
        bullet(f"{label}: {risk.level.value} - {risk.explanation}")
    pdf.ln(2)

    heading("AI Summary")
    body(parsed.ai_summary)

    heading("Recommended Sales Action")
    body(parsed.recommended_action.summary)
    for step in parsed.recommended_action.next_steps:
        bullet(step)
    pdf.ln(2)

    heading("Confidence Notes")
    body(parsed.confidence_notes)

    return bytes(pdf.output())
