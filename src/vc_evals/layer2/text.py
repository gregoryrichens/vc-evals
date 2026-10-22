"""Shared text preparation for the Layer 2 measures."""

import re
from dataclasses import dataclass, field
from functools import cache, cached_property

import pysbd

from vc_evals.briefs import HEADING_RE, count_words, parse_brief

BULLET_RE = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
URL_RE = re.compile(r"https?://\S+")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
THEMATIC_BREAK_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
TERMINAL_RE = re.compile(r"[.!?][\"')\]]*$")
TOP = "(before the first heading)"


@dataclass
class SectionText:
    heading: str
    words: int = 0  # the heading's words plus the lines directly under it
    bullets: int = 0
    blocks: list[str] = field(default_factory=list)  # cleaned prose lines


@dataclass
class Prepared:
    """A brief without its Inputs block, split by section into cleaned prose lines."""

    sections: list[SectionText]

    @property
    def words(self) -> int:
        return sum(s.words for s in self.sections)

    @cached_property
    def sentences(self) -> list[str]:
        return [
            sent for s in self.sections for block in s.blocks for sent in split_sentences(block)
        ]


def clean_line(line: str) -> str:
    """One line of Markdown as plain prose: list marker, link syntax, URLs and emphasis marks removed."""
    line = BULLET_RE.sub("", line)
    line = LINK_RE.sub(r"\1", line)
    line = URL_RE.sub("", line)
    line = re.sub(r"^\s*>\s?", "", line)
    line = re.sub(r"[*_`]", "", line)
    return " ".join(line.split())


@cache
def _segmenter() -> pysbd.Segmenter:
    return pysbd.Segmenter(language="en", clean=False)


def split_sentences(block: str) -> list[str]:
    """Sentences of one block. A sentence without end punctuation is given a full stop."""
    out = [s.strip() for s in _segmenter().segment(block) if s.strip()]
    return [s if TERMINAL_RE.search(s) else s + "." for s in out]


def prepare(body: str) -> Prepared:
    """Split a brief into sections of prose blocks. A block is one bullet or one paragraph;
    lines that continue a bullet or paragraph are joined onto it."""
    sections = [SectionText(TOP)]
    fence_char = ""  # "`" or "~" while inside a fenced block
    joinable = False  # the previous line was prose or a bullet, so a plain line continues it
    for line in parse_brief(body).text.splitlines():
        if not line.strip():
            joinable = False
            continue
        current = sections[-1]
        fence = FENCE_RE.match(line)
        if fence_char:
            current.words += count_words(line)
            if fence and fence.group(1)[0] == fence_char and not fence.group(2).strip():
                fence_char = ""
            continue
        if fence:
            current.words += count_words(line)
            joinable = False
            opened = fence.group(1)
            if opened not in fence.group(2):  # a fence that closes on its own line stays shut
                fence_char = opened[0]
            continue
        heading = HEADING_RE.match(line)
        if heading:
            sections.append(SectionText(heading.group(2), words=count_words(heading.group(2))))
            joinable = False
            continue
        current.words += count_words(line)
        if THEMATIC_BREAK_RE.match(line) or line.lstrip().startswith("|"):
            joinable = False
            continue
        cleaned = clean_line(line)
        if BULLET_RE.match(line):
            current.bullets += 1
        elif joinable and current.blocks:
            current.blocks[-1] += " " + cleaned
            continue
        if cleaned:
            current.blocks.append(cleaned)
        joinable = bool(cleaned)
    return Prepared([s for s in sections if s.heading != TOP or s.words])
