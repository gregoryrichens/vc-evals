"""Bullets per section."""

from vc_evals.layer2.result import Result
from vc_evals.layer2.text import Prepared

NAME = "bullets_per_section"
DESCRIPTION = "List items in each section, and the most in any one section."


def measure(prepared: Prepared) -> Result:
    sections = prepared.sections
    most = max(sections, key=lambda s: s.bullets, default=None)
    details = [f"{s.heading}: {s.bullets} bullets" for s in sections]
    return Result(
        {
            "bullets": sum(s.bullets for s in sections),
            "most bullets in one section": most.bullets if most else 0,
        },
        details,
    )
