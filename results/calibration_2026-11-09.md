# Calibration — Milestone 4

- Produced by: `calibrate.py::main` on the texts in `calibration_texts.py`
- Scoring: `detector.py::model_signal`, `stylometry.py::style_parts`,
  `scoring.py::combine_signals`, `scoring.py::score_to_label`
- 2026-11-09, after `criteria.md` was committed (fb27373). Before this, the
  only runs used a stubbed detector.
- Nothing here went through the service, so none of it is in the audit log.

**The texts.** Three AI paragraphs written by Claude (expository, personal
narrative, advice), the advice one again with light hand edits, and three
public-domain human passages: Jerome K. Jerome, *Three Men in a Boat* (1889,
casual), Booker T. Washington, *Up from Slavery* (1901, plain), and J. S. Mill,
*On Liberty* (1859, formal). None of them is my own writing, which is kept for
the criteria tests.

**Columns.** Perplexity and `model_score` are signal one. Spread (CV), TTR and
Punct /100w are the raw style measures; "→ AI" is each one's 0–1
machine-likeness; `style_score` is their average. Combined is
`combine_signals` (weights 0.6 / 0.4, pull 0.8).

## Run 1: starting settings

Detector midpoint 45, steepness 1.6 (the starter's). Style anchors spread
(0.25, 0.75), vocab (0.65, 0.85), punct (0, 6). Thresholds 0.35 / 0.70.

| Text | Words | Perplexity | model_score | Spread (CV) | TTR | Punct /100w | spread → AI | vocab → AI | punct → AI | style_score | Combined | Label |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ai_expository` | 164 | 20.8 | 0.774 | 0.365 | 0.894 | 0.00 | 0.77 | 0.00 | 1.00 | 0.590 | 0.671 | unsure |
| `ai_narrative` | 176 | 22.0 | 0.758 | 0.403 | 0.831 | 0.00 | 0.69 | 0.09 | 1.00 | 0.596 | 0.668 | unsure |
| `ai_advice` | 168 | 18.1 | 0.811 | 0.498 | 0.833 | 0.00 | 0.50 | 0.09 | 1.00 | 0.530 | 0.654 | unsure |
| `ai_lightly_edited` | 157 | 21.3 | 0.767 | 0.530 | 0.865 | 1.27 | 0.44 | 0.00 | 0.79 | 0.409 | 0.589 | unsure |
| `human_casual` | 396 | 34.6 | 0.603 | 0.702 | 0.794 | 3.03 | 0.10 | 0.28 | 0.49 | 0.290 | 0.484 | unsure |
| `human_plain` | 240 | 24.4 | 0.726 | 0.429 | 0.779 | 1.67 | 0.64 | 0.36 | 0.72 | 0.573 | 0.645 | unsure |
| `human_formal` | 228 | 28.6 | 0.673 | 0.520 | 0.790 | 2.19 | 0.46 | 0.30 | 0.63 | 0.465 | 0.575 | unsure |

AI average 0.664, human average 0.568: **a gap of 0.10, and every text
"unsure".**

What it showed:

1. **The vocabulary measure ran backwards.** Every AI paragraph had *more*
   varied vocabulary (TTR 0.83–0.89) than every human passage (0.78–0.79), so
   "vocab → AI" called the AI text the most human thing in the set. Published
   comparisons of ChatGPT and student essays found the same direction.
2. **Signal one leaned AI on everything.** At midpoint 45, every human
   passage scored above 0.5 (0.60–0.73). Their perplexity (24–35) sits below
   45, so the midpoint was inside ordinary human prose instead of between
   human and machine text.
3. **The plain human passage scored nearly like AI on signal one**: 0.726,
   against 0.758–0.811 for the AI texts. That's the blind spot from
   Milestone 1, measured.
4. **Punctuation separated cleanly.** All three AI texts used no varied
   punctuation at all, but the human-like end (6 per 100 words) was too far
   out: the most expressive human passage only reached 3.0.

## The changes

| Setting | Was | Now | Why |
|---|---|---|---|
| `VOCAB_ANCHORS` | (0.65, 0.85) | **(0.88, 0.74)**, flipped | Finding 1. It also stops a plain writer's small vocabulary counting against them on top of signal one |
| `PUNCT_ANCHORS` | (0.0, 6.0) | (0.0, **4.0**) | Finding 4. Real human punctuation should read as human |
| detector midpoint | 45 | **30** | Finding 2. Puts the 0.5 point between the AI texts (18–22) and most human ones (29–35) |
| detector steepness | 1.6 | **2.5** | The two groups are only ~1.5× apart in perplexity; at 1.6 the curve is too flat to tell them apart |
| `HUMAN_THRESHOLD` | 0.35 | **0.40** | With the changes above, the casual human passage scored 0.364 and nothing could reach 0.35. 0.40 keeps the AI threshold twice as far from the middle (0.20 vs 0.10) |

Unchanged: `SPREAD_ANCHORS`, weights 0.6 / 0.4, pull 0.8, `AI_THRESHOLD` 0.70.

## Run 2: after the changes

| Text | Words | Perplexity | model_score | Spread (CV) | TTR | Punct /100w | spread → AI | vocab → AI | punct → AI | style_score | Combined | Label |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ai_expository` | 164 | 20.8 | 0.714 | 0.365 | 0.894 | 0.00 | 0.77 | 1.00 | 1.00 | 0.923 | 0.748 | ai |
| `ai_narrative` | 176 | 22.0 | 0.684 | 0.403 | 0.831 | 0.00 | 0.69 | 0.65 | 1.00 | 0.781 | 0.706 | ai |
| `ai_advice` | 168 | 18.1 | 0.779 | 0.498 | 0.833 | 0.00 | 0.50 | 0.66 | 1.00 | 0.722 | 0.745 | ai |
| `ai_lightly_edited` | 157 | 21.3 | 0.701 | 0.530 | 0.865 | 1.27 | 0.44 | 0.89 | 0.68 | 0.671 | 0.685 | unsure |
| `human_casual` | 396 | 34.6 | 0.411 | 0.702 | 0.794 | 3.03 | 0.10 | 0.38 | 0.24 | 0.241 | 0.364 | human |
| `human_plain` | 240 | 24.4 | 0.625 | 0.429 | 0.779 | 1.67 | 0.64 | 0.28 | 0.58 | 0.501 | 0.568 | unsure |
| `human_formal` | 228 | 28.6 | 0.529 | 0.520 | 0.790 | 2.19 | 0.46 | 0.36 | 0.45 | 0.423 | 0.488 | unsure |

AI average 0.733, human average 0.473: **a gap of 0.26.** All three labels
are reached, with no crossed confident label.

## What this does and doesn't show

- Seven texts tuned five settings, so this is a fit, not a test. Criteria 1–3
  are tested in unit 8 on texts that played no part here.
- The gap of 0.26 is **below the 0.30 my criterion 2 asks for**, even on the
  texts it was tuned on. I'm not tuning toward it, which would be fitting the
  criterion; I expect criterion 2 to be at risk.
- The plain human passage lands on "unsure" (0.568), not "AI". That's the
  disagreement rule doing its job: signal one says 0.625, the style signal
  only 0.501.
- Lightly editing an AI paragraph (contractions, an aside in brackets, one
  typo) moved it from AI (0.745) to unsure (0.685). Most of that came from the
  style signal (0.722 → 0.671) and very little from signal one (0.779 →
  0.701). The style signal's blind spot is exactly what unit 8's evasion
  attacks will lean on.
- All three AI texts came from one model (Claude), and none of them uses
  dashes or colons. AI text that does, as many chatbots' does, would look
  more human to the punctuation measure.
- The human passages are 120–170 years old. Modern informal writing is likely
  to have higher perplexity, which pushes it toward "human" on signal one.
