"""
Turning two numbers into one, and one number into something a person can read.

`combine_signals` is where the false-positive decision from Milestone 1 gets
made. Everything above it — the labels, the appeal path — is downstream of a
number this function produced.

`score_to_label` is where the number becomes a sentence. A score of 0.62
means nothing to a writer.

README.md → "Signals and Scoring" names `scoring.py::combine_signals` as the
home of the combining rule, and "Label Variants" quotes the three labels word
for word. The numbers both use live in config.py.

    python scoring.py        prints the score band each label covers
"""

import math

import config


def _unit(value) -> float:
    """Clamp to 0–1. A missing or NaN score counts as 0.5 — no evidence either way."""
    if value is None:
        return 0.5
    value = float(value)
    if math.isnan(value):
        return 0.5
    return min(max(value, 0.0), 1.0)


def combine_signals(model_score: float, style_score: float) -> float:
    """
    Combine two 0–1 signals into one 0–1 score. Higher = more likely AI.

    The rule: take a weighted average of the two signals, then pull it back
    toward 0.5 in proportion to how far apart they are.

        average   = (w_model * model + w_style * style) / (w_model + w_style)
        agreement = 1 - DISAGREEMENT_PULL * |model - style|
        combined  = 0.5 + (average - 0.5) * agreement

    When the signals agree, the average stands. When they disagree, the score
    drifts toward the middle, so neither signal on its own can push writing
    into a confident label. Two methods disagreeing IS uncertainty.

    It's wrong on purpose in one direction: AI text that only one signal
    catches comes out "unsure" rather than "AI". That's the price of never
    letting the model signal alone accuse a plain writer — the false positive
    traced in README.md.

    Raising either signal never lowers the result, as long as
    DISAGREEMENT_PULL stays at or below twice the smaller weight. Weights and
    the pull are in config.py, with that bound explained.
    """
    m = _unit(model_score)
    s = _unit(style_score)
    w_m = config.WEIGHT_MODEL_SIGNAL
    w_s = config.WEIGHT_STYLE_SIGNAL

    average = (w_m * m + w_s * s) / (w_m + w_s)
    agreement = max(0.0, 1.0 - config.DISAGREEMENT_PULL * abs(m - s))
    combined = 0.5 + (average - 0.5) * agreement
    return round(_unit(combined), 4)


# ── What a reader sees ───────────────────────────────────────────────────────
# Written for someone who has never heard the word "threshold". Each label
# talks about the piece, not the person; only the last sentence of the unsure
# and AI labels speaks to the writer, to say what they can do.
#
# Second draft. A first draft was read back "as the writer" (README.md → Label
# Variants). The unsure label felt like "a small cloud with no way to clear
# it", so it now offers a review. The AI label read as "you cheated", so it now
# attributes the claim to the checks, says it isn't proof, and says an appeal
# needs only the writer's own words.

LABEL_HUMAN = (
    "We think a person wrote this. Our automated checks found that its wording "
    "and the shape of its sentences look like human writing."
)

LABEL_UNSURE = (
    "Our automated checks couldn't tell either way on this piece. That's "
    "common with genuine human writing, especially short or plainly worded "
    "pieces, and it isn't an accusation. If you wrote this and want a person "
    "to confirm it, you can ask for a review."
)

LABEL_AI = (
    "Our automated checks rate this as likely AI-generated: both its wording "
    "and the shape of its sentences point that way. These checks are sometimes "
    "wrong, most often on plain or second-language writing, so this is not "
    "proof. If you wrote it yourself, you can appeal in your own words and a "
    "person will review it."
)


def score_to_label(score: float) -> tuple[str, str]:
    """
    Turn a score into a guess and the text a reader actually sees.

    Returns:
        (guess, label_text) — `guess` is "ai", "human" or "unsure"; the label
        is the full sentence shown to a person.

    Every score from 0.0 to 1.0 lands in exactly one band: the AI check runs
    first, then the human check, and everything left over is "unsure" — so
    there is no gap to fall through.
    """
    score = _unit(score)
    if score >= config.AI_THRESHOLD:
        return "ai", LABEL_AI
    if score <= config.HUMAN_THRESHOLD:
        return "human", LABEL_HUMAN
    return "unsure", LABEL_UNSURE


def label_ranges() -> list[tuple[str, str]]:
    """
    The score range each label covers. README.md → "Label Variants" quotes
    these, generated here so the numbers can't drift apart from config.py.
    """
    h, a = config.HUMAN_THRESHOLD, config.AI_THRESHOLD
    return [
        ("high-confidence human", f"0.00 – {h:.2f}"),
        ("unsure", f"above {h:.2f} and below {a:.2f}"),
        ("high-confidence AI", f"{a:.2f} – 1.00"),
    ]


if __name__ == "__main__":
    for name, band in label_ranges():
        print(f"{name:<22} {band}")
