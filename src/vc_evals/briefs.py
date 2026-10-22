"""The scoring core. Takes a brief body and a prompts directory and returns a Score."""

import re
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
DEFAULT_INPUTS_HEADING = "Inputs"
INPUT_LINE_RE = re.compile(r"^[\s>*\-•]*\**([A-Za-z][A-Za-z ]*?)\**\s*:\s*(.*)$")


@dataclass
class Section:
    level: int
    heading: str
    text: str
    line: int = 0  # index of the heading line in the body


@dataclass
class ParsedBrief:
    sections: list[Section]
    inputs: dict[str, list[str]]
    text: str = ""  # the brief without its Inputs block

    @property
    def prompt_line(self) -> str | None:
        """The model's own claim of its prompt version, shown in the detail column."""
        values = self.inputs.get("prompt", [])
        return values[0] or None if values else None


@dataclass
class Score:
    prompt_version: str | None  # the version live when the note was created, or None
    prompt_line: str | None = None
    missing: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    words: int | None = None
    max_words: int | None = None
    has_table: bool = False
    bad_heading_levels: list[str] = field(default_factory=list)
    inputs_problems: list[str] = field(default_factory=list)
    links: dict[str, str] = field(default_factory=dict)  # url -> "loaded" | "could not fetch"

    @property
    def over_limit(self) -> bool:
        return self.max_words is not None and self.words is not None and self.words > self.max_words

    @property
    def spec_found(self) -> bool:
        return self.prompt_version is not None

    @property
    def layer1_pass(self) -> bool | None:
        """None when no prompt version was live at the note's creation."""
        if not self.spec_found:
            return None
        return not (
            self.missing
            or self.empty
            or self.over_limit
            or self.has_table
            or self.bad_heading_levels
            or self.inputs_problems
        )


def normalize(text: str) -> str:
    """Heading text lower-cased, with "?" and "-" removed, straight quotes, and the "— description" tail dropped."""
    text = re.split(r"\s+[—–]\s+", text, maxsplit=1)[0]
    text = text.replace("’", "'").replace("*", "").replace("?", "").replace("-", " ")
    return " ".join(text.lower().split())


def parse_brief(body: str, inputs_heading: str = DEFAULT_INPUTS_HEADING) -> ParsedBrief:
    sections: list[Section] = []
    lines = body.splitlines()
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            sections.append(Section(len(m.group(1)), m.group(2), "", i))
        elif sections:
            sections[-1].text += line + "\n"
    # a section's text includes its sub-sections, up to the next heading of the same or higher rank
    for i, sec in enumerate(sections):
        for nxt in sections[i + 1 :]:
            if nxt.level <= sec.level:
                break
            sec.text += f"{nxt.heading}\n{nxt.text}"
    inputs: dict[str, list[str]] = {}
    start = len(lines)
    for sec in sections:
        if normalize(sec.heading) == normalize(inputs_heading):
            _collect_inputs(sec.text.splitlines(), inputs)
            start = sec.line
            break
    while start and lines[start - 1].strip() in ("", "---", "***", "___"):
        start -= 1
    return ParsedBrief(sections, inputs, "\n".join(lines[:start]))


def _collect_inputs(lines, inputs: dict[str, list[str]]) -> None:
    for line in lines:
        m = INPUT_LINE_RE.match(line)
        if m:
            inputs.setdefault(m.group(1).strip().lower(), []).append(m.group(2).strip())


def _go_live(spec: dict) -> datetime | None:
    """`go_live` as an aware datetime. A plain date means the start of that day, UTC."""
    value = spec.get("go_live")
    if isinstance(value, str):  # the real specs write it as a quoted string: go_live = "2026-10-14"
        value = datetime.fromisoformat(value) if "T" in value else date.fromisoformat(value)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    return None


def live_spec(created_at: datetime, prompts_dir: Path, prefix: str = "") -> tuple[str, dict] | None:
    """The (version, spec) that was live when a note was created.

    That is the spec with the latest `go_live` at or before `created_at`. A spec with no
    `go_live` is skipped. Only files whose name starts with `prefix` are read ("brief_" for
    briefs, "ai_ic_" for votes). Returns None when no spec was live yet.
    """
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    live = []
    for path in prompts_dir.glob(f"{prefix}*.spec.toml"):
        spec = tomllib.loads(path.read_text())
        go_live = _go_live(spec)
        if go_live is not None and go_live <= created_at:
            live.append((go_live, path.name.removesuffix(".spec.toml"), spec))
    if not live:
        return None
    _, version, spec = max(live, key=lambda item: item[0])
    return version, spec


def required_sections(spec: dict) -> list[tuple[str, set[str]]]:
    """(display name, accepted normalized names) for each required section.

    Reads `[[sections]]` (name, aliases, required) or a plain `headings` list.
    """
    out = []
    for sec in spec.get("sections", []):
        if sec.get("required", True):
            names = {normalize(sec["name"])} | {normalize(a) for a in sec.get("aliases", [])}
            out.append((sec["name"], names))
    for name in spec.get("headings", []):
        out.append((name, {normalize(name)}))
    return out


TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
URL_RE = re.compile(r"^https?://\S+$")


def count_words(text: str) -> int:
    """Whitespace-separated tokens that contain a letter or digit. Tokens made only of Markdown marks are left out."""
    return sum(1 for token in text.split() if re.search(r"[A-Za-z0-9]", token))


def has_table(text: str) -> bool:
    return any(TABLE_SEPARATOR_RE.match(line) for line in text.splitlines())


def output_rules(spec: dict) -> dict:
    """max_words, allow_tables, heading_levels from `[output]` (v1) or `[limits]` (v0)."""
    out, lim = spec.get("output", {}), spec.get("limits", {})
    return {
        "max_words": out.get("max_words", lim.get("max_words")),
        "allow_tables": out.get("allow_tables", lim.get("tables_allowed", True)),
        "heading_levels": out.get("allowed_heading_levels"),
    }


def input_rules(spec: dict) -> list[dict]:
    """One rule per Inputs label, from `[[inputs.lines]]` (v1) or required/repeatable (v0)."""
    inputs = spec.get("inputs", {})
    if "lines" in inputs:
        return inputs["lines"]
    rules = [
        {"label": n, "required": True, "repeatable": False} for n in inputs.get("required", [])
    ]
    rules += [
        {"label": n, "required": False, "repeatable": True} for n in inputs.get("repeatable", [])
    ]
    for rule in rules:
        if rule["label"] == "Prompt" and "prompt_value" in inputs:
            rule["must_equal"] = inputs["prompt_value"]
    return rules


def check_inputs(inputs: dict[str, list[str]], rules: list[dict]) -> list[str]:
    problems = []
    for rule in rules:
        label = rule["label"]
        values = inputs.get(label.lower(), [])
        if not values:
            if rule.get("required"):
                problems.append(f"no {label} line")
            continue
        if not rule.get("repeatable") and len(values) > 1:
            problems.append(f"{label} appears {len(values)} times")
        for value in values:
            if not value:
                problems.append(f"{label} is empty")
            elif "must_equal" in rule and value != rule["must_equal"]:
                problems.append(f"{label} is {value!r}, not {rule['must_equal']!r}")
            elif rule.get("value_type") == "url" and not URL_RE.match(value):
                problems.append(f"{label} is not a URL: {value}")
    return problems


def web_urls(body: str) -> list[str]:
    """The `Web:` URLs listed in a brief's Inputs."""
    return [u for u in parse_brief(body).inputs.get("web", []) if URL_RE.match(u)]


def score_brief(body: str, created_at: datetime, prompts_dir: Path) -> Score:
    live = live_spec(created_at, prompts_dir, "brief_")
    if live is None:
        return Score(None, parse_brief(body).prompt_line)
    version, spec = live
    parsed = parse_brief(body, spec.get("inputs", {}).get("heading", DEFAULT_INPUTS_HEADING))
    score = Score(version, parsed.prompt_line)
    rules = output_rules(spec)
    score.words = count_words(parsed.text)
    score.max_words = rules["max_words"]
    score.has_table = not rules["allow_tables"] and has_table(parsed.text)
    if rules["heading_levels"]:
        score.bad_heading_levels = [
            f"{'#' * sec.level} {sec.heading}"
            for sec in parsed.sections
            if sec.level not in rules["heading_levels"]
        ]
    in_rules = input_rules(spec)
    if in_rules:
        score.inputs_problems = (
            check_inputs(parsed.inputs, in_rules) if parsed.inputs else ["no Inputs section"]
        )
    for name, accepted in required_sections(spec):
        found = [s for s in parsed.sections if normalize(s.heading) in accepted]
        if not found:
            score.missing.append(name)
        elif not any(s.text.strip() for s in found):
            score.empty.append(name)
    return score
