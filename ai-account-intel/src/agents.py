import json
import time
from concurrent.futures import ThreadPoolExecutor
import httpx
from google import genai
from google.genai import types        
from pydantic import ValidationError

from src import config, schema

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
        # A timeout so a stalled request fails over to the next model instead
        # of hanging the app forever (the SDK has none by default).
        _client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=config.REQUEST_TIMEOUT_SECONDS * 1000),
        )
    return _client


_RATE_LIMIT_CODES = {429}
_SERVER_ERROR_CODES = {500, 502, 503, 504}
_MODEL_GONE_CODES = {404}


def _error_code(e: Exception):
    code = getattr(e, "code", None)
    if isinstance(code, int):
        return code
    text = str(e)
    for c in _RATE_LIMIT_CODES | _SERVER_ERROR_CODES | _MODEL_GONE_CODES:
        if text.startswith(str(c)) or f"'code': {c}" in text:
            return c
    return None


def is_rate_limited(e: Exception) -> bool:
    return _error_code(e) in _RATE_LIMIT_CODES or "RESOURCE_EXHAUSTED" in str(e)


def is_overloaded(e: Exception) -> bool:
    """Google-side outages: the model is busy (503), errored (5xx), timed out
    or the connection dropped."""
    text = str(e)
    return (
        isinstance(e, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))
        or _error_code(e) in _SERVER_ERROR_CODES
        or "UNAVAILABLE" in text or "DEADLINE_EXCEEDED" in text or "timed out" in text
    )


def model_unavailable(e: Exception) -> bool:
    """The model itself can't be used on this key (retired or not found)."""
    return _error_code(e) in _MODEL_GONE_CODES or "NOT_FOUND" in str(e)


class IncompleteResponse(ValueError):
    """The model's JSON was cut off or is missing fields the agent needs."""


# Newer Gemini models "think" before answering, and those reasoning tokens
# count toward max_output_tokens. With a small limit (the old 1024) the
# answer itself gets cut off mid-JSON, so never go below this floor.
MIN_OUTPUT_TOKENS = 8192


def output_token_limit() -> int:
    return max(config.MAX_OUTPUT_TOKENS, MIN_OUTPUT_TOKENS)


def call_agent(system_prompt: str, user_prompt: str, output_schema, model: str = None,
               temperature: float = None) -> dict:
    """Calls Gemini with JSON mode enabled, using settings from config.py.

    Transient failures are handled without failing the run: a rate-limited
    (429), overloaded (5xx) or retired/unknown (404) model switches straight
    to the next fallback model, since each model has its own quota; malformed
    or incomplete JSON is retried on the same model. The last model in the
    chain waits and retries before giving up. Anything else (bad key, bad
    request) fails immediately, since retrying can't fix it.

    `output_schema` (a Pydantic model) is sent to Gemini as the response
    schema, so the model is constrained to that structure, and the answer is
    validated against it; a truncated or mis-shaped answer is retried like
    bad JSON. Returns plain JSON-compatible data."""
    client = get_client()
    active_model = model or config.GEMINI_MODEL
    generation_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=output_schema,
        max_output_tokens=output_token_limit(),
        temperature=temperature,
    )

    def generate(model_name):
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=generation_config,
        )
        finish = getattr(response.candidates[0], "finish_reason", None) if response.candidates else None
        if finish is not None and getattr(finish, "name", str(finish)) == "MAX_TOKENS":
            raise IncompleteResponse(f"{model_name} hit the output token limit")
        try:
            parsed = output_schema.model_validate(json.loads(response.text or ""))
        except ValidationError as e:
            raise IncompleteResponse(f"{model_name} returned the wrong structure: {e.errors()[:3]}") from e
        return parsed.model_dump(mode="json")

    models = list(dict.fromkeys([active_model, *config.FALLBACK_MODELS]))

    last_error = None
    for i, model_name in enumerate(models):
        is_last_model = i == len(models) - 1
        for attempt in range(config.MAX_RETRIES):
            try:
                return generate(model_name)
            except (json.JSONDecodeError, IncompleteResponse) as e:
                last_error = e
                continue  # a fresh attempt can fix a bad answer; no need to wait
            except Exception as e:
                last_error = e
                if model_unavailable(e):
                    break  # retired or unknown model: move on to the next one
                if (is_overloaded(e) or is_rate_limited(e)) and not is_last_model:
                    break  # busy or rate-limited (quotas are per model): try the next one instead of waiting
                if not (is_overloaded(e) or is_rate_limited(e)):
                    raise
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(config.RETRY_BASE_WAIT_SECONDS * (attempt + 1))
    raise RuntimeError(f"Gemini failed on {', '.join(models)} after retries: {last_error}")


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
- When you can't verify a field but have a reasonable basis (industry,
  location, typical company of this type), give your best inference and note
  the uncertainty in the description. When you have no basis at all, use null.
- Never claim you performed a lookup you cannot perform (WHOIS, reverse DNS,
  database checks). Phrase IP-based findings as inferences ("likely", "appears").
- Use null for any field you have no basis for (domain, employee_count,
  founded_year, tech_stack values) rather than "N/A", "unknown" or 0, and
  return an empty leadership list rather than placeholder people.
- Only list leaders you are confident really hold that role at this specific
  company (e.g. widely reported executives of well-known companies). For small,
  obscure or unfamiliar companies, return an empty leadership list. Never make
  up names."""

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

    return call_agent(system, user, schema.ResearchOutput, model)


NO_SIGNAL_SCORING = {
    "persona": {"likely_role": "Unknown (no visitor behavior provided)", "confidence": 0.0},
    "intent": {"score": 0.0, "stage": "Awareness"},
}


def has_behavior(visitor_signals: dict) -> bool:
    if not visitor_signals:
        return False
    return any(visitor_signals.get(k) for k in
               ("pages_visited", "time_on_site_seconds", "visits_this_week", "referral_source", "device"))


def run_scorer(visitor_signals: dict, model: str = None) -> dict:
    if not has_behavior(visitor_signals):
        # Nothing to score: a fixed answer, so it's always 0 / Awareness and costs no API call.
        return json.loads(json.dumps(NO_SIGNAL_SCORING))
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
  stage "Evaluation"; 9+ only with explicit buying actions (demo request,
  contact sales, trial signup) plus repeat visits, stage "Decision".
- Moderate signals (1-2 relevant pages, 1-2 visits) should score 4-6,
  stage "Evaluation".
- Weak/no signals (no pages, single short visit, blog-only browsing)
  should score 0-3, stage "Awareness".
- Example: pages ["/pricing", "/case-studies"], 3 visits this week,
  222 seconds on site -> score should be around 8.0-8.5, stage "Evaluation".
"stage" must be exactly one of: "Awareness", "Evaluation", "Decision"."""
    # Drop empty fields and fix key order so the same behavior always produces
    # the exact same prompt (e.g. "device": null vs. no device key gave
    # different scores), then score at temperature 0.
    signals = {k: v for k, v in sorted(visitor_signals.items()) if v not in (None, "", [])}
    user = f"Visitor signals: {json.dumps(signals)}"
    result = call_agent(system, user, schema.ScoringOutput, model, temperature=0)
    intent = result.get("intent", {})
    score = max(0.0, min(10.0, float(intent.get("score", 0))))
    intent["score"] = round(score, 1)
    intent["stage"] = stage_for_score(score)
    return result


def stage_for_score(score: float) -> str:
    """The funnel stage is derived from the score with fixed cutoffs, so the
    two can never disagree (the model alone sometimes gave one score two
    different stages across runs)."""
    if score < 4:
        return "Awareness"
    if score < 9:
        return "Evaluation"
    return "Decision"


_PLACEHOLDERS = {"", "n/a", "na", "none", "null", "unknown", "not available", "-"}


def _blank(value):
    return value is None or (isinstance(value, str) and value.strip().lower() in _PLACEHOLDERS)


def normalize_domain(domain):
    """"https://www.Fello.ai/" -> "fello.ai"; placeholders -> None."""
    if _blank(domain):
        return None
    d = str(domain).strip().lower()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    d = d.split("/")[0].split("?")[0]
    if d.startswith("www."):
        d = d[4:]
    return d or None


def clean_research(r: dict) -> dict:
    """Turns the model's placeholder values ("N/A", "unknown", 0) into real
    blanks so the UI and PDF show "Unknown" instead of fake data."""
    company = r.get("company", {})
    company["domain"] = normalize_domain(company.get("domain"))
    for key in ("employee_count", "founded_year"):
        if not isinstance(company.get(key), int) or company[key] <= 0:
            company[key] = None
    tech = r.get("tech_stack", {})
    for key, value in list(tech.items()):
        if _blank(value):
            tech[key] = None
    r["leadership"] = [
        p for p in r.get("leadership", [])
        if not _blank(p.get("name")) and not _blank(p.get("title"))
    ]
    r["business_signals"] = [s for s in r.get("business_signals", []) if not _blank(s)]
    return r


def run_strategist(company_profile: dict, scoring: dict, visitor_signals: dict = None, model: str = None) -> dict:
    system = """You are a sales strategist. Given a company profile and visitor
scoring data, write a 2-3 sentence plain-English summary and concrete next actions
for a salesperson. Return ONLY valid JSON, nothing else:
{
  "ai_summary": "",
  "recommended_action": {"summary": "", "next_steps": [""]},
  "confidence_notes": ""
}
Reference specific facts from the input (company name, pages visited, industry) —
do not write a generic summary that could apply to any company. Only mention
pages or behavior that appear in the visitor signals; if none were provided,
say the assessment is based on the company profile alone. If the company
profile is a low-confidence IP-based inference rather than a named company,
say so plainly in confidence_notes and recommend identity confirmation as a
next step before outreach."""
    user = (
        f"Company profile: {json.dumps(company_profile)}\n"
        f"Visitor signals: {json.dumps(visitor_signals) if visitor_signals else 'none provided'}\n"
        f"Scoring: {json.dumps(scoring)}"
    )
    return call_agent(system, user, schema.StrategyOutput, model)


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
  and stage from the scoring data: a score of 7 or above is "Low" risk, a
  score from 4 up to (not including) 7 is "Medium", and a score below 4 is
  "High".
- Keep each explanation to one concise sentence."""
    user = f"Company profile: {json.dumps(company_profile)}\nScoring: {json.dumps(scoring)}"
    return call_agent(system, user, schema.RiskAnalysis, model)


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
        max_output_tokens=output_token_limit(),
    )
    # Same fallback chain as the other agents: an overloaded or rate-limited
    # model shouldn't cost the report its news.
    response, last_error = None, None
    for model_name in dict.fromkeys([active_model, *config.FALLBACK_MODELS]):
        try:
            response = client.models.generate_content(model=model_name, contents=user, config=generation_config)
            break
        except Exception as e:
            last_error = e
            if not (is_overloaded(e) or is_rate_limited(e) or model_unavailable(e)):
                raise
    if response is None:
        raise RuntimeError(f"News search failed on every model: {last_error}")

    result = _extract_json_object(response.text or "")
    # News is best-effort: keep only well-formed items instead of letting one
    # bad item fail validation of the whole report.
    news = [_valid(schema.NewsItem, n) for n in result.get("recent_news") or []]
    sources = [_valid(schema.Source, s) for s in result.get("sources") or []]
    result = {"recent_news": [n for n in news if n][:5], "sources": [s for s in sources if s]}

    # Merge in the real grounding source URLs Google Search actually used,
    # in case the model didn't already list them under "sources".
    known_urls = {s["url"] for s in result["sources"]}
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


def _extract_json_object(text: str) -> dict:
    """Parses the first JSON object in free text (search answers sometimes add
    code fences or a sentence around the JSON)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    parsed = json.loads(text[start:end + 1])
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Expected a JSON object", text, start)
    return parsed


def _valid(model_cls, item):
    try:
        return model_cls.model_validate(item).model_dump(mode="json")
    except ValidationError:
        return None


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
    result = call_agent(system, user, schema.QnAOutput, model)
    return result.get("answer", "")


def _news_or_unavailable(company: dict, model: str = None):
    """Search grounding has its own quota separate from the other calls, so a
    failure here degrades to "no news" (flagged, so the UI can say so)
    instead of failing the whole report."""
    try:
        return run_news_and_sources(company["name"], company.get("domain"), model), False
    except Exception:
        return {"recent_news": [], "sources": []}, True


def run_full_pipeline(
    company_name: str = None,
    partial_domain: str = None,
    visitor_signals: dict = None,
    ip_address: str = None,
    location: str = None,
    model: str = None,
    on_step=None,
) -> dict:
    """Runs every agent and merges their output. `on_step(key)` is called as
    each stage starts (research, score, strategy, risk, news), always from
    the calling thread, so a UI can show progress."""
    step = on_step or (lambda key: None)

    step("research")
    researcher_output = run_researcher(
        company_name=company_name,
        partial_domain=partial_domain,
        ip_address=ip_address,
        location=location,
        model=model,
    )

    researcher_output = clean_research(researcher_output)

    # Independent agents run in parallel to cut waiting time: news only needs
    # the company, and the risk analyst doesn't need the strategist's output.
    # Progress callbacks stay on this thread (Streamlit UI calls must).
    with ThreadPoolExecutor(max_workers=2) as pool:
        news_future = (
            pool.submit(_news_or_unavailable, researcher_output["company"], model)
            if company_name and company_name.strip() else None  # IP-only: no company to search
        )

        step("score")
        scorer_output = run_scorer(visitor_signals, model)

        step("strategy")
        risk_future = pool.submit(run_risk_analyst, researcher_output, scorer_output, model)
        strategist_output = run_strategist(researcher_output, scorer_output, visitor_signals, model)

        step("risk")
        risk_output = risk_future.result()

        step("news")
        news_output, news_unavailable = (
            news_future.result() if news_future else ({"recent_news": [], "sources": []}, False)
        )

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
        "news_unavailable": news_unavailable,
    }