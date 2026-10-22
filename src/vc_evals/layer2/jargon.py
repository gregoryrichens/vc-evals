"""Jargon: words outside the XKCD Simple Writer list (the Thing Explainer words)."""

import re
from collections import Counter
from functools import cache
from pathlib import Path

from vc_evals.layer2.result import Result
from vc_evals.layer2.text import Prepared

NAME = "jargon"
DESCRIPTION = "Words not on the XKCD Simple Writer list, as a count and per 100 prose words."
WORDS_FILE = Path(__file__).parent / "xkcd_words.txt"
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
SENTENCE_START_MARKS = set(".!?:;([{\"“”‘’'")
SHOWN = 15


@cache
def word_list() -> frozenset[str]:
    lines = WORDS_FILE.read_text().splitlines()
    return frozenset(line for line in lines if line and not line.startswith("#"))


def is_listed(token: str, words: frozenset[str]) -> bool:
    word = token.lower().replace("’", "'")
    return word in words or (word.endswith("'s") and word[:-2] in words)


def is_capitalised(token: str) -> bool:
    """Capitalised like a name (Acme, McKinsey). An all-capitals word (FPGA) is not."""
    return token[0].isupper() and token != token.upper()


def jargon_words(text: str) -> tuple[Counter[str], int]:
    """(unlisted words with counts, total tokens).

    A word is a name when it appears capitalised somewhere other than the start of a sentence.
    Every occurrence of a name is skipped. Single letters (the "e" and "g" of "e.g.") are skipped.
    """
    tokens: list[tuple[str, bool]] = []  # (token, starts a sentence)
    previous_end = 0
    for m in TOKEN_RE.finditer(text):
        gap = text[previous_end : m.start()].strip()
        starts = previous_end == 0 and not gap or bool(gap) and gap[-1] in SENTENCE_START_MARKS
        tokens.append((m.group(), starts))
        previous_end = m.end()
    names = {t.lower() for t, starts in tokens if is_capitalised(t) and not starts}
    words, found = word_list(), Counter()
    for token, _ in tokens:
        if len(token) > 1 and not is_listed(token, words) and token.lower() not in names:
            found[token.lower()] += 1
    return found, len(tokens)


def measure(prepared: Prepared) -> Result:
    text = " ".join(prepared.sentences)
    found, total = jargon_words(text)
    count = sum(found.values())
    rate = round(100 * count / total, 1) if total else "-"
    details = [f"{word} x{n}" for word, n in found.most_common(SHOWN)]
    return Result(
        {
            "jargon words": count,
            "prose words": total,
            "jargon per 100 prose words": rate,
            "distinct jargon words": len(found),
        },
        details,
    )
