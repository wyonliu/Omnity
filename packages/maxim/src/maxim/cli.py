"""CLI entry point — `maxim run village.yaml`."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from maxim.config import load_scenario
from maxim.engine import Simulation
from maxim.models import World

console = Console()


@click.group()
def main():
    """Maxim — Multi-Agent Society Simulator with economics."""
    pass


@main.command()
@click.argument("scenario", type=click.Path(exists=True))
@click.option("--no-llm", is_flag=True, help="Rules-only mode (no LLM calls, fast)")
@click.option("--quiet", is_flag=True, help="Minimal output")
@click.option("--export", type=click.Path(), help="Export chronicle to JSON file")
@click.option("--verbose", is_flag=True, help="Show debug logs")
def run(scenario: str, no_llm: bool, quiet: bool, export: str, verbose: bool):
    """Run a civilization simulation."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    console.print(f"\n[bold cyan]Maxim[/] — Loading [yellow]{scenario}[/]...\n")

    world, ticks = load_scenario(scenario)
    sim = Simulation(world, use_llm=not no_llm)

    console.print(f"  World: [bold]{world.name}[/]")
    console.print(f"  Agents: {world.population}")
    console.print(f"  Duration: {ticks // 4} years ({ticks} seasons)")
    console.print(f"  LLM: {'[green]DeepSeek[/]' if not no_llm else '[yellow]Rules only[/]'}")
    console.print()

    # Show initial agents
    if not quiet:
        _print_agents(world)

    start = time.time()
    last_year = world.year

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Simulating...", total=ticks)

        def on_tick(w: World, tick: int, narration: str):
            nonlocal last_year
            progress.advance(task)
            progress.update(task, description=f"[cyan]{w.time_str()}[/] pop={w.population}")

            # Print yearly summary
            if w.year != last_year and not quiet:
                last_year = w.year
                if w.year % 10 == 0:
                    _print_decade_summary(w, narration)

        sim.on_tick(on_tick)
        chronicle = sim.run(ticks)

    elapsed = time.time() - start

    # Final summary
    console.print(f"\n[bold green]Simulation complete![/]")
    console.print(f"  Time: {elapsed:.1f}s")
    console.print(f"  Final year: {world.year}")
    console.print(f"  Final population: {world.population}")
    console.print(f"  Total events: {len(chronicle.events)}")
    console.print()

    # Final agents
    if not quiet:
        _print_agents(world)

    # Economy summary
    _print_economy(world)

    # Milestones
    console.print(f"\n[bold yellow]Milestones[/]")
    for m in chronicle.milestones:
        console.print(f"  Year {m.year}: {m.description}")

    if not chronicle.milestones:
        console.print("  (none)")

    # Notable events (last 10)
    notable = [e for e in chronicle.events if e.type in ("marriage", "death", "birth", "conflict", "milestone")]
    if notable:
        console.print(f"\n[bold yellow]Notable Events (last 20)[/]")
        for e in notable[-20:]:
            console.print(f"  Y{e.year} [{e.type}] {e.description}")

    # Export
    if export:
        chronicle.export_json(export)
        console.print(f"\n[dim]Chronicle exported to {export}[/]")

    console.print()


@main.command()
@click.argument("chronicle_json", type=click.Path(exists=True), required=False)
@click.option("--port", default=8765, help="HTTP server port")
def dashboard(chronicle_json: str, port: int):
    """Open the civilization dashboard in your browser."""
    import http.server
    import threading
    import webbrowser
    import json
    import os

    # Find dashboard.html
    pkg_dir = Path(__file__).resolve().parent.parent.parent
    html_path = pkg_dir / "dashboard.html"
    if not html_path.exists():
        console.print(f"[red]dashboard.html not found at {html_path}[/]")
        return

    html_content = html_path.read_text()

    # If chronicle JSON provided, inline it so it auto-loads
    if chronicle_json:
        json_data = Path(chronicle_json).read_text()
        inject = f"""<script>
        window.addEventListener('load', () => {{
          DATA = {json_data};
          initDashboard();
        }});
        </script></body>"""
        html_content = html_content.replace('</body>', inject)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(html_content.encode())
        def log_message(self, *args):
            pass  # Silence logs

    server = http.server.HTTPServer(('localhost', port), Handler)
    url = f'http://localhost:{port}'
    console.print(f"\n[bold cyan]Maxim Dashboard[/] serving at [yellow]{url}[/]")
    console.print("[dim]Press Ctrl+C to stop[/]\n")

    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped.[/]")
        server.shutdown()


def _print_agents(world: World):
    table = Table(title=f"Citizens of {world.name} — Year {world.year}")
    table.add_column("Name", style="cyan")
    table.add_column("Age", justify="right")
    table.add_column("Job")
    table.add_column("Wealth", justify="right", style="green")
    table.add_column("Needs (S/Sa/B/E/A)", justify="center")
    table.add_column("Status")

    for a in sorted(world.agents.values(), key=lambda x: (-x.alive, x.name)):
        if not a.alive:
            table.add_row(a.name, str(a.age), a.occupation, "-", "-", "[red]deceased[/]")
            continue
        needs = f"{a.needs.survival:.0f}/{a.needs.safety:.0f}/{a.needs.belonging:.0f}/{a.needs.esteem:.0f}/{a.needs.actualization:.0f}"
        spouse_str = ""
        if a.spouse:
            s = world.agents.get(a.spouse)
            spouse_str = f" married:{s.name if s else '?'}"
        status = f"{'[green]ok[/]' if a.needs.survival > 20 else '[red]struggling[/]'}{spouse_str}"
        table.add_row(a.name, str(a.age), a.occupation, f"{a.wealth:.0f}", needs, status)

    console.print(table)
    console.print()


def _print_economy(world: World):
    console.print(f"\n[bold yellow]Economy[/]")
    e = world.economy
    console.print(f"  GDP (last season): {e.gdp:.0f}")
    console.print(f"  Avg wealth: {e.avg_wealth:.0f}")
    console.print(f"  Gini: {e.gini:.3f}")
    console.print(f"  Unemployment: {e.unemployment_rate:.0%}")
    console.print(f"  Treasury: {world.treasury:.0f}")
    if e.prices:
        prices_str = ", ".join(f"{k}: {v:.1f}" for k, v in e.prices.items())
        console.print(f"  Prices: {prices_str}")


def _print_decade_summary(world: World, narration: str):
    pop = world.population
    gini = world.economy.gini
    avg_w = world.economy.avg_wealth
    console.print(
        f"\n  [dim]── Year {world.year} ── pop={pop}, avg_wealth={avg_w:.0f}, gini={gini:.2f}[/]"
    )
    if narration:
        console.print(f"  [italic]{narration}[/]")
