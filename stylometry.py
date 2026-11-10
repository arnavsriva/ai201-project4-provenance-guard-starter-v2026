"""
Signal two: the style signal.

Signal one reads the text for meaning. This one measures it *as text* — the
shape of it, without understanding a word.

Three measures, each on its own scale:

    sentence_length_spread   do sentences vary in length, or march in step?
                             coefficient of variation; HIGHER = more human
    type_token_ratio         how much of the vocabulary repeats?
                             moving-average ratio, 0–1; HIGHER = more MACHINE-like
                             (see below: the calibration texts ran this way)
    punctuation_density      how much punctuation beyond commas and full stops?
                             marks per 100 words; HIGHER = more human

`style_parts` puts each on a 0–1 "how machine-like" scale with a straight-line
ramp between two anchors, and averages them into `style_signal`.

Why these might differ between human and AI writing: generated prose tends
toward even, mid-length sentences and tidy punctuation, because that's what
"most likely next word" produces on average. Human writing is lumpier — a
three-word sentence next to a forty-word one, a dash, a question.

Vocabulary is the surprise. The brief's guess was that AI text has a narrower
vocabulary. On the Milestone 4 calibration texts it was the other way round:
the AI paragraphs scored 0.83–0.89 and the human passages 0.78–0.79, matching
published comparisons of ChatGPT and student essays. So the ramp runs the
other way — and that also means a plain writer with a small, repeated
vocabulary scores HUMAN here, instead of being accused by this measure on top
of signal one.

⚠️ **The blind spot.**

This signal cannot read. It has no idea what the text says. Anything that
changes the shape without changing the substance moves it — adding typos,
breaking up sentences, pasting in a quotation. That is a very cheap thing for
someone to do on purpose, and unit 8's attack set will do it to you.

From a terminal:

    python stylometry.py "some text to look at"
"""

import re
import statistics


# Titles and Latin abbreviations end in a full stop without ending a sentence.
# Splitting after them turned "Mrs. Ruffner" into a one-word "sentence", which
# inflated sentence_length_spread for any text with a title in it.
_NOT_SENTENCE_ENDS = {"mr.", "mrs.", "ms.", "dr.", "st.", "jr.", "sr.",
                      "prof.", "mt.", "vs.", "e.g.", "i.e."}


def sentences(text: str) -> list[str]:
    """
    Split into sentences. Rough and good enough — given to you, with one
    change: a piece ending in a title like "Mrs." is glued back onto the next.
    """
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    merged: list[str] = []
    for part in parts:
        if merged and merged[-1].split()[-1].lower() in _NOT_SENTENCE_ENDS:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return [p for p in merged if p.strip()]


def words(text: str) -> list[str]:
    """Split into lowercase words, punctuation stripped. Given to you."""
    return re.findall(r"[a-z0-9']+", text.lower())


# ── The three measures ───────────────────────────────────────────────────────

def sentence_length_spread(text: str) -> float | None:
    """
    How much sentence length varies: the standard deviation of sentence
    lengths (in words) divided by their mean — the coefficient of variation.
    Dividing by the mean makes a text of long sentences and a text of short
    ones comparable.

    Returns:
        0.0 when every sentence is the same length, rising as they vary.
        Most prose lands roughly 0.2–0.9. HIGHER = MORE HUMAN.

        None for fewer than two sentences. One sentence has no spread at all,
        and calling that "perfectly even" would push every one-sentence
        submission toward AI for no reason. `style_parts` treats None as no
        evidence either way (0.5).
    """
    lengths = [len(words(s)) for s in sentences(text)]
    lengths = [n for n in lengths if n > 0]
    if len(lengths) < 2:
        return None
    return statistics.stdev(lengths) / statistics.mean(lengths)


TTR_WINDOW = 50


def type_token_ratio(text: str) -> float:
    """
    Unique words over total words, averaged over every 50-word window (the
    "moving-average type-token ratio", MATTR).

    Plain unique/total falls as text gets longer, because common words repeat,
    so a 400-word essay would look less varied than a 60-word note just for
    being long. Measuring fixed 50-word windows and averaging them makes texts
    of different lengths comparable. Under 50 words it's plain unique/total,
    which runs a little high; that errs toward human, the safe direction.

    Returns:
        A float between 0 and 1. HIGHER = MORE VARIED VOCABULARY, which the
        calibration found to be MORE MACHINE-LIKE (see the module docstring).
        0.0 for text with no words.
    """
    tokens = words(text)
    if not tokens:
        return 0.0
    if len(tokens) <= TTR_WINDOW:
        return len(set(tokens)) / len(tokens)
    ratios = [
        len(set(tokens[i:i + TTR_WINDOW])) / TTR_WINDOW
        for i in range(len(tokens) - TTR_WINDOW + 1)
    ]
    return statistics.mean(ratios)


# Full stops and commas are left out on purpose. Every writer uses them, at
# about the rate their sentence count demands, so counting them mostly
# re-measures sentence length. These are the marks that vary between writers.
_VARIED_PUNCTUATION = re.compile(
    r"\.\.\.|…"                       # ellipses
    r"|--|—|–|(?<=\s)-(?=\s)"         # dashes, but not hyphens inside words
    r"|[;:!?()\[\]\"“”]"              # ; : ? ! brackets, double quotes
    r"|(?<!\w)['‘’]|['‘’](?!\w)"      # single quotes used as quotes, not apostrophes
)


def punctuation_density(text: str) -> float:
    """
    Varied punctuation per 100 words: semicolons, colons, dashes, brackets,
    question and exclamation marks, quotation marks and ellipses. Commas,
    full stops, apostrophes in words (don't) and hyphens in words (well-known)
    don't count.

    Returns:
        0.0 upward; most prose lands 0–10. HIGHER = MORE HUMAN.
        0.0 for text with no words.
    """
    n_words = len(words(text))
    if n_words == 0:
        return 0.0
    return 100 * len(_VARIED_PUNCTUATION.findall(text)) / n_words


# ── Combining them ───────────────────────────────────────────────────────────
# Each measure goes onto a 0–1 "how machine-like" scale with a straight-line
# ramp between two anchors:
#
#     (machine-like end, human-like end)
#
# A value at the machine-like end scores 1.0, at the human-like end 0.0,
# straight line between, clamped beyond either end. That flips the measures
# that run "higher = more human" and puts all three on one scale, so no
# measure wins just by having bigger raw numbers.
#
# Set in Milestone 4 from the calibration texts — README.md → "Signals and
# Scoring" has the table:
#   spread  AI 0.37–0.50, human 0.43–0.70. The weakest of the three; kept at
#           the starting anchors.
#   vocab   AI 0.83–0.89, human 0.78–0.79. FLIPPED from the starting
#           (0.65, 0.85), which ran backwards on every text.
#   punct   AI 0.0 on all three, human 1.7–3.0. Human-like end lowered from
#           6.0 to 4.0, so real human punctuation reads as human.

SPREAD_ANCHORS = (0.25, 0.75)
VOCAB_ANCHORS = (0.88, 0.74)
PUNCT_ANCHORS = (0.0, 4.0)

MEASURE_WEIGHTS = {"spread": 1.0, "vocab": 1.0, "punct": 1.0}


def _ramp(value: float | None, machine_end: float, human_end: float) -> float:
    """0–1 machine-likeness of one measure. None (no evidence) is 0.5."""
    if value is None:
        return 0.5
    position = (value - machine_end) / (human_end - machine_end)
    return min(max(1.0 - position, 0.0), 1.0)


def style_parts(text: str) -> dict:
    """
    Every number behind the style score: the three raw measures, each one's
    0–1 machine-likeness, and the weighted average of those.

    The service logs this whole dict beside each decision, because when a
    style score surprises you next unit, the first question is which of the
    three moved.
    """
    spread = sentence_length_spread(text)
    vocab = type_token_ratio(text)
    punct = punctuation_density(text)

    ai = {
        "spread": _ramp(spread, *SPREAD_ANCHORS),
        "vocab": _ramp(vocab, *VOCAB_ANCHORS),
        "punct": _ramp(punct, *PUNCT_ANCHORS),
    }
    total = sum(MEASURE_WEIGHTS.values())
    score = sum(MEASURE_WEIGHTS[name] * ai[name] for name in ai) / total

    return {
        "sentence_length_spread": None if spread is None else round(spread, 4),
        "type_token_ratio": round(vocab, 4),
        "punctuation_density": round(punct, 4),
        "spread_ai": round(ai["spread"], 4),
        "vocab_ai": round(ai["vocab"], 4),
        "punct_ai": round(ai["punct"], 4),
        "style_score": round(score, 4),
    }


def style_signal(text: str) -> float:
    """
    The style signal as a 0–1 score. **Higher means more likely AI** — the
    same direction as `detector.model_signal`, so `scoring.combine_signals`
    can treat the two alike.
    """
    return style_parts(text)["style_score"]


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or (
        "The system works well. It handles most cases correctly and provides "
        "good results. Users generally find it easy to use and understand."
    )

    parts = style_parts(text)
    spread = parts["sentence_length_spread"]
    print(f"{len(sentences(text))} sentences, {len(words(text))} words\n")
    print(f"{'measure':<24} {'raw':>8}   machine-like (0–1)")
    print(f"{'sentence_length_spread':<24} {'—' if spread is None else f'{spread:.3f}':>8}   {parts['spread_ai']:.3f}")
    print(f"{'type_token_ratio':<24} {parts['type_token_ratio']:>8.3f}   {parts['vocab_ai']:.3f}")
    print(f"{'punctuation_density':<24} {parts['punctuation_density']:>8.3f}   {parts['punct_ai']:.3f}")
    print(f"\nstyle_signal             {parts['style_score']:.4f}   (higher = more likely AI)")
