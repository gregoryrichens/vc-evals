import nltk
from typer.testing import CliRunner

from vc_evals.cli import app
from vc_evals.layer2 import (
    MEASURES,
    bullets,
    duplicates,
    jargon,
    readability,
    run_all,
    sections,
    sentences,
)
from vc_evals.layer2.text import prepare

runner = CliRunner()

BRIEF = """## What is it?
Acme sells a tool for dentists. It is cheap.

## Market
- Dentists pay for software every month.
- Dentists pay for software every month!
- The market is large.

### Inputs
Deck: none
Prompt: brief_v1
"""


def test_prepare_drops_inputs_and_counts_words_by_section():
    prepared = prepare(BRIEF)
    assert [s.heading for s in prepared.sections] == ["What is it?", "Market"]
    assert [s.words for s in prepared.sections] == [12, 17]


def test_words_per_section_total_matches_layer1_count():
    from vc_evals.briefs import count_words, parse_brief

    assert sections.measure(prepare(BRIEF)).metrics["total words"] == count_words(
        parse_brief(BRIEF).text
    )


def test_bullets_per_section():
    result = bullets.measure(prepare(BRIEF))
    assert result.metrics == {"bullets": 3, "most bullets in one section": 3}
    assert "Market: 3 bullets" in result.details


def test_sentence_length_splits_abbreviations_and_bullets():
    body = "## A\nWe sell to Dr. Smith in the U.S. It grew fast.\n- a bullet with no stop\n"
    result = sentences.measure(prepare(body))
    assert result.metrics["sentences"] == 3


def test_jargon_uses_the_word_list_and_skips_names():
    found, total = jargon.jargon_words("The cat met Acme. We use an FPGA and quantum chips.")
    assert total == 11
    assert set(found) == {
        "fpga",
        "quantum",
        "chips",
    }  # Acme is skipped as a name; FPGA, in capitals, is counted


def test_jargon_possessive_and_curly_apostrophe():
    found, _ = jargon.jargon_words("The cat’s hat isn’t big.")
    assert not found


def test_jargon_word_list_is_the_xkcd_list():
    words = jargon.word_list()
    assert {"the", "water", "don't"} <= words
    assert "algorithm" not in words


def test_near_duplicates_found_and_distinct_points_not():
    assert duplicates.measure(prepare(BRIEF)).metrics["near-duplicate pairs"] == 1
    assert duplicates.measure(
        prepare("## A\nWe sell chips to labs. Revenue is flat this year.\n")
    ).metrics == {"near-duplicate pairs": 0}


def test_readability_scores_plain_text():
    result = readability.measure(prepare("## A\nThe cat sat on the mat. It was happy.\n"))
    assert result.metrics["Flesch reading ease"] > 80


def test_every_measure_gives_zero_or_dash_on_an_empty_brief():
    results = run_all("")
    assert set(results) == set(MEASURES)
    flat = {k: v for r in results.values() for k, v in r.metrics.items()}
    assert flat["total words"] == 0
    assert flat["sentences"] == 0
    assert flat["mean words per sentence"] == "-"
    assert flat["jargon words"] == 0 and flat["jargon per 100 prose words"] == "-"
    assert flat["bullets"] == 0 and flat["near-duplicate pairs"] == 0


RULES_AND_TABLES = (
    "## A\nThe market for dental software is large and growing every year.\n\n---\n\n"
    "* * *\n\nThe team has built two companies before and sold both.\n\n"
    "| Year | Revenue |\n|---|---|\n| 2024 | 1m |\n"
)


def test_rules_and_table_rows_are_not_sentences_or_bullets_but_their_words_count():
    from vc_evals.briefs import count_words, parse_brief

    assert sentences.measure(prepare(RULES_AND_TABLES)).metrics["sentences"] == 2
    assert bullets.measure(prepare(RULES_AND_TABLES)).metrics["bullets"] == 0
    assert sections.measure(prepare(RULES_AND_TABLES)).metrics["total words"] == count_words(
        parse_brief(RULES_AND_TABLES).text
    )


def test_a_wrapped_bullet_and_a_wrapped_paragraph_are_one_sentence_each():
    body = (
        "## A\n- The company sells a tool to dentists\n  who pay every month for it.\n\n"
        "The team has built two companies\nbefore and sold both.\n"
    )
    assert prepare(body).sentences == [
        "The company sells a tool to dentists who pay every month for it.",
        "The team has built two companies before and sold both.",
    ]


def test_a_fence_that_closes_on_its_own_line_does_not_hide_the_rest():
    body = "## A\n```bash pip```\n## B\n- one bullet here.\n- two bullet here.\n"
    result = bullets.measure(prepare(body))
    assert [s.heading for s in prepare(body).sections] == ["A", "B"]
    assert result.metrics["bullets"] == 2


def test_tilde_fences_hide_their_contents():
    body = "## A\n~~~\n# not a heading\n- not a bullet\n~~~\nA real sentence follows here.\n"
    prepared = prepare(body)
    assert [s.heading for s in prepared.sections] == ["A"]
    assert prepared.sections[0].bullets == 0
    assert prepared.sentences == ["A real sentence follows here."]


def test_a_company_name_that_starts_a_sentence_is_not_jargon():
    text = "Democo builds a tool. We met the Democo team. Democo sells it."
    found, _ = jargon.jargon_words(text)
    assert "democo" not in found


def test_a_capitalised_word_after_a_colon_still_counts():
    found, _ = jargon.jargon_words("Risk: Regulatory approval is slow.")
    assert "regulatory" in found


def test_a_capitalised_word_after_a_bracket_or_quote_still_counts():
    found, _ = jargon.jargon_words('(Defensibility is low.) He said "Regulatory approval" matters.')
    assert {"defensibility", "regulatory"} <= set(found)


def test_single_letters_are_not_jargon():
    found, _ = jargon.jargon_words("We sell chips, e.g. to labs.")
    assert "e" not in found and "g" not in found


def test_the_jargon_rate_is_per_100_prose_words():
    result = jargon.measure(
        prepare("## Heading words do not count\nThe quantum cat sat. 2024 revenue.\n")
    )
    assert result.metrics["prose words"] == 5  # the heading and "2024" are left out
    assert result.metrics["jargon per 100 prose words"] == round(
        100 * result.metrics["jargon words"] / result.metrics["prose words"], 1
    )


def test_measure_command_runs_one_measure_from_stdin():
    out = runner.invoke(app, ["measure", "bullets_per_section", "--stdin"], input=BRIEF)
    assert out.exit_code == 0
    assert "- bullets: 3" in out.output
    assert "jargon" not in out.output


def test_measure_command_needs_exactly_one_selector():
    out = runner.invoke(app, ["measure", "jargon"])
    assert out.exit_code == 2


def fixture_score(*args):
    return runner.invoke(app, ["score", "--fixtures", "--fixtures-dir", "fixtures", *args])


def test_score_prints_a_layer2_row_and_a_passing_brief_exits_0():
    out = fixture_score("--note", "n-v1a")
    assert out.exit_code == 0
    rows = [ln for ln in out.output.splitlines() if ln.startswith("| n-v1a |")]
    assert len(rows) == 2  # one Layer 1 row, one Layer 2 row
    layer2 = rows[1].split("|")
    assert len(layer2) > 10 and all(cell.strip() for cell in layer2[1:-1])
    for header in ("Flesch reading ease", "jargon per 100 prose words", "near-duplicate pairs"):
        assert header in out.output


def test_a_failing_brief_exits_1_and_still_prints_layer2():
    out = fixture_score("--note", "n-bad")
    assert out.exit_code == 1
    assert "Layer 2, quality proxies" in out.output


def test_layer2_does_not_change_the_exit_code(monkeypatch):
    from vc_evals import cli

    monkeypatch.setattr(cli, "run_all", lambda body: run_all(""))
    assert fixture_score("--note", "n-v1a").exit_code == 0
    assert fixture_score("--note", "n-bad").exit_code == 1


def test_measure_runs_over_a_fixture_deal():
    out = runner.invoke(
        app, ["measure", "jargon", "--fixtures", "--fixtures-dir", "fixtures", "--deal", "deal-1"]
    )
    assert out.exit_code == 0
    assert out.output.count("- jargon words:") == 4
    assert "n = 4" in out.output


def test_measure_with_no_briefs_says_so():
    out = runner.invoke(
        app, ["measure", "jargon", "--fixtures", "--fixtures-dir", "fixtures", "--deal", "nope"]
    )
    assert out.exit_code == 0
    assert out.output.strip() == "no briefs"


def test_readability_uses_the_dictionary_in_the_repo():
    from vc_evals.layer2 import readability  # noqa: F401  (puts nltk_data on nltk's path)

    assert "nltk_data/corpora/cmudict" in str(nltk.data.find("corpora/cmudict"))


def test_run_all_prepares_the_brief_once(monkeypatch):
    from vc_evals import layer2

    calls = []
    real = layer2.prepare
    monkeypatch.setattr(layer2, "prepare", lambda body: calls.append(body) or real(body))
    run_all(BRIEF)
    assert len(calls) == 1


def test_sentences_are_split_once_per_prepared_brief():
    prepared = prepare(BRIEF)
    assert prepared.sentences is prepared.sentences


def test_quick_ratio_checks_give_the_same_pairs_as_the_full_ratio():
    from difflib import SequenceMatcher
    from itertools import combinations

    body = (
        "## A\nThe market for dental software is large.\n"
        "The market for dental software is very large.\n"
        "The team has built two companies before.\n"
        "Revenue was flat in the last quarter of the year.\n"
        "The market for dental software is huge.\n"
    )
    points = prepare(body).sentences
    expected = sum(
        1
        for a, b in combinations(points, 2)
        if SequenceMatcher(None, a.lower(), b.lower()).ratio() >= duplicates.SIMILARITY
    )
    assert expected > 0
    assert duplicates.measure(prepare(body)).metrics["near-duplicate pairs"] == expected
