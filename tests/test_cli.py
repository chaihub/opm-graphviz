"""CLI integration tests using actual subprocess exit codes and output files."""

from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import graphviz

from opm_graphviz.cli import main

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.input = self.directory / "input.opl"
        self.output = self.directory / "diagram.svg"
        self.input.write_text('object "Item".\nprocess "Making".\n"Making" yields "Item".\n')

    def run_cli(self, *args, env=None):
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        if env:
            environment.update(env)
        return subprocess.run([sys.executable, "-m", "opm_graphviz", *map(str, args)],
                              cwd=ROOT, env=environment, capture_output=True, text=True)

    @unittest.skipUnless(shutil.which("dot"), "Graphviz dot executable is required")
    def test_legend_default_and_opt_out_in_both_outputs(self):
        for flags, expected in (((), True), (("--no-legend",), False)):
            with self.subTest(flags=flags):
                result = self.run_cli(self.input, "-o", self.output, "--dot", *flags)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual("data:image/png;base64," in self.output.read_text(), expected)
                self.assertEqual("opm-legend" in self.output.with_suffix(".dot").read_text(), expected)

    def test_help_and_usage_errors(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--dot", result.stdout)
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertEqual(self.run_cli(self.input, "--unknown").returncode, 2)
        result = self.run_cli(self.input, "-o", self.directory / "image.png")
        self.assertEqual(result.returncode, 2)
        self.assertIn(".svg extension", result.stderr)

    @unittest.skipUnless(shutil.which("dot"), "Graphviz dot executable is required")
    def test_supported_fixture_svg_and_optional_dot(self):
        result = self.run_cli(ROOT / "examples/supported.opl", "-o", self.output, "--dot")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        root = ET.parse(self.output).getroot()
        groups = root.findall(".//{http://www.w3.org/2000/svg}g")
        self.assertEqual(sum("opm-link" in g.get("class", "").split() for g in groups), 19)
        self.assertIn("digraph opm", self.output.with_suffix(".dot").read_text())
        self.assertIn(f"Wrote {self.output}", result.stdout)

    @unittest.skipUnless(shutil.which("dot"), "Graphviz dot executable is required")
    def test_default_svg_only_and_nested_destination(self):
        result = self.run_cli(self.input)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.input.with_suffix(".svg").exists())
        self.assertFalse(self.input.with_suffix(".dot").exists())
        output = self.directory / "new" / "nested" / "diagram.svg"
        result = self.run_cli(self.input, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.exists())

    @unittest.skipUnless(shutil.which("dot"), "Graphviz dot executable is required")
    def test_unsupported_statement_renders_with_incomplete_summary(self):
        with self.input.open("a") as stream:
            stream.write('"Making" changes "Item" from "old" to "new".\n')
        result = self.run_cli(self.input, "-o", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"{self.input}:4: WARNING W001:", result.stderr)
        self.assertIn("Diagram is incomplete: 1", result.stderr)
        root = ET.parse(self.output).getroot()
        groups = root.findall(".//{http://www.w3.org/2000/svg}g")
        links = [g for g in groups if "opm-link" in g.get("class", "").split()]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].get("data-kind"), "result")
        self.assertFalse(any("opm-state" in g.get("class", "").split() for g in groups))

    @unittest.skipUnless(shutil.which("dot"), "Graphviz dot executable is required")
    def test_duplicate_warning_does_not_report_incomplete(self):
        with self.input.open("a") as stream:
            stream.write('"Making" yields "Item".\n')
        result = self.run_cli(self.input, "-o", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARNING W002", result.stderr)
        self.assertNotIn("incomplete", result.stderr)
        root = ET.parse(self.output).getroot()
        groups = root.findall(".//{http://www.w3.org/2000/svg}g")
        self.assertEqual(sum("opm-link" in g.get("class", "").split() for g in groups), 1)

    def test_parse_errors_do_not_replace_or_create_outputs(self):
        self.output.write_text("previous SVG")
        dot = self.output.with_suffix(".dot")
        dot.write_text("previous DOT")
        result = self.run_cli(ROOT / "examples/diagnostics.opl", "-o", self.output, "--dot")
        self.assertEqual(result.returncode, 1)
        self.assertIn("diagnostics.opl:8: ERROR E003", result.stderr)
        self.assertIn("Cannot render: 6 error(s)", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.output.read_text(), "previous SVG")
        self.assertEqual(dot.read_text(), "previous DOT")
        fresh = self.directory / "uncreated" / "diagram.svg"
        self.run_cli(ROOT / "examples/diagnostics.opl", "-o", fresh)
        self.assertFalse(fresh.parent.exists())

    def test_unreadable_and_non_utf8_input(self):
        result = self.run_cli(self.directory / "missing.opl", "-o", self.output)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.input.write_bytes(b"\xff")
        result = self.run_cli(self.input, "-o", self.output)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.output.exists())
        result = self.run_cli(".")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)

    def test_input_output_aliases_are_rejected(self):
        original = self.input.read_text()
        for alias in ("symlink", "hardlink"):
            with self.subTest(alias=alias):
                output = self.directory / f"{alias}.svg"
                if alias == "symlink":
                    output.symlink_to(self.input)
                else:
                    os.link(self.input, output)
                result = self.run_cli(self.input, "-o", output)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.input.read_text(), original)
        # Optional DOT cannot overwrite the input, even with a non-OPL suffix.
        source = self.directory / "input.dot"
        source.write_text(original)
        result = self.run_cli(source, "-o", source.with_suffix(".svg"), "--dot")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(source.read_text(), original)

    def test_svg_dot_aliases_are_rejected(self):
        self.output.write_text("previous output")
        self.output.with_suffix(".dot").symlink_to(self.output)
        result = self.run_cli(self.input, "-o", self.output, "--dot")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.output.read_text(), "previous output")

    def test_missing_dot_preserves_outputs(self):
        self.output.write_text("previous SVG")
        result = self.run_cli(self.input, "-o", self.output, "--dot", env={"PATH": ""})
        self.assertEqual(result.returncode, 1)
        self.assertIn("Graphviz 'dot' was not found", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.output.read_text(), "previous SVG")
        self.assertFalse(self.output.with_suffix(".dot").exists())
        self.assertEqual(list(self.directory.glob(".opm-*")), [])

    def test_render_failure_is_reported_without_replacing_output(self):
        self.output.write_text("previous SVG")
        error = graphviz.CalledProcessError(1, ["dot"])
        stderr = io.StringIO()
        with patch("opm_graphviz.cli.render_svg", side_effect=error):
            with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                code = main([str(self.input), "-o", str(self.output)])
        self.assertEqual(code, 1)
        self.assertIn("Graphviz rendering failed", stderr.getvalue())
        self.assertEqual(self.output.read_text(), "previous SVG")

    def test_output_directory_is_rejected_before_replacement(self):
        self.output.write_text("previous SVG")
        self.output.with_suffix(".dot").mkdir()
        result = self.run_cli(self.input, "-o", self.output, "--dot")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.output.read_text(), "previous SVG")


if __name__ == "__main__":
    unittest.main()
