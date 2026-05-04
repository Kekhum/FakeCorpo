import os

import httpx
import typer
from rich.console import Console
from rich.table import Table

clock_app = typer.Typer(no_args_is_help=True)
console = Console()


def _api_url() -> str:
    return os.environ.get("FAKECORPO_API_URL", "http://localhost:8000")


def _get(path: str) -> dict:
    r = httpx.get(f"{_api_url()}{path}", timeout=10.0)
    r.raise_for_status()
    return r.json()


def _post(path: str, json: dict | None = None) -> dict:
    r = httpx.post(f"{_api_url()}{path}", json=json or {}, timeout=10.0)
    r.raise_for_status()
    return r.json()


def _render(state: dict) -> None:
    table = Table(title="Clock state", show_header=False, box=None)
    table.add_column("field", style="cyan")
    table.add_column("value")
    table.add_row("sim_time",     state["sim_time"])
    table.add_row("speed_ratio",  f'{state["speed_ratio"]} (1 real sec = {state["speed_ratio"]} sim sec)')
    table.add_row("paused",       "yes" if state["paused"] else "no")
    table.add_row("updated_at",   state["updated_at"])
    console.print(table)


@clock_app.command()
def status() -> None:
    """Show current clock state."""
    _render(_get("/clock/state"))


@clock_app.command()
def pause() -> None:
    """Pause the simulation. Heartbeat ticks continue with paused=true."""
    _render(_post("/clock/pause"))


@clock_app.command()
def resume() -> None:
    """Resume the simulation."""
    _render(_post("/clock/resume"))


@clock_app.command()
def speed(
    ratio: int = typer.Argument(
        ...,
        help="Sim seconds per real second. 288 = 1 sim day per 5 real min. Min 1.",
    ),
) -> None:
    """Set the simulation speed."""
    if ratio < 1:
        raise typer.BadParameter("ratio must be >= 1")
    _render(_post("/clock/speed", {"speed_ratio": ratio}))


@clock_app.command()
def seek(
    sim_time: str = typer.Argument(
        ...,
        help='ISO 8601 datetime, e.g. "2024-12-24T08:00:00+00:00"',
    ),
) -> None:
    """Jump the simulated clock to a specific point in time."""
    _render(_post("/clock/seek", {"sim_time": sim_time}))
