# Provenance Guard

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first.**
>
> Once `python test.py` passes, in one terminal:
>
> ```bash
> python app.py
> ```
>
> and in another:
>
> ```bash
> curl -X POST http://127.0.0.1:5000/ping \
>   -H "Content-Type: application/json" \
>   -d '{"message": "hello"}'
> ```
>
> That's a web service. Something sent it text and it sent something back.
> Everything this unit is filling in the middle.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     Unit 7 asks for the first five sections. Unit 8 adds the five below.

     Everything is pasted as TEXT. A pasted curl response gets full credit;
     a picture of your terminal gets none.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 7 — THE BUILD ═══════════════════════ -->

## What This Does

<!-- The path a submission takes, from arriving to the label a reader sees.
     Six or seven steps — this is the trace you wrote in Milestone 1. -->

Provenance Guard reads a piece of writing and says, in plain words, whether it
looks machine-written, human-written, or too close to call. It also gives the
writer a way to push back when it gets that wrong.

**Stretch feature I'm adding:** `GET /content/<content_id>`, which returns one
item's current status and any appeals, so a writer can check where their
appeal stands.

### The path a submission takes

1. **It arrives at `POST /submit`** (`app.py::submit`) as JSON:
   `{"text": ..., "creator_id": ...}`. The route checks the input before
   anything else runs: the body must be a JSON object, `text` a string of at
   least 20 words and at most 20,000 characters, and `creator_id` a non-empty
   string. Anything else is refused with a 400 (413 for too long) that names
   the field, and the refusal is written to the audit log
   (`audit.log_rejection`), so a flood of bad requests still leaves a trace.
   *Adds: both signals are guaranteed real text.*
2. **It gets a `content_id`**, a random UUID. *Adds: the handle that the appeal
   and the status lookup refer back to.*
3. **Signal one reads it.** `detector.model_signal(text)` runs GPT-2 locally,
   measures how predictable the first ~400 tokens are (perplexity), and maps
   that to a 0–1 `model_score`, where higher means more machine-like. *Adds: a
   judgement about the wording.*
4. **Signal two measures it.** `stylometry.style_signal(text)` uses no model.
   It measures sentence-length variation, vocabulary variety and punctuation
   and maps them to a 0–1 `style_score`, where higher means more machine-like.
   *Adds: a judgement about the shape, made independently of the first.*
5. **The two are combined.** `scoring.combine_signals(model_score,
   style_score)` returns `confidence`, from 0 (confidently human) to 1
   (confidently AI). When the signals disagree, the score is pulled toward the
   middle, because two methods disagreeing is uncertainty. *Adds: one number,
   and the decision about how far to trust a lone signal.*
6. **The number becomes words.** `scoring.score_to_label(confidence)` returns
   a `guess` (`ai` / `human` / `unsure`) and the full sentence a reader sees.
   *Adds: something a person can understand and act on.*
7. **It's logged, then answered.** `audit.log_decision(...)` appends one JSON
   line to `logs/audit.jsonl` with all nine fields: timestamp, content_id,
   creator_id, guess, model_score, style_score, combined_score, label and
   status (`decided`). The same facts go back to the caller as JSON. *Adds: a
   permanent record an appeal can attach to.*

**If the writer disagrees,** they send `POST /appeal` (`app.py::appeal`) with
the `content_id` and their reasoning. The route looks the id up in the log. An
unknown id gets a 404, never a silent success. It then appends an appeal entry
beside the original decision with status `under_review` (`audit.log_appeal`;
nothing is overwritten) and confirms. Nothing is re-scored automatically: the
item waits for a person.

### The contract

**`POST /submit`**

| Request field | Type | Rule |
|---|---|---|
| `text` | string | Required. At least 20 words after trimming, at most 20,000 characters |
| `creator_id` | string | Required. 1–100 characters after trimming |

| Response field (200) | Type | Meaning |
|---|---|---|
| `content_id` | string | UUID for this submission. Needed to appeal |
| `creator_id` | string | Echoed back |
| `guess` | string | `"ai"`, `"human"` or `"unsure"` |
| `confidence` | float, 0–1 | The combined score: 0 = confidently human, 1 = confidently AI. The log calls the same number `combined_score` |
| `label` | string | The full sentence a reader sees |
| `model_score` | float, 0–1 | Signal one alone. Higher = more AI-like |
| `style_score` | float, 0–1 | Signal two alone. Higher = more AI-like |
| `status` | string | `"decided"` |

Errors:

- `400 {"error": "invalid_input", "field": ..., "message": ...}`: the body
  isn't a JSON object, a field is missing, blank or not a string, the text
  is under 20 words, or `creator_id` is over 100 characters.
- `413 {"error": "text_too_long", ...}`: the text is over 20,000 characters.
  A whole request body over 1 MB gets `413 {"error": "body_too_large", ...}`
  before the route even reads it.
- `503 {"error": "detector_unavailable", ...}`: the model couldn't load.
  Nothing is decided and nothing is labelled.

Every refusal is logged with `status: "rejected"`.

**`POST /appeal`**

| Request field | Type | Rule |
|---|---|---|
| `content_id` | string | Required. Must match a submission in the log |
| `reasoning` | string | Required. 1–5,000 characters after trimming |

| Response field (200) | Type | Meaning |
|---|---|---|
| `content_id` | string | Echoed back |
| `status` | string | `"under_review"` |
| `message` | string | Plain-English confirmation for the writer |
| `appeal_count` | int | Appeals recorded on this item, including this one |
| `original_decision` | object | `guess`, `confidence`, `label` and `decided_at` from the first decision. Never changed |

Errors:

- `400 invalid_input`: a field is missing, blank or not a string, or
  `reasoning` is over 5,000 characters.
- `404 {"error": "not_found", ...}`: the content_id was never issued.

A refused appeal is logged too, under `attempted_content_id`, so a mistyped
id never shows up in a real item's history.

A second appeal on the same item is recorded too, and the status stays
`under_review`.

**`GET /content/<content_id>`** (stretch) returns `content_id`, `creator_id`,
`status`, `guess`, `confidence`, `label`, `model_score`, `style_score`,
`decided_at` and `appeals` (a list of `{timestamp, reasoning}`). An unknown id
gets a 404.

### Following a false positive through

A writer who learned English as a second language submits 180 words about
their first winter in a new city. They use short sentences and common words
they're sure of, and every word is theirs.

- **Signal one** finds the text easy to predict, because plain, common words
  are exactly what GPT-2 predicts well. I expect their `model_score` to come
  back high, around 0.7–0.8. That's the structural blind spot, not a bug.
- **Signal two is their only protection.** If their sentence lengths vary and
  their punctuation is their own, `style_score` lands mid-range or lower. The
  signals then disagree, and the combining rule pulls the score toward the
  middle, so the label is **unsure** rather than an accusation. If they also
  write in very even, short sentences, both signals agree and they can land on
  **likely AI**. That's the false positive.
- **What the label says to them:** never "you used AI". The AI label says what
  was measured, that the measurement can be wrong (plain and second-language
  writing are named as the known case), and how to appeal.
- **What they can do:** `POST /appeal` with their `content_id` and their
  reasons. The item moves to `under_review`, the appeal sits next to the
  original decision in the log, and `GET /content/<id>` shows them the status.

**What this decides:**

1. One signal alone is never enough for the AI label. Disagreement goes to
   "unsure".
2. The AI threshold sits further from the middle than the human threshold,
   because accusing this writer costs more than missing a machine-written
   paragraph.
3. The AI label's text names the appeal.

**Checked in Milestone 4** with a real plain passage (Booker T. Washington,
*Up from Slavery*, 1901). Signal one gave 0.73 at the starter's settings and
0.63 after calibration, the style signal gave 0.50, and the rule combined them
to 0.568: **unsure**, as the trace predicted. Its full run, with an appeal, is
the Sample Run below.

**Checks you can rerun:** `python test_service.py` runs about a hundred checks
of the routes, input handling, appeals and the combining rule, with the model
stubbed out, in a second. `python calibrate.py` scores the seven calibration
texts with both signals.

---

## Signals and Scoring

<!-- For each signal: what property it measures, why that might differ between
     human and AI writing, and WHAT IT CAN'T SEE.

     The blind spot is not optional. If you can't name it you don't understand
     the signal yet — and unit 8's attack set is built out of blind spots. -->

### Signal one — the model signal

**What it measures:** How predictable the text is to GPT-2: its perplexity
over the first ~400 tokens (about 300 words), mapped onto 0–1 so that low
perplexity (easy to predict) gives a high score. `detector.py::model_signal`.

**Why that might differ between human and AI writing:** A language model
writes by repeatedly choosing a likely next word, so its output sits where a
model expects it, which means low perplexity. People make odd, specific
choices, like a rare word or an abrupt turn, that a model fails to predict.

**What it can't see:** Who wrote it. Predictability isn't authorship. Plain
writing is predictable, so it scores machine-like: a second-language writer
sticking to words they're sure of, a younger writer, someone writing simply on
purpose, or a formulaic genre like instructions. It fails the other way too.
AI text pushed toward rare words, by a paraphrasing tool or a "use unusual
vocabulary" prompt, scores human. And it only reads the first ~400 tokens, so
anything after that is invisible to it. AI text placed under a human-written
opening paragraph would get past it.

**Calibrated in Milestone 4:** I moved the midpoint from 45 to 30 and the
steepness from 1.6 to 2.5, in `detector.py::model_signal`. At 45, every human
passage I tried scored above 0.5 on this signal (0.60–0.73). Their perplexity
(24–35) sat below the midpoint, so the signal leaned AI on all ordinary prose,
not only plain prose. 30 sits between my AI texts (18–22) and most of the
human ones (29–35). The two groups are only about 1.5× apart in perplexity,
which was too close for the old slope to separate. Both runs are in
[`results/calibration_2026-11-09.md`](results/calibration_2026-11-09.md).

### Signal two — the style signal

**What it measures:** The shape of the text, with no model and no idea what it
says (`stylometry.py::style_signal`): how much sentence length varies, how
varied the vocabulary is, and how much punctuation is used and of what kinds.

**Why that might differ between human and AI writing:** Generated prose tends
toward even, mid-length sentences and tidy punctuation, because "most likely
next word" produces the average case. People are lumpier: a three-word
sentence beside a forty-word one, a dash, a question. Vocabulary turned out to
work the other way from my first guess (see below).

**How it's computed** (`stylometry.py::style_parts`): three measures, each put
on a 0–1 machine-likeness scale by a straight line between two anchors, then
averaged with equal weight.

| Measure | What it counts | Machine-like end (→ 1.0) | Human-like end (→ 0.0) |
|---|---|---|---|
| `sentence_length_spread` | Standard deviation ÷ mean of sentence lengths in words | 0.25 | 0.75 |
| `type_token_ratio` | Unique ÷ total words, averaged over every 50-word window | 0.88 | 0.74 |
| `punctuation_density` | Semicolons, colons, dashes, brackets, ? and !, quotation marks and ellipses per 100 words; commas and full stops don't count | 0.0 | 4.0 |

**Vocabulary runs backwards from the brief's guess.** I started with "more
varied = more human". On the calibration texts, every AI paragraph had *more*
varied vocabulary (0.83–0.89) than every human passage (0.78–0.79), so I
flipped it. Published comparisons of ChatGPT and student essays found the same
direction. The flip also helps the writer from the false-positive trace: a
plain, repeated vocabulary now counts as *human* here, instead of being held
against them by both signals.

**What it can't see:** Meaning. Anything that changes the shape without
changing the substance moves it, and all of it is cheap to do on purpose:
typos, chopping sentences up or gluing them together, sprinkling in dashes or
semicolons, a pasted quotation. It's also unstable on short texts, because
one or two sentences have no meaningful spread. And it's genre-blind: a
recipe, a list or a poem has an unusual shape for reasons unrelated to who
wrote it.

### The combining rule

<!-- Write the rule in words, then give the numbers. What happens when the two
     signals disagree? -->

**The rule:** Take a weighted average of the two signals, then pull it back
toward 0.5 in proportion to how far apart they are. When the signals agree,
the average stands. When they disagree, the score drifts toward the middle, so
neither signal alone can push writing into a confident label. Two methods
disagreeing *is* uncertainty, and the writer in the false-positive trace is
exactly the case where one signal is wrong on its own.

```
average   = 0.6 × model_score + 0.4 × style_score
agreement = 1 − 0.8 × |model_score − style_score|
combined  = 0.5 + (average − 0.5) × agreement        → returned as "confidence"
```

**The numbers** (all in `config.py`):

| Setting | Value | Why |
|---|---|---|
| `WEIGHT_MODEL_SIGNAL` / `WEIGHT_STYLE_SIGNAL` | 0.6 / 0.4 | The style signal actually separated the calibration texts better. But its anchors were set from those same texts, and it's the signal a few typos and dashes can move: the lightly-edited AI paragraph lost 0.05 on style and slipped from AI to unsure. The model signal is harder to fool cheaply |
| `DISAGREEMENT_PULL` | 0.8 | The strongest pull that keeps the rule monotone at these weights (2 × 0.4). Above it, raising one signal can *lower* the score. At 1.0 (with the human threshold then at 0.35), model 0.41 with style 0.00 gave unsure, but style 0.02 gave human. `test_service.py` caught that and now checks it |
| `HUMAN_THRESHOLD` | 0.40 | Started at 0.35, which no human calibration text could reach |
| `AI_THRESHOLD` | 0.70 | Twice as far from the middle as the human threshold (0.20 against 0.10), because a false accusation costs the writer more than a miss costs anyone |

**Where it lives:** `scoring.py::combine_signals` holds the rule, and
`config.py` holds the numbers.

<!-- ⚠️ The grader checks your code against that line. If your rule lives
     somewhere else, say where. -->

**A case where my two signals split, and what my rule does with it:** The
plain human passage from *Up from Slavery*, which is the false-positive trace
made real. Signal one says **0.625**, leaning AI, because plain, everyday words
are easy for GPT-2 to predict. The style signal says **0.501**, neutral. A
plain weighted average would give 0.575. The gap between the signals, 0.12,
pulls that a tenth of the way back toward the middle, to **0.568: unsure**.
The model signal on its own would have leaned toward an accusation, and the
rule doesn't let it. Where the signals agree, the rule leaves them alone. The
three AI paragraphs (both signals 0.68–0.92) all stay AI, and the casual
human passage (0.41 and 0.24) stays human.

---

## Label Variants

<!-- The exact text of all three labels, as a reader would see them, and the
     score range each covers.

     Write them for someone who has never heard the word "threshold". -->

| Label | Score range | The exact text a reader sees |
|---|---|---|
| high-confidence human | 0.00 – 0.40 | We think a person wrote this. Our automated checks found that its wording and the shape of its sentences look like human writing. |
| unsure | above 0.40, below 0.70 | Our automated checks couldn't tell either way on this piece. That's common with genuine human writing, especially short or plainly worded pieces, and it isn't an accusation. If you wrote this and want a person to confirm it, you can ask for a review. |
| high-confidence AI | 0.70 – 1.00 | Our automated checks rate this as likely AI-generated: both its wording and the shape of its sentences point that way. These checks are sometimes wrong, most often on plain or second-language writing, so this is not proof. If you wrote it yourself, you can appeal in your own words and a person will review it. |

The ranges come from `python scoring.py`, so they can't drift from
`config.py`. `scoring.py::score_to_label` checks `>= 0.70` → AI first, then
`<= 0.40` → human, and everything else is unsure. Every score from 0 to 1 gets
exactly one label, and 0.51 and 0.95 get different ones.

**All three are reachable.** These come from a live run, recorded in
`logs/audit.jsonl`:

| Label | Reached by | Confidence | content_id |
|---|---|---|---|
| high-confidence AI | `ai_expository`, written by Claude | 0.748 | `0ba11390-8990-4a6f-8fae-ca956f0f63d5` |
| unsure | `human_plain`, *Up from Slavery* | 0.568 | `0562407a-e74c-4df6-8c44-e7a3a7f6529c` |
| high-confidence human | `human_casual`, *Three Men in a Boat* | 0.364 | `f974b15b-e078-4f64-8a5b-b5455c50c5b0` |

**Why I worded the "unsure" one this way:**
<!-- It's the hardest of the three. It has to admit uncertainty without
     sounding like an accusation, because the person reading it may well have
     written every word themselves. -->

It has to admit the checks failed without making that the writer's problem:

- **It's about the checks, not the person:** "our automated checks couldn't
  tell".
- **It says this is common for real human writing,** and names the kinds most
  likely to land here.
- **It says outright that it isn't an accusation.**
- **It ends with something the writer can do.**

That last sentence is new. The first draft ended with "This label is not a
finding that AI was used." Read back as the writer (the brief's prompt; see
How I Used AI), it felt like "a small cloud with no way to clear it". The
reader said they'd rewrite their own work "to sound more human", and wished
there were a button to say "I wrote this". That's the wrong incentive
entirely, so the label now offers a review, which uses the same `/appeal`
route.

The same read changed the AI label too. It had come across as "you cheated",
so now it attributes the claim to the checks, says it's not proof, and says an
appeal needs only the writer's own words. What the reader dreaded most was
having to prove their innocence to a stranger.

---

## Sample Run

<!-- One submission and one appeal, pasted as text: the request, the response,
     and the log entries. -->

This is a live run against `python app.py` on 2026-11-09, after the
calibration. The submission is the plain human passage from the
false-positive trace. The first request after start-up took 3.2 s while gpt2
loaded; later ones took about 0.1 s.

**A submission**

<!-- The response needs content_id, guess, confidence, label, AND both
     signal scores - model_score and style_score. Unit 8's tools read those
     two off the response, so leaving them out costs you next unit's
     diagnostics. -->

```bash
$ curl -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "After hearing of the Hampton Institute, I continued to work for a few months longer in the coal-mine. While at work there, I heard of a vacant position in the household of General Lewis Ruffner, the owner of the salt-furnace and coal-mine. Mrs. Viola Ruffner, the wife of General Ruffner, was a “Yankee” woman from Vermont. Mrs. Ruffner had a reputation all through the vicinity for being very strict with her servants, and especially with the boys who tried to serve her. Few of them remained with her more than two or three weeks. They all left with the same excuse: she was too strict. I decided, however, that I would rather try Mrs. Ruffner’s house than remain in the coal-mine, and so my mother applied to her for the vacant position. I was hired at a salary of $5 per month.\n\nI had heard so much about Mrs. Ruffner’s severity that I was almost afraid to see her, and trembled when I went into her presence. I had not lived with her many weeks, however, before I began to understand her. I soon began to learn that, first of all, she wanted everything kept clean about her, that she wanted things done promptly and systematically, and that at the bottom of everything she wanted absolute honesty and frankness. Nothing must be sloven or slipshod; every door, every fence, must be kept in repair.", "creator_id": "plain_writer_demo"}'
```

```json
{
    "confidence": 0.568,
    "content_id": "0562407a-e74c-4df6-8c44-e7a3a7f6529c",
    "creator_id": "plain_writer_demo",
    "guess": "unsure",
    "label": "Our automated checks couldn't tell either way on this piece. That's common with genuine human writing, especially short or plainly worded pieces, and it isn't an accusation. If you wrote this and want a person to confirm it, you can ask for a review.",
    "model_score": 0.6252,
    "status": "decided",
    "style_score": 0.5009
}
```

**An appeal**

```bash
$ curl -X POST http://127.0.0.1:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "0562407a-e74c-4df6-8c44-e7a3a7f6529c", "reasoning": "Test appeal for the README sample run. This passage is from Up from Slavery (1901), so a person wrote every word; plain sentences are not evidence of AI, and an unsure label on it should go to a person."}'
```

```json
{
    "appeal_count": 1,
    "content_id": "0562407a-e74c-4df6-8c44-e7a3a7f6529c",
    "message": "Thank you. Your appeal is recorded and this piece is now under review. The original decision and your reasons are kept side by side for the person who reviews it, and the decision isn't final while that review is open.",
    "original_decision": {
        "confidence": 0.568,
        "decided_at": "2026-11-10T00:49:39+00:00",
        "guess": "unsure",
        "label": "Our automated checks couldn't tell either way on this piece. That's common with genuine human writing, especially short or plainly worded pieces, and it isn't an accusation. If you wrote this and want a person to confirm it, you can ask for a review."
    },
    "status": "under_review"
}
```

**What the log shows afterwards:** the decision with all nine fields, plus
the style signal's breakdown, then the appeal after it. Nothing is
overwritten. Timestamps are UTC.

```bash
$ curl "http://127.0.0.1:5000/log?limit=2"
```

```json
{
    "count": 2,
    "entries": [
        {
            "combined_score": 0.568,
            "content_id": "0562407a-e74c-4df6-8c44-e7a3a7f6529c",
            "creator_id": "plain_writer_demo",
            "guess": "unsure",
            "label": "Our automated checks couldn't tell either way on this piece. That's common with genuine human writing, especially short or plainly worded pieces, and it isn't an accusation. If you wrote this and want a person to confirm it, you can ask for a review.",
            "model_score": 0.6252,
            "status": "decided",
            "style_parts": {
                "punct_ai": 0.5833,
                "punctuation_density": 1.6667,
                "sentence_length_spread": 0.4291,
                "spread_ai": 0.6419,
                "style_score": 0.5009,
                "type_token_ratio": 0.7788,
                "vocab_ai": 0.2775
            },
            "style_score": 0.5009,
            "timestamp": "2026-11-10T00:49:39+00:00",
            "word_count": 240
        },
        {
            "content_id": "0562407a-e74c-4df6-8c44-e7a3a7f6529c",
            "creator_id": "plain_writer_demo",
            "event": "appeal",
            "reasoning": "Test appeal for the README sample run. This passage is from Up from Slavery (1901), so a person wrote every word; plain sentences are not evidence of AI, and an unsure label on it should go to a person.",
            "status": "under_review",
            "timestamp": "2026-11-10T00:49:39+00:00"
        }
    ]
}
```

**The item's status afterwards** (stretch: `GET /content/<id>`)

```bash
$ curl "http://127.0.0.1:5000/content/0562407a-e74c-4df6-8c44-e7a3a7f6529c"
```

```json
{
    "appeals": [
        {
            "reasoning": "Test appeal for the README sample run. This passage is from Up from Slavery (1901), so a person wrote every word; plain sentences are not evidence of AI, and an unsure label on it should go to a person.",
            "timestamp": "2026-11-10T00:49:39+00:00"
        }
    ],
    "confidence": 0.568,
    "content_id": "0562407a-e74c-4df6-8c44-e7a3a7f6529c",
    "creator_id": "plain_writer_demo",
    "decided_at": "2026-11-10T00:49:39+00:00",
    "guess": "unsure",
    "label": "Our automated checks couldn't tell either way on this piece. That's common with genuine human writing, especially short or plainly worded pieces, and it isn't an accusation. If you wrote this and want a person to confirm it, you can ask for a review.",
    "model_score": 0.6252,
    "status": "under_review",
    "style_score": 0.5009
}
```

**An appeal with a mistyped id fails loudly, not silently,** and leaves its
own trace in the log:

```bash
$ curl -X POST http://127.0.0.1:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "not-a-real-id", "reasoning": "I wrote this."}'
```

```json
{"error":"not_found","message":"No submission has the content_id 'not-a-real-id'. Check it against the content_id that /submit returned."}
```

```json
{
    "attempted_content_id": "not-a-real-id",
    "creator_id": "unknown",
    "event": "rejected",
    "path": "/appeal",
    "reason": "appeal_unknown_content_id",
    "status": "rejected",
    "timestamp": "2026-11-10T00:49:40+00:00"
}
```

---

## How I Used AI

I used Claude Code (Claude Opus 5.5) for nearly all of this unit. It built the
service, ran the calibration, and drafted the criteria at my request. The
commits that end with a `Co-Authored-By: Claude` line are its work.

**Moment 1: the acceptance criteria**

- *What I asked for:* I asked Claude Code to complete the project from the
  brief. Before building anything, it stopped to ask how `criteria.md` should
  be written, because the brief says not to have a model write it. I said I'd
  write the criteria myself, then later asked it to draft them instead.
- *What came back:* five criteria covering false positives, score spread,
  label coverage, the appeal path and bad input. It committed them
  (`fb27373`) before any real text had gone through either signal; the only
  runs before that used a stubbed detector. In `criteria.md` it marked them as
  a first draft written by Claude at my request.
- *What I changed:* nothing yet. The wording and the numbers are Claude's.
  Before unit 8 I have to rewrite each one in my own words and decide whether
  I'd defend every target, starting with the false-positive rate.

**Moment 2: the labels, read as the writer**

- *What I asked for:* the brief's Milestone 5 check. Claude Code gave the
  three first-draft labels to a separate Claude agent that knew nothing about
  how the system works. It used the brief's prompt: say what each label would
  tell me about myself and what I'd do next, answer as the writer, and don't
  rewrite them.
- *What came back:*
  - **Human:** read as "a quiet pat on the back", though "typical" sounded
    slightly like "bland".
  - **Unsure:** felt like "a small cloud with no way to clear it"; the reader
    would rewrite their own work to sound more human.
  - **AI:** read as "you cheated", even with the hedging. Naming plain and
    second-language writing helped, but having to prove their innocence to a
    stranger was the worst part.
- *What changed:* Claude rewrote all three in `scoring.py` (`bff9e2a`):
  - **Unsure** now offers a review.
  - **AI** now attributes the claim to the checks, says it isn't proof, and
    says an appeal needs only the writer's own words.
  - **Human** no longer says "typical".

  I haven't edited them myself.

<!-- ═══════════════════════ UNIT 8 — THE TEST ═══════════════════════ -->

---

## Rate Limiting

**My limits:** ___ per minute, ___ per day

**Why those numbers and not others:**
<!-- Think about two people: a real writer submitting their own work a few
     times an hour, and a script sending a thousand variations to map your
     thresholds. Your numbers have to be liveable for the first and hostile to
     the second. -->

**What a caller counts as:** <!-- per address, or per creator_id? They fail
differently — one script can look like a thousand callers, and one household
can look like one. -->

**The run of status codes when I pushed past it:**

<!-- python run_attacks.py --flood 15 -->

```

```

---

## Attack Run — Before

<!-- Every attack with its outcome and a held-or-broke mark.
     `run_attacks.py --label before` produces the table. -->



**Ten audit log entries from the run**

<!-- Choose entries that show the interesting failures, not the ten easiest. -->

```json

```

**The single worst outcome** — the one I'd least want to explain to a writer
whose work got caught by it:



---

## Run Log and Verdicts

<!-- Your five criteria across three trials. `run_eval.py --label before`. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |
| 2.  |  |  |  |  |  |
| 3.  |  |  |  |  |  |
| 4.  |  |  |  |  |  |
| 5.  |  |  |  |  |  |

**Real output from one trial**, pasted as text, naming the file and function
that produced it:

```json

```

**Diagnoses**

<!-- For each miss AND each broken attack: the stage and the mechanism.

     Your service has five stages: the route, signal one, signal two, the
     combining rule, and the label mapping.

     Not a diagnosis:  "The evasion attacks got through."
     A diagnosis:      "Four evasion inputs got through. All four had typos
                        added to AI-generated text. My second signal measures
                        word variety, and typos raise word variety — so it read
                        them as more human. My combining rule weights that
                        signal at 0.6, so it dragged the whole score down."

     Look for a pattern. Five failures on one signal is one problem, not five. -->



---

## The Improvement

**What I changed:**

**Which diagnosis pointed at it:**

### Attack Run — After

<!-- Same format. `run_attacks.py --label after` -->



**Did it help, and how do I know:**

<!-- Widening the unsure band usually fixes one problem and creates another.
     Reporting that trade honestly is worth full credit. -->



---

## What's Still Broken

<!-- For each attack still getting through and each criterion still missed:
     what you'd do, and why you stopped. -->



**The trade I'd make if this ran for real:**

<!-- Two sentences. Fewer wrong accusations means more AI text getting through.
     Say which way you'd go and WHO PAYS FOR IT. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 7

       [ ] criteria.md has five numbered criteria, each naming a target
       [ ] Each has a reason underneath
       [ ] POST /submit returns content_id, guess, confidence, label,
           model_score and style_score
       [ ] Two signals that measure DIFFERENT things, each with a named blind spot
       [ ] Three label variants, all reachable, written out in full
       [ ] POST /appeal changes status and writes to the log
       [ ] Signals and Scoring names scoring.py::combine_signals
       [ ] Sample Run: a submission AND an appeal, as pasted text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN

     SUBMISSION CHECKLIST — unit 8

       [ ] Rate limiting on /submit, with your numbers justified
       [ ] The pasted run of status codes showing 429
       [ ] Audit log with all nine fields, recording rejections too
       [ ] The attack set run IN FULL, every input with an outcome
       [ ] Ten audit log entries pasted as text
       [ ] Five criteria across three trials
       [ ] A diagnosis for every miss and every broken attack — stage AND mechanism
       [ ] One improvement, with Attack Run — After
       [ ] What's Still Broken, including the production trade
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
