# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""CLI for the governed-reasoning POC."""

import shutil
import subprocess  # nosec B404 - used only to invoke the local `dot` binary in --render-svg path; arguments are list-form, no shell, binary resolved via shutil.which
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel

from .agent import ReasoningAgent
from .adversary import Adversary
from .bedrock_client import BedrockClient
from .memo import MemoGenerator
from .persistence import load_case, load_record, save_memo, save_record
from .visualize import to_dot, to_html, to_mermaid_headline


app = typer.Typer(help="Governed reasoning POC: schema-bounded records with adversarial validation.")
console = Console()


@app.command()
def run(
    case_path: Path = typer.Argument(..., help="Path to case JSON file"),
    out_dir: Path = typer.Option(Path("records"), help="Output directory for record + memo"),
):
    """Run the full agent → adversary → memo loop on a case."""
    case = load_case(case_path)
    case_id = case["case_id"]

    client = BedrockClient()
    agent = ReasoningAgent(client)
    adversary = Adversary(client)
    memo_gen = MemoGenerator(client)

    console.print(Panel(f"[bold]Reasoning agent[/bold] producing initial record for case [cyan]{case_id}[/cyan]", expand=False))
    record = agent.run(case)
    console.print(f"  → {len(record.nodes)} nodes")

    console.print(Panel(f"[bold]Adversary[/bold] attacking record", expand=False))
    record = adversary.run_validation_round(record, case_body=case["case_body"], agent=agent)
    if record.adversarial_rounds:
        n_challenges = len(record.adversarial_rounds[-1].challenges)
        console.print(f"  → {n_challenges} challenge(s); record extended to {len(record.nodes)} nodes")
    else:
        console.print("  → no substantive challenges")

    console.print(Panel("[bold]Memo generator[/bold] rendering view", expand=False))
    memo = memo_gen.render(record)

    record_path = out_dir / f"{case_id}.json"
    memo_path = out_dir / f"{case_id}.md"
    save_record(record, record_path)
    save_memo(memo, memo_path)
    console.print(f"\n[green]Wrote[/green] {record_path}")
    console.print(f"[green]Wrote[/green] {memo_path}")


@app.command()
def inspect(record_path: Path = typer.Argument(..., help="Path to record JSON")):
    """Pretty-print the structure of an existing record."""
    record = load_record(record_path)
    console.print(f"[bold]Case:[/bold] {record.case_id}")
    console.print(f"[bold]Nodes:[/bold] {len(record.nodes)}")
    by_kind: dict[str, list[str]] = {}
    for nid, node in record.nodes.items():
        by_kind.setdefault(node.kind, []).append(nid)
    for kind, ids in sorted(by_kind.items()):
        console.print(f"  [cyan]{kind}[/cyan]: {len(ids)} ({', '.join(ids)})")
    if record.adversarial_rounds:
        console.print(f"[bold]Adversarial rounds:[/bold] {len(record.adversarial_rounds)}")


@app.command()
def visualize(
    record_path: Path = typer.Argument(..., help="Path to record JSON"),
    format: str = typer.Option("both", "--format", help="dot | mermaid | html | both | all"),
    out_dir: Path = typer.Option(None, "--out-dir", help="Output directory (default: same as record)"),
    render_svg: bool = typer.Option(False, "--render-svg", help="Also render the .dot to .svg via the dot CLI"),
):
    """Render a reasoning record as DOT, Mermaid, and/or interactive HTML.

    Format choices:
      - dot: Graphviz DOT (full record)
      - mermaid: Mermaid headline view (conclusions + supports only)
      - html: Self-contained interactive viewer (Cytoscape.js)
      - both: dot + mermaid (the default; preserves prior behavior)
      - all: dot + mermaid + html
    """
    if format not in ("dot", "mermaid", "html", "both", "all"):
        raise typer.BadParameter("--format must be one of: dot, mermaid, html, both, all")

    record = load_record(record_path)
    target_dir = out_dir if out_dir is not None else record_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = record_path.stem

    wrote: list[Path] = []
    do_dot = format in ("dot", "both", "all")
    do_mermaid = format in ("mermaid", "both", "all")
    do_html = format in ("html", "all")

    if do_dot:
        dot_path = target_dir / f"{stem}.dot"
        dot_path.write_text(to_dot(record))
        wrote.append(dot_path)

        if render_svg:
            dot_bin = shutil.which("dot")
            if dot_bin is None:
                console.print("[yellow]dot not on PATH; skipping SVG render. Install with `brew install graphviz`.[/yellow]")
            else:
                svg_path = target_dir / f"{stem}.svg"
                # nosec B603 dangerous-subprocess-use-audit
                # Safe: list-form args (no shell expansion), no shell=True,
                # dot_bin from shutil.which() (PATH-resolved, not user input),
                # paths are user's local CLI args validated by typer.
                result = subprocess.run(  # noqa: S603  # nosec B603  # nosemgrep: dangerous-subprocess-use-audit
                    [dot_bin, "-Tsvg", str(dot_path), "-o", str(svg_path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    console.print(f"[red]dot failed:[/red] {result.stderr.strip()}")
                else:
                    wrote.append(svg_path)

    if do_mermaid:
        mmd_path = target_dir / f"{stem}.headline.mmd"
        mmd_path.write_text(to_mermaid_headline(record))
        wrote.append(mmd_path)

    if do_html:
        html_path = target_dir / f"{stem}.html"
        html_path.write_text(to_html(record))
        wrote.append(html_path)

    console.print(f"[bold]Case:[/bold] {record.case_id}")
    console.print(f"[bold]Nodes:[/bold] {len(record.nodes)}")
    for path in wrote:
        console.print(f"[green]Wrote[/green] {path}")


if __name__ == "__main__":
    app()
