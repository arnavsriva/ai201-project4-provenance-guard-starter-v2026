"""
Settings for Provenance Guard.

Everything you're likely to change lives here, at the top, on purpose.

You'll edit the thresholds in Milestone 5 and the rate limits in unit 8.
"""

import os
from pathlib import Path

ROOT = Path(__file__).parent


# ─── The service ─────────────────────────────────────────────────────────────

# `127.0.0.1` is loopback — only your own machine can reach it, which is what
# you want all through units 7 and 8. A host somewhere else has to accept
# traffic from outside the box, and that means `0.0.0.0`. Setting the env var
# is how you get it; the default keeps your local `curl` commands unchanged.
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))

# Flask's debug mode gives anyone who can reach the service an interactive
# Python prompt inside your process. Fine on loopback, a gift to strangers
# anywhere else — so it turns itself off the moment HOST isn't loopback.
DEBUG = os.getenv("AI201_DEBUG", "1") == "1" and HOST in ("127.0.0.1", "localhost")


# ─── The local model ─────────────────────────────────────────────────────────
# Your first signal runs a language model ON YOUR OWN MACHINE. No account, no
# key, no card. It downloads about 550 MB the first time — do that before
# class, not during it.
#
# What it measures: how *predictable* your text is to a language model. Text a
# model finds easy to predict tends to be text a model wrote.
#
# The first call is the slow one — ten to twenty seconds while the model loads,
# longer on an older laptop. After that it stays in memory and a submission
# takes a second or two. That cost is part of what you're learning: this is
# what running a model inline in a request actually looks like.

DETECTOR_MODEL = os.getenv("AI201_DETECTOR_MODEL", "gpt2")

# Longer text gives a steadier reading but takes longer. 400 tokens is roughly
# 300 words, which is enough for the signal to mean something.
DETECTOR_MAX_TOKENS = 400


# ─── What /submit and /appeal accept (Milestone 3) ───────────────────────────
# README.md → "The contract" quotes these numbers. Change one here, change it
# there too.
#
# MIN_WORDS — below this, neither signal means anything: perplexity over a
# dozen tokens is mostly noise, and one or two sentences have no spread to
# measure. Too-short text is refused with a 400, which is kinder to a writer
# than a confident-sounding label built on nothing.
#
# MAX_TEXT_CHARS — the model only reads the first ~400 tokens anyway, and
# 20,000 characters (~3,500 words) is a long essay. Past that, someone is
# testing the service rather than submitting writing.

MIN_WORDS = 20
MAX_TEXT_CHARS = 20_000
MAX_CREATOR_ID_CHARS = 100
MAX_REASONING_CHARS = 5_000

# A request body bigger than this is refused before any route parses it.
MAX_BODY_BYTES = 1_000_000


# ─── Scoring (Milestone 4) ───────────────────────────────────────────────────
# The rule is in scoring.py::combine_signals; its numbers are here. README.md →
# "Signals and Scoring" explains both.

WEIGHT_MODEL_SIGNAL = 0.6
WEIGHT_STYLE_SIGNAL = 0.4

# How hard disagreement between the two signals pulls the combined score back
# toward 0.5. 0.0 is no pull at all — a plain weighted average.
#
# ⚠️ Keep it at or below 2 × the smaller weight (weights normalised to sum to
# 1). Above that the rule stops being monotone: raising one signal can LOWER
# the score slightly, which right at a threshold flips the label the wrong way
# (model 0.41 + style 0.00 → unsure, but style 0.02 → human). With 0.6 / 0.4
# the ceiling is 0.8. test_service.py checks this.
DISAGREEMENT_PULL = 0.8


# ─── Thresholds (Milestone 5) ────────────────────────────────────────────────
# Where one label becomes another. Scores run 0.0 (confidently human) to 1.0
# (confidently AI).
#
#   score <= HUMAN_THRESHOLD          -> high-confidence human
#   between the two                   -> unsure
#   score >= AI_THRESHOLD             -> high-confidence AI
#
# ⚠️ This is where the false-positive decision from Milestone 1 gets made.
# Widening the unsure band means fewer wrong accusations and more AI text
# getting through. There is no setting that avoids the trade — only settings
# that decide who pays for it.
#
# The AI threshold sits twice as far from 0.5 as the human one (0.20 against
# 0.10) on purpose: calling a real writer's work AI costs them far more than
# missing some AI text costs anyone else.
#
# Set in Milestone 5. HUMAN_THRESHOLD started at 0.35; on the calibration
# texts no human passage could reach it, because signal one leans AI on
# plain prose and the disagreement pull keeps a lone signal from going far.
# 0.40 makes the human label reachable without moving the AI side at all.

HUMAN_THRESHOLD = 0.40
AI_THRESHOLD = 0.70

# The disagreement pull means the AI label is only reachable when BOTH signals
# lean AI — that's the point of it. `python scoring.py` prints the bands.


# ─── Rate limiting (UNIT 8) ──────────────────────────────────────────────────
# Off in unit 7. You turn it on and choose the numbers in unit 8, Milestone 1.
#
# Think about two people: a real writer submitting their own work a few times
# an hour, and a script sending a thousand variations to map your thresholds.
# Your README has to say why your numbers and not others.

RATE_LIMITING_ENABLED = os.getenv("AI201_RATE_LIMITS", "0") == "1"

RATE_LIMIT_PER_MINUTE = 10
RATE_LIMIT_PER_DAY = 200

# Flask-Limiter warns loudly without this. In-memory is right for one laptop
# and wrong for anything real — a restart forgets every count, and two copies
# of the service wouldn't share limits.
RATE_LIMIT_STORAGE = "memory://"


# ─── Paths ───────────────────────────────────────────────────────────────────

LOG_DIR = ROOT / "logs"
AUDIT_LOG = LOG_DIR / "audit.jsonl"
RESULTS_DIR = ROOT / "results"
