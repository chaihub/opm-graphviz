"""Acceptance tests for syntax.md and semantic validation of parsed input."""

from pathlib import Path
import shutil
import tempfile
import unittest

from examples.supported_model import build_model
from opm_graphviz.diagnostics import Severity
from opm_graphviz.model import Affiliation, EntityKind, Essence, LinkKind
from opm_graphviz.parser import parse_file, parse_text

ROOT = Path(__file__).resolve().parents[1]


class ParserTests(unittest.TestCase):
    def codes(self, text):
        return [d.code for d in parse_text(text).diagnostics]

    def test_supported_fixture_matches_hand_built_model(self):
        text = (ROOT / "examples/supported.opl").read_text()
        result = parse_text(text, "examples/supported.opl")
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(result.require_model(), build_model())
        self.assertFalse(result.has_errors)
        self.assertFalse(result.incomplete)

    def test_diagnostic_fixture_exact_codes_and_lines(self):
        result = parse_file(ROOT / "examples/diagnostics.opl")
        self.assertEqual([(d.source.line, d.code) for d in result.diagnostics], [
            (6, "W001"), (7, "W001"), (8, "E003"), (9, "E004"),
            (10, "E004"), (13, "E002"), (14, "E001"), (15, "E006"), (17, "W002"),
        ])
        self.assertTrue(result.has_errors)
        self.assertIsNone(result.model)
        with self.assertRaisesRegex(ValueError, "Cannot render"):
            result.require_model()
        self.assertTrue(all(d.severity is (Severity.ERROR if d.code.startswith("E") else Severity.WARNING)
                            for d in result.diagnostics))

    def test_warning_only_input_retains_subset_and_reports_incomplete(self):
        text = '\n'.join((ROOT / "examples/diagnostics.opl").read_text().splitlines()[:7])
        result = parse_text(text, "partial.opl")
        self.assertEqual(len(result.require_model().entities), 4)
        self.assertEqual(result.model.links, ())
        self.assertEqual(result.skipped_statements, 2)
        self.assertIn("Diagram is incomplete: 2", result.summary)
        self.assertEqual(str(result.diagnostics[0]),
                         "partial.opl:6: WARNING W001: Statement is outside the supported syntax; skipped in full.")

    def test_empty_comments_and_crlf_line_numbers(self):
        self.assertEqual(parse_text('  # comment\r\n\r\n').require_model().entities, ())
        result = parse_text('  # comment\r\n\r\n object "A".\r\nprocess "P".\r\n"P" yields "A".\r\n')
        self.assertEqual([e.source.line for e in result.require_model().entities], [3, 4])
        self.assertEqual(result.model.links[0].source.line, 5)

    def test_attribute_defaults_and_every_combination(self):
        for kind in EntityKind:
            for essence in (None, *Essence):
                for affiliation in (None, *Affiliation):
                    with self.subTest(kind=kind, essence=essence, affiliation=affiliation):
                        attributes = ' '.join(v.value for v in (essence, affiliation) if v is not None)
                        entity = parse_text(f'{kind.value} "Thing" {attributes}.').require_model().entities[0]
                        self.assertEqual(entity.kind, kind)
                        self.assertEqual(entity.essence, essence or Essence.INFORMATICAL)
                        self.assertEqual(entity.affiliation, affiliation or Affiliation.SYSTEMIC)

    def test_quoted_names_and_escapes_remain_literal(self):
        text = r'''
object "A \\\" & <tag>: and, or.".
process "P".
"A \\\" & <tag>: and, or." has state "ready\\now".
"P" yields "A \\\" & <tag>: and, or.".
'''
        model = parse_text(text).require_model()
        self.assertEqual(model.entities[0].name, 'A \\" & <tag>: and, or.')
        self.assertEqual(model.states[0].name, 'ready\\now')
        self.assertEqual(model.links[0].target, model.entities[0].name)

    def test_malformed_input_never_creates_partial_statements(self):
        malformed = [
            'object A.', 'object "A"', 'object "A" human.',
            'object "A" systemic physical.', 'object "A" physical physical.',
            'object "A" "physical".', 'object "".', 'object " A".',
            'object "A ".', 'object "A\tB".', 'object "A\x00B".',
            r'object "bad\nname".', r'object "bad\tname".',
            'object "unterminated.', 'object "A". object "B".',
            '"P" consumes.', 'P consumes "A".', '"A" has state.',
            '"A" consists "B".', '"A" is a "B".',
            '"A" relates to "B".', '"A" relates to "B" as "".',
            '"A" unknown "unterminated.', '"A" unknown "B"',
        ]
        for text in malformed:
            with self.subTest(text=text):
                result = parse_text(text)
                self.assertEqual([d.code for d in result.diagnostics], ["E001"])
                self.assertIsNone(result.model)

    def test_unsupported_constructs_are_skipped_without_inference(self):
        unsupported = [
            '"A" changes "B" from "old" to "new".',
            '"A" zooms into "B".', '"A" can be "ready", "done".',
            '"A" likes "B".', '"A" consists of "B", "C".',
            '"A" exhibits "B" and "C".', '"A" has state "one" or "two".',
            'Object "A".',  # Keywords are case-sensitive.
        ]
        for text in unsupported:
            with self.subTest(text=text):
                result = parse_text(text)
                self.assertEqual([d.code for d in result.diagnostics], ["W001"])
                model = result.require_model()
                self.assertEqual((model.entities, model.states, model.links), ((), (), ()))

    def test_forward_references_resolve_and_preserve_source_order(self):
        text = '\n'.join([
            '"A" has state "ready".', '"P" consumes "A".',
            'process "P".', 'object "A".',
        ])
        model = parse_text(text).require_model()
        self.assertEqual([e.name for e in model.entities], ["P", "A"])
        self.assertEqual(model.states[0].source.line, 1)
        self.assertEqual(model.links[0].source.line, 2)

    def test_duplicate_declarations_and_states(self):
        for extra in ('object "A".', 'process "A".'):
            self.assertEqual(self.codes('object "A".\n' + extra), ["E002"])
        self.assertEqual(self.codes('object "A".\n"A" has state "ready".\n"A" has state "ready".'), ["E002"])
        model = parse_text('object "A".\nobject "B".\n"A" has state "ready".\n"B" has state "ready".').require_model()
        self.assertEqual(len(model.states), 2)

    def test_missing_references_and_state_owners(self):
        cases = [
            ('"Missing" has state "ready".', "E003"),
            ('process "P".\n"P" has state "ready".', "E004"),
            ('object "A".\n"Missing" consumes "A".', "E003"),
            ('process "P".\n"P" yields "Missing".', "E003"),
            ('"Missing" yields "Also missing".', "E003"),
            ('object "A".\nprocess "P".\n"P" consumes "a".', "E003"),
        ]
        for text, code in cases:
            with self.subTest(text=text):
                self.assertEqual(self.codes(text), [code])

    def test_endpoint_matrix_for_every_template(self):
        same = {("object", "object"), ("process", "process")}
        all_pairs = {(a.value, b.value) for a in EntityKind for b in EntityKind}
        templates = [
            ('"A" consists of "B".', same), ('"A" exhibits "B".', all_pairs),
            ('"A" is an "B".', {("object", "object")}),
            ('"A" is "B".', {("process", "process")}),
            ('"A" is an instance of "B".', same),
            ('"A" relates to "B" as "tag".', same),
            ('"A" relates bidirectionally to "B" as "tag".', same),
            *[(f'"A" {verb} "B".', {("process", "object")})
              for verb in ("consumes", "yields", "affects", "requires")],
            ('"A" handles "B".', {("object", "process")}),
        ]
        for statement, allowed in templates:
            for pair in all_pairs:
                with self.subTest(statement=statement, pair=pair):
                    result = parse_text(f'{pair[0]} "A".\n{pair[1]} "B".\n{statement}')
                    self.assertEqual([d.code for d in result.diagnostics], [] if pair in allowed else ["E004"])

    def test_self_links_are_errors(self):
        self.assertEqual(self.codes('object "A".\n"A" relates to "A" as "tag".'), ["E006"])

    def test_duplicate_link_identity_and_retained_source(self):
        text = '\n'.join([
            'object "A".', 'object "B".',
            '"A" relates bidirectionally to "B" as "same".',
            '"B" relates bidirectionally to "A" as "same".',
            '"A" relates bidirectionally to "B" as "different".',
            '"A" relates to "B" as "same".',
            '"B" relates to "A" as "same".',
            '"A" relates to "B" as "same".',
            '"A" consists of "B".', '"A" consists of "B".',
        ])
        result = parse_text(text)
        self.assertEqual([(d.source.line, d.code) for d in result.diagnostics],
                         [(4, "W002"), (8, "W002"), (10, "W002")])
        self.assertEqual(len(result.require_model().links), 5)
        self.assertEqual(result.model.links[0].source.line, 3)
        self.assertFalse(result.incomplete)

    def test_no_human_inanimate_metadata_or_e005(self):
        result = parse_text('object "Machine".\nprocess "Working".\n"Machine" handles "Working".\n"Working" requires "Machine".')
        self.assertEqual(result.diagnostics, ())
        self.assertEqual([link.kind for link in result.require_model().links], [LinkKind.AGENT, LinkKind.INSTRUMENT])

    @unittest.skipUnless(shutil.which("dot"), "Graphviz dot executable is required")
    def test_parse_then_render(self):
        from opm_graphviz.render import render_svg
        import xml.etree.ElementTree as ET
        result = parse_file(ROOT / "examples/supported.opl")
        with tempfile.TemporaryDirectory() as directory:
            output = render_svg(result.require_model(), Path(directory) / "parsed.svg")
            root = ET.parse(output).getroot()
            groups = root.findall('.//{http://www.w3.org/2000/svg}g')
            self.assertEqual(sum('opm-link' in g.get('class', '').split() for g in groups), 19)


if __name__ == "__main__":
    unittest.main()
