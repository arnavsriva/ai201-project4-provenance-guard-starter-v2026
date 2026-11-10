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
# Written for someone who has never heard the word "threshold". The reader may
# be the writer, so none of them says "you".

LABEL_HUMAN = (
    "We think a person wrote this. Our automated checks found its wording and "
    "its sentence patterns typical of human writing."
)

LABEL_UNSURE = (
    "Our automated checks couldn't tell whether this was written by a person "
    "or by AI. Their results were mixed or in the middle, which is common for "
    "genuine human writing, especially short or plainly worded pieces. This "
    "label is not a finding that AI was used."
)

LABEL_AI = (
    "This looks likely to be AI-generated: our two automated checks, of how "
    "predictable the wording is and how uniform the sentences are, both point "
    "that way. They can be wrong, most often on plain or second-language "
    "writing. If you wrote this yourself, you can appeal and a person will "
    "review it."
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
