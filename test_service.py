"""
Service test: routes, input handling, logging, appeals, labels and the
combining rule. About a hundred checks, in a second or two.

    python test_service.py

The detector is STUBBED to a constant, so no real writing is scored and the
model never loads, and the audit log goes to a temp folder, so nothing lands
in logs/audit.jsonl. This tests the plumbing, not whether the signals are any
good. That's what calibration and unit 8's attack set are for.
"""

import json
import math
import os
import sys
import tempfile
from pathlib import Path

BUILD = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD))

# These checks send dozens of requests as one creator on purpose, so the rate
# limiter is switched off for this run only. `run_attacks.py --flood` is the
# check that the limiter works.
os.environ["AI201_RATE_LIMITS"] = "0"

import config  # noqa: E402

tmp = Path(tempfile.mkdtemp())
config.LOG_DIR = tmp
config.AUDIT_LOG = tmp / "audit.jsonl"

import detector  # noqa: E402

STUB = {"value": 0.5, "raise": None}


def stub_model_signal(text):
    if STUB["raise"] is not None:
        raise STUB["raise"]
    return STUB["value"]


detector.model_signal = stub_model_signal

import app as appmod  # noqa: E402
import audit  # noqa: E402
import scoring  # noqa: E402
import stylometry  # noqa: E402

client = appmod.app.test_client()
failures = []


def check(name, cond, detail=""):
    mark = "ok  " if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def words(n):
    # Synthetic filler, several sentences, n words total.
    vocab = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]
    out = []
    for i in range(n):
        w = vocab[i % len(vocab)]
        out.append(w + ("." if i % 7 == 6 else ""))
    return " ".join(out)


VALID = words(30)

# ── /submit ─────────────────────────────────────────────────────────────────
print("\n/submit")
r = client.post("/submit", json={"text": VALID, "creator_id": "tester"})
body = r.get_json()
check("valid → 200", r.status_code == 200, r.status_code)
for field in ("content_id", "creator_id", "guess", "confidence", "label",
              "model_score", "style_score", "status"):
    check(f"  has {field}", field in body, body)
check("  guess in set", body.get("guess") in ("ai", "human", "unsure"))
check("  status decided", body.get("status") == "decided")
check("  confidence in 0–1", 0 <= body.get("confidence", -1) <= 1)
first_id = body["content_id"]

r2 = client.post("/submit", json={"text": VALID, "creator_id": "tester2"})
second_id = r2.get_json()["content_id"]
check("ids are unique", first_id != second_id)

cases = [
    ("body is a JSON list", dict(json=["text", "x"]), 400, "body"),
    ("body is a JSON string", dict(json="hello"), 400, "body"),
    ("text/plain body", dict(data="text=hello", content_type="text/plain"), 400, "body"),
    ("broken JSON", dict(data='{"text": "a', content_type="application/json"), 400, "body"),
    ("empty body", dict(data="", content_type="application/json"), 400, "body"),
    ("no text field", dict(json={"creator_id": "x"}), 400, "text"),
    ("text empty", dict(json={"text": "", "creator_id": "x"}), 400, "text"),
    ("text whitespace", dict(json={"text": "   \n\t ", "creator_id": "x"}), 400, "text"),
    ("text null", dict(json={"text": None, "creator_id": "x"}), 400, "text"),
    ("text number", dict(json={"text": 12345, "creator_id": "x"}), 400, "text"),
    ("text list", dict(json={"text": ["a", "b"], "creator_id": "x"}), 400, "text"),
    ("text 5 words", dict(json={"text": "this is far too short", "creator_id": "x"}), 400, "text"),
    ("text 19 words", dict(json={"text": words(19), "creator_id": "x"}), 400, "text"),
    ("text punctuation only", dict(json={"text": "!!! ??? ... --- ;;;", "creator_id": "x"}), 400, "text"),
    ("text 20,001 chars", dict(json={"text": "a" * 20_001, "creator_id": "x"}), 413, "text"),
    ("text 'word ' * 50000", dict(json={"text": "word " * 50_000, "creator_id": "x"}), 413, "text"),
    ("no creator_id", dict(json={"text": VALID}), 400, "creator_id"),
    ("creator_id blank", dict(json={"text": VALID, "creator_id": "  "}), 400, "creator_id"),
    ("creator_id number", dict(json={"text": VALID, "creator_id": 7}), 400, "creator_id"),
    ("creator_id 101 chars", dict(json={"text": VALID, "creator_id": "c" * 101}), 400, "creator_id"),
]
for name, kwargs, want, field in cases:
    r = client.post("/submit", **kwargs)
    b = r.get_json(silent=True) or {}
    check(f"{name} → {want} ({field})", r.status_code == want and b.get("field") == field,
          f"got {r.status_code} {b}")

r = client.post("/submit", json={"text": words(20), "creator_id": "x"})
check("text exactly 20 words → 200", r.status_code == 200, r.status_code)

big = json.dumps({"text": "x " * 600_000, "creator_id": "x"})
r = client.post("/submit", data=big, content_type="application/json")
b = r.get_json(silent=True) or {}
check("body over 1 MB → 413 body_too_large", r.status_code == 413 and b.get("error") == "body_too_large",
      f"got {r.status_code} {b}")

STUB["raise"] = detector.DetectorUnavailable("no model")
r = client.post("/submit", json={"text": VALID, "creator_id": "x"})
check("detector unavailable → 503", r.status_code == 503, r.status_code)
STUB["raise"] = ValueError("too short")
r = client.post("/submit", json={"text": VALID, "creator_id": "x"})
check("detector ValueError → 400", r.status_code == 400, r.status_code)
STUB["raise"] = None

r = client.get("/submit")
check("GET /submit → 405 JSON", r.status_code == 405 and r.is_json, r.status_code)
r = client.post("/nope", json={})
check("unknown path → 404 JSON", r.status_code == 404 and r.is_json, r.status_code)

# ── /appeal ─────────────────────────────────────────────────────────────────
print("\n/appeal")
r = client.post("/appeal", json={"content_id": first_id, "reasoning": "I wrote this myself."})
b = r.get_json()
check("valid → 200", r.status_code == 200, b)
check("  status under_review", b.get("status") == "under_review")
check("  appeal_count 1", b.get("appeal_count") == 1)
check("  original_decision kept", b.get("original_decision", {}).get("guess") in ("ai", "human", "unsure"))
check("  first-appeal message", b.get("message") == appmod.APPEAL_RECORDED)

r = client.post("/appeal", json={"content_id": first_id, "reasoning": "More context: drafts attached."})
b = r.get_json()
check("second appeal → 200, count 2", r.status_code == 200 and b.get("appeal_count") == 2, b)
check("  second-appeal message", b.get("message") == appmod.APPEAL_ADDED)

appeal_cases = [
    ("unknown id", dict(json={"content_id": "not-a-real-id", "reasoning": "x"}), 404),
    ("no content_id", dict(json={"reasoning": "x"}), 400),
    ("content_id number", dict(json={"content_id": 5, "reasoning": "x"}), 400),
    ("no reasoning", dict(json={"content_id": first_id}), 400),
    ("reasoning blank", dict(json={"content_id": first_id, "reasoning": "  "}), 400),
    ("reasoning too long", dict(json={"content_id": first_id, "reasoning": "r" * 5_001}), 400),
    ("body is a list", dict(json=[first_id]), 400),
    ("text/plain body", dict(data="hi", content_type="text/plain"), 400),
]
for name, kwargs, want in appeal_cases:
    r = client.post("/appeal", **kwargs)
    check(f"{name} → {want}", r.status_code == want, f"got {r.status_code} {r.get_json(silent=True)}")

# ── /content/<id> ───────────────────────────────────────────────────────────
print("\n/content/<id>")
r = client.get(f"/content/{first_id}")
b = r.get_json()
check("appealed item → under_review with 2 appeals",
      r.status_code == 200 and b.get("status") == "under_review" and len(b.get("appeals", [])) == 2, b)
r = client.get(f"/content/{second_id}")
b = r.get_json()
check("untouched item → decided, 0 appeals",
      r.status_code == 200 and b.get("status") == "decided" and b.get("appeals") == [], b)
r = client.get("/content/not-a-real-id")
check("unknown id → 404", r.status_code == 404, r.status_code)

# ── control routes ──────────────────────────────────────────────────────────
print("\ncontrol routes")
r = client.post("/ping", json={"message": "hello"})
check("/ping still answers", r.status_code == 200 and r.get_json().get("you_sent") == "hello")
r = client.get("/health")
check("/health answers", r.status_code == 200, r.status_code)
r = client.get("/log?limit=5")
check("/log answers with 5", r.status_code == 200 and r.get_json()["count"] == 5)

# ── the log itself ──────────────────────────────────────────────────────────
print("\nthe log")
entries = audit.read_entries()
decisions = [e for e in entries if e.get("event") is None]
appeals = [e for e in entries if e.get("event") == "appeal"]
rejections = [e for e in entries if e.get("event") == "rejected"]
nine = ["timestamp", "content_id", "creator_id", "guess", "model_score",
        "style_score", "combined_score", "label", "status"]
check("every decision has all nine fields",
      all(all(f in d and d[f] is not None for f in nine) for d in decisions), decisions[:1])
check("decisions carry word_count and style_parts",
      all("word_count" in d and "style_parts" in d for d in decisions))
check("2 appeals logged as under_review",
      len(appeals) == 2 and all(a["status"] == "under_review" for a in appeals))
expected_rejections = len(cases) + 1 + 1 + 1 + len(appeal_cases)  # +body 413, +503, +ValueError
check(f"every refusal logged ({expected_rejections})", len(rejections) == expected_rejections,
      f"got {len(rejections)}")
check("unknown-id appeal is not filed under that id",
      audit.entries_for("not-a-real-id") == [])
check("no rejection holds the text itself",
      all("text" not in e for e in rejections))
print(f"  {len(decisions)} decisions, {len(appeals)} appeals, {len(rejections)} rejections")

# ── scoring ─────────────────────────────────────────────────────────────────
print("\nscoring")
grid = [i / 20 for i in range(21)]
values = {(m, s): scoring.combine_signals(m, s) for m in grid for s in grid}
check("combined always within 0–1", all(0 <= v <= 1 for v in values.values()))
check("agreeing signals: combined == the signal",
      all(abs(scoring.combine_signals(x, x) - x) < 1e-3 for x in grid))
check("full split lands in unsure",
      scoring.score_to_label(scoring.combine_signals(1, 0))[0] == "unsure"
      and scoring.score_to_label(scoring.combine_signals(0, 1))[0] == "unsure")
w_total = config.WEIGHT_MODEL_SIGNAL + config.WEIGHT_STYLE_SIGNAL
pull_ceiling = 2 * min(config.WEIGHT_MODEL_SIGNAL, config.WEIGHT_STYLE_SIGNAL) / w_total
check(f"pull {config.DISAGREEMENT_PULL} <= 2 x smaller weight ({pull_ceiling:.2f})",
      config.DISAGREEMENT_PULL <= pull_ceiling + 1e-12)
order = {"human": 0, "unsure": 1, "ai": 2}
fine = [i / 200 for i in range(201)]
monotone = True
for s in fine:
    labels = [order[scoring.score_to_label(scoring.combine_signals(m, s))[0]] for m in fine]
    if any(b < a for a, b in zip(labels, labels[1:])):
        monotone = False
        break
for m in fine:
    labels = [order[scoring.score_to_label(scoring.combine_signals(m, s))[0]] for s in fine]
    if any(b < a for a, b in zip(labels, labels[1:])):
        monotone = False
        break
check("raising either signal never moves the label back down", monotone)
reached = {scoring.score_to_label(v)[0] for v in values.values()}
check("all three labels reachable from the grid", reached == {"human", "unsure", "ai"}, reached)
check("one signal alone (other at 0.5) can't reach AI",
      max(scoring.combine_signals(m, 0.5) for m in fine) < config.AI_THRESHOLD
      and max(scoring.combine_signals(0.5, s) for s in fine) < config.AI_THRESHOLD)

boundaries = [
    (0.0, "human"), (config.HUMAN_THRESHOLD, "human"), (config.HUMAN_THRESHOLD + 1e-4, "unsure"),
    (0.5, "unsure"), (config.AI_THRESHOLD - 1e-4, "unsure"), (config.AI_THRESHOLD, "ai"),
    (1.0, "ai"), (None, "unsure"), (math.nan, "unsure"), (-3, "human"), (7, "ai"),
    (0.51, "unsure"), (0.95, "ai"),
]
for score, want in boundaries:
    got = scoring.score_to_label(score)[0]
    check(f"score {score} → {want}", got == want, got)
check("0.51 and 0.95 give different labels",
      scoring.score_to_label(0.51)[1] != scoring.score_to_label(0.95)[1])

# ── stylometry on synthetic edge cases ───────────────────────────────────────
print("\nstylometry edge cases")
check("one sentence → spread None", stylometry.sentence_length_spread("no full stop here at all") is None)
check("titles don't end sentences",
      stylometry.sentences("I met Mrs. Ruffner and Dr. Lee. They were kind.")
      == ["I met Mrs. Ruffner and Dr. Lee.", "They were kind."],
      stylometry.sentences("I met Mrs. Ruffner and Dr. Lee. They were kind."))
check("ordinary sentence ends still split",
      len(stylometry.sentences("It rained. We stayed in! Did you? Yes.")) == 4)
check("empty text → no crash", stylometry.style_parts("")["style_score"] is not None)
check("punctuation only → no crash", stylometry.style_parts("!!! ???")["style_score"] is not None)
p = stylometry._VARIED_PUNCTUATION.findall
check("apostrophes in words don't count", p("don't won't it's the writer's") == [], p("don't won't it's the writer's"))
check("hyphens in words don't count", p("well-known AI-powered") == [], p("well-known AI-powered"))
check("quotes count", len(p("my 'waterproof' boots")) == 2, p("my 'waterproof' boots"))
check("dashes count", len(p("snow — the snow -- is pretty - really")) == 3, p("snow — the snow -- is pretty - really"))
check("ellipses count once", len(p("wait... and… then")) == 2, p("wait... and… then"))
check("; : ? ! ( ) count", len(p("a; b: c? d! (e)")) == 6, p("a; b: c? d! (e)"))
long_text = " ".join(f"w{i % 37}" for i in range(400))
ttr = stylometry.type_token_ratio(long_text)
check("MATTR stays in 0–1 on long text", 0 < ttr <= 1, ttr)
for t in ["", "a", "a. b.", VALID, long_text]:
    sc = stylometry.style_signal(t)
    check(f"style_signal in 0–1 for {t[:12]!r}", 0 <= sc <= 1, sc)

print(f"\n{'ALL PASSED' if not failures else f'{len(failures)} FAILED: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
