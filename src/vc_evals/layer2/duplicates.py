"""Near-duplicate points: pairs of sentences that say nearly the same thing."""

from difflib import SequenceMatcher
from itertools import combinations

from vc_evals.briefs import count_words
from vc_evals.layer2.result import Result
from vc_evals.layer2.text import Prepared

NAME = "near_duplicates"
DESCRIPTION = "Pairs of sentences (four words or more) that are at least 80% alike."
SIMILARITY = 0.8  # first guess, to be set by calibration
MIN_WORDS = 4


def measure(prepared: Prepared) -> Result:
    points = [s for s in prepared.sentences if count_words(s) >= MIN_WORDS]
    pairs = []
    for a, b in combinations(points, 2):
        matcher = SequenceMatcher(None, a.lower(), b.lower())
        # the two quick ratios are upper bounds on ratio(), so they rule pairs out cheaply
        if (
            matcher.real_quick_ratio() >= SIMILARITY
            and matcher.quick_ratio() >= SIMILARITY
            and (ratio := matcher.ratio()) >= SIMILARITY
        ):
            pairs.append((ratio, a, b))
    pairs.sort(reverse=True)
    return Result(
        {"near-duplicate pairs": len(pairs)},
        [f"{r:.0%}: {a} | {b}" for r, a, b in pairs],
    )
