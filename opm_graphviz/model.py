"""Graphviz-independent data model for one OPM diagram.

Endpoint order follows the written statement, never the rendered arrow direction.
Construction does not validate a model: call validate_integrity() after assembling
all declarations, including those that follow references in the input.
"""

from dataclasses import dataclass
from enum import Enum


class EntityKind(Enum):
    OBJECT = "object"
    PROCESS = "process"


class Essence(Enum):
    PHYSICAL = "physical"
    INFORMATICAL = "informatical"


class Affiliation(Enum):
    SYSTEMIC = "systemic"
    ENVIRONMENTAL = "environmental"


class LinkKind(Enum):
    AGGREGATION = "aggregation"
    EXHIBITION = "exhibition"
    SPECIALIZATION = "specialization"
    INSTANTIATION = "instantiation"
    TAGGED = "tagged"
    TAGGED_BIDIRECTIONAL = "tagged_bidirectional"
    CONSUMPTION = "consumption"
    RESULT = "result"
    EFFECT = "effect"
    AGENT = "agent"
    INSTRUMENT = "instrument"


@dataclass(frozen=True)
class SourceLocation:
    """Original input path and one-based line number."""

    path: str
    line: int

    def __post_init__(self) -> None:
        if not self.path or self.line < 1:
            raise ValueError("Source location needs a path and a positive line number")


@dataclass(frozen=True)
class Entity:
    name: str
    kind: EntityKind
    source: SourceLocation
    essence: Essence = Essence.INFORMATICAL
    affiliation: Affiliation = Affiliation.SYSTEMIC


@dataclass(frozen=True)
class ObjectState:
    """A possible state, identified by (owner, name), not a current state."""

    owner: str
    name: str
    source: SourceLocation


@dataclass(frozen=True)
class Link:
    """One relationship; subject and target are globally unique entity names.

    Kind                  subject             target
    AGGREGATION           whole               part
    EXHIBITION            exhibitor           feature
    SPECIALIZATION        specialization      generalization
    INSTANTIATION         instance            class
    TAGGED                origin              destination
    TAGGED_BIDIRECTIONAL  first participant   second participant
    CONSUMPTION           process             consumed object
    RESULT                process             resulting object
    EFFECT                process             affected object
    AGENT                 agent object        process
    INSTRUMENT            process             instrument object

    label is used only for tagged links. Bidirectional and effect relationships
    each occupy one Link. Neither implies state transitions. Source locations
    are provenance, not part of relationship identity.
    """

    kind: LinkKind
    subject: str
    target: str
    source: SourceLocation
    label: str | None = None


@dataclass(frozen=True)
class Model:
    """Collections in source order within each category, for a single diagram.

    Names are case-sensitive, unescaped text; Graphviz identifiers and styling
    are deliberately absent. Entity names are references, not persistent IDs
    across renames. Use source locations to recover cross-category ordering.
    """

    entities: tuple[Entity, ...] = ()
    states: tuple[ObjectState, ...] = ()
    links: tuple[Link, ...] = ()

    def validate_integrity(self) -> None:
        """Raise ValueError on the first broken reference or ownership invariant.

        This is a construction check, not the OPL validator. Lexical rules,
        relationship type restrictions, labels, self-links, duplicate links, and
        user-facing diagnostic codes belong to the subsequent validator step.
        No human/inanimate object metadata is stored or checked.
        """
        entities: dict[str, Entity] = {}
        for entity in self.entities:
            if entity.name in entities:
                raise ValueError(f"Duplicate entity: {entity.name!r}")
            entities[entity.name] = entity

        seen_states: set[tuple[str, str]] = set()
        for state in self.states:
            owner = entities.get(state.owner)
            if owner is None:
                raise ValueError(f"Undefined state owner: {state.owner!r}")
            if owner.kind is not EntityKind.OBJECT:
                raise ValueError(f"State owner must be an object: {state.owner!r}")
            key = (state.owner, state.name)
            if key in seen_states:
                raise ValueError(f"Duplicate state: {key!r}")
            seen_states.add(key)

        for link in self.links:
            for name in (link.subject, link.target):
                if name not in entities:
                    raise ValueError(f"Undefined link endpoint: {name!r}")
