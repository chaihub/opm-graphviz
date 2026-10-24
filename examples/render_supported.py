"""Render the programmatic coverage model, without an OPL parser.

Run from the repository root: python -m examples.render_supported
Optional positional argument: output SVG path (default: build/supported.svg).
"""

import argparse
from pathlib import Path

from examples.supported_model import build_model
from opm_graphviz.render import render_svg, to_dot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path("build/supported.svg"))
    args = parser.parse_args()
    if args.output.suffix.lower() != ".svg":
        parser.error("output must have the .svg extension")
    model = build_model()
    svg = render_svg(model, args.output)
    dot = svg.with_suffix(".dot")
    dot.write_text(to_dot(model).source, encoding="utf-8")
    print(f"Rendered {svg} and {dot}")


if __name__ == "__main__":
    main()
