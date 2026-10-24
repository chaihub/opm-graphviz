"""Resolve parsed statements and validate the documented OPM subset."""

from dataclasses import dataclass
from typing import Iterable

from .diagnostics import Diagnostic, ParseResult, Severity
from .model import Entity, EntityKind, Link, LinkKind, Model, ObjectState


@dataclass(frozen=True)
class LinkStatement:
    """Retain the specialization grammar choice until types are resolved."""

    link: Link
    specialization_type: EntityKind | None = None


Statement = Entity | ObjectState | LinkStatement

_SAME_KIND = {
    LinkKind.AGGREGATION, LinkKind.SPECIALIZATION, LinkKind.INSTANTIATION,
    LinkKind.TAGGED, LinkKind.TAGGED_BIDIRECTIONAL,
}
_PROCESS_OBJECT = {
    LinkKind.CONSUMPTION, LinkKind.RESULT, LinkKind.EFFECT, LinkKind.INSTRUMENT,
}


def validate(statements: Iterable[Statement],
             diagnostics: Iterable[Diagnostic] = ()) -> ParseResult:
    """Collect declarations first, then resolve states and relationships.

    Retain the first declaration for error recovery. Rejected statements never
    enter the model. Agent/instrument kinds do not check human metadata.
    This function consumes parsed statements; lexical validation is in parser.py.
    """
    statements = tuple(statements)
    issues = list(diagnostics)
    entities: dict[str, Entity] = {}
    states: list[ObjectState] = []
    links: list[Link] = []
    seen_states = set()
    seen_links = set()

    def report(code, message, source):
        severity = Severity.WARNING if code.startswith("W") else Severity.ERROR
        issues.append(Diagnostic(code, severity, message, source))

    for statement in statements:
        if isinstance(statement, Entity):
            if statement.name in entities:
                report("E002", f"Duplicate entity declaration: {statement.name!r}.", statement.source)
            else:
                entities[statement.name] = statement

    for statement in statements:
        if isinstance(statement, Entity):
            continue
        if isinstance(statement, ObjectState):
            owner = entities.get(statement.owner)
            if owner is None:
                report("E003", f"Undefined state owner: {statement.owner!r}.", statement.source)
            elif owner.kind is not EntityKind.OBJECT:
                report("E004", "A state owner must be an object.", statement.source)
            elif (statement.owner, statement.name) in seen_states:
                report("E002", f"Duplicate state {statement.name!r} in {statement.owner!r}.", statement.source)
            else:
                seen_states.add((statement.owner, statement.name))
                states.append(statement)
            continue

        link = statement.link
        missing = [name for name in dict.fromkeys((link.subject, link.target))
                   if name not in entities]
        if missing:
            report("E003", f"Undefined entity reference(s): {', '.join(repr(n) for n in missing)}.", link.source)
            continue
        if link.subject == link.target:
            report("E006", "Self-links are unsupported.", link.source)
            continue
        subject_kind = entities[link.subject].kind
        target_kind = entities[link.target].kind
        allowed = True
        if link.kind in _SAME_KIND:
            allowed = subject_kind is target_kind
        elif link.kind in _PROCESS_OBJECT:
            allowed = (subject_kind, target_kind) == (EntityKind.PROCESS, EntityKind.OBJECT)
        elif link.kind is LinkKind.AGENT:
            allowed = (subject_kind, target_kind) == (EntityKind.OBJECT, EntityKind.PROCESS)
        # Exhibition permits every object/process combination.
        if statement.specialization_type is not None:
            allowed = allowed and subject_kind is statement.specialization_type
        if not allowed:
            report("E004", f"Invalid endpoint types for {link.kind.value}: "
                   f"{subject_kind.value}/{target_kind.value}.", link.source)
            continue
        endpoints = (link.subject, link.target)
        if link.kind is LinkKind.TAGGED_BIDIRECTIONAL:
            endpoints = tuple(sorted(endpoints))
        key = (link.kind, endpoints, link.label)
        if key in seen_links:
            report("W002", "Duplicate relationship; retained its first occurrence.", link.source)
        else:
            seen_links.add(key)
            links.append(link)

    issues.sort(key=lambda d: (d.source.path, d.source.line))
    if any(issue.severity is Severity.ERROR for issue in issues):
        return ParseResult(None, tuple(issues))
    model = Model(tuple(entities.values()), tuple(states), tuple(links))
    model.validate_integrity()
    return ParseResult(model, tuple(issues))
