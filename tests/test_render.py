"""Rendering checks against actual Graphviz output, without pixel snapshots."""

import base64
from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from examples.supported_model import build_model
from opm_graphviz.model import (
    Affiliation, Entity, EntityKind, Essence, Link, LinkKind,
    Model, ObjectState, SourceLocation,
)
from opm_graphviz.render import render_svg, to_dot
from opm_graphviz.parser import parse_text

NS = {"svg": "http://www.w3.org/2000/svg"}


def members(root, name):
    return [g for g in root.findall(".//svg:g", NS)
            if name in g.get("class", "").split()]


@unittest.skipUnless(shutil.which("dot"), "Graphviz dot executable is required")
class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "nested" / "diagram.svg"
        self.source = SourceLocation("example.opl", 1)

    def render(self, model):
        self.assertEqual(render_svg(model, self.output), self.output)
        return ET.parse(self.output).getroot()

    def test_legend_is_boxed_embedded_and_below_all_entities(self):
        model = build_model()
        root = self.render(model)
        legend, = members(root, "opm-legend")
        self.assertIsNone(legend.get("data-source-path"))
        border = legend.find("svg:polygon", NS)
        self.assertEqual(border.get("stroke"), "black")
        self.assertEqual(float(border.get("stroke-width", "1")), 1)
        image = legend.find("svg:image", NS)
        uri = image.get("{http://www.w3.org/1999/xlink}href")
        prefix, data = uri.split(",", 1)
        self.assertEqual(prefix, "data:image/png;base64")
        asset = Path(__file__).resolve().parents[1] / "docs/OPM legend.drawio.png"
        self.assertEqual(base64.b64decode(data), asset.read_bytes())
        self.assertIn("meet", image.get("preserveAspectRatio"))
        # Graphviz coordinates increase upwards. Include disconnected entities
        # and cluster bounding boxes, not only nodes with outgoing model links.
        layout = json.loads(to_dot(model).pipe(format="json", quiet=True))
        decoration = next(n for n in layout["objects"] if n.get("id") == "opm-legend")
        top = float(decoration["pos"].split(",")[1]) + float(decoration["height"]) * 36
        for node in layout["objects"]:
            if node.get("class") not in {"opm-entity", "opm-state"}:
                continue
            if "bb" in node:
                bottom = float(node["bb"].split(",")[1])
            elif "pos" in node:
                bottom = float(node["pos"].split(",")[1]) - float(node["height"]) * 36
            else:
                continue
            self.assertLess(top, bottom)

    def test_legend_can_be_disabled_without_asset(self):
        with patch("opm_graphviz.render._LEGEND_PATH", Path(self.temp.name) / "missing.png"):
            with self.assertRaisesRegex(FileNotFoundError, "Legend image not found"):
                render_svg(build_model(), self.output)
            render_svg(build_model(), self.output, include_legend=False)
            self.assertNotIn("opm-legend", to_dot(build_model(), include_legend=False).source)
        root = ET.parse(self.output).getroot()
        self.assertEqual(members(root, "opm-legend"), [])
        self.assertEqual(len(members(root, "opm-link")), 19)

    def test_complete_example_svg_and_provenance(self):
        model = build_model()
        root = self.render(model)
        self.assertEqual(len(members(root, "opm-entity")), 13)
        self.assertEqual(len(members(root, "opm-state")), 3)
        self.assertEqual(len(members(root, "opm-link")), 19)
        ids = [e.get("id") for e in root.iter() if e.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        for prefix, elements in (("e", model.entities), ("s", model.states), ("l", model.links)):
            for i, element in enumerate(elements):
                group = root.find(f".//svg:g[@id='{prefix}{i}']", NS)
                self.assertIsNotNone(group)
                self.assertEqual(group.get("data-source-line"), str(element.source.line))
                self.assertEqual(group.get("data-source-path"), element.source.path)

    def test_all_markers_at_semantic_endpoints(self):
        model = build_model()
        laid_out = json.loads(to_dot(model, include_legend=False).pipe(format="json"))
        edges = {edge["id"]: edge for edge in laid_out["edges"] if "id" in edge}
        # Hand-reviewed expected (tail, head) pairs in supported.opl statement order.
        expected = [
            ("normal", "none"), ("normal", "none"),
            ("tee", "none"), ("tee", "none"), ("tee", "none"), ("tee", "none"),
            ("none", "onormal"), ("none", "onormal"),
            ("none", "curve"), ("none", "curve"),
            ("none", "vee"), ("none", "vee"),
            ("lvee", "lvee"), ("lvee", "lvee"),
            ("onormal", "none"), ("none", "onormal"), ("onormal", "onormal"),
            ("none", "dot"), ("odot", "none"),
        ]
        for i, (tail, head) in enumerate(expected):
            with self.subTest(link=i):
                edge = edges[f"l{i}"]
                self.assertEqual((edge["arrowtail"], edge["arrowhead"]), (tail, head))
                self.assertEqual(bool(edge.get("_tdraw_")), tail != "none")
                self.assertEqual(bool(edge.get("_hdraw_")), head != "none")
        self.assertEqual(edges["l6"]["lhead"], "cluster_e0")
        self.assertEqual(edges["l2"]["ltail"], "cluster_e0")
        self.assertEqual(edges["l16"]["lhead"], "cluster_e0")

    def test_parsed_relationships_keep_their_semantic_endpoints(self):
        # Declare Target first so insertion order cannot substitute for semantic
        # direction. Expected marked ends come from the README, not _MARKERS.
        cases = [
            ("object", "object", 'consists of "Target"', {"Subject"}),
            ("object", "process", 'exhibits "Target"', {"Subject"}),
            ("object", "object", 'is an "Target"', {"Target"}),
            ("process", "process", 'is "Target"', {"Target"}),
            ("object", "object", 'is an instance of "Target"', {"Target"}),
            ("object", "object", 'relates to "Target" as "tag"', {"Target"}),
            ("object", "object", 'relates bidirectionally to "Target" as "tag"', {"Subject", "Target"}),
            ("process", "object", 'consumes "Target"', {"Subject"}),
            ("process", "object", 'yields "Target"', {"Target"}),
            ("process", "object", 'affects "Target"', {"Subject", "Target"}),
            ("object", "process", 'handles "Target"', {"Target"}),
            ("process", "object", 'requires "Target"', {"Subject"}),
        ]
        for subject_type, target_type, phrase, marked_ends in cases:
            with self.subTest(phrase=phrase):
                text = (f'{target_type} "Target".\n{subject_type} "Subject".\n'
                        f'"Subject" {phrase}.')
                result = parse_text(text)
                self.assertEqual(result.diagnostics, ())
                model = result.require_model()
                layout = json.loads(to_dot(model, include_legend=False).pipe(format="json"))
                nodes = {node["_gvid"]: node for node in layout["objects"]}
                edge, = [edge for edge in layout["edges"] if edge.get("id") == "l0"]
                self.assertEqual(nodes[edge["tail"]]["label"], "Subject")
                self.assertEqual(nodes[edge["head"]]["label"], "Target")
                actual_marks = set()
                if edge.get("_tdraw_"):
                    actual_marks.add(nodes[edge["tail"]]["label"])
                if edge.get("_hdraw_"):
                    actual_marks.add(nodes[edge["head"]]["label"])
                self.assertEqual(actual_marks, marked_ends)
                root = self.render(model)
                group, = members(root, "opm-link")
                self.assertEqual(group.get("data-subject"), "Subject")
                self.assertEqual(group.get("data-target"), "Target")

    def test_same_named_states_stay_with_their_own_objects(self):
        model = parse_text('\n'.join([
            'object "First".', 'object "Second".',
            '"Second" has state "ready".', '"First" has state "ready".',
            '"First" relates bidirectionally to "Second" as "paired".',
        ])).require_model()
        root = self.render(model)
        states = members(root, "opm-state")
        self.assertEqual(len(states), 2)
        self.assertEqual({g.get("data-owner") for g in states}, {"First", "Second"})
        self.assertEqual(len({g.get("id") for g in states}), 2)
        self.assertTrue(all(g.find("svg:text", NS).text == "ready" for g in states))
        layout = json.loads(to_dot(model, include_legend=False).pipe(format="json"))
        objects = {obj["name"]: obj for obj in layout["objects"]}
        for state_id, parent_id in (("s0", "cluster_e1"), ("s1", "cluster_e0")):
            state, parent = objects[state_id], objects[parent_id]
            self.assertIn(state["_gvid"], parent["nodes"])
            x, y = map(float, state["pos"].split(","))
            x0, y0, x1, y1 = map(float, parent["bb"].split(","))
            self.assertTrue(x0 < x < x1 and y0 < y < y1)
        link = next(edge for edge in layout["edges"] if edge.get("id") == "l0")
        self.assertEqual(link["ltail"], "cluster_e0")
        self.assertEqual(link["lhead"], "cluster_e1")

    def test_only_tagged_links_have_light_grey_dotted_strokes(self):
        root = self.render(build_model())
        tagged_count = 0
        for group in members(root, "opm-link"):
            tagged = group.get("data-kind") in {"tagged", "tagged_bidirectional"}
            tagged_count += tagged
            with self.subTest(link=group.get("id")):
                shapes = [child for child in group
                          if child.tag.rsplit("}", 1)[-1] in {"path", "polygon", "ellipse"}]
                self.assertTrue(shapes)
                for shape in shapes:
                    self.assertEqual(shape.get("stroke"), "#999999" if tagged else "#374151")
                line = group.find("svg:path", NS)
                self.assertIsNotNone(line)
                self.assertEqual(line.get("stroke-dasharray"), "1,5" if tagged else None)
                label = group.find("svg:text", NS)
                if tagged:
                    self.assertIsNotNone(label)
                    self.assertEqual(label.get("fill"), "#374151")
                else:
                    self.assertIsNone(label)
        self.assertEqual(tagged_count, 4)

    def test_shapes_styles_and_shadows(self):
        model = build_model()
        root = self.render(model)
        for i, entity in enumerate(model.entities):
            with self.subTest(entity=entity.name):
                group = root.find(f".//svg:g[@id='e{i}']", NS)
                shadow = [c for c in group if c.get("class") == "opm-shadow"]
                self.assertEqual(len(shadow), int(entity.essence is Essence.PHYSICAL))
                shape = next(c for c in group if c.tag.rsplit("}", 1)[-1] in ("polygon", "ellipse")
                             and c.get("class") != "opm-shadow")
                self.assertEqual(shape.tag.rsplit("}", 1)[-1],
                                 "polygon" if entity.kind is EntityKind.OBJECT else "ellipse")
                self.assertEqual(shape.get("stroke"), "#228b22" if entity.kind is EntityKind.OBJECT else "#2459b3")
                self.assertEqual(shape.get("stroke-width"), "2")
                self.assertEqual(bool(shape.get("stroke-dasharray")), entity.affiliation is Affiliation.ENVIRONMENTAL)
        for state in members(root, "opm-state"):
            self.assertEqual(state.get("data-owner"), "Order")
            self.assertIsNotNone(state.find("svg:path", NS))  # Rounded corners.
            self.assertFalse(any(c.get("class") == "opm-shadow" for c in state))

    def test_state_containment_in_all_object_styles(self):
        for essence in Essence:
            for affiliation in Affiliation:
                with self.subTest(essence=essence, affiliation=affiliation):
                    obj = Entity("Parent", EntityKind.OBJECT, self.source, essence, affiliation)
                    proc = Entity("Working", EntityKind.PROCESS, self.source)
                    states = tuple(ObjectState("Parent", name, self.source) for name in ("idle", "a long state name"))
                    model = Model((obj, proc), states,
                                  (Link(LinkKind.EFFECT, "Working", "Parent", self.source),))
                    root = self.render(model)
                    group = root.find(".//svg:g[@id='e0']", NS)
                    self.assertEqual(sum(c.get("class") == "opm-shadow" for c in group),
                                     int(essence is Essence.PHYSICAL))
                    boundary = next(c for c in group if c.tag.endswith("polygon") and c.get("class") != "opm-shadow")
                    self.assertEqual(bool(boundary.get("stroke-dasharray")), affiliation is Affiliation.ENVIRONMENTAL)
                    layout = json.loads(to_dot(model, include_legend=False).pipe(format="json"))
                    cluster = next(o for o in layout["objects"] if o["name"] == "cluster_e0")
                    x0, y0, x1, y1 = map(float, cluster["bb"].split(","))
                    for state_id in ("s0", "s1"):
                        node = next(o for o in layout["objects"] if o["name"] == state_id)
                        x, y = map(float, node["pos"].split(","))
                        half_w, half_h = float(node["width"]) * 36, float(node["height"]) * 36
                        self.assertGreater(x - half_w, x0)
                        self.assertLess(x + half_w, x1)
                        self.assertGreater(y - half_h, y0)
                        self.assertLess(y + half_h, y1)

    def test_literal_names_and_labels_are_escaped(self):
        names = ('<B>Object & "name"</B>', r'Process:with\N')
        label = r'<tag> & "quote" \n'
        entities = tuple(Entity(name, EntityKind.OBJECT, self.source) for name in names)
        link = Link(LinkKind.TAGGED, *names, self.source, label)
        state = ObjectState(names[0], r'ready & <ok> \N', self.source)
        root = self.render(Model(entities, (state,), (link,)))
        text = [e.text for e in root.findall(".//svg:text", NS)]
        for value in (*names, label, state.name):
            self.assertIn(value, text)
        self.assertEqual(len(members(root, "opm-entity")), 2)

    def test_failure_does_not_replace_existing_output(self):
        self.output.parent.mkdir(parents=True)
        self.output.write_text("keep me")
        model = build_model()
        bad = replace(model, links=(replace(model.links[0], target="Missing"),))
        with self.assertRaisesRegex(ValueError, "Undefined link endpoint"):
            render_svg(bad, self.output)
        self.assertEqual(self.output.read_text(), "keep me")

    def test_labels_cannot_be_silently_discarded(self):
        model = build_model()
        for link in (replace(model.links[0], label="unexpected"),
                     replace(model.links[10], label=None)):
            with self.subTest(link=link.kind):
                with self.assertRaises(ValueError):
                    to_dot(replace(model, links=(link,)))

    def test_empty_model_is_valid_svg(self):
        root = self.render(Model())
        self.assertEqual(members(root, "opm-entity"), [])
        self.assertEqual(members(root, "opm-link"), [])


if __name__ == "__main__":
    unittest.main()
