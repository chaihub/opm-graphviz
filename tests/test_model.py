"""Integrity and example-contract checks; no parser or renderer required."""

from dataclasses import replace
from pathlib import Path
import unittest

from examples.supported_model import build_model
from opm_graphviz.model import (
    Affiliation, Entity, EntityKind, Essence, Link, LinkKind, Model,
    ObjectState, SourceLocation,
)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.source = SourceLocation("test.opl", 1)
        self.order = Entity("Order", EntityKind.OBJECT, self.source)
        self.process = Entity("Handling", EntityKind.PROCESS, self.source)

    def test_duplicate_entity_names_share_one_namespace(self):
        with self.assertRaisesRegex(ValueError, "Duplicate entity"):
            Model(entities=(self.order, replace(self.process, name="Order"))).validate_integrity()

    def test_link_references_must_exist(self):
        for subject, target in (("Missing", "Order"), ("Handling", "Missing")):
            with self.subTest(subject=subject, target=target):
                link = Link(LinkKind.RESULT, subject, target, self.source)
                with self.assertRaisesRegex(ValueError, "Undefined link endpoint"):
                    Model((self.order, self.process), links=(link,)).validate_integrity()

    def test_states_require_existing_object_owners(self):
        for owner, message in (("Missing", "Undefined state owner"),
                               ("Handling", "State owner must be an object")):
            with self.subTest(owner=owner):
                state = ObjectState(owner, "ready", self.source)
                with self.assertRaisesRegex(ValueError, message):
                    Model((self.order, self.process), (state,)).validate_integrity()

    def test_state_names_are_local_but_unique_per_owner(self):
        other = replace(self.order, name="Other Order")
        state = ObjectState("Order", "ready", self.source)
        Model((self.order, other), (state, replace(state, owner=other.name))).validate_integrity()
        with self.assertRaisesRegex(ValueError, "Duplicate state"):
            Model((self.order,), (state, state)).validate_integrity()

    def test_source_lines_are_one_based(self):
        with self.assertRaises(ValueError):
            SourceLocation("test.opl", 0)

    def test_example_coverage_and_forward_reference(self):
        model = build_model()
        self.assertEqual((len(model.entities), len(model.states), len(model.links)), (13, 3, 19))
        self.assertEqual(sum(e.kind is EntityKind.OBJECT for e in model.entities), 8)
        self.assertEqual({link.kind for link in model.links}, set(LinkKind))
        for kind in EntityKind:
            self.assertEqual(
                {(e.essence, e.affiliation) for e in model.entities if e.kind is kind},
                {(essence, affiliation) for essence in Essence for affiliation in Affiliation},
            )
        delivery = next(e for e in model.entities if e.name == "Delivery")
        reference = next(link for link in model.links if link.target == "Delivery")
        self.assertLess(reference.source.line, delivery.source.line)
        consumption = next(link for link in model.links if link.kind is LinkKind.CONSUMPTION)
        self.assertEqual((consumption.subject, consumption.target), ("Printing", "Order Record"))

    def test_example_corresponds_to_every_opl_statement(self):
        # Fixture contract, not a parser: compare canonical spellings to source
        # and ensure every input statement is represented exactly once.
        model = build_model()
        root = Path(__file__).resolve().parents[1]
        source_path = "examples/supported.opl"
        lines = (root / source_path).read_text().splitlines()
        expected = {}
        for entity in model.entities:
            text = f'{entity.kind.value} "{entity.name}"'
            if entity.name != "Order":
                text += f" {entity.essence.value} {entity.affiliation.value}"
            expected[entity.source.line] = text + "."
        for state in model.states:
            expected[state.source.line] = f'"{state.owner}" has state "{state.name}".'
        verbs = {
            LinkKind.AGGREGATION: "consists of", LinkKind.EXHIBITION: "exhibits",
            LinkKind.INSTANTIATION: "is an instance of", LinkKind.CONSUMPTION: "consumes",
            LinkKind.RESULT: "yields", LinkKind.EFFECT: "affects",
            LinkKind.AGENT: "handles", LinkKind.INSTRUMENT: "requires",
            LinkKind.TAGGED: "relates to", LinkKind.TAGGED_BIDIRECTIONAL: "relates bidirectionally to",
        }
        entities = {e.name: e for e in model.entities}
        for link in model.links:
            if link.kind is LinkKind.SPECIALIZATION:
                verb = "is an" if entities[link.subject].kind is EntityKind.OBJECT else "is"
            else:
                verb = verbs[link.kind]
            text = f'"{link.subject}" {verb} "{link.target}"'
            if link.label is not None:
                text += f' as "{link.label}"'
            expected[link.source.line] = text + "."
        actual = {i: text for i, text in enumerate(lines, 1)
                  if text.strip() and not text.lstrip().startswith("#")}
        self.assertEqual(expected, actual)
        elements = (*model.entities, *model.states, *model.links)
        self.assertEqual(len(expected), len(elements))
        self.assertTrue(all(e.source.path == source_path for e in elements))


if __name__ == "__main__":
    unittest.main()
