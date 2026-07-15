
**AI Account Intelligence & Enrichment System**
Built for the Fello AI Builder Hackathon. Converts a company name, an anonymous visitor's IP/behavior, or both, into structured, sales-ready account intelligence and a recommended next action — in one Streamlit app, powered by a three-agent Gemini pipeline.
Table of contents
The problem
How it works
Example output
Coverage against the brief
Tech stack
Project structure
Setup
How to use it
Testing
Design decisions worth knowing
Known limitations / what's next
The problem, briefly
Sales and marketing teams have two data problems: anonymous website visitors give almost no actionable signal, and incomplete company data makes it hard to know who to prioritize. This system takes either a bare company name, raw anonymous visitor activity (IP + behavior), or both — and turns it into something a salesperson can act on immediately: a company profile, likely persona, an intent score, and a recommended next step.


**How it works: a 3-agent pipeline**
Rather than stitching together multiple paid enrichment APIs (Clearbit, Apollo, BuiltWild, etc.) within a short build window, this prototype uses Gemini as a simulated research agent, split into three narrow, sequential roles — a real multi-agent workflow, not one large prompt:
Input (company name, and/or IP + location, and/or visitor behavior)
        │
        ▼
 [Agent 1: Researcher]   → company profile, tech stack, business signals, leadership
        │
        ▼
 [Agent 2: Scorer]       → persona inference + intent score/stage from behavior
        │
        ▼
 [Agent 3: Strategist]   → plain-English summary + recommended sales action
        │
        ▼
   Validated JSON (Pydantic)  →  Streamlit dashboard

Each agent has a narrow, single-purpose prompt and hands its output to the next. The full pipeline lives in src/agents.py.
Example output
Given the company name BrightPath Lending plus visitor behavior (pages visited: /pricing, /ai-sales-agent, /case-studies; 3 visits this week; 222 seconds on site), the system returns:
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

What it covers, against the brief
Brief requirement
Where it lives
Company Identification (name, or IP/location)
Researcher agent
Persona Inference
Scorer agent
Intent Scoring
Scorer agent
Company Profile Enrichment
Researcher agent
Technology Stack Detection
Researcher agent
Business Signals
Researcher agent
Leadership Discovery
Researcher agent
Key Signals Observed
Derived directly from the visitor inputs entered, shown in the UI
AI Account Intelligence Summary
Strategist agent
Recommended Sales Action
Strategist agent
Multi-agent workflow (optional extension)
Researcher → Scorer → Strategist
Data confidence scoring (optional extension)
confidence_notes field on every result

**Tech stack**
Python 3.10+
Streamlit — single-page frontend
Google Gemini API (google-genai SDK) — free tier (Flash / Flash-Lite)
Pydantic — validates every model response against a locked schema, so malformed output fails cleanly instead of silently corrupting the UI
Project structure
ai-account-intel/
├── app.py                          # Streamlit frontend (single page)
├── README.md
├── requirements.txt
├── .env.example                    # copy to .env and fill in your key
├── run_tests.py                    # runs the pipeline against all sample data
└── src/
    ├── config.py                  # all settings — nothing hardcoded elsewhere
    ├── schema.py                  # locked Pydantic output schema
    ├── validate.py                # schema validation helper
    ├── agents.py                  # the 3-agent pipeline
    └── data/
        ├── sample_companies.json
        └── sample_visitor_signals.json

**Setup**
git clone <this-repo-url>
cd ai-account-intel
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

Get a free Gemini API key at aistudio.google.com — no credit card required — and paste it into .env:
GEMINI_API_KEY=your-key-here

Everything else in .env (model name, retry count, batch delay, etc.) is optional with sensible defaults — see .env.example for the full list. None of these values are hardcoded anywhere in the Python code.
Run it:
streamlit run app.py

**How to use it**
The app accepts any combination of the following — the only requirement is at least one way to identify a company:
Company name (most reliable) — e.g. BrightPath Lending
Partial domain (optional) — sharpens identification
IP address and/or location, with no company name at all — simulates identifying an anonymous visitor via reverse IP lookup, the approach explicitly named in the brief
Visitor behavior (optional, collapsible section) — pages visited, time on site, visits this week, referral source, device — sharpens the intent score and persona from "no signal" to a real inference
Leave the behavior section collapsed to get just a company profile. Expand it and fill it in to also get a real intent score and persona.
Testing
Two ways to test, both against the same sample data in src/data/:
Via the UI — copy any entry from sample_companies.json or sample_visitor_signals.json into the app manually.
Automated — run the full sample set against the pipeline in one command:
 python run_tests.py
This prints OK / SCHEMA ERROR / CRASHED for every golden-path and deliberately-messy test case (misspelled names, empty fields, garbled input, fabricated companies, IP-only input with no name), so the system's handling of messy real-world data is verifiable in one run rather than taken on faith.
Design decisions worth knowing
Gemini as a simulated enrichment engine. In production, the Researcher agent would call real enrichment APIs (Clearbit, Apollo, BuiltWith) and a real reverse-IP lookup service. This prototype uses Gemini to simulate that research step directly — a deliberate choice to ship a working end-to-end system inside the build window, stated here rather than hidden.
Anonymous visitors get a role, not a name. The Scorer infers a likely persona (e.g. "Decision Maker") from behavior, but never attaches a name to it — the brief's own premise is that visitors are anonymous. Named individuals only appear under Leadership Discovery (the company's known leadership, e.g. CEO, VP Sales), surfaced as suggested outreach targets, not as the visitor's identity.
IP-only identification is explicitly low-confidence. When no company name is given, the system labels the result as a simulated inference rather than inventing a specific real company with false certainty. This shows up directly in confidence_notes.
Built for Gemini's free tier on purpose. agents.py includes retry-with-backoff on rate limits, and the sidebar exposes a fallback model switch — a real constraint of the free tier, handled explicitly rather than assumed away.
Known limitations / what's next
Company and tech-stack data is model-inferred, not pulled from live enrichment APIs — clearly labeled as such throughout the UI.
Running on Gemini's free tier means a real requests-per-minute ceiling exists; handled via retry/backoff and a fallback model, but still a constraint worth knowing about ahead of a live demo.
Natural next steps given more time: wire in real enrichment APIs behind the same agent interface, add a lightweight vector store for historical visitor tracking, and a CRM integration for one-click outreach from the Recommended Action section.

