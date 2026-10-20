# AI Account Intelligence & Enrichment System

Built for the **Fello AI Builder Hackathon**. Turns a company name, an anonymous website visitor's IP/behavior, or both, into structured, sales-ready account intelligence — company profile, tech stack, leadership, likely persona, intent score, live news, and a recommended next action — in a single Streamlit app powered by a multi-agent Gemini pipeline.

**Stack:** Python · Google Gemini API (`google-genai`) with Google Search grounding · Pydantic · Streamlit · fpdf2

## Contents

- [The problem](#the-problem)
- [How it works](#how-it-works)
- [Features](#features)
- [Example output](#example-output)
- [Coverage against the brief](#coverage-against-the-brief)
- [Project structure](#project-structure)
- [Setup](#setup)
- [How to use it](#how-to-use-it)
- [Testing](#testing)
- [Design decisions](#design-decisions)
- [Known limitations / what's next](#known-limitations--whats-next)

## The problem

Sales and marketing teams have two data problems: anonymous website visitors give almost no actionable signal, and incomplete company data makes it hard to know whom to prioritize. This system takes a bare company name, raw anonymous visitor activity (IP + behavior), or both, and turns it into something a salesperson can act on immediately.

## How it works

Rather than one large prompt, the work is split across narrow, single-purpose agents. Each returns JSON that the next one builds on, and the combined result is validated against a Pydantic schema before it reaches the UI.

```
Input: company name and/or IP + location, plus optional visitor behavior
        │
        ▼
 [Researcher]     → company profile, tech stack, business signals, leadership
        │
        ▼
 [Scorer]         → likely persona + intent score (0–10) and stage from behavior
        │
        ├──► [Strategist]     → plain-English summary, recommended sales action, confidence notes
        ├──► [Risk Analyst]   → five account-risk ratings (Low / Medium / High)
        └──► [News & Sources] → real recent news + verification links via live Google Search
        │
        ▼
 Validated JSON (Pydantic)  →  Streamlit dashboard  →  PDF report
                                     │
                                     ▼
                            [Q&A agent] answers follow-up questions
                            grounded in the generated account data
```

All agents live in [`ai-account-intel/src/agents.py`](ai-account-intel/src/agents.py).

## Features

- **Company identification** from a name (most reliable) or, with no name at all, from an IP address and/or location — a simulated reverse-IP lookup, explicitly labeled low-confidence.
- **Profile enrichment** — domain, industry, size, HQ, founding year, tech stack (CRM, marketing automation, website platform, analytics), leadership, and business signals.
- **Persona and intent scoring** from browsing behavior (pages visited, visits this week, time on site, referral source, device). Hover the *Intent* heading to see which signals drove the score.
- **Live news and sources** — Gemini with Google Search grounding returns real, dated news and verification URLs, merged with the grounding metadata so cited links are never invented.
- **Recommended sales action** with concrete next steps and a `confidence_notes` field on every result.
- **AI Research Agent** — ask free-form questions ("Who should I contact first?", "What's the likelihood they'll buy?") answered from the account data, with one-click example questions.
- **Download PDF** — one-click account report, including the risk analysis (employee turnover, funding slowdown, negative news, declining hiring, low buying intent).

## Example output

Given **BrightPath Lending** plus visitor behavior (pages `/pricing`, `/ai-sales-agent`, `/case-studies`; 3 visits this week; 222 seconds on site):

```
Company:          BrightPath Lending
Website/Domain:   brightpathlending.com
Industry:         Mortgage Lending
Company Size:     ~200 employees
Headquarters:     Chicago, USA

Technology Stack: CRM: Salesforce · Marketing Automation: HubSpot
                  Website Platform: WordPress · Analytics: Google Analytics

Leadership:       Jane Doe — VP of Lending
                  John Smith — President & CEO

Business Signals: High reliance on digital lead generation
                  Likely active in residential refinancing

Likely Persona:   Decision Maker (85% confidence)
Intent Score:     8.2 / 10
Intent Stage:     Evaluation

AI Summary:       BrightPath Lending is an established mortgage lender
                  currently evaluating tools to improve lead-to-loan
                  conversion, based on strong recent engagement with
                  pricing and case study content.

Recommended Action:
  - Reach out to VP of Lending via LinkedIn with a relevant case study
  - Monitor for continued pricing-page engagement as a buying signal
  - Reference mortgage-specific ROI data in first outreach
```

## Coverage against the brief

| Brief requirement | Where it lives |
| --- | --- |
| Company identification (name, or IP/location) | Researcher agent |
| Company profile enrichment | Researcher agent |
| Technology stack detection | Researcher agent |
| Business signals | Researcher agent |
| Leadership discovery | Researcher agent |
| Persona inference | Scorer agent |
| Intent scoring | Scorer agent |
| Key signals observed | Derived directly from the visitor inputs, shown in the UI |
| AI account intelligence summary | Strategist agent |
| Recommended sales action | Strategist agent |
| Multi-agent workflow *(optional extension)* | Researcher → Scorer → Strategist / Risk Analyst / News |
| Data confidence scoring *(optional extension)* | `confidence_notes` on every result |
| Beyond the brief | Live search-grounded news & sources, AI Q&A agent, risk analysis, PDF export |

## Project structure

```
ai-account-intel/
├── app.py                 # Streamlit frontend (single page)
├── requirements.txt
├── .env.example           # copy to .env and add your key
├── run_tests.py           # runs the pipeline against all sample data
├── .streamlit/config.toml
└── src/
    ├── config.py          # all settings, read from .env or Streamlit secrets
    ├── schema.py          # locked Pydantic output schema
    ├── validate.py        # schema validation helper
    ├── agents.py          # the agent pipeline + Q&A agent
    ├── report.py          # PDF report generation
    ├── ui.py              # page theme (CSS) and HTML for each results card
    └── data/
        ├── sample_companies.json
        └── sample_visitor_signals.json
```

## Setup

Requires Python 3.10+.

```bash
git clone https://github.com/AishwaryaSingh2004/ai-account-intelligence.git
cd ai-account-intelligence/ai-account-intel
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com) (no credit card required) and put it in `.env`:

```
GEMINI_API_KEY=your-key-here
```

Everything else in `.env` (model, fallback model, retry count, output token limit) is optional with sensible defaults. When deployed on Streamlit Community Cloud, the same keys are read from Streamlit secrets instead.

Run it:

```bash
streamlit run app.py
```

The repo also includes a Dev Container config, so it runs in GitHub Codespaces with no local setup.

## How to use it

Provide at least one way to identify a company:

- **Company name** (most reliable), e.g. `BrightPath Lending`, optionally with a **website or domain** to sharpen identification. A website on its own (e.g. `fello.ai`) also works.
- **IP address and/or location** with no company name, to simulate identifying an anonymous visitor via reverse-IP lookup. IP addresses are validated (IPv4 or IPv6) before anything is sent to the model.
- **Visitor behavior** (optional, collapsible) — pages visited, time on site, visits this week, referral source, device. This moves the intent score and persona from "no signal" to a real inference.

Click **Analyze**, then explore the results, ask the AI Research Agent follow-up questions, or download the PDF report.

## Testing

Both test paths use the sample data in `src/data/`:

- **Via the UI** — copy any entry from `sample_companies.json` or `sample_visitor_signals.json` into the app.
- **Automated** — run every sample through the full pipeline:

  ```bash
  python run_tests.py
  ```

  This prints `OK` / `SCHEMA ERROR` / `CRASHED` for each golden-path and deliberately messy case (misspelled names, empty fields, garbled input, fabricated companies) and for high-, medium- and low-intent visitor profiles, so the handling of messy real-world input is verifiable in one run.

## Design decisions

- **Narrow agents over one big prompt.** Each agent has one job, which makes outputs more consistent, failures easier to debug, and any step replaceable (e.g. swapping the Researcher for real enrichment APIs) without touching the rest.
- **Schema-validated output.** Every result is parsed into Pydantic models with enums and range constraints (intent 0–10, confidence 0–1, stage ∈ Awareness/Evaluation/Decision), so malformed model output fails cleanly instead of corrupting the UI.
- **Calibrated scoring.** The Scorer prompt includes explicit score bands and a worked example — without them, the model confused the 0–10 intent scale with the 0–1 confidence scale.
- **Consistent intent.** The Scorer runs at temperature 0 on normalized input, and the funnel stage is derived from the score with fixed cutoffs (under 4 Awareness, 4–8.9 Evaluation, 9+ Decision), so the same behavior always gets the same score and stage. With no behavior at all, the result is a fixed 0 / Awareness with no model call.
- **No placeholder data.** Model placeholders like "N/A" or "unknown" are turned into blanks, and the Researcher returns no leadership rather than inventing names for companies it doesn't know.
- **Gemini as a simulated enrichment engine.** In production, the Researcher would call real enrichment APIs (Clearbit, Apollo, BuiltWith) and a real reverse-IP service. Using Gemini for that step was a deliberate choice to ship a working end-to-end system inside the hackathon window.
- **Anonymous visitors get a role, not a name.** The Scorer infers a likely persona (e.g. "Decision Maker") but never attaches a name to a visitor. Named individuals appear only under Leadership, as suggested outreach targets.
- **IP-only identification is explicitly low-confidence.** With no company name, the system returns a clearly labeled inference instead of inventing a specific company, and says so in `confidence_notes`.
- **Structured output on every agent.** Each agent passes its Pydantic model to Gemini as the response schema and validates the answer, so even the lighter fallback models return exactly the expected structure. Output tokens never drop below 8,192, since thinking models spend part of that budget on reasoning.
- **Resilient to outages and the free tier.** A rate-limited (429), overloaded (5xx) or retired (404) model switches straight to the next model in a fallback chain (`GEMINI_FALLBACK_MODEL` + `GEMINI_EXTRA_FALLBACK_MODELS`); cut-off or mis-shaped answers are retried; users see plain-English errors. The search-grounded news step has its own quota, so it degrades to a "news unavailable" note rather than failing the run, and malformed news items are dropped individually.
- **Parallel where possible.** News runs alongside the Scorer and the Risk Analyst alongside the Strategist, which roughly halves the wait.
- **Safe redeploys.** Streamlit keeps imported modules in memory across a deploy, so `app.py` reloads the project's own modules whenever their files change. Streamlit is pinned to the version the custom UI was tested on.
- **Search grounding workaround.** Gemini's JSON response mode can't be combined with the Google Search tool, so the news agent asks for raw JSON in the prompt, extracts the JSON object from the reply, validates each item, and merges in the URLs from the grounding metadata.

## Known limitations / what's next

- Company, tech-stack and leadership data is model-inferred, not pulled from live enrichment APIs. Only the news and sources come from live search.
- Gemini's free tier has a real requests-per-minute ceiling. Retry/backoff and a fallback model handle it, but it's worth knowing before a live demo.
- Next steps: wire real enrichment and reverse-IP APIs behind the same agent interface, persist visitor history for tracking intent over time, and add a CRM integration for one-click outreach from the Recommended Action section.
