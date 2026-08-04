import json
import time
from google import genai
from google.genai import types        
from src import config

_client = None


def get_client():
    """Lazily creates the Gemini client on first real use, so importing this
    module never crashes just because no API key is configured yet."""
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise ValueError(
                "No GEMINI_API_KEY found. Add one to your .env file (local) or "
                "to Streamlit secrets (deployed) — get a free key at "
                "https://aistudio.google.com"
            )
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def call_agent(system_prompt: str, user_prompt: str, model: str = None) -> dict:
    """Calls Gemini with JSON mode enabled. Retries on free-tier rate limits
    using settings from config.py — no numbers hardcoded here."""
    client = get_client()
    active_model = model or config.GEMINI_MODEL
    generation_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        max_output_tokens=config.MAX_OUTPUT_TOKENS,
    )

    last_error = None
    for attempt in range(config.MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=active_model,
                contents=user_prompt,
                config=generation_config,
            )
            return json.loads(response.text)
        except Exception as e:
            last_error = e
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = config.RETRY_BASE_WAIT_SECONDS * (attempt + 1)
                time.sleep(wait)
            else:
                raise
    if active_model != config.GEMINI_FALLBACK_MODEL:
        try:
            response = client.models.generate_content(
                model=config.GEMINI_FALLBACK_MODEL,
                contents=user_prompt,
                config=generation_config,
            )
            return json.loads(response.text)
        except Exception as e:
            last_error = e
    raise RuntimeError(f"Failed after {config.MAX_RETRIES} retries: {last_error}")


def run_researcher(
    company_name: str = None,
    partial_domain: str = None,
    ip_address: str = None,
    location: str = None,
    model: str = None,
) -> dict:
    """Identifies and profiles a company. Can work from a company name (most
    reliable), or — when no name is given — from an IP address and/or location,
    simulating the "reverse IP lookup" identification approach named in the
    brief. IP-only identification is inherently lower-confidence than a known
    company name, and the prompt asks the model to say so explicitly rather
    than inventing false precision."""
    system = """You are a B2B account research agent. You may be given a company
name directly, OR only an IP address and/or location with no company name — in
that second case, act as a simulated reverse-IP-lookup research agent: infer the
MOST LIKELY type of company/organization that IP range and location could belong
to, clearly treating this as a lower-confidence inference rather than a verified
identification.

Return ONLY valid JSON matching this schema, and nothing else:
{
  "company": {"name": "", "domain": "", "industry": "", "employee_count": 0,
    "headquarters": "", "founded_year": 0, "description": ""},
  "tech_stack": {"crm": "", "marketing_automation": "", "website_platform": "", "analytics": ""},
  "business_signals": [""],
  "leadership": [{"name": "", "title": ""}]
}

Rules:
- If given a company name, identify and profile that specific real or
  realistic company as usual.
- If given ONLY an IP address/location with no company name, do not invent a
  specific real company name with false confidence. Instead, return a
  clearly-labeled placeholder/generic profile (e.g. company.name like
  "Unidentified Visitor (IP-based inference)") and explain in
  company.description that this is a simulated reverse-IP inference limited by
  available data, naming the most plausible industry/company type given the
  location and any other signals.
- If you cannot verify a field, make a reasonable inference rather than
  leaving it blank, and note uncertainty in business_signals or description
  instead of inventing false precision."""

    if company_name and company_name.strip():
        user = f'Company name: "{company_name}". Partial domain: {partial_domain or "none provided"}.'
    elif ip_address or location:
        user = (
            f"No company name provided. Identify the likely company via simulated "
            f"reverse IP lookup. IP address: {ip_address or 'not provided'}. "
            f"Location: {location or 'not provided'}."
        )
    else:
        raise ValueError("Must provide either a company_name or an ip_address/location.")

    return call_agent(system, user, model)


def run_scorer(visitor_signals: dict, model: str = None) -> dict:
    system = """You are a visitor-behavior analyst. Given raw browsing signals,
infer the visitor's likely persona and an intent score. Return ONLY valid JSON,
nothing else:
{
  "persona": {"likely_role": "", "confidence": 0.0},
  "intent": {"score": 0.0, "stage": "Awareness"}
}

IMPORTANT ON SCORING:
- "intent.score" is on a 0 TO 10 scale, NOT 0 to 1. Do not confuse it with
  "persona.confidence", which IS 0 to 1.
- Strong signals (pricing page visits, product/demo pages, case studies,
  3+ visits in a week, 2+ minutes on site) should score in the 7-9 range,
  matching stage "Evaluation" or "Decision".
- Moderate signals (1-2 relevant pages, 1-2 visits) should score 4-6,
  stage "Evaluation".
- Weak/no signals (no pages, single short visit, blog-only browsing)
  should score 0-3, stage "Awareness".
- Example: pages ["/pricing", "/case-studies"], 3 visits this week,
  222 seconds on site -> score should be around 8.0-8.5, stage "Evaluation".
"stage" must be exactly one of: "Awareness", "Evaluation", "Decision"."""
    user = f"Visitor signals: {json.dumps(visitor_signals)}"
    return call_agent(system, user, model)


def run_strategist(company_profile: dict, scoring: dict, model: str = None) -> dict:
    system = """You are a sales strategist. Given a company profile and visitor
scoring data, write a 2-3 sentence plain-English summary and concrete next actions
for a salesperson. Return ONLY valid JSON, nothing else:
{
  "ai_summary": "",
  "recommended_action": {"summary": "", "next_steps": [""]},
  "confidence_notes": ""
}
Reference specific facts from the input (company name, pages visited, industry) —
do not write a generic summary that could apply to any company. If the company
profile is a low-confidence IP-based inference rather than a named company,
say so plainly in confidence_notes and recommend identity confirmation as a
next step before outreach."""
    user = f"Company profile: {json.dumps(company_profile)}\nScoring: {json.dumps(scoring)}"
    return call_agent(system, user, model)


def run_qna(question: str, account_intel: dict, model: str = None) -> str:
    """Answers a free-form sales question grounded in one account's already-
    generated intelligence (company profile, tech stack, persona, intent,
    recommended action, etc.) — no new research, just reasoning over that data."""
    system = """You are a B2B sales research assistant. Answer the sales rep's
question using ONLY the account intelligence data provided as context — do not
invent facts it doesn't support. Be direct and concise (a few sentences, plain
English, no filler, no restating the question). If the data doesn't contain
enough information to answer confidently, say so plainly and note what's missing
rather than guessing.

Return ONLY valid JSON matching this schema, and nothing else:
{"answer": ""}"""
    user = f"Account intelligence:\n{json.dumps(account_intel)}\n\nQuestion: {question}"
    result = call_agent(system, user, model)
    return result.get("answer", "")


def run_full_pipeline(
    company_name: str = None,
    partial_domain: str = None,
    visitor_signals: dict = None,
    ip_address: str = None,
    location: str = None,
    model: str = None,
) -> dict:
    researcher_output = run_researcher(
        company_name=company_name,
        partial_domain=partial_domain,
        ip_address=ip_address,
        location=location,
        model=model,
    )

    signals_for_scoring = visitor_signals or {
        "pages_visited": [],
        "time_on_site_seconds": 0,
        "visits_this_week": 0,
    }
    scorer_output = run_scorer(signals_for_scoring, model)

    strategist_output = run_strategist(researcher_output, scorer_output, model)

    return {
        "company": researcher_output["company"],
        "tech_stack": researcher_output["tech_stack"],
        "business_signals": researcher_output["business_signals"],
        "leadership": researcher_output["leadership"],
        "persona": scorer_output["persona"],
        "intent": scorer_output["intent"],
        "ai_summary": strategist_output["ai_summary"],
        "recommended_action": strategist_output["recommended_action"],
        "confidence_notes": strategist_output["confidence_notes"],
    }