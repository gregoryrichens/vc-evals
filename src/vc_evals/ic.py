"""Checks for one AI IC vote. Takes the JSON payload and a prompts directory and returns a Vote."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from vc_evals.briefs import count_words, live_spec

SPEC_PREFIX = "ai_ic_"
BULLET_RE = re.compile(r"^\s*[-*•]\s+")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Vote:
    version: str | None  # the spec live at check time, or None
    company: str | None = None
    words: int | None = None
    verdict: str | None = None
    conviction: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def spec_found(self) -> bool:
        return self.version is not None

    @property
    def passed(self) -> bool | None:
        """None when no spec was live."""
        if not self.spec_found:
            return None
        return not self.problems


def check_vote(raw: str, now: datetime, prompts_dir: Path) -> Vote:
    """Check one payload (JSON text) against the spec live at `now`."""
    live = live_spec(now, prompts_dir, SPEC_PREFIX)
    if live is None:
        return Vote(None)
    version, spec = live
    vote = Vote(version)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        vote.problems.append(f"payload is not valid JSON ({e})")
        return vote
    pay = spec["payload"]
    if not isinstance(payload, dict):
        vote.problems.append("payload is not a JSON object")
        return vote
    text = payload.get(pay["output_key"])
    if not isinstance(text, str) or not text.strip():
        vote.problems.append(f"payload has no text in {pay['output_key']!r}")
        text = None
    checks = payload.get(pay["checks_key"])
    payload_ok = True
    if not isinstance(checks, dict):
        vote.problems.append(f"payload has no object in {pay['checks_key']!r}")
        payload_ok = False
    else:
        problems = check_payload(checks, spec)
        vote.problems += problems
        payload_ok = not problems
    for key in payload:
        if key not in (pay["output_key"], pay["checks_key"]):
            vote.problems.append(f"payload has an unknown key {key!r}")
    if text is not None:
        check_text(text, spec, vote)
    if payload_ok and vote.verdict is not None:
        vote.problems += check_gates(checks, vote.verdict, spec)
    return vote


# --- payload ----------------------------------------------------------------


def _check_group(group, label: str, names: list[str], values: list[str]) -> list[str]:
    if not isinstance(group, dict):
        return [f"checks.{label} is not an object"]
    problems = [f"checks.{label}.{n} is missing" for n in names if n not in group]
    problems += [f"checks.{label} has an unknown key {k!r}" for k in group if k not in names]
    for name in names:
        if name in group and group[name] not in values:
            problems.append(f"checks.{label}.{name} is {group[name]!r}, not one of {values}")
    return problems


def check_payload(checks: dict, spec: dict) -> list[str]:
    """Problems with the `checks` object: missing keys, unknown keys, values outside the spec."""
    pay = spec["payload"]
    integ, forces, exit_ = pay["integrity"], pay["forces"], pay["exit_pathway"]
    expected = {integ["key"], forces["key"], exit_["key"]}
    problems = [f"checks.{k} is missing" for k in sorted(expected) if k not in checks]
    problems += [f"checks has an unknown key {k!r}" for k in checks if k not in expected]
    if integ["key"] in checks:
        problems += _check_group(
            checks[integ["key"]], integ["key"], integ["checks"], integ["values"]
        )
    if forces["key"] in checks:
        problems += _check_group(
            checks[forces["key"]], forces["key"], forces["names"], forces["values"]
        )
    if exit_["key"] in checks and checks[exit_["key"]] not in exit_["values"]:
        problems.append(
            f"checks.{exit_['key']} is {checks[exit_['key']]!r}, not one of {exit_['values']}"
        )
    return problems


# --- vote text --------------------------------------------------------------


def _clean(line: str) -> str:
    """A line without Markdown decoration: bullet marks, heading marks, bold, code marks."""
    line = line.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"^[\s>#*\-•]+", "", line).strip()


def _has_content(text: str) -> bool:
    return re.search(r"[A-Za-z0-9]", text) is not None


def _label_value(line: str, name: str) -> str | None:
    """The text after "NAME:" if the line starts with that label, else None."""
    m = re.match(rf"^{re.escape(name)}\s*:\s*(.*)$", _clean(line), re.IGNORECASE)
    return m.group(1).strip() if m else None


def _strip_fences(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if not FENCE_RE.match(ln)]


def check_text(text: str, spec: dict, vote: Vote) -> None:
    """Fill `vote` from the vote text and add one problem per format failure."""
    fmt = spec["format"]
    vote.words = count_words(text)
    if not fmt["min_words"] <= vote.words <= fmt["max_words"]:
        vote.problems.append(f"{vote.words} words, range {fmt['min_words']} to {fmt['max_words']}")
    for rule in fmt.get("forbidden", []):
        m = re.search(rule["pattern"], text)
        if m:
            vote.problems.append(f"text contains {rule['description']}: {m.group(0)!r}")

    lines = [ln for ln in _strip_fences(text) if ln.strip()]
    _check_header(lines[0] if lines else "", fmt, vote)
    sections = _split_labels(lines, fmt["labels"], vote)
    for label in fmt["labels"]:
        name = label["name"]
        if name not in sections:
            continue
        inline, body = sections[name]
        if label.get("inline", True):
            value = " ".join([inline, *body]).strip()
            if not _has_content(value):
                vote.problems.append(f"{name} is empty")
            elif "allowed" in label and value not in label["allowed"]:
                vote.problems.append(f"{name} is {value!r}, not one of {label['allowed']}")
            elif name == "VERDICT":
                vote.verdict = value
            elif name == "CONVICTION":
                vote.conviction = value
        elif name == "RATIONALE":
            _check_bullets(body, fmt["bullets"], vote)
    if vote.verdict is not None:
        lowered = text.lower()
        for rule in fmt.get("verdict_phrases", []):
            if vote.verdict == rule["verdict"] and not any(p in lowered for p in rule["any_of"]):
                vote.problems.append(
                    f"{vote.verdict} vote has none of: "
                    + ", ".join(repr(p) for p in rule["any_of"])
                )


def _check_header(line: str, fmt: dict, vote: Vote) -> None:
    fields, sep = fmt["header_fields"], fmt["header_separator"]
    parts = [p.strip() for p in _clean(line).split(sep)]
    vote.company = parts[0] if parts and _has_content(parts[0]) else None
    if len(parts) != len(fields):
        vote.problems.append(
            f"header has {len(parts)} values, expected {len(fields)}: {sep.join(fields)}"
        )
        return
    for name, value in zip(fields, parts, strict=True):
        if not _has_content(value):
            vote.problems.append(f"header {name} is empty")
        elif value.upper() == name:
            vote.problems.append(f"header {name} is not filled in")
    if vote.company and vote.company.upper() == fields[0]:
        vote.company = None


def _split_labels(lines: list[str], labels: list[dict], vote: Vote) -> dict[str, tuple]:
    """name -> (text after the colon, following lines up to the next label). Reports order."""
    found: list[tuple[int, str, str]] = []
    for name in (label["name"] for label in labels):
        hit = next(
            ((i, v) for i, ln in enumerate(lines) if (v := _label_value(ln, name)) is not None),
            None,
        )
        if hit is None:
            vote.problems.append(f"no {name} line")
        else:
            found.append((hit[0], name, hit[1]))
    positions = [i for i, _, _ in found]
    if positions != sorted(positions):
        vote.problems.append("label lines are out of order")
    ends = sorted(positions) + [len(lines)]
    sections = {}
    for i, name, inline in found:
        end = next(e for e in ends if e > i)
        sections[name] = (inline, lines[i + 1 : end])
    return sections


def _check_bullets(body: list[str], expected: list[dict], vote: Vote) -> None:
    bullets: list[str] = []
    for ln in body:
        if BULLET_RE.match(ln) or not bullets:
            bullets.append(_clean(ln))
        else:
            bullets[-1] += " " + _clean(ln)
    names = [[b["name"], *b.get("aliases", [])] for b in expected]
    where: list[int | None] = []
    rest_of: dict[int, str] = {}
    for spec_bullet, options in zip(expected, names, strict=True):
        idx, rest = _find_bullet(bullets, options)
        where.append(idx)
        if idx is None:
            vote.problems.append(f"RATIONALE has no bullet '{spec_bullet['name']}'")
        else:
            rest_of[idx] = rest
            if not _has_content(rest):
                vote.problems.append(f"RATIONALE bullet '{spec_bullet['name']}' is empty")
            tags = spec_bullet.get("require_any")
            if tags and not any(re.search(rf"\b{re.escape(t)}\b", bullets[idx]) for t in tags):
                vote.problems.append(
                    f"RATIONALE bullet '{spec_bullet['name']}' has none of: " + ", ".join(tags)
                )
    present = [i for i in where if i is not None]
    if present != sorted(present):
        vote.problems.append("RATIONALE bullets are out of order")
    extra = len(bullets) - len(present)
    if extra > 0 and not any(i is None for i in where):
        vote.problems.append(f"RATIONALE has {extra} extra bullet(s)")


def _find_bullet(bullets: list[str], options: list[str]) -> tuple[int | None, str]:
    """(index, text after the label) of the first bullet starting with a name or alias."""
    for i, bullet in enumerate(bullets):
        for option in sorted(options, key=len, reverse=True):
            if bullet.lower().startswith(option.lower()):
                return i, bullet[len(option) :].lstrip(" :.-–—")
    return None, ""


# --- gates ------------------------------------------------------------------


def holds(cond: dict, checks: dict, spec: dict) -> bool:
    """Whether a gate condition holds for these checks. Raises ValueError for a condition the vocabulary lacks."""
    pay = spec["payload"]
    forces = checks[pay["forces"]["key"]]
    integrity = checks[pay["integrity"]["key"]]
    if "all" in cond:
        return all(holds(c, checks, spec) for c in cond["all"])
    if "any" in cond:
        return any(holds(c, checks, spec) for c in cond["any"])
    if "not" in cond:
        return not holds(cond["not"], checks, spec)
    if "force" in cond:
        return forces[cond["force"]] in cond["is"]
    if "integrity" in cond:
        which = cond["integrity"]
        if which == "any":
            return any(v in cond["is"] for v in integrity.values())
        if which == "all":
            return all(v in cond["is"] for v in integrity.values())
        return integrity[which] in cond["is"]
    if "exit_pathway" in cond:
        return checks[pay["exit_pathway"]["key"]] == cond["exit_pathway"]
    if cond.get("count_forces"):
        n = sum(1 for v in forces.values() if v in cond["is"])
        return n >= cond.get("at_least", 0) and n <= cond.get("at_most", len(forces))
    raise ValueError(f"unknown gate condition: {cond}")


def tripped_gates(checks: dict, spec: dict) -> list[dict]:
    return [g for g in spec.get("gates", []) if holds(g["when"], checks, spec)]


def check_gates(checks: dict, verdict: str, spec: dict) -> list[str]:
    """One problem for each tripped gate whose `allows` list lacks the verdict."""
    problems = []
    for gate in tripped_gates(checks, spec):
        if verdict not in gate["allows"]:
            options = " or ".join(gate["allows"])
            problems.append(
                f"gate {gate['id']}: {gate['description']}, so the verdict must be {options}"
                f" (vote says {verdict})"
            )
    return problems
