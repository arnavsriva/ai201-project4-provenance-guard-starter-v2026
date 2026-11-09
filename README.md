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
  isn't a JSON object, a field is missing, blank or not a string, or the text
  is under 20 words.
- `413 {"error": "text_too_long", ...}`: the text is over 20,000 characters.

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
| `original_decision` | object | `guess`, `confidence` and `label` as first decided. Never changed |

Errors:

- `400 invalid_input`: a field is missing, blank or not a string.
- `404 {"error": "not_found", ...}`: the content_id was never issued.

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

Milestone 4 checks the expected scores above against a real plain-writing
sample.

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

### Signal two — the style signal

**What it measures:** The shape of the text, with no model and no idea what it
says (`stylometry.py::style_signal`): how much sentence length varies, how
varied the vocabulary is, and how much punctuation is used and of what kinds.

**Why that might differ between human and AI writing:** Generated prose tends
toward even, mid-length sentences, a narrower vocabulary and regular
punctuation, because "most likely next word" produces the average case. People
are lumpier: a three-word sentence beside a forty-word one, a dash, a
question.

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

**The rule:**

**The numbers:**

**Where it lives:** `scoring.py::combine_signals`

<!-- ⚠️ The grader checks your code against that line. If your rule lives
     somewhere else, say where. -->

**A case where my two signals split, and what my rule does with it:**



---

## Label Variants

<!-- The exact text of all three labels, as a reader would see them, and the
     score range each covers.

     Write them for someone who has never heard the word "threshold". -->

| Label | Score range | The exact text a reader sees |
|---|---|---|
| high-confidence human |  |  |
| unsure |  |  |
| high-confidence AI |  |  |

**Why I worded the "unsure" one this way:**
<!-- It's the hardest of the three. It has to admit uncertainty without
     sounding like an accusation, because the person reading it may well have
     written every word themselves. -->



---

## Sample Run

<!-- One submission and one appeal, pasted as text: the request, the response,
     and the log entries. -->

**A submission**

<!-- The response needs content_id, guess, confidence, label, AND both
     signal scores - model_score and style_score. Unit 8's tools read those
     two off the response, so leaving them out costs you next unit's
     diagnostics. -->

```bash
$ curl -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "...", "creator_id": "..."}'
```

```json

```

**An appeal**

```bash
$ curl -X POST http://127.0.0.1:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "...", "reasoning": "..."}'
```

```json

```

**What the log shows afterwards**

```bash
$ curl "http://127.0.0.1:5000/log?limit=3"
```

```json

```

---

## How I Used AI

**Moment 1**

- *What I asked for:*
- *What came back:*
- *What I changed:*

**Moment 2**

- *What I asked for:*
- *What came back:*
- *What I changed:*

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
