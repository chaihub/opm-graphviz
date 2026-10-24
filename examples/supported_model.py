"""Hand-constructed counterpart of supported.opl; no OPL parsing involved.

Run from the repository root: python -m examples.supported_model
"""

from opm_graphviz.model import (
    Affiliation, Entity, EntityKind, Essence, Link, LinkKind, Model,
    ObjectState, SourceLocation,
)


def build_model() -> Model:
    """Build a fresh model with provenance pointing into examples/supported.opl."""
    def source(line: int) -> SourceLocation:
        return SourceLocation("examples/supported.opl", line)

    entities = (
        Entity("Order", EntityKind.OBJECT, source(2)),
        Entity("Priority Order", EntityKind.OBJECT, source(3)),
        Entity("Order 001", EntityKind.OBJECT, source(4)),
        Entity("Order Record", EntityKind.OBJECT, source(5),
               affiliation=Affiliation.ENVIRONMENTAL),
        Entity("Operator", EntityKind.OBJECT, source(6),
               Essence.PHYSICAL, Affiliation.ENVIRONMENTAL),
        Entity("Machine", EntityKind.OBJECT, source(7), Essence.PHYSICAL),
        Entity("Machine Component", EntityKind.OBJECT, source(8), Essence.PHYSICAL),
        Entity("Receipt", EntityKind.OBJECT, source(9)),
        Entity("Order Handling", EntityKind.PROCESS, source(11)),
        Entity("Priority Handling", EntityKind.PROCESS, source(12)),
        Entity("Handling Run 001", EntityKind.PROCESS, source(13),
               affiliation=Affiliation.ENVIRONMENTAL),
        Entity("Printing", EntityKind.PROCESS, source(14), Essence.PHYSICAL),
        Entity("Delivery", EntityKind.PROCESS, source(50),
               Essence.PHYSICAL, Affiliation.ENVIRONMENTAL),
    )
    states = (
        ObjectState("Order", "pending", source(16)),
        ObjectState("Order", "approved", source(17)),
        ObjectState("Order", "completed", source(18)),
    )
    # Kind, subject, target, label, original statement line.
    link_specs = (
        (LinkKind.AGGREGATION, "Machine", "Machine Component", None, 21),
        (LinkKind.AGGREGATION, "Order Handling", "Printing", None, 22),
        (LinkKind.EXHIBITION, "Order", "Order Record", None, 25),
        (LinkKind.EXHIBITION, "Machine", "Printing", None, 26),
        (LinkKind.EXHIBITION, "Order Handling", "Order Record", None, 27),
        (LinkKind.EXHIBITION, "Order Handling", "Priority Handling", None, 28),
        (LinkKind.SPECIALIZATION, "Priority Order", "Order", None, 31),
        (LinkKind.SPECIALIZATION, "Priority Handling", "Order Handling", None, 32),
        (LinkKind.INSTANTIATION, "Order 001", "Order", None, 33),
        (LinkKind.INSTANTIATION, "Handling Run 001", "Order Handling", None, 34),
        (LinkKind.TAGGED, "Order", "Receipt", "documented by", 37),
        (LinkKind.TAGGED, "Order Handling", "Printing", "scheduled before", 38),
        (LinkKind.TAGGED_BIDIRECTIONAL, "Order", "Order Record", "corresponds to", 39),
        (LinkKind.TAGGED_BIDIRECTIONAL, "Printing", "Delivery", "coordinates with", 40),
        (LinkKind.CONSUMPTION, "Printing", "Order Record", None, 43),
        (LinkKind.RESULT, "Printing", "Receipt", None, 44),
        (LinkKind.EFFECT, "Order Handling", "Order", None, 45),
        (LinkKind.AGENT, "Operator", "Order Handling", None, 46),
        (LinkKind.INSTRUMENT, "Printing", "Machine", None, 47),
    )
    links = tuple(
        Link(kind, subject, target, source(line), label)
        for kind, subject, target, label, line in link_specs
    )
    model = Model(entities, states, links)
    model.validate_integrity()
    return model


if __name__ == "__main__":
    model = build_model()
    print(f"{len(model.entities)} entities, {len(model.states)} states, "
          f"{len(model.links)} links; integrity checks passed")
