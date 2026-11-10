# Acceptance criteria — Provenance Guard

Five criteria that say what "working" means for this service, written in unit 7
**before** you built it.

**All five are yours.** None are given.

An acceptance criterion names a number or something plainly observable. *"The
detector is accurate"* is an opinion — and perfect AI detection isn't possible
anyway, so it's an opinion about something nobody can deliver. *"Of 10 pieces I
wrote myself, at most 1 is labelled high-confidence AI"* is a criterion.

Under each, write a sentence or two on **why that target**. *"I allow at most 1
false positive in 10 because on a writing site a wrong accusation costs more
than a missed detection"* is a real answer.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

---

## Pick numbers you can defend

**Cover at least three of these five areas.** They're prompts, not a form.

| Area | A question it could answer |
|---|---|
| False positives | How often may a human's writing get called AI? |
| Score spread | How far apart should clearly-AI and clearly-human text score? |
| Label coverage | Is every one of your three labels actually reachable? |
| The appeal path | Does an appeal always change status and always get recorded? |
| Bad input | What happens when `text` is missing, empty, or enormous? |

Two things worth knowing before you pick numbers:

- **The expensive mistake is one-sided.** Missing some AI text costs the site a
  little. Accusing a real writer costs that person a lot. A criterion that
  treats both errors as equally bad is describing a system nobody would ship.
- **Unit 8 tests across three trials, and the target has to hold across all
  three.** Your first signal runs a model, so identical input can score
  differently twice. A target of "at most 1 in 10" against trials of 2, 1, 2 is
  a **miss**.

---

> **Status: first draft.** Claude Code drafted these five at my request on
> 2026-11-09, before any real text had been scored. README → How I Used AI
> says so. Next step: rewrite each one in my own words, and check I'd defend
> every number.

## 1. My own writing is almost never called AI

Of 10 pieces I wrote myself, each 100–300 words, unedited and never run
through an AI tool, with at least 3 of them deliberately plain (short
sentences, everyday words), **at most 1 is labelled high-confidence AI**. This
has to hold in each of three trials.

**Why this target:** On a writing site, a wrong accusation costs the writer
far more than a missed AI paragraph costs anyone, so this is the number that
matters most. One in ten is already more than I'd want to explain to the
person it happens to. Zero is a promise a 2019 language model can't keep for
plain writing, and that's exactly why plain pieces are in the set rather than
left out to make the number easier.

---

## 2. AI and human text score clearly apart

Take 5 AI-generated texts and 5 human-written texts that were **not** used to
set the weights or thresholds. The AI texts' average combined score is **at
least 0.30 higher** than the human texts' average, in each of three trials.

**Why this target:** If the two averages are closer together than the unsure
band is wide (currently 0.35), a typical AI text and a typical human text can
both land in "unsure", and the labels stop meaning anything. 0.30 asks for
nearly that much separation, on texts the system was never tuned on.

---

## 3. Every label is reachable, and none is crossed

Use a 9-text set: 3 clearly AI, 3 clearly human, and 3 AI texts I've lightly
edited by hand. In every trial, **each of the three labels appears at least
once**, and **no text gets the opposite confident label**: no clearly-human
text is labelled high-confidence AI, and no clearly-AI text is labelled
high-confidence human.

**Why this target:** A label nothing can reach is a gap in the ranges, not a
design. The crossed-label rule is the stronger half. "Unsure" is an honest
answer to a hard case, but a confident label pointing the wrong way is the
system being sure and wrong, and that's the failure that hurts people.

---

## 4. An appeal is always recorded and always changes the status

Submit 5 texts and appeal each one with its real content_id. All **5 of 5**
appeals get a 200 with status `under_review`. Afterwards,
`GET /content/<id>` reports `under_review` with the appeal's reasoning, and
`GET /log` shows the original decision unchanged with the appeal entry after
it. An appeal with a made-up content_id gets a 404 **5 of 5 times** and adds
nothing to any real item's history.

**Why this target:** The appeal is the only thing standing between a wrongly
accused writer and nothing at all, so no failure rate is acceptable. An
appeal that silently doesn't land is worse than having no appeal button.
This one is tested by hand, since `run_eval.py` only sends submissions.

---

## 5. Bad input never crashes the service and never goes unrecorded

Send these 10 requests:

- no `text` field
- `"text": ""`
- whitespace-only text
- `"text": null`
- `"text": 42`
- a 19-word text
- 50,000 words of text
- a body that's a JSON list
- a body that isn't JSON at all
- a body over 10 MB

In every trial, each one gets a **4xx with a JSON error naming the problem,
never a 5xx**, and leaves a `rejected` entry in the audit log.

**Why this target:** A crash on malformed input is one of the most common real
failures, and unit 8's attack set will send all of these. The log half matters
as much as the status code: a refusal that leaves no trace makes a flood of bad
requests look like a quiet afternoon.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 8 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath, like this:

         ## 2. Uncertain cases land in the unsure band

         The system handles uncertain cases well.

         **Why this target:** ...

         > **Revised in unit 8:** Text I judged borderline scores between
         > 0.4 and 0.6 in at least 4 of 5 cases.
         >
         > **Why revised:** "well" gave me nothing to check. I couldn't
         > reach a verdict from it at all.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "At most 1 of 10 of my own pieces flagged as AI" → "at most 3
            of 10", because 1 of 10 turned out to be hard.

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
