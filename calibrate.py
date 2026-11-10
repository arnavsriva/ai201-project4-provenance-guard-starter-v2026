#!/usr/bin/env python3
"""
Both signals, every measure, on the calibration texts. Milestone 4.

    python calibrate.py

Prints one markdown table row per text: perplexity and model_score for signal
one, the three raw style measures and their 0-1 machine-likeness, the style
score, the combined score and the label. It calls the signal functions
directly, so nothing goes into the audit log.

results/calibration_2026-11-09.md has the runs before and after the
calibration changes, and why each change was made.
"""

import detector
import scoring
import stylometry
from calibration_texts import TEXTS


def main():
    print("| Text | Words | Perplexity | model_score | Spread (CV) | TTR | Punct /100w "
          "| spread → AI | vocab → AI | punct → AI | style_score | Combined | Label |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, text in TEXTS.items():
        ppl = detector.perplexity(text)
        model = detector.model_signal(text)
        parts = stylometry.style_parts(text)
        combined = scoring.combine_signals(model, parts["style_score"])
        guess, _ = scoring.score_to_label(combined)
        spread = parts["sentence_length_spread"]
        print(f"| `{name}` | {len(stylometry.words(text))} | {ppl:.1f} | {model:.3f} "
              f"| {'—' if spread is None else f'{spread:.3f}'} | {parts['type_token_ratio']:.3f} "
              f"| {parts['punctuation_density']:.2f} | {parts['spread_ai']:.2f} "
              f"| {parts['vocab_ai']:.2f} | {parts['punct_ai']:.2f} | {parts['style_score']:.3f} "
              f"| {combined:.3f} | {guess} |")


if __name__ == "__main__":
    main()
