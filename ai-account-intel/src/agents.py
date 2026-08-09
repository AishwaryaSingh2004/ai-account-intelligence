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
    and on truncated/malformed JSON output (both transient) using settings
    from config.py — no numbers hardcoded here."""
    client = get_client()
    active_model = model or config.GEMINI_MODEL
    generation_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        max_output_tokens=config.MAX_OUTPUT_TOKENS,
    )

    def generate(model_name):
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=generation_config,
        )
        return json.loads(response.text)

    last_error = None
    for attempt in range(config.MAX_RETRIES):
        try:
            return generate(active_model)
        except json.JSONDecodeError as e:
            last_error = e
            time.sleep(config.RETRY_BASE_WAIT_SECONDS * (attempt + 1))
        except Exception as e:
            last_error = e
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                time.sleep(config.RETRY_BASE_WAIT_SECONDS * (attempt + 1))
            else:
                raise
    if active_model != config.GEMINI_FALLBACK_MODEL:
        try:
            return generate(config.GEMINI_FALLBACK_MODEL)
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


def run_risk_analyst(company_profile: dict, scoring: dict, model: str = None) -> dict:
    """Assesses a fixed set of account-risk categories from the company profile
    and visitor scoring data — flags that matter to a salesperson deciding
    whether/how hard to pursue an account."""
    system = """You are a B2B account risk analyst. Given a company profile and
visitor/intent scoring data, assess exactly these five risk categories for this
account. Return ONLY valid JSON matching this schema, and nothing else:
{
  "employee_turnover": {"level": "Low", "explanation": ""},
  "funding_slowdown": {"level": "Low", "explanation": ""},
  "negative_news": {"level": "Low", "explanation": ""},
  "declining_hiring": {"level": "Low", "explanation": ""},
  "low_buying_intent": {"level": "Low", "explanation": ""}
}

Rules:
- "level" must be exactly one of "Low", "Medium", "High".
- Base each assessment on real signals in the company profile and scoring data
  (industry, company size/stage, business_signals, intent score/stage) where
  available. If there's no direct evidence for a category, infer a reasonable
  baseline for a company of this profile/industry and say plainly in the
  explanation that it's an inferred baseline, not observed evidence — never
  default everything to "Low" with no reasoning.
- "low_buying_intent" must specifically reference the visitor's intent score
  and stage from the scoring data: score 7-10 / stage Decision or Evaluation
  should be "Low" risk; score 4-6 should be "Medium"; score 0-3 / stage
  Awareness should be "High" risk.
- Keep each explanation to one concise sentence."""
    user = f"Company profile: {json.dumps(company_profile)}\nScoring: {json.dumps(scoring)}"
    return call_agent(system, user, model)


def run_news_and_sources(company_name: str, domain: str = None, model: str = None) -> dict:
    """Uses live Google Search grounding to find real, recent news about the
    company and real source links a salesperson/marketer can use to verify
    the account data — separate from the other agents because Gemini's JSON
    response-schema mode isn't supported together with the search tool, so
    this call asks for raw JSON in the prompt and parses it manually.

    Best-effort: search grounding isn't always available on free-tier keys
    (it can hit its own quota independent of the other calls), so callers
    should treat failures here as "no news found" rather than fatal."""
    client = get_client()
    active_model = model or config.GEMINI_MODEL
    system = """You are a B2B research assistant with access to live Google Search.
Find real, recent news about the given company, and real source links a
salesperson or marketer could use to verify facts about the company.

Return ONLY raw JSON (no markdown, no code fences, no commentary) matching
exactly this schema:
{
  "recent_news": [{"headline": "", "summary": "", "date": ""}],
  "sources": [{"title": "", "url": ""}]
}

Rules:
- "recent_news": up to 5 real, dated news items from roughly the last 12
  months if available (funding, leadership changes, product launches,
  expansion, layoffs, notable press) — written to be useful for a marketing
  team crafting outreach. If you genuinely find no recent news, return an
  empty list — never invent items.
- "sources": real URLs you actually found via search (company site, news
  articles, LinkedIn, Crunchbase, etc.) that back up who this company is —
  never invented URLs.
- "date" should be an approximate date or time frame (e.g. "2026-03" or
  "March 2026") if known, else an empty string."""
    domain_note = f" (domain: {domain})" if domain else ""
    user = f'Company: "{company_name}"{domain_note}. Find recent news and verification sources.'

    generation_config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        max_output_tokens=config.MAX_OUTPUT_TOKENS,
    )
    response = client.models.generate_content(
        model=active_model, contents=user, config=generation_config,
    )
    text = response.text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    result = json.loads(text)
    result.setdefault("recent_news", [])
    result.setdefault("sources", [])

    # Merge in the real grounding source URLs Google Search actually used,
    # in case the model didn't already list them under "sources".
    known_urls = {s.get("url") for s in result["sources"]}
    try:
        chunks = response.candidates[0].grounding_metadata.grounding_chunks or []
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            if web and web.uri and web.uri not in known_urls:
                result["sources"].append({"title": web.title or web.uri, "url": web.uri})
                known_urls.add(web.uri)
    except Exception:
        pass

    return result


def run_qna(question: str, account_intel: dict, model: str = None) -> str:
    """Answers a free-form sales question grounded in one account's already-
    generated intelligence (company profile, tech stack, persona, intent,
    recommended action, etc.) — no new research, just reasoning over that data."""
    system = """You are a B2B sales research assistant. Answer the sales rep's
question with a specific, concrete answer synthesized from the account
intelligence data provided as context (company profile, tech stack, business
signals, persona, intent, risks, recommended action) — do not invent facts the
data doesn't support, but actively reason over and combine what IS there rather
than only repeating literal fields verbatim.

Rules:
- Never open with a disclaimer like "the data doesn't explicitly state X."
  Give the specific answer directly, grounded in concrete details you do have
  (company name, industry, tech stack, business signals, intent score/stage,
  risk levels).
- Only if the account data contains literally nothing relevant to the
  question, say so in one sentence and name the single most useful next step
  to find out — still no other hedging.
- Be direct and concise (2-4 sentences, plain English, no filler, no restating
  the question).

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
    risk_output = run_risk_analyst(researcher_output, scorer_output, model)

    try:
        news_output = run_news_and_sources(
            researcher_output["company"]["name"],
            researcher_output["company"].get("domain"),
            model,
        )
    except Exception:
        # Search grounding has its own quota separate from the other calls —
        # degrade to "no news found" rather than failing the whole pipeline.
        news_output = {"recent_news": [], "sources": []}

    return {
        "company": researcher_output["company"],
        "tech_stack": researcher_output["tech_stack"],
        "business_signals": researcher_output["business_signals"],
        "leadership": researcher_output["leadership"],
        "persona": scorer_output["persona"],
        "intent": scorer_output["intent"],
        "ai_summary": strategist_output["ai_summary"],
        "recommended_action": strategist_output["recommended_action"],
        "risks": risk_output,
        "recent_news": news_output.get("recent_news", []),
        "sources": news_output.get("sources", []),
        "confidence_notes": strategist_output["confidence_notes"],
    }