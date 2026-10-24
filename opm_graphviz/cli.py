"""Command-line OPL-to-SVG conversion."""

import argparse
from pathlib import Path
import sys
import tempfile

import graphviz

from .model import Model
from .parser import parse_file
from .render import render_svg, to_dot


def _same_file(first: Path, second: Path) -> bool:
    """Include normalized paths, symlinks, and existing hard links."""
    return (first.resolve() == second.resolve()
            or (first.exists() and second.exists() and first.samefile(second)))


def _write_outputs(model: Model, output: Path, include_dot: bool, *, include_legend: bool = True) -> list[Path]:
    destinations = [output]
    if include_dot:
        destinations.append(output.with_suffix(".dot"))
    for path in destinations:
        if path.is_dir():
            raise IsADirectoryError(f"Output destination is a directory: {path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Prepare both files before replacing either destination. Each replacement
    # is atomic; this is not a transaction across the two output files.
    with tempfile.TemporaryDirectory(prefix=".opm-", dir=output.parent) as directory:
        staged_svg = Path(directory) / "diagram.svg"
        render_svg(model, staged_svg, include_legend=include_legend)
        staged = [staged_svg]
        if include_dot:
            staged_dot = Path(directory) / "diagram.dot"
            staged_dot.write_text(to_dot(model, include_legend=include_legend).source, encoding="utf-8")
            staged.append(staged_dot)
        for source, destination in zip(staged, destinations):
            source.replace(destination)
    return destinations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="opm-graphviz",
        description="Parse OPL input and render an SVG using Graphviz.",
    )
    parser.add_argument("input", type=Path, help="UTF-8 OPL input file")
    parser.add_argument("-o", "--output", type=Path, metavar="SVG",
                        help="output SVG path (default: input path with .svg suffix)")
    parser.add_argument("--dot", action="store_true",
                        help="also write DOT beside the SVG, with a .dot suffix")
    parser.add_argument("--no-legend", action="store_true",
                        help="omit the legend from SVG and DOT output")
    args = parser.parse_args(argv)
    try:
        output = args.output if args.output is not None else args.input.with_suffix(".svg")
        if output.suffix.lower() != ".svg":
            parser.error("output must have the .svg extension")
        destinations = [output, output.with_suffix(".dot")] if args.dot else [output]
        if any(_same_file(args.input, path) for path in destinations):
            parser.error("an output path refers to the input file; refusing to overwrite it")
        if args.dot and _same_file(*destinations):
            parser.error("SVG and DOT destinations must refer to different files")
        result = parse_file(args.input)
        for diagnostic in result.diagnostics:
            print(diagnostic, file=sys.stderr)
        if result.diagnostics:
            print(result.summary, file=sys.stderr)
        if result.has_errors:
            return 1
        paths = _write_outputs(result.require_model(), output, args.dot,
                               include_legend=not args.no_legend)
    except graphviz.ExecutableNotFound:
        print("opm-graphviz: error: Graphviz 'dot' was not found. "
              "Install the system Graphviz package and ensure dot is on PATH.", file=sys.stderr)
        return 1
    except graphviz.CalledProcessError as exc:
        print(f"opm-graphviz: error: Graphviz rendering failed (exit {exc.returncode}).", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"opm-graphviz: error: {exc}", file=sys.stderr)
        return 1

    for path in paths:
        print(f"Wrote {path}")
    return 0
