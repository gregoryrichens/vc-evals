import shutil
from pathlib import Path

from typer.testing import CliRunner

from vc_evals.cli import app

FIXTURES = Path(__file__).parent.parent / "fixtures"
runner = CliRunner()


def score(*args, fixtures_dir=FIXTURES):
    return runner.invoke(app, ["score", "--fixtures", "--fixtures-dir", str(fixtures_dir), *args])


def make_fixtures(tmp_path, n_good: int) -> Path:
    """A fixtures dir with n_good passing brief_v1 briefs, all on deal-x."""
    shutil.copytree(FIXTURES / "prompts", tmp_path / "prompts")
    good = (FIXTURES / "briefs" / "n-v1a.md").read_text()
    (tmp_path / "briefs").mkdir()
    index = ""
    for i in range(n_good):
        (tmp_path / "briefs" / f"g{i}.md").write_text(good)
        index += (
            f'[[briefs]]\nnote_id = "g{i}"\ndeal_id = "deal-x"\n'
            f'created_at = "2026-10-{15 + i}T00:00:00Z"\nfile = "briefs/g{i}.md"\n\n'
        )
    (tmp_path / "briefs.toml").write_text(index)
    return tmp_path


def test_no_selector_is_an_error():
    r = score()
    assert r.exit_code == 2 and "exactly one of --note, --deal or --stdin" in r.output


def test_stdin_scores_a_brief_that_is_not_in_attio():
    good = (FIXTURES / "briefs" / "n-v1a.md").read_text()
    r = runner.invoke(
        app, ["score", "--stdin", "--prompts-dir", str(FIXTURES / "prompts")], input=good
    )
    assert r.exit_code == 0 and "| stdin | - |" in r.output and "pass" in r.output


def test_stdin_exits_non_zero_when_a_check_fails():
    r = runner.invoke(
        app,
        ["score", "--stdin", "--prompts-dir", str(FIXTURES / "prompts")],
        input="## Market\nx\n",
    )
    assert r.exit_code == 1 and "FAIL" in r.output


def test_stdin_with_another_selector_is_an_error():
    r = runner.invoke(app, ["score", "--stdin", "--note", "n-v0"], input="x")
    assert r.exit_code == 2


def test_both_selectors_is_an_error():
    r = score("--note", "n-v0", "--deal", "deal-1")
    assert r.exit_code == 2


def test_zero_briefs_prints_no_briefs_and_exits_0():
    r = score("--deal", "no-such-deal")
    assert r.exit_code == 0 and r.output.strip() == "no briefs"


def test_unknown_note_prints_no_briefs():
    assert score("--note", "nope").output.strip() == "no briefs"


def test_note_without_prompt_line_is_brief_v0():
    r = score("--note", "n-v0")
    assert r.exit_code == 0
    assert "| n-v0 | deal-1 | 2026-09-20 | brief_v0 | 41 | pass | - |" in r.output


def test_n4_prints_rows_only_and_fails_on_the_bad_brief():
    r = score("--deal", "deal-1")
    assert r.exit_code == 1
    assert (
        "| n-bad | deal-1 | 2026-10-17 | brief_v1 | 30 | FAIL | missing: Competitors |" in r.output
    )
    assert "n = 4 (below 5: rows only, no percentages)" in r.output
    assert "%" not in r.output
    rows = [ln for ln in r.output.splitlines() if ln.startswith("| n-") and "| deal-1 |" in ln]
    assert [ln.split("|")[1].strip() for ln in rows] == ["n-bad", "n-v1b", "n-v1a", "n-v0"]


def test_note_from_before_any_version_went_live_is_not_a_failure(tmp_path):
    d = make_fixtures(tmp_path, 1)
    index = (d / "briefs.toml").read_text().replace("2026-10-15", "2026-08-01")
    (d / "briefs.toml").write_text(index)
    r = score("--deal", "deal-x", fixtures_dir=d)
    assert r.exit_code == 0
    assert "| g0 | deal-x | 2026-08-01 | - | - | no version live | - |" in r.output


def test_n5_prints_percentages(tmp_path):
    r = score("--deal", "deal-x", fixtures_dir=make_fixtures(tmp_path, 5))
    assert r.exit_code == 0
    assert "n = 5. Layer 1 pass: 5 of 5 checked (100%)" in r.output


def test_limit_caps_a_deals_briefs_newest_first():
    r = score("--deal", "deal-1", "--limit", "2")
    rows = [ln for ln in r.output.splitlines() if ln.startswith("| n-") and "| deal-1 |" in ln]
    assert [ln.split("|")[1].strip() for ln in rows] == ["n-bad", "n-v1b"]
    assert "n = 2" in r.output


def test_unreachable_links_are_shown_but_are_not_a_failure(monkeypatch):
    async def fake(urls, client):
        return {u: "could not fetch" for u in urls}

    monkeypatch.setattr("vc_evals.cli.check_links", fake)
    r = score("--note", "n-v1a", "--links")
    assert r.exit_code == 0
    assert "could not fetch 1 of 1 links" in r.output
