import json
import time
from src.agents import run_full_pipeline
from src.validate import validate_intel
from src import config

with open("src/data/sample_companies.json") as f:
    companies = json.load(f)

with open("src/data/sample_visitor_signals.json") as f:
    visitors = json.load(f)

print("=== COMPANY TESTS ===")
for category, entries in companies.items():
    if category.startswith("_"):
        continue
    for entry in entries:
        name = entry.get("company_name", "")
        try:
            raw = run_full_pipeline(name, entry.get("partial_domain"))
            parsed, error = validate_intel(raw)
            status = "OK" if not error else f"SCHEMA ERROR: {error[:80]}"
        except Exception as e:
            status = f"CRASHED: {e}"
        print(f"[{category}] '{name}' -> {status}")
        time.sleep(config.BATCH_DELAY_SECONDS)  # stay under the free-tier RPM cap across a long test run

print("\n=== VISITOR SIGNAL TESTS ===")
for category, signals in visitors.items():
    if category.startswith("_"):
        continue
    try:
        raw = run_full_pipeline("Generic Test Co", visitor_signals=signals)
        parsed, error = validate_intel(raw)
        status = f"OK (score={parsed.intent.score}, stage={parsed.intent.stage.value})" if not error else f"SCHEMA ERROR: {error[:80]}"
    except Exception as e:
        status = f"CRASHED: {e}"
    print(f"[{category}] -> {status}")
    time.sleep(config.BATCH_DELAY_SECONDS)