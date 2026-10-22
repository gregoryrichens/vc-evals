"""Words per section, and the longest section."""

from vc_evals.layer2.result import Result
from vc_evals.layer2.text import Prepared

NAME = "words_per_section"
DESCRIPTION = "Words in each section, and the longest section."


def measure(prepared: Prepared) -> Result:
    sections = prepared.sections
    if not sections:
        return Result({"total words": 0, "longest section (words)": "-"})
    longest = max(sections, key=lambda s: s.words)
    details = [f"{s.heading}: {s.words} words" for s in sections]
    return Result(
        {
            "total words": sum(s.words for s in sections),
            "longest section (words)": f"{longest.heading} ({longest.words})",
        },
        details,
    )
