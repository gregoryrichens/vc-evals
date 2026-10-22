import asyncio
import sys
import tomllib
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Annotated

import httpx
import typer

from vc_evals.attio import AttioClient, Brief, load_api_key
from vc_evals.briefs import Score, score_brief, web_urls
from vc_evals.ic import Vote, check_vote
from vc_evals.layer2 import MEASURES, Result, run_all
from vc_evals.layer2.text import prepare
from vc_evals.links import COULD_NOT_FETCH, check_links

app = typer.Typer(no_args_is_help=True, add_completion=False)
MIN_N_FOR_PERCENT = 5


@app.callback()
def main() -> None:
    """Checks for a VC fund's LLM output."""


class FixtureSource:
    """The same two reads as AttioClient, from fixtures/briefs.toml."""

    def __init__(self, fixtures_dir: Path):
        index = tomllib.loads((fixtures_dir / "briefs.toml").read_text())
        self._briefs = [
            Brief(
                note_id=b["note_id"],
                deal_id=b["deal_id"],
                created_at=b["created_at"],
                title="Founder Call Brief — fixture",
                body=(fixtures_dir / b["file"]).read_text(),
            )
            for b in index["briefs"]
        ]

    async def get_brief(self, note_id: str) -> Brief | None:
        return next((b for b in self._briefs if b.note_id == note_id), None)

    async def list_briefs(self, deal_id: str, limit: int = 20) -> list[Brief]:
        found = [b for b in self._briefs if b.deal_id == deal_id]
        return sorted(found, key=lambda b: b.created_at, reverse=True)[:limit]

    async def aclose(self) -> None:
        pass


async def _fetch(source, note: str | None, deal: str | None, limit: int) -> list[Brief]:
    try:
        if note:
            brief = await source.get_brief(note)
            return [brief] if brief else []
        return await source.list_briefs(deal, limit)
    finally:
        await source.aclose()


def _result(score: Score) -> str:
    if score.layer1_pass is None:
        return "no version live"
    return "pass" if score.layer1_pass else "FAIL"


def _detail(score: Score) -> str:
    parts = []
    if score.missing:
        parts.append("missing: " + ", ".join(score.missing))
    if score.empty:
        parts.append("empty: " + ", ".join(score.empty))
    if score.over_limit:
        parts.append(f"{score.words} words, limit {score.max_words}")
    if score.has_table:
        parts.append("has a table")
    if score.bad_heading_levels:
        parts.append("heading level: " + ", ".join(score.bad_heading_levels))
    if score.inputs_problems:
        parts.append("Inputs: " + ", ".join(score.inputs_problems))
    if score.spec_found and score.prompt_line and score.prompt_line != score.prompt_version:
        parts.append(f"Prompt line says {score.prompt_line}")
    dead = [u for u, r in score.links.items() if r == COULD_NOT_FETCH]
    if dead:
        parts.append(f"could not fetch {len(dead)} of {len(score.links)} links")
    return "; ".join(parts) or "-"


async def _links_for(scored: list[tuple[Brief, Score]]) -> None:
    async with httpx.AsyncClient() as client:
        for brief, s in scored:
            s.links = await check_links(web_urls(brief.body), client)


def _echo_layer2(results: list[tuple[Brief, dict[str, Result]]]) -> None:
    """One table of every Layer 2 number."""
    columns = [(name, key) for name in MEASURES for key in results[0][1][name].metrics]
    typer.echo("")
    typer.echo("Layer 2, quality proxies (reported only, not pass or fail)")
    typer.echo("")
    typer.echo("| Note | " + " | ".join(key for _, key in columns) + " |")
    typer.echo("|---|" + "---|" * len(columns))
    for b, res in results:
        cells = " | ".join(str(res[name].metrics[key]) for name, key in columns)
        typer.echo(f"| {b.note_id} | {cells} |")


def _select(
    note: str | None, deal: str | None, stdin: bool, limit: int, fixtures: bool, fixtures_dir: Path
) -> list[Brief]:
    """The briefs chosen by exactly one of --note, --deal or --stdin."""
    if (note is not None) + (deal is not None) + stdin != 1:
        typer.echo("Error: give exactly one of --note, --deal or --stdin.", err=True)
        raise typer.Exit(2)
    if stdin:
        return [
            Brief(
                note_id="stdin",
                deal_id="-",
                created_at=datetime.now(UTC),
                title="stdin",
                body=sys.stdin.read(),
            )
        ]
    source = FixtureSource(fixtures_dir) if fixtures else AttioClient(load_api_key())
    return asyncio.run(_fetch(source, note, deal, limit))


@app.command()
def score(
    note: Annotated[str | None, typer.Option(help="Score one note by its note ID.")] = None,
    deal: Annotated[str | None, typer.Option(help="Score one deal's briefs, newest first.")] = None,
    limit: Annotated[int, typer.Option(help="Most briefs to score for a deal.", min=1)] = 20,
    stdin: Annotated[bool, typer.Option(help="Score one brief read from standard input.")] = False,
    fixtures: Annotated[bool, typer.Option(help="Read fixtures, not Attio.")] = False,
    fixtures_dir: Annotated[Path, typer.Option(help="Where the fixtures are.")] = Path("fixtures"),
    links: Annotated[bool, typer.Option(help="Also check that each Web: URL loads.")] = False,
    prompts_dir: Annotated[
        Path | None, typer.Option(help="Where the spec files are. Default: prompts/.")
    ] = None,
) -> None:
    """Score briefs. Give exactly one of --note, --deal or --stdin."""
    briefs = _select(note, deal, stdin, limit, fixtures, fixtures_dir)
    if prompts_dir is None:
        prompts_dir = fixtures_dir / "prompts" if fixtures else Path("prompts")
    if not briefs:
        typer.echo("no briefs")
        return

    scored = [(b, score_brief(b.body, b.created_at, prompts_dir)) for b in briefs]
    if links:
        asyncio.run(_links_for(scored))
    typer.echo("| Note | Deal | Created | Prompt | Words | Result | Detail |")
    typer.echo("|---|---|---|---|---|---|---|")
    for b, s in scored:
        typer.echo(
            f"| {b.note_id} | {b.deal_id} | {b.created_at:%Y-%m-%d} | {s.prompt_version or '-'} "
            f"| {s.words if s.words is not None else '-'} | {_result(s)} | {_detail(s)} |"
        )
    n = len(scored)
    typer.echo("")
    checked = [s for _, s in scored if s.layer1_pass is not None]
    passed = sum(1 for s in checked if s.layer1_pass)
    if n < MIN_N_FOR_PERCENT:
        typer.echo(f"n = {n} (below {MIN_N_FOR_PERCENT}: rows only, no percentages)")
    else:
        pct = f"{100 * passed / len(checked):.0f}%" if checked else "n/a"
        typer.echo(f"n = {n}. Layer 1 pass: {passed} of {len(checked)} checked ({pct})")
    _echo_layer2([(b, run_all(b.body)) for b in briefs])
    if any(s.layer1_pass is False for s in checked):
        raise typer.Exit(1)


MeasureName = Enum("MeasureName", {name: name for name in MEASURES}, type=str)


@app.command()
def measure(
    name: Annotated[MeasureName, typer.Argument(help="Which Layer 2 measure to run.")],
    note: Annotated[str | None, typer.Option(help="Measure one note by its note ID.")] = None,
    deal: Annotated[
        str | None, typer.Option(help="Measure one deal's briefs, newest first.")
    ] = None,
    limit: Annotated[int, typer.Option(help="Most briefs to measure for a deal.", min=1)] = 20,
    stdin: Annotated[
        bool, typer.Option(help="Measure one brief read from standard input.")
    ] = False,
    fixtures: Annotated[bool, typer.Option(help="Read fixtures, not Attio.")] = False,
    fixtures_dir: Annotated[Path, typer.Option(help="Where the fixtures are.")] = Path("fixtures"),
) -> None:
    """Run one Layer 2 measure on briefs. Give exactly one of --note, --deal or --stdin."""
    briefs = _select(note, deal, stdin, limit, fixtures, fixtures_dir)
    if not briefs:
        typer.echo("no briefs")
        return
    chosen = MEASURES[name.value]
    typer.echo(f"{chosen.NAME}: {chosen.DESCRIPTION}")
    for b in briefs:
        result = chosen.measure(prepare(b.body))
        typer.echo(f"\n{b.note_id} ({b.created_at:%Y-%m-%d})")
        for key, value in result.metrics.items():
            typer.echo(f"- {key}: {value}")
        for line in result.details:
            typer.echo(f"  - {line}")
    typer.echo(f"\nn = {len(briefs)}")


def _vote_result(vote: Vote) -> str:
    if vote.passed is None:
        return "no version live"
    return "pass" if vote.passed else "FAIL"


@app.command()
def ic(
    stdin: Annotated[
        bool, typer.Option(help="Check one AI IC vote (JSON payload) read from standard input.")
    ] = False,
    prompts_dir: Annotated[
        Path, typer.Option(help="Where the spec files are. Default: prompts/.")
    ] = Path("prompts"),
) -> None:
    """Check an AI IC vote. Give --stdin."""
    if not stdin:
        typer.echo("Error: give --stdin.", err=True)
        raise typer.Exit(2)
    vote = check_vote(sys.stdin.read(), datetime.now(UTC), prompts_dir)
    detail = "; ".join(vote.problems).replace("|", "/").replace("\n", " ") or "-"
    typer.echo("| Company | Prompt | Words | Verdict | Conviction | Result | Detail |")
    typer.echo("|---|---|---|---|---|---|---|")
    typer.echo(
        f"| {(vote.company or '-').replace('|', '/')} | {vote.version or '-'} "
        f"| {vote.words if vote.words is not None else '-'} | {vote.verdict or '-'} "
        f"| {vote.conviction or '-'} | {_vote_result(vote)} | {detail} |"
    )
    typer.echo("")
    typer.echo(f"n = 1 (below {MIN_N_FOR_PERCENT}: rows only, no percentages)")
    if vote.passed is False:
        raise typer.Exit(1)
