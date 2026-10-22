from datetime import UTC, datetime
from pathlib import Path

from vc_evals.briefs import (
    check_inputs,
    count_words,
    has_table,
    input_rules,
    normalize,
    parse_brief,
    score_brief,
)

PROMPTS = Path(__file__).parent.parent / "fixtures" / "prompts"
# fixture specs: brief_v0 went live 2026-09-01, brief_v1 on 2026-10-14
V0_ERA = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
V1_ERA = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)

GOOD_V1 = """## What is it?
A thing.

## Founders
Two founders.

## Market
Some buyers.

## Competitors
Two rivals.

## Follow Up
- A question?

### Inputs
Deck: none
Other Company Materials: none
Web: https://example.com
Prompt: brief_v1
Model: m
"""


def test_normalize_drops_case_question_mark_hyphen_and_description():
    assert normalize("What is it?") == "what is it"
    assert normalize("Follow-Up Questions") == "follow up questions"
    assert normalize("Market — who pays") == "market"
    assert normalize("What’s actually real") == "what's actually real"


def test_parse_inputs_lines_and_prompt_version():
    parsed = parse_brief(GOOD_V1)
    assert parsed.inputs["prompt"] == ["brief_v1"]
    assert parsed.inputs["web"] == ["https://example.com"]
    assert parsed.prompt_line == "brief_v1"


def test_version_comes_from_the_creation_date_not_the_prompt_line():
    body = "## What it is\nx\n\n## Market\ny\n\n## Team\nz\n"
    assert parse_brief(body).prompt_line is None
    s = score_brief(body, V0_ERA, PROMPTS)
    assert (s.prompt_version, s.spec_found, s.layer1_pass) == ("brief_v0", True, True)


def test_a_wrong_prompt_line_does_not_change_the_version():
    body = GOOD_V1.replace("Prompt: brief_v1", "Prompt: brief_v0")
    s = score_brief(body, V1_ERA, PROMPTS)
    # the version still comes from the date. The spec says the Prompt line must equal brief_v1.
    assert (s.prompt_version, s.prompt_line) == ("brief_v1", "brief_v0")
    assert s.inputs_problems == ["Prompt is 'brief_v0', not 'brief_v1'"]
    assert s.layer1_pass is False


def test_a_v1_brief_made_in_the_v0_era_is_checked_against_v0():
    s = score_brief(GOOD_V1, V0_ERA, PROMPTS)
    assert s.prompt_version == "brief_v0" and s.layer1_pass is False
    assert "What it is" in s.missing


def test_go_live_boundary_is_inclusive_at_the_start_of_the_day():
    before = datetime(2026, 10, 13, 23, 59, 59, tzinfo=UTC)
    on = datetime(2026, 10, 14, 0, 0, 0, tzinfo=UTC)
    assert score_brief(GOOD_V1, before, PROMPTS).prompt_version == "brief_v0"
    assert score_brief(GOOD_V1, on, PROMPTS).prompt_version == "brief_v1"


def test_no_version_live_yet_means_no_spec_not_a_fallback():
    s = score_brief(GOOD_V1, datetime(2026, 8, 1, tzinfo=UTC), PROMPTS)
    assert s.prompt_version is None and s.spec_found is False and s.layer1_pass is None


def test_spec_without_go_live_is_never_live(tmp_path):
    (tmp_path / "brief_v7.spec.toml").write_text('headings = ["Anything"]\n')
    s = score_brief(GOOD_V1, V1_ERA, tmp_path)
    assert s.prompt_version is None


def test_all_sections_present_passes():
    s = score_brief(GOOD_V1, V1_ERA, PROMPTS)
    assert s.missing == [] and s.empty == [] and s.layer1_pass is True


def test_missing_section_fails():
    body = GOOD_V1.replace("## Competitors\nTwo rivals.\n\n", "")
    s = score_brief(body, V1_ERA, PROMPTS)
    assert s.missing == ["Competitors"] and s.layer1_pass is False


def test_missing_founders_section_fails():
    body = GOOD_V1.replace("## Founders\nTwo founders.\n\n", "")
    s = score_brief(body, V1_ERA, PROMPTS)
    assert s.missing == ["Founders"] and s.layer1_pass is False


def test_empty_section_fails():
    body = GOOD_V1.replace("## Market\nSome buyers.\n", "## Market\n\n")
    s = score_brief(body, V1_ERA, PROMPTS)
    assert s.empty == ["Market"] and s.missing == [] and s.layer1_pass is False


def test_subsection_text_counts_for_parent():
    body = GOOD_V1.replace("## Market\nSome buyers.\n", "## Market\n### Size\nBig.\n")
    assert score_brief(body, V1_ERA, PROMPTS).layer1_pass is True


def test_alias_accepted():
    body = GOOD_V1.replace("## Follow Up", "## Follow-Up Questions")
    assert score_brief(body, V1_ERA, PROMPTS).layer1_pass is True


def test_inputs_block_without_a_heading_fails():
    body = GOOD_V1.replace("### Inputs\n", "---\n")
    assert parse_brief(body).inputs == {}
    s = score_brief(body, V1_ERA, PROMPTS)
    assert s.inputs_problems == ["no Inputs section"]
    assert s.layer1_pass is False


def test_trailing_text_that_is_not_label_value_gives_no_inputs():
    body = GOOD_V1.split("### Inputs")[0] + "\nThat is all.\n"
    assert parse_brief(body).inputs == {}


def test_appended_eval_result_is_not_part_of_the_brief():
    appended = (
        "\n---\n\n## Eval result\n\n```\n| Note | Result |\nResult: FAIL\nWeb: not a url\n```\n"
    )
    body = GOOD_V1 + appended
    parsed = parse_brief(body)
    assert parsed.inputs["prompt"] == ["brief_v1"]
    assert parsed.text == parse_brief(GOOD_V1).text
    s = score_brief(body, V1_ERA, PROMPTS)
    assert (s.prompt_version, s.layer1_pass) == ("brief_v1", True)


def test_go_live_may_be_a_quoted_string(tmp_path):
    (tmp_path / "brief_v1.spec.toml").write_text(
        'go_live = "2026-10-14"\n[[sections]]\nname = "Market"\n'
    )
    assert score_brief(GOOD_V1, V1_ERA, tmp_path).prompt_version == "brief_v1"
    assert score_brief(GOOD_V1, V0_ERA, tmp_path).prompt_version is None


def test_count_words_ignores_markdown_marks():
    assert count_words("## Hello *world* — 12 -") == 3


def test_word_count_excludes_the_inputs_block():
    assert score_brief(GOOD_V1, V1_ERA, PROMPTS).words == 18


def test_over_the_word_limit_fails():
    body = GOOD_V1.replace("A thing.", "word " * 60)  # limit in the fixture spec is 60
    s = score_brief(body, V1_ERA, PROMPTS)
    assert (s.words, s.max_words, s.over_limit, s.layer1_pass) == (76, 60, True, False)


def test_exactly_at_the_limit_passes():
    body = GOOD_V1.replace("A thing.", "word " * 44)  # 18 - 2 + 44 = 60
    s = score_brief(body, V1_ERA, PROMPTS)
    assert (s.words, s.over_limit, s.layer1_pass) == (60, False, True)


def test_table_detection():
    assert has_table("| a | b |\n|---|---|\n| 1 | 2 |")
    assert has_table("a | b\n--- | ---\n1 | 2")
    assert not has_table("Some text\n---\nMore text")
    assert not has_table("- a | b\n- c")


def test_table_in_a_brief_fails():
    body = GOOD_V1.replace("Some buyers.", "| a | b |\n|---|---|\n| 1 | 2 |")
    s = score_brief(body, V1_ERA, PROMPTS)
    assert s.has_table and s.layer1_pass is False


def test_a_required_section_must_be_a_markdown_heading():
    body = GOOD_V1.replace("## Market", "**Market**")
    s = score_brief(body, V1_ERA, PROMPTS)
    assert s.missing == ["Market"] and s.layer1_pass is False


def test_heading_levels_1_to_3_are_allowed_by_the_spec():
    for marks in ("#", "##", "###"):
        body = GOOD_V1.replace("## Market", f"{marks} Market")
        assert score_brief(body, V1_ERA, PROMPTS).layer1_pass is True


def test_a_level_the_spec_does_not_allow_fails():
    body = GOOD_V1.replace("## Market", "#### Market")
    s = score_brief(body, V1_ERA, PROMPTS)
    assert s.bad_heading_levels == ["#### Market"] and s.layer1_pass is False


def test_the_allowed_levels_come_from_the_spec(tmp_path):
    spec = '{}\n[[sections]]\nname = "Market"\n[output]\nallowed_heading_levels = {}\n'
    body = "# Market\ntext\n"
    (tmp_path / "brief_v1.spec.toml").write_text(
        'go_live = "2026-10-14"\n' + spec.format("", "[2, 3]")
    )
    assert score_brief(body, V1_ERA, tmp_path).bad_heading_levels == ["# Market"]
    (tmp_path / "brief_v1.spec.toml").write_text(
        'go_live = "2026-10-14"\n' + spec.format("", "[1, 2, 3]")
    )
    assert score_brief(body, V1_ERA, tmp_path).bad_heading_levels == []


def test_inputs_rules_missing_duplicate_and_bad_url():
    rules = input_rules(
        {
            "inputs": {
                "lines": [
                    {"label": "Deck", "required": True, "repeatable": False},
                    {"label": "Web", "required": False, "repeatable": True, "value_type": "url"},
                    {"label": "Model", "required": True, "repeatable": False},
                ]
            }
        }
    )
    inputs = {"deck": ["a.pdf", "b.pdf"], "web": ["https://ok.com", "not a url"]}
    assert check_inputs(inputs, rules) == [
        "Deck appears 2 times",
        "Web is not a URL: not a url",
        "no Model line",
    ]


def test_no_inputs_block_at_all_is_a_problem_when_the_spec_has_rules():
    body = GOOD_V1.split("### Inputs")[0]
    s = score_brief(body, V1_ERA, PROMPTS)
    assert s.inputs_problems == ["no Inputs section"] and s.layer1_pass is False


def test_old_spec_format_still_gives_input_rules():
    rules = input_rules(
        {
            "inputs": {
                "required": ["Deck", "Prompt"],
                "repeatable": ["Web"],
                "prompt_value": "brief_v0",
            }
        }
    )
    assert [(r["label"], r["required"]) for r in rules] == [
        ("Deck", True),
        ("Prompt", True),
        ("Web", False),
    ]
    assert rules[1]["must_equal"] == "brief_v0"


def test_an_ai_ic_spec_does_not_change_which_spec_a_brief_is_scored_against(tmp_path):
    import shutil

    from vc_evals.briefs import live_spec

    shutil.copytree(PROMPTS, tmp_path / "p")
    (tmp_path / "p" / "ai_ic_v1.spec.toml").write_text('go_live = "2026-10-20"\n')
    assert live_spec(V1_ERA, tmp_path / "p", "brief_")[0] == "brief_v1"
    assert score_brief(GOOD_V1, V1_ERA, tmp_path / "p").prompt_version == "brief_v1"
    # a brief from after the ai_ic go_live is still scored against the latest brief spec
    later = datetime(2026, 10, 25, tzinfo=UTC)
    assert score_brief(GOOD_V1, later, tmp_path / "p").prompt_version == "brief_v1"


def test_a_brief_spec_does_not_change_which_spec_a_vote_is_checked_against(tmp_path):
    import shutil

    from vc_evals.briefs import live_spec

    shutil.copytree(PROMPTS, tmp_path / "p")
    (tmp_path / "p" / "ai_ic_v1.spec.toml").write_text('go_live = "2026-10-01"\n')
    # brief_v1 went live later (2026-10-14), but it is not a vote spec
    assert live_spec(V1_ERA, tmp_path / "p", "ai_ic_")[0] == "ai_ic_v1"
    assert live_spec(datetime(2026, 9, 20, tzinfo=UTC), tmp_path / "p", "ai_ic_") is None


def test_no_prefix_reads_every_spec(tmp_path):
    from vc_evals.briefs import live_spec

    (tmp_path / "ai_ic_v1.spec.toml").write_text('go_live = "2026-10-01"\n')
    assert live_spec(V1_ERA, tmp_path)[0] == "ai_ic_v1"


def test_inputs_heading_comes_from_the_spec(tmp_path):
    (tmp_path / "brief_v1.spec.toml").write_text(
        'go_live = "2026-10-14"\n'
        '[[sections]]\nname = "Market"\n'
        '[inputs]\nheading = "Sources"\n'
        '[[inputs.lines]]\nlabel = "Deck"\nrequired = true\nrepeatable = false\n'
    )
    sources = "## Market\ntext\n\n## Sources\nDeck: a.pdf\n"
    assert score_brief(sources, V1_ERA, tmp_path).layer1_pass is True
    inputs = sources.replace("Sources", "Inputs")
    assert score_brief(inputs, V1_ERA, tmp_path).inputs_problems == ["no Inputs section"]
