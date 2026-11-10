#!/usr/bin/env python3
"""
Provenance Guard — the web service.

    python app.py

Then, in another terminal:

    curl -X POST http://127.0.0.1:5000/ping \
      -H "Content-Type: application/json" \
      -d '{"message": "hello"}'

That's the example route. **Leave it alone** — it's your control. When
something breaks later, check that `/ping` still answers: if it does, the
problem is in a handler; if it doesn't, it's the service itself.

Routes:

    POST /ping                the worked example. Don't edit it
    POST /submit              score a piece of writing, label it, log it
    POST /appeal              a writer disputes a decision → under_review
    GET  /content/<id>        one item's current status and appeals (stretch)
    GET  /log                 the audit log
    GET  /health              is the service up, and is the model loaded

Every field and every error of /submit and /appeal is written down in
README.md under "The contract".
"""

import uuid

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

import audit
import config
import detector
import scoring
import stylometry

app = Flask(__name__)

# A body bigger than this never reaches a route: Flask raises 413 while reading
# it, and `body_too_large` below answers. Real submissions are capped far lower
# by config.MAX_TEXT_CHARS; this only stops a giant body being parsed at all.
app.config["MAX_CONTENT_LENGTH"] = config.MAX_BODY_BYTES


# ── Rate limiting — UNIT 8 ────────────────────────────────────────────────────
# Off until you turn it on. In unit 8, Milestone 1:
#
#   1. Set RATE_LIMITING_ENABLED = True in config.py (or AI201_RATE_LIMITS=1)
#   2. Choose your numbers there
#   3. Uncomment the @limiter.limit(...) line on /submit below
#
# The order doesn't matter. While limiting is off, that decorator is a no-op
# that quietly does nothing, so uncommenting it early costs you nothing — but
# it also means no 429 until you've done step 1.
#
# The storage backend is preconfigured, which stops Flask-Limiter printing a
# warning on every start. In-memory is right for one laptop and wrong for
# anything real — a restart forgets every count.

class _LimiterOff:
    """
    Stands in for the real limiter while rate limiting is off.

    It makes @limiter.limit(...) a decorator that returns the route
    untouched, so uncommenting the line before you flip the setting is
    harmless instead of a crash on startup.
    """

    def limit(self, *args, **kwargs):
        return lambda view: view


limiter = _LimiterOff()
if config.RATE_LIMITING_ENABLED:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    def rate_limit_key():
        """
        Who a request counts against.

        Falling back to the caller's address is the easy version. Unit 8's
        stretch asks about per-creator limits instead — and the difference
        matters: one script can look like a thousand callers, and one household
        can look like one.
        """
        payload = request.get_json(silent=True)
        # A body that parses as JSON but isn't an object — a bare list or
        # string — has no .get. Without this guard the key function raises
        # BEFORE the route runs, and a malformed request becomes a 500 that
        # looks like your handler crashed when your handler never ran.
        if not isinstance(payload, dict):
            return get_remote_address()
        creator = payload.get("creator_id")
        return creator if isinstance(creator, str) and creator.strip() else get_remote_address()

    limiter = Limiter(
        key_func=rate_limit_key,
        app=app,
        storage_uri=config.RATE_LIMIT_STORAGE,
        default_limits=[],
    )

    @app.errorhandler(429)
    def rate_limited(exc):
        """
        A rejected request still leaves a trace.

        ⚠️ An attack that shows up only as an absence is one you'll never find.
        """
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            payload = {}
        audit.log_rejection(
            creator_id=payload.get("creator_id", "unknown"),
            reason="rate_limited",
            limit=str(exc.description),
        )
        return jsonify({
            "error": "rate_limited",
            "message": "Too many submissions. Try again shortly.",
            "limit": str(exc.description),
        }), 429


# ── The worked example. Already works. Don't edit. ────────────────────────────

@app.post("/ping")
def ping():
    """
    Everything a route needs, in six lines.

    JSON arrives as a dict. You pull things out of it. You return a dict and
    the framework turns it into a response. That's the whole idea.
    """
    payload = request.get_json(silent=True) or {}
    return jsonify({
        "ok": True,
        "you_sent": payload.get("message"),
        "service": "provenance-guard",
    })


@app.get("/health")
def health():
    """Is the service up, and has the model been downloaded yet?"""
    import detector

    loaded = detector._model is not None
    return jsonify({
        "ok": True,
        "detector_model": config.DETECTOR_MODEL,
        "detector_loaded": loaded,
        "rate_limiting": config.RATE_LIMITING_ENABLED,
        "log_entries": len(audit.read_entries()),
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _refuse(field, reason, message, *, creator_id="unknown", status=400,
            error="invalid_input", **extra):
    """
    Turn a bad request away with a 4xx that names the field — and log it.

    `error` is what the caller sees (the contract's codes); `reason` is the
    precise cause, which only the log needs. A refusal that left no log entry
    would make a flood of malformed requests look like a quiet afternoon.
    """
    audit.log_rejection(
        creator_id=creator_id,
        reason=reason,
        field=field,
        http_status=status,
        path=request.path,
        **extra,
    )
    return jsonify({"error": error, "field": field, "message": message}), status


def _decision_in(entries: list[dict]) -> dict | None:
    """
    The original decision among one item's log entries.

    Decisions are the entries with no `event`; appeals carry
    `event: "appeal"` and refusals `event: "rejected"`. Matching on that,
    rather than taking the first entry, means a stray entry can't pass
    itself off as the decision.
    """
    for entry in entries:
        if entry.get("event") is None and "guess" in entry:
            return entry
    return None


def _not_found(content_id: str):
    return jsonify({
        "error": "not_found",
        "message": (f"No submission has the content_id {content_id!r}. Check it "
                    f"against the content_id that /submit returned."),
    }), 404


# ── Submitting ────────────────────────────────────────────────────────────────

@app.post("/submit")
@limiter.limit(f"{config.RATE_LIMIT_PER_MINUTE}/minute;{config.RATE_LIMIT_PER_DAY}/day")
def submit():
    """
    Take a piece of text, decide about it, log the decision, answer.

    Expects JSON:
        {"text": "...", "creator_id": "..."}

    Returns JSON:
        {"content_id", "creator_id", "guess", "confidence", "label",
         "model_score", "style_score", "status"}

    Both signal scores go in the response as well as the log: unit 8's
    `run_attacks.py` and `run_eval.py` read `model_score` and `style_score`
    straight off it.

    Bad input never reaches the signals. Missing, blank or non-string fields
    and too-short text get a 400; too-long text a 413. Every refusal is logged.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _refuse(
            "body", "body_not_json_object",
            'Send a JSON object like {"text": "...", "creator_id": "..."}, '
            "with the header Content-Type: application/json.",
            content_type=request.content_type,
        )

    creator_id = payload.get("creator_id")
    if not isinstance(creator_id, str) or not creator_id.strip():
        return _refuse(
            "creator_id", "creator_id_missing",
            "creator_id is required: a non-empty string saying who wrote this.",
        )
    creator_id = creator_id.strip()
    if len(creator_id) > config.MAX_CREATOR_ID_CHARS:
        return _refuse(
            "creator_id", "creator_id_too_long",
            f"creator_id can be at most {config.MAX_CREATOR_ID_CHARS} characters.",
            creator_id=creator_id[:config.MAX_CREATOR_ID_CHARS],
        )

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return _refuse(
            "text", "text_missing",
            "text is required: a non-empty string holding the writing to check.",
            creator_id=creator_id,
        )
    text = text.strip()
    if len(text) > config.MAX_TEXT_CHARS:
        return _refuse(
            "text", "text_too_long",
            f"This is {len(text):,} characters and the limit is "
            f"{config.MAX_TEXT_CHARS:,}. Send a shorter excerpt.",
            creator_id=creator_id, status=413, error="text_too_long",
            text_chars=len(text),
        )
    word_count = len(stylometry.words(text))
    if word_count < config.MIN_WORDS:
        return _refuse(
            "text", "text_too_short",
            f"This is {word_count} words, which is too short to check. We need "
            f"at least {config.MIN_WORDS} words of English text.",
            creator_id=creator_id, word_count=word_count,
        )

    content_id = str(uuid.uuid4())

    # Signal one — the model. ~10 s on the first call while gpt2 loads, then a
    # second or two.
    try:
        model_score = detector.model_signal(text)
    except detector.DetectorUnavailable as exc:
        audit.log_rejection(creator_id=creator_id, reason="detector_unavailable",
                            detail=str(exc)[:300], path=request.path)
        return jsonify({
            "error": "detector_unavailable",
            "message": "The checker isn't available right now, so nothing was "
                       "decided about this text. Try again shortly.",
        }), 503
    except ValueError:
        # Fewer than three tokens for the model. MIN_WORDS should make this
        # unreachable — if it ever isn't, it's still a 400, not a crash.
        return _refuse(
            "text", "text_too_short_for_model",
            f"This is too short to check. We need at least {config.MIN_WORDS} "
            f"words of English text.",
            creator_id=creator_id, word_count=word_count,
        )

    # Signal two — the shape of the text. No model; instant.
    style_score = stylometry.style_signal(text)

    confidence = scoring.combine_signals(model_score, style_score)
    guess, label = scoring.score_to_label(confidence)

    audit.log_decision(
        content_id=content_id,
        creator_id=creator_id,
        guess=guess,
        model_score=model_score,
        style_score=style_score,
        combined_score=confidence,
        label=label,
        status="decided",
        word_count=word_count,
        style_parts=stylometry.style_parts(text),
    )

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "guess": guess,
        "confidence": confidence,
        "label": label,
        "model_score": model_score,
        "style_score": style_score,
        "status": "decided",
    })


# ── Appealing ─────────────────────────────────────────────────────────────────

APPEAL_RECORDED = (
    "Thank you. Your appeal is recorded and this piece is now under review. "
    "The original decision and your reasons are kept side by side for the "
    "person who reviews it, and the decision isn't final while that review "
    "is open."
)

APPEAL_ADDED = (
    "Thank you. This piece was already under review, and your new reasons "
    "have been added beside the earlier ones."
)


@app.post("/appeal")
def appeal():
    """
    A writer says the decision is wrong.

    Expects JSON:
        {"content_id": "...", "reasoning": "..."}

    Checks the content_id belongs to a real decision (an unknown id is a 404,
    never a silent success), appends the appeal beside the original decision
    with `audit.log_appeal` — which moves the item to `under_review` without
    overwriting anything — and confirms. Nothing is re-scored.

    This is the smallest endpoint in the project and the one that matters most
    to the person on the other end: it's all that stands between a wrong
    accusation and nothing at all.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _refuse(
            "body", "body_not_json_object",
            'Send a JSON object like {"content_id": "...", "reasoning": "..."}, '
            "with the header Content-Type: application/json.",
            content_type=request.content_type,
        )

    content_id = payload.get("content_id")
    if not isinstance(content_id, str) or not content_id.strip():
        return _refuse(
            "content_id", "content_id_missing",
            "content_id is required: the id that /submit gave back.",
        )
    content_id = content_id.strip()

    reasoning = payload.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        return _refuse(
            "reasoning", "reasoning_missing",
            "reasoning is required: say, in your own words, why the decision "
            "is wrong.",
            attempted_content_id=content_id,
        )
    reasoning = reasoning.strip()
    if len(reasoning) > config.MAX_REASONING_CHARS:
        return _refuse(
            "reasoning", "reasoning_too_long",
            f"reasoning can be at most {config.MAX_REASONING_CHARS:,} characters.",
            attempted_content_id=content_id,
        )

    entries = audit.entries_for(content_id)
    decision = _decision_in(entries)
    if decision is None:
        # Logged under a different key on purpose, so a mistyped id can never
        # appear in a real item's history.
        audit.log_rejection(creator_id="unknown", reason="appeal_unknown_content_id",
                            attempted_content_id=content_id, path=request.path)
        return _not_found(content_id)

    earlier_appeals = sum(1 for e in entries if e.get("event") == "appeal")
    audit.log_appeal(
        content_id=content_id,
        creator_id=decision.get("creator_id", "unknown"),
        reasoning=reasoning,
    )

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": APPEAL_ADDED if earlier_appeals else APPEAL_RECORDED,
        "appeal_count": earlier_appeals + 1,
        "original_decision": {
            "guess": decision.get("guess"),
            "confidence": decision.get("combined_score"),
            "label": decision.get("label"),
            "decided_at": decision.get("timestamp"),
        },
    })


# ── Stretch: one item's status ────────────────────────────────────────────────

@app.get("/content/<content_id>")
def content_status(content_id):
    """
    Where one submission stands now: its decision, its current status, and
    every appeal against it, oldest first.

        curl http://127.0.0.1:5000/content/<content_id>

    The status is whatever the item's latest decision-or-appeal entry says,
    so it follows the append-only log rather than a second copy of the truth.
    """
    entries = audit.entries_for(content_id)
    decision = _decision_in(entries)
    if decision is None:
        return _not_found(content_id)

    history = [e for e in entries if e.get("event") in (None, "appeal")]
    appeals = [e for e in history if e.get("event") == "appeal"]

    return jsonify({
        "content_id": content_id,
        "creator_id": decision.get("creator_id"),
        "status": history[-1].get("status"),
        "guess": decision.get("guess"),
        "confidence": decision.get("combined_score"),
        "label": decision.get("label"),
        "model_score": decision.get("model_score"),
        "style_score": decision.get("style_score"),
        "decided_at": decision.get("timestamp"),
        "appeals": [{"timestamp": a.get("timestamp"), "reasoning": a.get("reasoning")}
                    for a in appeals],
    })


# ── Already works ─────────────────────────────────────────────────────────────

@app.get("/log")
def get_log():
    """
    The audit log, most recent last.

        curl "http://127.0.0.1:5000/log?limit=10"

    You need this in unit 8 to paste entries into your README, and you need it
    now to see whether your logging is actually working.
    """
    limit = request.args.get("limit", type=int)
    entries = audit.read_entries(limit=limit)
    return jsonify({"count": len(entries), "entries": entries})


# ── Errors as JSON ────────────────────────────────────────────────────────────

@app.errorhandler(413)
def body_too_large(exc):
    """A body over MAX_BODY_BYTES. Logged like any other refusal."""
    audit.log_rejection(creator_id="unknown", reason="body_too_large",
                        http_status=413, path=request.path)
    return jsonify({
        "error": "body_too_large",
        "message": f"Request bodies are limited to {config.MAX_BODY_BYTES:,} bytes.",
    }), 413


@app.errorhandler(HTTPException)
def http_error_as_json(exc):
    """
    Any other HTTP error — a 404 for a mistyped path, a 405 for GET /submit —
    as JSON instead of an HTML page, so every caller can parse every answer.
    """
    name = (exc.name or "error").lower().replace(" ", "_")
    return jsonify({"error": name, "message": exc.description}), exc.code


def main():
    print(f"Provenance Guard on http://{config.HOST}:{config.PORT}")
    print(f"  detector model:  {config.DETECTOR_MODEL}")
    print(f"  rate limiting:   {'ON' if config.RATE_LIMITING_ENABLED else 'off (unit 8)'}")
    print(f"  audit log:       {config.AUDIT_LOG}")
    print()
    print("Check it's alive:")
    print(f'  curl -X POST http://{config.HOST}:{config.PORT}/ping \\')
    print('    -H "Content-Type: application/json" \\')
    print("    -d '{\"message\": \"hello\"}'")
    print()
    # debug=True hands out an interactive debugger, so it's local-only — see config.py
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)


if __name__ == "__main__":
    main()
