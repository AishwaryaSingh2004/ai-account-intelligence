"""Presentation layer: the page theme (CSS) and HTML builders for each results
card. Every value that comes from the model or the user is escaped with `_e`
before it is put into HTML, and links are only rendered for http(s) URLs."""
import html
from urllib.parse import urlparse

PIPELINE_STEPS = [
    ("research", "Researcher", "Profiling the company, tech stack and leadership"),
    ("score", "Scorer", "Reading visitor behavior for persona and intent"),
    ("strategy", "Strategist", "Writing the summary and next best action"),
    ("risk", "Risk Analyst", "Rating account risk signals"),
    ("news", "News & Sources", "Searching the live web for recent news"),
]

STAGES = ["Awareness", "Evaluation", "Decision"]


def _e(value) -> str:
    return html.escape("" if value is None else str(value))


def _safe_url(url):
    """Returns the URL only if it is a plain http(s) link, else None."""
    if not url:
        return None
    url = str(url).strip()
    scheme = urlparse(url).scheme.lower()
    if scheme and scheme not in ("http", "https") and "." not in scheme:
        return None  # javascript:, data:, mailto: etc.
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return url
    return None


def _initials(name: str) -> str:
    parts = [p for p in str(name).replace(".", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def _d(i: int, step: float = 0.07, base: float = 0.0) -> str:
    """Inline animation delay for staggered entrances."""
    return f"--d:{base + i * step:.2f}s"


# ---------------------------------------------------------------- CSS ----
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap');

@property --ang { syntax: '<angle>'; inherits: false; initial-value: 0deg; }
@property --pct { syntax: '<number>'; inherits: false; initial-value: 0; }

:root {
  --bg: #05070f;
  --card: rgba(14, 19, 36, .72);
  --card-solid: #0c1122;
  --line: rgba(148, 163, 255, .14);
  --line-strong: rgba(148, 163, 255, .32);
  --text: #e6e9f5;
  --muted: #94a0bf;
  --cyan: #22d3ee;
  --violet: #8b5cf6;
  --pink: #f472b6;
  --green: #34d399;
  --amber: #fbbf24;
  --rose: #fb7185;
  --display: 'Space Grotesk', 'Inter', system-ui, sans-serif;
  --sans: 'Inter', system-ui, sans-serif;
  --mono: 'JetBrains Mono', ui-monospace, monospace;
}

/* ---------- base + animated background ---------- */
.stApp { background: var(--bg); color: var(--text); }
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea,
.stApp button, .stApp summary, .stApp [data-baseweb="select"] { font-family: var(--sans); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stAppViewContainer"] { background: transparent; }
[data-testid="stAppViewContainer"]::before {
  content: ''; position: fixed; inset: -25%; z-index: 0; pointer-events: none;
  background:
    radial-gradient(38% 32% at 18% 22%, rgba(139, 92, 246, .30), transparent 70%),
    radial-gradient(32% 30% at 82% 18%, rgba(34, 211, 238, .22), transparent 70%),
    radial-gradient(36% 34% at 70% 82%, rgba(244, 114, 182, .16), transparent 70%),
    radial-gradient(30% 30% at 22% 85%, rgba(34, 211, 238, .12), transparent 70%);
  filter: blur(40px);
  animation: aurora 26s ease-in-out infinite alternate;
}
[data-testid="stAppViewContainer"]::after {
  content: ''; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(rgba(148, 163, 255, .05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 255, .05) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 30%, transparent 85%);
  -webkit-mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 30%, transparent 85%);
}
[data-testid="stAppViewContainer"] > * { position: relative; z-index: 1; }
@keyframes aurora {
  0%   { transform: translate3d(0, 0, 0) rotate(0deg) scale(1); }
  50%  { transform: translate3d(4%, -3%, 0) rotate(8deg) scale(1.08); }
  100% { transform: translate3d(-4%, 3%, 0) rotate(-6deg) scale(1.02); }
}
[data-testid="stMainBlockContainer"], .block-container {
  max-width: 1200px; padding-top: 2.5rem; padding-bottom: 5rem;
  padding-left: clamp(16px, 4vw, 48px); padding-right: clamp(16px, 4vw, 48px);
}

/* ---------- shared pieces ---------- */
.ai-eyebrow { font-family: var(--mono); font-size: 11px; letter-spacing: .16em; text-transform: uppercase; color: var(--cyan); margin: 0 0 12px; display: flex; align-items: center; gap: 10px; }
.ai-eyebrow::before { content: ''; width: 18px; height: 1px; background: currentColor; opacity: .7; }
.ai-card {
  position: relative; background: var(--card); border: 1px solid var(--line);
  border-radius: 20px; padding: clamp(18px, 2.4vw, 28px);
  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 24px 60px -30px rgba(0, 0, 0, .8), inset 0 1px 0 rgba(255, 255, 255, .04);
  transition: transform .35s cubic-bezier(.2, .8, .2, 1), border-color .35s, box-shadow .35s;
}
.ai-card:hover { transform: translateY(-3px); border-color: var(--line-strong); box-shadow: 0 30px 70px -30px rgba(139, 92, 246, .35), inset 0 1px 0 rgba(255, 255, 255, .06); }
.ai-card h3 { font-family: var(--display); font-weight: 600; font-size: 13px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin: 0 0 18px; display: flex; align-items: center; gap: 10px; }
.ai-card h3 .ic { width: 28px; height: 28px; border-radius: 9px; display: grid; place-items: center; font-size: 14px; background: linear-gradient(135deg, rgba(139, 92, 246, .25), rgba(34, 211, 238, .18)); border: 1px solid var(--line); }
.glow-border {
  border: 1px solid transparent;
  background: linear-gradient(var(--card-solid), var(--card-solid)) padding-box,
              conic-gradient(from var(--ang), rgba(139, 92, 246, .9), rgba(34, 211, 238, .9), rgba(244, 114, 182, .8), rgba(139, 92, 246, .9)) border-box;
  animation: spin-border 7s linear infinite;
}
@keyframes spin-border { to { --ang: 360deg; } }
.rise { opacity: 0; animation: rise .8s cubic-bezier(.2, .8, .2, 1) forwards; animation-delay: var(--d, 0s); }
@keyframes rise { from { opacity: 0; transform: translateY(26px) scale(.98); filter: blur(6px); } to { opacity: 1; transform: none; filter: none; } }
.grad-text {
  background: linear-gradient(100deg, #fff 0%, #c4b5fd 25%, #67e8f9 50%, #f9a8d4 75%, #fff 100%);
  background-size: 250% 100%; -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: shimmer 8s linear infinite;
}
@keyframes shimmer { to { background-position: -250% 0; } }

/* ---------- hero ---------- */
.ai-hero { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: clamp(24px, 4vw, 56px); align-items: center; margin-bottom: 28px; }
.live-chip { display: inline-flex; align-items: center; gap: 10px; padding: 7px 14px 7px 10px; border-radius: 999px; border: 1px solid var(--line-strong); background: rgba(14, 19, 36, .6); font-family: var(--mono); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 0 rgba(52, 211, 153, .6); animation: ping 1.8s ease-out infinite; }
@keyframes ping { 70% { box-shadow: 0 0 0 10px rgba(52, 211, 153, 0); } 100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); } }
.ai-hero h1 { font-family: var(--display); font-weight: 700; font-size: clamp(40px, 6.4vw, 78px); line-height: .98; letter-spacing: -.035em; margin: 22px 0 18px; padding: 0; }
.ai-hero p.sub { font-size: clamp(15px, 1.4vw, 18px); line-height: 1.6; color: var(--muted); max-width: 560px; margin: 0; }
.flow { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 26px; }
.flow span.node { font-family: var(--mono); font-size: 11px; letter-spacing: .06em; padding: 8px 12px; border-radius: 10px; border: 1px solid var(--line); background: rgba(14, 19, 36, .7); color: var(--text); }
.flow span.node b { color: var(--cyan); font-weight: 500; margin-right: 6px; }
.flow span.wire { width: 22px; height: 2px; border-radius: 2px; background: linear-gradient(90deg, var(--violet), var(--cyan), var(--violet)); background-size: 200% 100%; animation: wire 1.6s linear infinite; }
@keyframes wire { to { background-position: -200% 0; } }

.radar { position: relative; width: min(100%, 360px); aspect-ratio: 1; margin-left: auto; border-radius: 50%;
  background: repeating-radial-gradient(circle, transparent 0 17%, rgba(34, 211, 238, .16) 17% calc(17% + 1px)), radial-gradient(circle, rgba(34, 211, 238, .10), rgba(5, 7, 15, .2) 70%);
  border: 1px solid rgba(34, 211, 238, .28); box-shadow: 0 0 80px -10px rgba(34, 211, 238, .25), inset 0 0 60px rgba(139, 92, 246, .18); overflow: hidden; }
.radar::before { content: ''; position: absolute; inset: 0; border-radius: 50%; background: conic-gradient(from 0deg, transparent 0 290deg, rgba(34, 211, 238, .05) 300deg, rgba(34, 211, 238, .55) 360deg); animation: sweep 4s linear infinite; }
.radar::after { content: ''; position: absolute; inset: 0; background: linear-gradient(rgba(34, 211, 238, .18), rgba(34, 211, 238, .18)) center / 1px 100% no-repeat, linear-gradient(90deg, rgba(34, 211, 238, .18), rgba(34, 211, 238, .18)) center / 100% 1px no-repeat; }
@keyframes sweep { to { transform: rotate(360deg); } }
.blip { position: absolute; width: 10px; height: 10px; margin: -5px; border-radius: 50%; background: var(--c, var(--cyan)); box-shadow: 0 0 14px var(--c, var(--cyan)); animation: blip 4s ease-out infinite; animation-delay: var(--d, 0s); z-index: 1; }
@keyframes blip { 0%, 100% { opacity: .15; transform: scale(.6); } 8% { opacity: 1; transform: scale(1.35); } 40% { opacity: .55; transform: scale(1); } }
.radar-tag { position: absolute; z-index: 2; font-family: var(--mono); font-size: 10px; letter-spacing: .08em; padding: 4px 8px; border-radius: 6px; background: rgba(5, 7, 15, .8); border: 1px solid var(--line-strong); color: var(--text); white-space: nowrap; animation: blip 4s ease-out infinite; animation-delay: var(--d, 0s); }

/* ---------- input panel (Streamlit widgets) ---------- */
.st-key-input_panel {
  background: var(--card); border: 1px solid var(--line); border-radius: 24px;
  padding: clamp(18px, 3vw, 32px); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 30px 80px -40px rgba(0, 0, 0, .9);
}
.panel-head { margin-bottom: 6px; }
.panel-head h2 { font-family: var(--display); font-weight: 600; font-size: clamp(22px, 2.4vw, 28px); letter-spacing: -.02em; margin: 0 0 6px; padding: 0; color: var(--text); }
.panel-head p { font-size: 14.5px; line-height: 1.5; color: var(--muted); margin: 0; }

/* the two ways to identify an account, side by side with an OR between them */
@media (min-width: 641px) {
  .st-key-id_cols [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 48px !important; }
  .st-key-id_cols [data-testid="stColumn"] { flex: 1 1 0 !important; width: auto !important; min-width: 0 !important; }
}
.st-key-id_cols [data-testid="stColumn"] {
  position: relative; padding: 20px 20px 6px; border-radius: 18px;
  background: rgba(255, 255, 255, .025); border: 1px solid var(--line);
  transition: border-color .3s, background .3s, box-shadow .3s;
}
.st-key-id_cols [data-testid="stColumn"]:focus-within { border-color: rgba(139, 92, 246, .45); background: rgba(139, 92, 246, .05); box-shadow: 0 20px 50px -30px rgba(139, 92, 246, .6); }
.st-key-id_cols [data-testid="stColumn"]:first-of-type::after {
  content: 'OR'; position: absolute; z-index: 2; top: 50%; right: -24px; transform: translate(50%, -50%);
  width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center;
  font-family: var(--mono); font-size: 11px; letter-spacing: .08em; color: var(--text);
  background: #0c1122; border: 1px solid var(--line-strong); box-shadow: 0 0 24px -4px rgba(139, 92, 246, .55);
}
.col-head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 6px; }
.col-head .ic { flex: none; width: 36px; height: 36px; border-radius: 11px; display: grid; place-items: center; font-family: var(--mono); font-size: 12px; color: #fff; background: linear-gradient(135deg, var(--violet), #4f46e5); box-shadow: 0 8px 20px -8px rgba(139, 92, 246, .8); }
.col-head.alt .ic { background: linear-gradient(135deg, #0891b2, var(--violet)); box-shadow: 0 8px 20px -8px rgba(34, 211, 238, .7); }
.col-head b { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-family: var(--display); font-weight: 600; font-size: 17px; color: var(--text); }
.col-head b em { font-style: normal; font-family: var(--mono); font-weight: 500; font-size: 10px; letter-spacing: .08em; text-transform: uppercase; padding: 3px 8px; border-radius: 999px; color: var(--green); background: rgba(52, 211, 153, .1); border: 1px solid rgba(52, 211, 153, .3); }
.col-head.alt b em { color: var(--cyan); background: rgba(34, 211, 238, .08); border-color: rgba(34, 211, 238, .3); }
.col-head span { display: block; font-size: 13.5px; line-height: 1.45; color: var(--muted); margin-top: 3px; }

/* form fields */
[data-testid="stWidgetLabel"] p { font-size: 13.5px !important; color: #c9cfe4 !important; font-weight: 500; letter-spacing: .01em; }
.stApp [data-testid="stTextInputRootElement"], .stApp [data-testid="stTextAreaRootElement"],
.stApp [data-testid="stNumberInputContainer"], .stApp [data-testid="stSelectbox"] div:has(> input) {
  background: rgba(5, 7, 15, .75) !important; border: 1px solid rgba(148, 163, 255, .22) !important; border-radius: 12px !important;
  transition: border-color .2s, box-shadow .2s, background .2s;
}
.stApp [data-testid="stTextInputRootElement"] { min-height: 48px; }
.stApp [data-testid="stTextInputRootElement"]:hover, .stApp [data-testid="stTextAreaRootElement"]:hover,
.stApp [data-testid="stNumberInputContainer"]:hover, .stApp [data-testid="stSelectbox"] div:has(> input):hover { border-color: rgba(148, 163, 255, .42) !important; }
.stApp [data-testid="stTextInputRootElement"]:focus-within, .stApp [data-testid="stTextAreaRootElement"]:focus-within,
.stApp [data-testid="stNumberInputContainer"]:focus-within, .stApp [data-testid="stSelectbox"] div:has(> input):focus-within {
  border-color: rgba(139, 92, 246, .85) !important; background: rgba(5, 7, 15, .95) !important;
  box-shadow: 0 0 0 4px rgba(139, 92, 246, .16), 0 0 28px -8px rgba(34, 211, 238, .5) !important;
}
.stApp input, .stApp textarea { background: transparent !important; color: #f1f3fb !important; font-size: 15px !important; }
.stApp input::placeholder, .stApp textarea::placeholder { color: #5d6886 !important; opacity: 1; }

/* optional behavior section */
[data-testid="stExpander"] details { background: rgba(255, 255, 255, .02); border: 1px solid var(--line); border-radius: 16px; transition: border-color .25s; }
[data-testid="stExpander"] details:hover, [data-testid="stExpander"] details[open] { border-color: var(--line-strong); }
[data-testid="stExpander"] summary { padding-top: 14px; padding-bottom: 14px; }
[data-testid="stExpander"] summary p { font-size: 14.5px; }
[data-testid="stExpander"] summary:hover p { color: #fff; }

/* run row */
.st-key-go_row { align-items: center; gap: 16px 20px; margin-top: 6px; }
.go-hint { font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 8px; }
.go-hint i { width: 6px; height: 6px; border-radius: 50%; background: var(--green); box-shadow: 0 0 10px var(--green); }

/* buttons */
.stApp [data-testid="stBaseButton-primary"] {
  position: relative; overflow: hidden; border: 0; border-radius: 14px; min-height: 52px; padding: 0 28px;
  font-family: var(--display) !important; font-weight: 600; letter-spacing: .02em; color: #fff;
  background: linear-gradient(110deg, #7c3aed, #6366f1 35%, #0891b2 70%, #7c3aed); background-size: 220% 100%;
  box-shadow: 0 14px 40px -12px rgba(124, 58, 237, .75), inset 0 1px 0 rgba(255, 255, 255, .25);
  animation: btn-flow 6s linear infinite; transition: transform .2s, box-shadow .3s;
}
.stApp [data-testid="stBaseButton-primary"]::after { content: ''; position: absolute; top: 0; left: -60%; width: 40%; height: 100%; background: linear-gradient(100deg, transparent, rgba(255, 255, 255, .35), transparent); transform: skewX(-20deg); transition: left .7s; }
.stApp [data-testid="stBaseButton-primary"]:hover { transform: translateY(-2px); box-shadow: 0 20px 50px -12px rgba(34, 211, 238, .6), inset 0 1px 0 rgba(255, 255, 255, .3); color: #fff; }
.stApp [data-testid="stBaseButton-primary"]:hover::after { left: 120%; }
.stApp [data-testid="stBaseButton-primary"]:active { transform: translateY(0) scale(.98); }
@keyframes btn-flow { to { background-position: -220% 0; } }
.stApp [data-testid="stBaseButton-secondary"], .stApp [data-testid="stDownloadButton"] button {
  border-radius: 999px; border: 1px solid var(--line-strong); background: rgba(14, 19, 36, .7); color: var(--text);
  transition: border-color .25s, background .25s, transform .2s, box-shadow .25s;
}
.stApp [data-testid="stBaseButton-secondary"]:hover, .stApp [data-testid="stDownloadButton"] button:hover {
  border-color: var(--cyan); color: #fff; background: rgba(34, 211, 238, .1); transform: translateY(-2px); box-shadow: 0 10px 30px -12px rgba(34, 211, 238, .6);
}

/* ---------- pipeline tracker ---------- */
.tracker { margin-top: 8px; }
.tracker-bar { height: 3px; border-radius: 3px; background: var(--line); overflow: hidden; margin: 6px 0 20px; }
.tracker-bar i { display: block; height: 100%; width: var(--p); background: linear-gradient(90deg, var(--violet), var(--cyan)); box-shadow: 0 0 16px var(--cyan); transition: width .6s cubic-bezier(.2, .8, .2, 1); }
.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.step { position: relative; border-radius: 16px; padding: 16px; border: 1px solid var(--line); background: rgba(5, 7, 15, .55); overflow: hidden; transition: border-color .3s, opacity .3s; }
.step .n { font-family: var(--mono); font-size: 11px; color: var(--muted); }
.step .t { font-family: var(--display); font-weight: 600; font-size: 16px; margin: 6px 0 4px; }
.step .s { font-size: 12.5px; line-height: 1.45; color: var(--muted); }
.step .badge { position: absolute; top: 14px; right: 14px; width: 18px; height: 18px; border-radius: 50%; border: 2px solid var(--line-strong); }
.step.pending { opacity: .5; }
.step.active { border-color: rgba(34, 211, 238, .6); box-shadow: 0 0 40px -12px rgba(34, 211, 238, .55); }
.step.active::before { content: ''; position: absolute; inset: 0; background: linear-gradient(100deg, transparent 30%, rgba(34, 211, 238, .12), transparent 70%); background-size: 250% 100%; animation: scan 1.4s linear infinite; }
@keyframes scan { from { background-position: 150% 0; } to { background-position: -100% 0; } }
.step.active .badge { border-color: rgba(34, 211, 238, .25); border-top-color: var(--cyan); animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.step.done { border-color: rgba(52, 211, 153, .35); }
.step.done .badge { border: 0; background: var(--green); box-shadow: 0 0 14px rgba(52, 211, 153, .7); }
.step.done .badge::after { content: ''; position: absolute; left: 6px; top: 3px; width: 4px; height: 8px; border: solid #05070f; border-width: 0 2px 2px 0; transform: rotate(45deg); }

/* ---------- results ---------- */
.ai-grid { display: grid; gap: 18px; margin-bottom: 18px; }
.g-hero { grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr); }
.g-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.company-name { font-family: var(--display); font-weight: 700; font-size: clamp(34px, 5vw, 60px); line-height: 1; letter-spacing: -.035em; margin: 6px 0 14px; }
.domain-pill { display: inline-flex; align-items: center; gap: 8px; font-family: var(--mono); font-size: 12px; padding: 7px 12px; border-radius: 999px; background: rgba(34, 211, 238, .1); border: 1px solid rgba(34, 211, 238, .35); color: var(--cyan) !important; text-decoration: none !important; transition: background .25s, transform .25s; }
.domain-pill:hover { background: rgba(34, 211, 238, .2); transform: translateY(-1px); }
.company-desc { color: #c4cae0; line-height: 1.65; margin: 16px 0 22px; font-size: 15.5px; }
.facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.fact { border-radius: 14px; padding: 14px 16px; background: rgba(5, 7, 15, .5); border: 1px solid var(--line); transition: border-color .25s, transform .25s; }
.fact:hover { border-color: rgba(139, 92, 246, .55); transform: translateY(-2px); }
.fact small { display: block; font-family: var(--mono); font-size: 10.5px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
.fact b { font-family: var(--display); font-weight: 600; font-size: 16px; color: var(--text); }

.intent-wrap { display: flex; flex-direction: column; align-items: center; text-align: center; height: 100%; }
.intent-head { width: 100%; display: flex; justify-content: space-between; align-items: center; }
.intent-head h3 { margin: 0; }
.tip { position: relative; display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--line-strong); font-family: var(--mono); font-size: 12px; color: var(--muted); cursor: help; outline: none; }
.tip:hover, .tip:focus { color: var(--cyan); border-color: var(--cyan); }
.tip .tip-body { position: absolute; z-index: 50; right: 0; top: calc(100% + 10px); width: min(320px, 78vw); padding: 12px 14px; border-radius: 12px; text-align: left; font-family: var(--sans); font-size: 13px; line-height: 1.5; color: var(--text); background: #0c1122; border: 1px solid var(--line-strong); box-shadow: 0 20px 50px -10px rgba(0, 0, 0, .9); opacity: 0; visibility: hidden; transform: translateY(-4px); transition: opacity .2s, transform .2s, visibility .2s; }
.tip:hover .tip-body, .tip:focus .tip-body { opacity: 1; visibility: visible; transform: none; }
.gauge { position: relative; width: min(220px, 70%); aspect-ratio: 1; margin: 18px auto 10px; }
.gauge .ring { position: absolute; inset: 0; border-radius: 50%;
  background: conic-gradient(var(--gc) calc(var(--pct) * 1%), rgba(148, 163, 255, .12) 0);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 14px), #000 calc(100% - 13px));
  mask: radial-gradient(farthest-side, transparent calc(100% - 14px), #000 calc(100% - 13px));
  filter: drop-shadow(0 0 10px var(--gc)); animation: ring 1.8s cubic-bezier(.2, .8, .2, 1) .3s backwards; }
.gauge .halo { position: absolute; inset: 18%; border-radius: 50%; background: radial-gradient(circle, color-mix(in srgb, var(--gc) 22%, transparent), transparent 70%); animation: breathe 3.2s ease-in-out infinite; }
@keyframes ring { from { --pct: 0; } }
@keyframes breathe { 50% { transform: scale(1.15); opacity: .6; } }
.gauge .num { position: absolute; inset: 0; display: grid; place-content: center; }
.gauge .num b { font-family: var(--display); font-weight: 700; font-size: clamp(40px, 5vw, 56px); line-height: 1; letter-spacing: -.04em; color: var(--text); animation: pop .8s cubic-bezier(.3, 1.6, .5, 1) 1s backwards; }
.gauge .num small { font-family: var(--mono); font-size: 11px; color: var(--muted); letter-spacing: .1em; margin-top: 4px; }
@keyframes pop { from { opacity: 0; transform: scale(.4); } }
.stages { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; width: 100%; margin: 6px 0 18px; }
.stages div { font-family: var(--mono); font-size: 10.5px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); padding-top: 10px; border-top: 3px solid var(--line); transition: color .3s; }
.stages div.on { color: var(--text); border-top-color: var(--gc); }
.stages div.cur { color: var(--gc); text-shadow: 0 0 12px var(--gc); }
.persona { width: 100%; text-align: left; border-radius: 14px; padding: 14px 16px; background: rgba(5, 7, 15, .5); border: 1px solid var(--line); }
.persona small { font-family: var(--mono); font-size: 10.5px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.persona .row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin: 6px 0 10px; }
.persona b { font-family: var(--display); font-weight: 600; font-size: 17px; }
.persona span { font-family: var(--mono); font-size: 12px; color: var(--cyan); }
.bar { height: 6px; border-radius: 6px; background: rgba(148, 163, 255, .12); overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: 6px; background: linear-gradient(90deg, var(--violet), var(--cyan)); box-shadow: 0 0 12px rgba(34, 211, 238, .6); animation: fill 1.6s cubic-bezier(.2, .8, .2, 1) .6s backwards; }
@keyframes fill { from { width: 0; } }

.tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.tile { border-radius: 14px; padding: 14px 16px; background: rgba(5, 7, 15, .5); border: 1px solid var(--line); transition: transform .25s, border-color .25s; }
.tile:hover { transform: translateY(-2px) rotate(-.4deg); border-color: rgba(34, 211, 238, .5); }
.tile small { display: block; font-family: var(--mono); font-size: 10.5px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
.tile b { font-family: var(--display); font-weight: 600; font-size: 15.5px; overflow-wrap: anywhere; }
.tile b.unk { color: var(--muted); font-weight: 500; }

.people { display: grid; gap: 10px; }
.person { display: flex; align-items: center; gap: 14px; padding: 12px 14px; border-radius: 14px; background: rgba(5, 7, 15, .5); border: 1px solid var(--line); transition: transform .25s, border-color .25s; }
.person:hover { transform: translateX(4px); border-color: rgba(244, 114, 182, .5); }
.avatar { flex: none; width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center; font-family: var(--display); font-weight: 700; font-size: 14px; color: #fff; background: linear-gradient(135deg, var(--violet), var(--pink)); box-shadow: 0 8px 20px -8px rgba(244, 114, 182, .7); }
.person:nth-child(3n+2) .avatar { background: linear-gradient(135deg, #0891b2, var(--violet)); }
.person:nth-child(3n+3) .avatar { background: linear-gradient(135deg, var(--pink), var(--amber)); }
.person b { display: block; font-family: var(--display); font-weight: 600; font-size: 15px; }
.person div > span { font-size: 13px; color: var(--muted); }

.list { list-style: none; margin: 0 !important; padding: 0 !important; display: grid; gap: 10px; }
.list li { position: relative; padding: 0 0 0 26px; margin: 0; line-height: 1.55; color: #c4cae0; font-size: 14.5px; }
.list li::before { content: ''; position: absolute; left: 2px; top: .45em; width: 10px; height: 10px; border-radius: 3px; transform: rotate(45deg); background: linear-gradient(135deg, var(--violet), var(--cyan)); box-shadow: 0 0 10px rgba(34, 211, 238, .55); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { font-size: 12.5px; padding: 7px 12px; border-radius: 999px; background: rgba(139, 92, 246, .12); border: 1px solid rgba(139, 92, 246, .35); color: #ddd6fe; }
.chip.cy { background: rgba(34, 211, 238, .1); border-color: rgba(34, 211, 238, .35); color: #a5f3fc; }
.empty { color: var(--muted); font-size: 14px; margin: 0; }
.src-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; padding-top: 16px; border-top: 1px dashed var(--line); }
.src { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; font-size: 12px; padding: 6px 11px; border-radius: 8px; background: rgba(5, 7, 15, .6); border: 1px solid var(--line); color: var(--muted) !important; text-decoration: none !important; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: color .2s, border-color .2s; }
.src:hover { color: var(--cyan) !important; border-color: rgba(34, 211, 238, .5); }

.timeline { position: relative; display: grid; gap: 18px; padding-left: 24px; }
.timeline::before { content: ''; position: absolute; left: 5px; top: 6px; bottom: 6px; width: 2px; background: linear-gradient(var(--cyan), var(--violet), transparent); }
.news { position: relative; }
.news::before { content: ''; position: absolute; left: -24px; top: 5px; width: 12px; height: 12px; border-radius: 50%; background: var(--bg); border: 2px solid var(--cyan); box-shadow: 0 0 12px rgba(34, 211, 238, .7); }
.news .date { font-family: var(--mono); font-size: 11px; color: var(--cyan); letter-spacing: .06em; }
.news b { display: block; font-family: var(--display); font-weight: 600; font-size: 16px; margin: 4px 0 4px; }
.news p { margin: 0; color: var(--muted); font-size: 14px; line-height: 1.55; }

.strategy .summary { font-family: var(--display); font-weight: 500; font-size: clamp(18px, 2vw, 22px); line-height: 1.5; letter-spacing: -.01em; margin: 0 0 22px; color: var(--text); }
.action-sum { color: #c4cae0; line-height: 1.6; margin: 0 0 16px; }
.next { list-style: none; counter-reset: s; margin: 0 !important; padding: 0 !important; display: grid; gap: 10px; }
.next li { counter-increment: s; display: flex; gap: 14px; align-items: flex-start; padding: 14px 16px; margin: 0; border-radius: 14px; background: rgba(5, 7, 15, .5); border: 1px solid var(--line); line-height: 1.55; color: var(--text); transition: border-color .25s, transform .25s; }
.next li:hover { border-color: rgba(52, 211, 153, .5); transform: translateX(4px); }
.next li::before { content: counter(s, decimal-leading-zero); flex: none; font-family: var(--mono); font-size: 12px; color: var(--green); padding: 3px 7px; border-radius: 7px; background: rgba(52, 211, 153, .12); border: 1px solid rgba(52, 211, 153, .35); }
.note { display: flex; gap: 12px; margin-top: 18px; padding: 14px 16px; border-radius: 14px; background: rgba(251, 191, 36, .07); border: 1px solid rgba(251, 191, 36, .3); color: #fde68a; font-size: 13.5px; line-height: 1.55; }

.results-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 12px; margin: 34px 0 14px; }
.results-head h2 { font-family: var(--display); font-weight: 700; font-size: clamp(26px, 3.4vw, 38px); letter-spacing: -.03em; margin: 0; padding: 0; }

/* Q&A */
.qa { display: grid; gap: 14px; margin-top: 8px; }
.bubble-q { justify-self: end; max-width: min(620px, 92%); padding: 12px 16px; border-radius: 18px 18px 4px 18px; background: linear-gradient(135deg, #6d28d9, #4f46e5); color: #fff; font-weight: 500; box-shadow: 0 12px 30px -14px rgba(109, 40, 217, .8); }
.bubble-a { display: flex; gap: 12px; max-width: min(760px, 100%); }
.bubble-a .bot { flex: none; width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; font-family: var(--mono); font-size: 11px; color: #05070f; font-weight: 700; background: linear-gradient(135deg, var(--cyan), var(--green)); }
.bubble-a div.txt { padding: 12px 16px; border-radius: 4px 18px 18px 18px; background: rgba(14, 19, 36, .85); border: 1px solid var(--line); line-height: 1.6; color: #d6dbee; }
.st-key-examples [data-testid="stBaseButton-secondary"] { font-size: 13px; min-height: 38px; }

/* ---------- responsive ---------- */
@media (max-width: 900px) {
  .ai-hero, .g-hero, .g-2 { grid-template-columns: minmax(0, 1fr); }
  .radar { width: min(68vw, 280px); margin: 0 auto; }
}
@media (max-width: 640px) {
  .st-key-id_cols [data-testid="stHorizontalBlock"] { gap: 44px !important; }
  .st-key-id_cols [data-testid="stColumn"]:first-of-type::after { top: auto; bottom: -22px; right: 50%; transform: translate(50%, 50%); }
}
@media (max-width: 560px) {
  .radar { display: none; }
  .tiles { grid-template-columns: minmax(0, 1fr); }
  .flow span.wire { width: 12px; }
  .stApp [data-testid="stBaseButton-primary"] { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .001s !important; animation-iteration-count: 1 !important; animation-delay: 0s !important; transition-duration: .001s !important; }
  [data-testid="stAppViewContainer"]::before { animation: none; }
}
</style>
"""


# ------------------------------------------------------------- builders ----
def hero_html() -> str:
    nodes = ["Researcher", "Scorer", "Strategist", "News"]
    flow = '<span class="wire"></span>'.join(
        f'<span class="node"><b>{i + 1:02d}</b>{n}</span>' for i, n in enumerate(nodes)
    )
    blips = [
        (28, 34, "0s", "var(--cyan)"), (66, 26, "1.1s", "var(--pink)"),
        (72, 64, "2.1s", "var(--violet)"), (36, 72, "3s", "var(--green)"),
    ]
    blip_html = "".join(
        f'<span class="blip" style="left:{x}%;top:{y}%;--d:{d};--c:{c}"></span>' for x, y, d, c in blips
    )
    tags = (
        '<span class="radar-tag" style="left:34%;top:26%;--d:0s">intent 8.2</span>'
        '<span class="radar-tag" style="left:52%;top:70%;--d:2.1s">decision maker</span>'
    )
    return f"""
<section class="ai-hero">
  <div class="rise" style="--d:.05s">
    <span class="live-chip"><span class="live-dot"></span>Multi-agent Gemini pipeline</span>
    <h1><span class="grad-text">Account<br>Intelligence</span></h1>
    <p class="sub">Drop in a company name, or just an anonymous visitor's IP and clicks. A team of AI agents researches the account, scores buying intent and hands you the next move.</p>
    <div class="flow">{flow}</div>
  </div>
  <div class="radar rise" style="--d:.25s" aria-hidden="true">{blip_html}{tags}</div>
</section>"""


def panel_head_html() -> str:
    return """
<div class="panel-head">
  <h2>Who are we looking at?</h2>
  <p>Fill in either side. Add a company name if you know it, or the visitor's IP and location if you don't.</p>
</div>"""


def col_head_html(num: str, title: str, badge: str, text: str, alt: bool = False) -> str:
    return (
        f'<div class="col-head{" alt" if alt else ""}"><span class="ic">{_e(num)}</span>'
        f'<div><b>{_e(title)}<em>{_e(badge)}</em></b><span>{_e(text)}</span></div></div>'
    )


def go_hint_html() -> str:
    return '<div class="go-hint"><i></i>5 AI agents run one after another</div>'


def tracker_html(active: str) -> str:
    keys = [k for k, _, _ in PIPELINE_STEPS]
    idx = keys.index(active) if active in keys else len(keys)
    pct = int(idx / len(keys) * 100) if active in keys else 100
    cards = []
    for i, (key, title, sub) in enumerate(PIPELINE_STEPS):
        state = "done" if i < idx else "active" if i == idx else "pending"
        cards.append(
            f'<div class="step {state}"><span class="badge"></span>'
            f'<div class="n">AGENT {i + 1:02d}</div><div class="t">{title}</div>'
            f'<div class="s">{sub}</div></div>'
        )
    return f"""
<div class="ai-card tracker">
  <p class="ai-eyebrow">Pipeline running</p>
  <div class="tracker-bar"><i style="--p:{max(pct, 4)}%"></i></div>
  <div class="steps">{''.join(cards)}</div>
</div>"""


def results_head_html(name: str) -> str:
    return f"""
<div class="results-head rise">
  <div><p class="ai-eyebrow">Account report</p><h2>Here's what the agents found on <span class="grad-text">{_e(name)}</span></h2></div>
</div>"""


def _score_color(score: float) -> str:
    if score >= 7:
        return "var(--green)"
    if score >= 4:
        return "var(--amber)"
    return "var(--rose)"


def company_and_intent_html(parsed, intent_help: str) -> str:
    c = parsed.company
    url = _safe_url(c.domain)
    domain = (
        f'<a class="domain-pill" href="{_e(url)}" target="_blank" rel="noopener noreferrer">&#8599; {_e(c.domain)}</a>'
        if url else ""
    )
    facts = [
        ("Industry", c.industry),
        ("Company size", f"{c.employee_count:,} employees" if c.employee_count else "Unknown"),
        ("Headquarters", c.headquarters),
        ("Founded", c.founded_year or "Unknown"),
    ]
    fact_html = "".join(
        f'<div class="fact rise" style="{_d(i, base=.35)}"><small>{k}</small><b>{_e(v)}</b></div>'
        for i, (k, v) in enumerate(facts)
    )

    score = max(0.0, min(10.0, float(parsed.intent.score)))
    stage = parsed.intent.stage.value
    stage_idx = STAGES.index(stage) if stage in STAGES else 0
    stages = "".join(
        f'<div class="{"on" if i <= stage_idx else ""}{" cur" if i == stage_idx else ""}">{s}</div>'
        for i, s in enumerate(STAGES)
    )
    conf = round(parsed.persona.confidence * 100)
    gc = _score_color(score)

    return f"""
<div class="ai-grid g-hero">
  <div class="ai-card glow-border rise" style="--d:.05s">
    <p class="ai-eyebrow">Company profile</p>
    <div class="company-name">{_e(c.name)}</div>
    {domain}
    <p class="company-desc">{_e(c.description)}</p>
    <div class="facts">{fact_html}</div>
  </div>
  <div class="ai-card rise" style="--d:.15s;--gc:{gc}">
    <div class="intent-wrap">
      <div class="intent-head">
        <h3><span class="ic">&#9673;</span>Intent</h3>
        <span class="tip" tabindex="0" aria-label="How the intent score is calculated">i<span class="tip-body">{_e(intent_help)}</span></span>
      </div>
      <div class="gauge">
        <span class="halo"></span><span class="ring" style="--pct:{score * 10:.1f}"></span>
        <div class="num"><b>{score:g}</b><small>OF 10</small></div>
      </div>
      <div class="stages">{stages}</div>
      <div class="persona">
        <small>Likely persona</small>
        <div class="row"><b>{_e(parsed.persona.likely_role)}</b><span>{conf}% confidence</span></div>
        <div class="bar"><i style="width:{conf}%"></i></div>
      </div>
    </div>
  </div>
</div>"""


def stack_and_people_html(parsed) -> str:
    ts = parsed.tech_stack
    tiles = []
    for i, (label, val) in enumerate([
        ("CRM", ts.crm), ("Marketing automation", ts.marketing_automation),
        ("Website platform", ts.website_platform), ("Analytics", ts.analytics),
    ]):
        cls = "" if val else ' class="unk"'
        tiles.append(f'<div class="tile rise" style="{_d(i, base=.25)}"><small>{label}</small><b{cls}>{_e(val or "Unknown")}</b></div>')

    if parsed.leadership:
        people = "".join(
            f'<div class="person rise" style="{_d(i, base=.3)}"><span class="avatar">{_e(_initials(p.name))}</span>'
            f'<div><b>{_e(p.name)}</b><span>{_e(p.title)}</span></div></div>'
            for i, p in enumerate(parsed.leadership)
        )
    else:
        people = '<p class="empty">No leadership identified.</p>'

    return f"""
<div class="ai-grid g-2">
  <div class="ai-card rise" style="--d:.2s"><h3><span class="ic">&#9881;</span>Technology stack</h3><div class="tiles">{''.join(tiles)}</div></div>
  <div class="ai-card rise" style="--d:.28s"><h3><span class="ic">&#9733;</span>Leadership</h3><div class="people">{people}</div></div>
</div>"""


def signals_html(parsed, observed: list) -> str:
    if parsed.business_signals:
        biz = '<ul class="list">' + "".join(f"<li>{_e(s)}</li>" for s in parsed.business_signals) + "</ul>"
    else:
        biz = '<p class="empty">No business signals identified.</p>'

    links = []
    for s in parsed.sources or []:
        url = _safe_url(s.url)
        if url:
            links.append(f'<a class="src" href="{_e(url)}" target="_blank" rel="noopener noreferrer">&#8599; {_e(s.title)}</a>')
    sources = f'<div class="src-list">{"".join(links)}</div>' if links else ""

    if observed:
        obs = '<div class="chips">' + "".join(f'<span class="chip cy">{_e(o)}</span>' for o in observed) + "</div>"
    else:
        obs = '<p class="empty">No visitor signals provided, so this result is based on the company alone.</p>'

    return f"""
<div class="ai-grid g-2">
  <div class="ai-card rise" style="--d:.3s"><h3><span class="ic">&#8599;</span>Business signals</h3>{biz}{sources}</div>
  <div class="ai-card rise" style="--d:.36s"><h3><span class="ic">&#9678;</span>Key signals observed</h3>{obs}</div>
</div>"""


def news_html(parsed) -> str:
    items = parsed.recent_news or []
    if not items:
        if getattr(parsed, "news_unavailable", False):
            return """
<div class="ai-grid"><div class="ai-card rise" style="--d:.4s">
  <h3><span class="ic">&#9889;</span>Recent news</h3>
  <p class="empty">Live news search isn't available right now (the Google Search quota is used up or the service is busy). The rest of this report is unaffected; try again later for news and source links.</p>
</div></div>"""
        return ""
    rows = []
    for i, n in enumerate(items):
        date = f'<span class="date">{_e(n.date)}</span>' if n.date else ""
        rows.append(
            f'<div class="news rise" style="{_d(i, base=.4)}">{date}'
            f"<b>{_e(n.headline)}</b><p>{_e(n.summary)}</p></div>"
        )
    rows = "".join(rows)
    return f"""
<div class="ai-grid"><div class="ai-card rise" style="--d:.4s">
  <h3><span class="ic">&#9889;</span>Recent news <span class="chip cy" style="margin-left:auto;text-transform:none;letter-spacing:0">live search</span></h3>
  <div class="timeline">{rows}</div>
</div></div>"""


def strategy_html(parsed) -> str:
    steps = "".join(
        f'<li class="rise" style="{_d(i, .1, .55)}">{_e(s)}</li>' for i, s in enumerate(parsed.recommended_action.next_steps)
    )
    return f"""
<div class="ai-grid"><div class="ai-card glow-border strategy rise" style="--d:.45s">
  <p class="ai-eyebrow">AI summary</p>
  <p class="summary">{_e(parsed.ai_summary)}</p>
  <h3><span class="ic">&#10148;</span>Recommended sales action</h3>
  <p class="action-sum">{_e(parsed.recommended_action.summary)}</p>
  <ol class="next">{steps}</ol>
  <div class="note"><span>&#9888;</span><span>{_e(parsed.confidence_notes)}</span></div>
</div></div>"""


def qna_head_html() -> str:
    return """
<div class="results-head" style="margin-top:42px">
  <div><p class="ai-eyebrow">AI research agent</p><h2>Ask anything about this account</h2></div>
</div>"""


def qna_html(history: list) -> str:
    if not history:
        return ""
    rows = "".join(
        f'<div class="bubble-q rise">{_e(q)}</div>'
        f'<div class="bubble-a rise" style="--d:.1s"><span class="bot">AI</span><div class="txt">{_e(a)}</div></div>'
        for q, a in history
    )
    return f'<div class="qa">{rows}</div>'
