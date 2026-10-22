import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vc_evals.briefs import count_words
from vc_evals.cli import app
from vc_evals.ic import check_gates, check_vote, tripped_gates

ROOT = Path(__file__).parent.parent
SPEC_FILE = ROOT / "prompts" / "ai_ic_v1.spec.toml"
IC = ROOT / "fixtures" / "ic"
NOW = datetime(2026, 11, 1, tzinfo=UTC)
FILL = "A partner met both founders twice and saw one build a working controller in a single afternoon. One has ten years of ceramics production and the other has run hardware sales. They have answered every diligence question directly and with documents. "
runner = CliRunner()


@pytest.fixture
def prompts(tmp_path):
    """A prompts dir holding the real spec, live since 2026-01-01."""
    text = SPEC_FILE.read_text()
    text = re.sub(r'^go_live = ".*"$', 'go_live = "2026-01-01T00:00:00Z"', text, flags=re.MULTILINE)
    (tmp_path / "ai_ic_v1.spec.toml").write_text(text)
    return tmp_path


@pytest.fixture
def spec(prompts):
    import tomllib

    return tomllib.loads((prompts / "ai_ic_v1.spec.toml").read_text())


def fixture(name: str) -> dict:
    return json.loads((IC / f"{name}.json").read_text())


def run(payload, prompts, now=NOW):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return check_vote(raw, now, prompts)


def with_text(base: str, edit) -> dict:
    p = fixture(base)
    p["output"] = edit(p["output"])
    return p


def checks(**forces):
    """A passing set of checks, with force ratings overridden by keyword."""
    c = copy.deepcopy(fixture("pass_yes")["checks"])
    c["forces"].update(forces)
    return c


def problems_with(text: str, vote) -> list[str]:
    return [p for p in vote.problems if text in p]


# --- the fixtures pass ----------------------------------------------------------


@pytest.mark.parametrize(
    "name,verdict", [("pass_yes", "YES"), ("pass_no", "NO"), ("pass_conditional", "CONDITIONAL")]
)
def test_fixtures_pass(prompts, name, verdict):
    p = fixture(name)
    assert 400 <= count_words(p["output"]) <= 700
    v = run(p, prompts)
    assert v.problems == [] and v.passed is True
    assert v.version == "ai_ic_v1" and v.verdict == verdict
    assert v.company == "Northwind Pottery Labs" and v.words == count_words(p["output"])


def test_conviction_is_read(prompts):
    assert run(fixture("pass_yes"), prompts).conviction == "3"


# --- gates: each one trips and does not trip -----------------------------------------


def ids(c, spec):
    return [g["id"] for g in tripped_gates(c, spec)]


def test_nothing_trips_on_the_passing_checks(spec):
    assert ids(checks(), spec) == []


@pytest.mark.parametrize(
    "integrity,expected",
    [
        ({}, []),
        ({"clean_ip": "FAIL"}, ["G1"]),
        ({"round_mechanics": "FAIL", "no_litigation": "FAIL"}, ["G1"]),
        ({"clean_ip": "NOT VISIBLE", "no_litigation": "NOT VISIBLE"}, []),
        ({"clean_ip": "NOT VISIBLE", "full_time_founders": "FAIL"}, ["G1"]),
    ],
)
def test_g1_integrity(spec, integrity, expected):
    c = checks()
    c["integrity"].update(integrity)
    assert ids(c, spec) == expected


def test_every_integrity_check_can_trip_g1(spec):
    for name in list(checks()["integrity"]):
        c = checks()
        c["integrity"][name] = "FAIL"
        assert ids(c, spec) == ["G1"], name


def test_g2_exit_pathway(spec):
    c = checks()
    c["exit_pathway"] = "not credible"
    assert ids(c, spec) == ["G2"]
    c["exit_pathway"] = "credible"
    assert ids(c, spec) == []


@pytest.mark.parametrize(
    "founders,expected",
    [
        ("Weak", ["G3"]),
        ("Not visible", ["G3"]),
        ("Adequate", []),
        ("Exceptional", []),
    ],
)
def test_g3_founders(spec, founders, expected):
    assert ids(checks(founders=founders), spec) == expected


@pytest.mark.parametrize(
    "mt,sm,expected",
    [
        ("Weak", "Not visible", ["G4", "G5"]),
        ("Weak", "Weak", ["G4", "G5"]),
        ("Not visible", "Not visible", ["G4", "G6", "G7"]),
        ("Adequate", "Weak", ["G5"]),
        ("Exceptional", "Weak", ["G5"]),
        ("Weak", "Adequate", ["G5"]),
        ("Adequate", "Adequate", []),
        ("Exceptional", "Not visible", []),
    ],
)
def test_g4_and_g5_market_and_secret(spec, mt, sm, expected):
    # capital_efficiency Adequate, founders Adequate
    got = ids(checks(market_timing=mt, secret_monopoly=sm), spec)
    # two Not visible forces also trip G6 and G7; compare the G4 and G5 part only here
    assert [g for g in got if g in ("G4", "G5")] == [g for g in expected if g in ("G4", "G5")]


def test_g4_does_not_trip_when_one_of_the_two_is_adequate(spec):
    assert "G4" not in ids(checks(market_timing="Weak", secret_monopoly="Adequate"), spec)
    assert "G4" not in ids(checks(market_timing="Not visible", secret_monopoly="Exceptional"), spec)


def test_g5_does_not_trip_when_founders_are_exceptional(spec):
    c = checks(market_timing="Weak", founders="Exceptional")
    assert "G5" not in ids(c, spec)


def test_g5_trips_when_founders_are_adequate(spec):
    assert "G5" in ids(checks(secret_monopoly="Weak"), spec)


def test_g6_and_g7_two_not_visible(spec):
    c = checks(market_timing="Not visible", capital_efficiency="Not visible")
    assert ids(c, spec) == ["G6", "G7"]


def test_g6_does_not_trip_with_an_exceptional_force_but_g7_does(spec):
    c = checks(
        market_timing="Not visible", capital_efficiency="Not visible", founders="Exceptional"
    )
    assert ids(c, spec) == ["G7"]


def test_g7_one_not_visible_force_trips_nothing(spec):
    assert ids(checks(capital_efficiency="Not visible"), spec) == []


def test_g7_three_not_visible(spec):
    c = checks(
        market_timing="Not visible", secret_monopoly="Not visible", capital_efficiency="Not visible"
    )
    assert {"G4", "G6", "G7"} <= set(ids(c, spec))


# --- gates: what a verdict may be --------------------------------------------------


def test_g1_allows_only_no(spec):
    c = checks()
    c["integrity"]["clean_ip"] = "FAIL"
    assert check_gates(c, "NO", spec) == []
    for verdict in ("YES", "CONDITIONAL"):
        got = check_gates(c, verdict, spec)
        assert len(got) == 1 and got[0].startswith("gate G1: an integrity check failed")


def test_g7_allows_conditional_but_not_yes(spec):
    c = checks(
        market_timing="Not visible", capital_efficiency="Not visible", founders="Exceptional"
    )
    assert check_gates(c, "NO", spec) == []
    assert check_gates(c, "CONDITIONAL", spec) == []
    got = check_gates(c, "YES", spec)
    assert len(got) == 1 and "gate G7" in got[0] and "NO or CONDITIONAL" in got[0]


def test_stricter_gate_wins_when_two_gates_differ(spec):
    # G3 (NO only) and G7 (NO or CONDITIONAL) both trip
    c = checks(founders="Not visible", capital_efficiency="Not visible")
    assert set(ids(c, spec)) >= {"G3", "G7"}
    got = check_gates(c, "CONDITIONAL", spec)
    assert any("gate G3" in p for p in got) and not any("gate G7" in p for p in got)
    assert check_gates(c, "NO", spec) == []
    both = check_gates(c, "YES", spec)
    assert any("gate G3" in p for p in both) and any("gate G7" in p for p in both)


def test_no_gate_trips_so_any_verdict_is_allowed(spec):
    for verdict in ("YES", "NO", "CONDITIONAL"):
        assert check_gates(checks(), verdict, spec) == []


def test_vote_fails_when_the_verdict_breaks_a_gate(prompts):
    p = fixture("pass_yes")
    p["checks"]["forces"]["founders"] = "Weak"
    v = run(p, prompts)
    assert v.passed is False
    assert problems_with("gate G3: Founders is Weak or Not visible, so the verdict must be NO", v)


# --- vote text failures -------------------------------------------------------------


def test_missing_header_field(prompts):
    p = with_text(
        "pass_yes", lambda t: t.replace("Seed / SAFE / $1.2M / $12M", "Seed / SAFE / $1.2M")
    )
    assert problems_with("header has 4 values, expected 5", run(p, prompts))


def test_empty_header_field(prompts):
    p = with_text("pass_yes", lambda t: t.replace("Seed / SAFE", "Seed /  "))
    assert problems_with("header INSTRUMENT is empty", run(p, prompts))


def test_header_left_as_the_template(prompts):
    p = with_text("pass_yes", lambda t: t.replace("Northwind Pottery Labs", "COMPANY"))
    v = run(p, prompts)
    assert problems_with("header COMPANY is not filled in", v) and v.company is None


def test_empty_label(prompts):
    p = with_text(
        "pass_yes",
        lambda t: re.sub(r"THESIS IN ONE SENTENCE:.*", "THESIS IN ONE SENTENCE:", t),
    )
    assert problems_with("THESIS IN ONE SENTENCE is empty", run(p, prompts))


def test_missing_label_line(prompts):
    p = with_text("pass_yes", lambda t: re.sub(r"CONVICTION: 3\n\n", "", t))
    assert problems_with("no CONVICTION line", run(p, prompts))


def test_bad_verdict(prompts):
    p = with_text("pass_yes", lambda t: t.replace("VERDICT: YES", "VERDICT: MAYBE"))
    v = run(p, prompts)
    assert problems_with("VERDICT is 'MAYBE'", v) and v.verdict is None


def test_verdict_left_as_the_template(prompts):
    p = with_text(
        "pass_yes", lambda t: t.replace("VERDICT: YES", "VERDICT: YES | NO | CONDITIONAL")
    )
    assert problems_with("VERDICT is", run(p, prompts))


def test_conviction_4(prompts):
    p = with_text("pass_yes", lambda t: t.replace("CONVICTION: 3", "CONVICTION: 4"))
    assert problems_with("CONVICTION is '4'", run(p, prompts))


def test_labels_out_of_order(prompts):
    def swap(t):
        return (
            t.replace("VERDICT: YES", "@@")
            .replace("CONVICTION: 3", "VERDICT: YES")
            .replace("@@", "CONVICTION: 3")
        )

    assert problems_with("out of order", run(with_text("pass_yes", swap), prompts))


def test_bullets_in_the_wrong_order(prompts):
    def swap(t):
        lines = t.split("\n")
        i = next(n for n, ln in enumerate(lines) if ln.startswith("- Structure"))
        lines[i], lines[i + 1] = lines[i + 1], lines[i]
        return "\n".join(lines)

    v = run(with_text("pass_yes", swap), prompts)
    assert problems_with("RATIONALE bullets are out of order", v)


def test_missing_bullet(prompts):
    p = with_text("pass_yes", lambda t: re.sub(r"- Material things I could not see:.*", "", t))
    v = run(p, prompts)
    assert problems_with("no bullet 'Material things I could not see'", v)


def test_empty_bullet(prompts):
    p = with_text(
        "pass_yes",
        lambda t: re.sub(
            r"- Material things I could not see:.*", "- Material things I could not see:", t
        ),
    )
    assert problems_with("bullet 'Material things I could not see' is empty", run(p, prompts))


def test_no_observed_or_claimed_tag(prompts):
    p = with_text("pass_yes", lambda t: t.replace("OBSERVED", "SEEN").replace("CLAIMED", "STATED"))
    assert problems_with("none of: OBSERVED, CLAIMED", run(p, prompts))


def test_one_tag_is_enough(prompts):
    p = with_text("pass_yes", lambda t: t.replace("OBSERVED", "SEEN"))
    assert run(p, prompts).problems == []


def test_no_verdict_needs_no_now_or_no_ever(prompts):
    p = with_text("pass_no", lambda t: t.replace("no, now", "not yet"))
    assert problems_with("NO vote has none of", run(p, prompts))


def test_no_ever_is_accepted_in_any_case(prompts):
    p = with_text("pass_no", lambda t: t.replace("no, now", "No, Ever"))
    assert run(p, prompts).problems == []


def test_yes_verdict_does_not_need_the_no_phrase(prompts):
    assert "no, now" not in fixture("pass_yes")["output"].lower()
    assert run(fixture("pass_yes"), prompts).problems == []


@pytest.mark.parametrize("code", ["G5", "G1", "Gate 3", "gate 7", "Gate3"])
def test_gate_codes_are_forbidden(prompts, code):
    p = with_text("pass_yes", lambda t: t + f"\nThis failed {code}.")
    assert problems_with("text contains", run(p, prompts))


def test_words_that_only_look_like_gate_codes_are_fine(prompts):
    p = with_text("pass_yes", lambda t: t + "\nThe gateway and G55 and Gate keeper are fine.")
    assert run(p, prompts).problems == []


def test_under_400_words(prompts):
    p = with_text("pass_yes", lambda t: t.replace(FILL, ""))
    v = run(p, prompts)
    assert v.words < 400 and problems_with("range 400 to 700", v)


def test_over_700_words(prompts):
    p = with_text("pass_yes", lambda t: t + " word" * 300)
    v = run(p, prompts)
    assert v.words > 700 and problems_with("range 400 to 700", v)


def test_word_limits_are_inclusive(prompts):
    base = fixture("pass_yes")["output"].replace(FILL, "")
    short = count_words(base)
    for target in (400, 700):
        p = {"output": base + " w" * (target - short), "checks": fixture("pass_yes")["checks"]}
        v = run(p, prompts)
        assert v.words == target and not problems_with("range", v)


# --- Markdown decoration ------------------------------------------------------------


def bold(t: str) -> str:
    t = re.sub(
        r"^(VERDICT|CONVICTION|THESIS IN ONE SENTENCE|STRONGEST CASE AGAINST MY OWN VOTE|RATIONALE):",
        r"**\1:**",
        t,
        flags=re.MULTILINE,
    )
    return re.sub(r"^- ([^:]+):", r"- **\1:**", t, flags=re.MULTILINE)


def test_bold_labels_are_tolerated(prompts):
    v = run(with_text("pass_no", bold), prompts)
    assert v.problems == [] and v.verdict == "NO"


def test_bold_header_and_inner_bold(prompts):
    p = with_text(
        "pass_yes",
        lambda t: t.replace("Northwind Pottery Labs", "**Northwind Pottery Labs**").replace(
            "VERDICT: YES", "VERDICT: **YES**"
        ),
    )
    v = run(p, prompts)
    assert v.problems == [] and v.verdict == "YES"


def test_code_fence_is_tolerated(prompts):
    p = with_text("pass_yes", lambda t: "```\n" + t + "\n```")
    v = run(p, prompts)
    assert v.problems == [] and v.company == "Northwind Pottery Labs"


def test_code_fence_with_language_and_bold_together(prompts):
    p = with_text("pass_conditional", lambda t: "```text\n" + bold(t) + "\n```")
    assert run(p, prompts).problems == []


def test_star_bullets_and_label_without_dash_space(prompts):
    p = with_text("pass_yes", lambda t: re.sub(r"^- ", "* ", t, flags=re.MULTILINE))
    assert run(p, prompts).problems == []


def test_alias_why_no_bullet(prompts):
    p = fixture("pass_no")
    assert "Why NO:" in p["output"]
    assert run(p, prompts).problems == []


def test_why_bullet_label_in_the_template_form(prompts):
    p = with_text("pass_no", lambda t: t.replace("Why NO:", "Why Yes / No / Conditional:"))
    assert run(p, prompts).problems == []


# --- payload errors -----------------------------------------------------------------


def test_invalid_json(prompts):
    v = run("{not json", prompts)
    assert v.passed is False and v.version == "ai_ic_v1"
    assert problems_with("not valid JSON", v) and v.company is None


@pytest.mark.parametrize("raw", ["[]", '"text"', "3", "null"])
def test_json_that_is_not_an_object(prompts, raw):
    assert problems_with("not a JSON object", run(raw, prompts))


def test_missing_checks_key(prompts):
    p = fixture("pass_yes")
    del p["checks"]
    v = run(p, prompts)
    assert problems_with("no object in 'checks'", v) and v.passed is False


def test_missing_output_key_still_checks_the_payload(prompts):
    p = fixture("pass_yes")
    del p["output"]
    v = run(p, prompts)
    assert problems_with("no text in 'output'", v) and v.words is None


def test_empty_output(prompts):
    p = fixture("pass_yes")
    p["output"] = "   "
    assert problems_with("no text in 'output'", run(p, prompts))


def test_missing_force_key(prompts):
    p = fixture("pass_yes")
    del p["checks"]["forces"]["founders"]
    assert problems_with("checks.forces.founders is missing", run(p, prompts))


def test_missing_integrity_check(prompts):
    p = fixture("pass_yes")
    del p["checks"]["integrity"]["clean_ip"]
    assert problems_with("checks.integrity.clean_ip is missing", run(p, prompts))


def test_missing_exit_pathway(prompts):
    p = fixture("pass_yes")
    del p["checks"]["exit_pathway"]
    assert problems_with("checks.exit_pathway is missing", run(p, prompts))


def test_unknown_force_value(prompts):
    p = fixture("pass_yes")
    p["checks"]["forces"]["founders"] = "Great"
    assert problems_with("checks.forces.founders is 'Great'", run(p, prompts))


def test_integrity_value_in_the_wrong_case(prompts):
    p = fixture("pass_yes")
    p["checks"]["integrity"]["clean_ip"] = "pass"
    assert problems_with("checks.integrity.clean_ip is 'pass'", run(p, prompts))


def test_unknown_exit_pathway_value(prompts):
    p = fixture("pass_yes")
    p["checks"]["exit_pathway"] = "maybe"
    assert problems_with("checks.exit_pathway is 'maybe'", run(p, prompts))


def test_unknown_keys(prompts):
    p = fixture("pass_yes")
    p["checks"]["forces"]["luck"] = "Weak"
    p["checks"]["mood"] = "good"
    p["extra"] = 1
    v = run(p, prompts)
    assert problems_with("unknown key 'luck'", v)
    assert problems_with("checks has an unknown key 'mood'", v)
    assert problems_with("payload has an unknown key 'extra'", v)


def test_a_payload_problem_is_not_hidden_by_a_gate_pass(prompts):
    p = fixture("pass_yes")
    p["checks"]["forces"]["founders"] = "Great"
    v = run(p, prompts)
    assert v.passed is False and not problems_with("gate", v)


def test_text_problems_and_payload_problems_are_both_reported(prompts):
    p = with_text("pass_yes", lambda t: t.replace("VERDICT: YES", "VERDICT: MAYBE"))
    p["checks"]["exit_pathway"] = "maybe"
    v = run(p, prompts)
    assert problems_with("VERDICT is", v) and problems_with("exit_pathway", v)


# --- version selection --------------------------------------------------------------


def test_no_version_live_before_go_live(prompts):
    v = run(fixture("pass_yes"), prompts, now=datetime(2025, 12, 31, tzinfo=UTC))
    assert v.version is None and v.passed is None and v.problems == []


def test_no_version_live_without_any_ai_ic_spec(tmp_path):
    (tmp_path / "brief_v1.spec.toml").write_text('go_live = "2026-01-01"\n')
    v = run(fixture("pass_yes"), tmp_path)
    assert v.passed is None


def test_no_version_live_in_an_empty_directory(tmp_path):
    assert run(fixture("pass_yes"), tmp_path).passed is None


def test_go_live_instant_is_inclusive(prompts):
    assert (
        run(fixture("pass_yes"), prompts, now=datetime(2026, 1, 1, tzinfo=UTC)).version
        == "ai_ic_v1"
    )


def test_latest_go_live_at_or_before_the_check_wins(prompts):
    text = (prompts / "ai_ic_v1.spec.toml").read_text()
    later = re.sub(
        r'^go_live = ".*"$', 'go_live = "2026-12-01T00:00:00Z"', text, flags=re.MULTILINE
    )
    (prompts / "ai_ic_v2.spec.toml").write_text(later)
    p = fixture("pass_yes")
    assert run(p, prompts, now=datetime(2026, 11, 1, tzinfo=UTC)).version == "ai_ic_v1"
    assert run(p, prompts, now=datetime(2026, 12, 2, tzinfo=UTC)).version == "ai_ic_v2"


def test_brief_specs_are_not_used_for_votes(prompts):
    (prompts / "brief_v9.spec.toml").write_text('go_live = "2026-06-01"\n')
    assert run(fixture("pass_yes"), prompts).version == "ai_ic_v1"


# --- the spec file ------------------------------------------------------------------


def test_the_real_spec_has_seven_gates_and_valid_conditions(spec):
    assert [g["id"] for g in spec["gates"]] == [f"G{i}" for i in range(1, 8)]
    for g in spec["gates"]:
        assert g["description"] and g["allows"] and set(g["allows"]) <= {"YES", "NO", "CONDITIONAL"}
        tripped_gates(checks(), spec)  # raises on a condition the code does not know


def test_unknown_condition_is_reported_loudly(spec):
    spec["gates"].append(
        {"id": "GX", "description": "x", "when": {"mood": "bad"}, "allows": ["NO"]}
    )
    with pytest.raises(ValueError, match="unknown gate condition"):
        tripped_gates(checks(), spec)


# --- the command --------------------------------------------------------------------


def ic(payload, prompts, *args):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return runner.invoke(app, ["ic", "--stdin", "--prompts-dir", str(prompts), *args], input=raw)


def test_ic_without_stdin_is_an_error(prompts):
    r = runner.invoke(app, ["ic", "--prompts-dir", str(prompts)])
    assert r.exit_code == 2 and "--stdin" in r.output


def test_ic_pass_exits_0_and_prints_one_row(prompts):
    r = ic(fixture("pass_no"), prompts)
    assert r.exit_code == 0
    assert "| Company | Prompt | Words | Verdict | Conviction | Result | Detail |" in r.output
    words = count_words(fixture("pass_no")["output"])
    assert f"| Northwind Pottery Labs | ai_ic_v1 | {words} | NO | 2 | pass | - |" in r.output
    assert "n = 1 (below 5: rows only, no percentages)" in r.output
    assert "%" not in r.output


def test_ic_gate_failure_exits_1_and_names_the_gate(prompts):
    p = fixture("pass_yes")
    p["checks"]["forces"]["founders"] = "Weak"
    r = ic(p, prompts)
    assert r.exit_code == 1
    assert (
        "| FAIL | gate G3: Founders is Weak or Not visible, so the verdict must be NO" in r.output
    )


def test_ic_format_failure_exits_1(prompts):
    p = with_text("pass_yes", lambda t: t.replace("CONVICTION: 3", "CONVICTION: 4"))
    r = ic(p, prompts)
    assert r.exit_code == 1 and "CONVICTION is '4'" in r.output


def test_ic_invalid_json_exits_1_with_a_fail_row(prompts):
    r = ic("{oops", prompts)
    assert r.exit_code == 1
    assert "| - | ai_ic_v1 | - | - | - | FAIL | payload is not valid JSON" in r.output


def test_ic_empty_input_exits_1(prompts):
    r = ic("", prompts)
    assert r.exit_code == 1 and "FAIL" in r.output


def test_ic_no_version_live_is_not_a_failure(tmp_path):
    r = ic(fixture("pass_yes"), tmp_path)
    assert r.exit_code == 0
    assert "| - | - | - | - | - | no version live | - |" in r.output


def test_ic_spec_goes_live_in_the_future(prompts):
    text = (prompts / "ai_ic_v1.spec.toml").read_text()
    text = re.sub(r'^go_live = ".*"$', 'go_live = "2999-01-01T00:00:00Z"', text, flags=re.MULTILINE)
    (prompts / "ai_ic_v1.spec.toml").write_text(text)
    r = ic(fixture("pass_yes"), prompts)
    assert r.exit_code == 0 and "no version live" in r.output


def test_ic_does_not_use_the_network(prompts, monkeypatch):
    import socket

    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(socket, "socket", boom)
    assert ic(fixture("pass_yes"), prompts).exit_code == 0
