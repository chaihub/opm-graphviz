"""Rendering checks against actual Graphviz output, without pixel snapshots."""

from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

from examples.supported_model import build_model
from opm_graphviz.model import (
    Affiliation, Entity, EntityKind, Essence, Link, LinkKind,
    Model, ObjectState, SourceLocation,
)
from opm_graphviz.render import render_svg, to_dot

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
        laid_out = json.loads(to_dot(model).pipe(format="json"))
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
                    layout = json.loads(to_dot(model).pipe(format="json"))
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
