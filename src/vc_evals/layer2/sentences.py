"""Sentence length, with pySBD finding the sentences."""

from statistics import mean

from vc_evals.briefs import count_words
from vc_evals.layer2.result import Result
from vc_evals.layer2.text import Prepared

NAME = "sentence_length"
DESCRIPTION = "Number of sentences, mean words per sentence, and the longest sentence."
TOP_N = 3  # how many of the longest sentences the detail lines list


def measure(prepared: Prepared) -> Result:
    sentences = prepared.sentences
    if not sentences:
        return Result(
            {"sentences": 0, "mean words per sentence": "-", "longest sentence (words)": "-"}
        )
    lengths = [count_words(s) for s in sentences]
    ranked = sorted(zip(lengths, sentences, strict=True), reverse=True)[:TOP_N]
    return Result(
        {
            "sentences": len(sentences),
            "mean words per sentence": round(mean(lengths), 1),
            "longest sentence (words)": max(lengths),
        },
        [f"{n} words: {s}" for n, s in ranked],
    )
