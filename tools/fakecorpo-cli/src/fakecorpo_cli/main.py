import typer

from .clock import clock_app

app = typer.Typer(
    no_args_is_help=True,
    help="FakeCorpo admin CLI — control the simulated company.",
)
app.add_typer(clock_app, name="clock", help="Inspect and control the simulation clock.")


if __name__ == "__main__":
    app()
