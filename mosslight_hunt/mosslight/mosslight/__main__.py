"""Command line interface for making, growing, and viewing gardens."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import webbrowser

from .engine import create, step, summary
from .model import load, save
from .render import render_svg
from .server import make_server
from .commands import execute, command_catalog
from .analysis import report, forecast, compare, recommendations
from .charts import render_map, render_history
from .exchange import export_csv, export_markdown, blueprint, transform_blueprint, replay
from .catalog import field_guide


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mosslight", description="Tend a tiny offline world under glass.")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", help="Create a garden save file")
    new.add_argument("path")
    new.add_argument("--seed", type=int, default=7)
    new.add_argument("--width", type=int, default=16)
    new.add_argument("--height", type=int, default=11)
    grow = sub.add_parser("grow", help="Advance an existing garden")
    grow.add_argument("path")
    grow.add_argument("--days", type=int, default=1)
    render = sub.add_parser("render", help="Export an illustrated SVG")
    render.add_argument("path")
    render.add_argument("--output", "-o", required=True)
    inspect = sub.add_parser("inspect", help="Show a garden summary")
    inspect.add_argument("path")
    serve = sub.add_parser("serve", help="Run the local browser studio")
    serve.add_argument("--file", help="Load and autosave a garden at this path")
    serve.add_argument("--seed", type=int, default=7)
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true", help="Open browser automatically")
    render.add_argument("--layer", default="art")
    command = sub.add_parser("command", help="Apply one transactional JSON command")
    command.add_argument("path")
    command.add_argument("json", help='JSON such as {"op":"harvest","args":{"x":0,"y":0}}')
    script = sub.add_parser("replay", help="Apply a JSON command array atomically")
    script.add_argument("path")
    script.add_argument("script")
    script.add_argument("--output", "-o")
    guide = sub.add_parser("guide", help="Show field guide and command signatures")
    report_parser = sub.add_parser("report", help="Full census, beds, alerts and tasks")
    report_parser.add_argument("path")
    prediction = sub.add_parser("forecast", help="Simulate without changing the garden")
    prediction.add_argument("path")
    prediction.add_argument("--days", type=int, default=7)
    prediction.add_argument("--every", type=int, default=1)
    prediction.add_argument("--output", "-o", help="Save the predicted garden separately")
    difference = sub.add_parser("compare", help="Compare equal-size gardens")
    difference.add_argument("path")
    difference.add_argument("other")
    recommend = sub.add_parser("recommend", help="Find suitable planting locations")
    recommend.add_argument("path")
    recommend.add_argument("species")
    recommend.add_argument("--limit", type=int, default=10)
    export = sub.add_parser("export", help="Export survey, notebook, or history chart")
    export.add_argument("path")
    export.add_argument("format", choices=("csv", "markdown", "history"))
    export.add_argument("--output", "-o", required=True)
    export.add_argument("--metric", default="moisture")
    pattern = sub.add_parser("blueprint", help="Save a reusable rectangular garden pattern")
    pattern.add_argument("path")
    pattern.add_argument("--rect", nargs=4, type=int, required=True, metavar=("X1", "Y1", "X2", "Y2"))
    pattern.add_argument("--turns", type=int, default=0)
    pattern.add_argument("--mirror", action="store_true")
    pattern.add_argument("--output", "-o", required=True)
    weather = sub.add_parser("almanac", help="Seeded weather and calendar")
    weather.add_argument("path")
    weather.add_argument("--days", type=int, default=12)
    weather.add_argument("--calendar", action="store_true")
    trial_parser = sub.add_parser("experiment", help="Compare a control with treatment scripts")
    trial_parser.add_argument("path")
    trial_parser.add_argument("treatments", help="JSON array of named treatments and offset events")
    trial_parser.add_argument("--days", type=int, default=7)
    trial_parser.add_argument("--every", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            world = create(args.seed, args.width, args.height)
            save(world, args.path)
            print(f"Created {args.path}")
        elif args.command == "grow":
            world = load(args.path)
            step(world, args.days)
            save(world, args.path)
            print(json.dumps(summary(world), indent=2))
        elif args.command == "render":
            world = load(args.path)
            Path(args.output).write_text(render_map(world, args.layer) + "\n", encoding="utf-8")
            print(f"Rendered {args.output}")
        elif args.command == "inspect":
            print(json.dumps(summary(load(args.path)), indent=2))
        elif args.command == "almanac":
            from .weather import almanac, calendar
            function = calendar if args.calendar else almanac
            print(json.dumps(function(load(args.path), args.days), indent=2))
        elif args.command == "experiment":
            from .experiments import experiment
            treatments = json.loads(Path(args.treatments).read_text(encoding="utf-8"))
            print(json.dumps(experiment(load(args.path), args.days, treatments, args.every), indent=2))
        elif args.command == "command":
            world = load(args.path)
            result = execute(world, json.loads(args.json))
            save(world, args.path)
            print(json.dumps({"result": result, "summary": summary(world)}, indent=2))
        elif args.command == "replay":
            world, results = replay(load(args.path), json.loads(Path(args.script).read_text(encoding="utf-8")))
            save(world, args.output or args.path)
            print(json.dumps({"results": results, "summary": summary(world)}, indent=2))
        elif args.command == "guide":
            print(json.dumps({**field_guide(), "commands": command_catalog()}, indent=2))
        elif args.command == "report":
            print(json.dumps(report(load(args.path)), indent=2))
        elif args.command == "forecast":
            result = forecast(load(args.path), args.days, args.every)
            predicted = result.pop("world")
            if args.output:
                if args.output == args.path:
                    raise ValueError("Forecast output must differ from the source garden")
                from .model import World
                save(World.from_dict(predicted), args.output)
            print(json.dumps(result, indent=2))
        elif args.command == "compare":
            print(json.dumps(compare(load(args.path), load(args.other)), indent=2))
        elif args.command == "recommend":
            print(json.dumps(recommendations(load(args.path), args.species, args.limit), indent=2))
        elif args.command == "export":
            world = load(args.path)
            content = export_csv(world) if args.format == "csv" else export_markdown(world) if args.format == "markdown" else render_history(world, args.metric)
            Path(args.output).write_text(content, encoding="utf-8")
            print(f"Exported {args.output}")
        elif args.command == "blueprint":
            data = transform_blueprint(blueprint(load(args.path), *args.rect), args.turns, args.mirror)
            Path(args.output).write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
            print(f"Exported {args.output}")
        else:
            if not 0 <= args.port <= 65535:
                raise ValueError("Port must be 0–65535")
            world = load(args.file) if args.file and Path(args.file).exists() else create(args.seed)
            server = make_server(world, args.port, args.file)
            server.persist()
            url = f"http://127.0.0.1:{server.server_port}/"
            print(f"Mosslight is growing at {url} (Ctrl+C to stop)", flush=True)
            if args.open:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("\nGoodnight, garden.")
            finally:
                server.server_close()
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"mosslight: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
