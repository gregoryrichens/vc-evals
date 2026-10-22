"""Layer 2, quality proxies. Each module is one measure: `measure(prepared) -> Result`.

Thresholds are set later, once a partner has rated
some briefs good and bad.
"""

from vc_evals.layer2 import bullets, duplicates, jargon, readability, sections, sentences
from vc_evals.layer2.result import Result
from vc_evals.layer2.text import prepare

MEASURES = {m.NAME: m for m in (sections, sentences, readability, jargon, bullets, duplicates)}


def run_all(body: str) -> dict[str, Result]:
    prepared = prepare(body)
    return {name: m.measure(prepared) for name, m in MEASURES.items()}


__all__ = ["MEASURES", "Result", "run_all"]
