"""Strict line-oriented parser for docs/syntax.md, with no LLM inference."""

from dataclasses import dataclass
from pathlib import Path
import unicodedata

from .diagnostics import Diagnostic, ParseResult, Severity
from .model import Affiliation, Entity, EntityKind, Essence, Link, LinkKind, ObjectState, SourceLocation
from .validator import LinkStatement, Statement, validate


@dataclass(frozen=True)
class _Token:
    value: str
    quoted: bool = False


class _Unsupported(ValueError):
    pass


# None matches a quoted string. Exact templates keep arbitrary English out.
_TEMPLATES = (
    (("has", "state", None), None, None),
    (("consists", "of", None), LinkKind.AGGREGATION, None),
    (("exhibits", None), LinkKind.EXHIBITION, None),
    (("is", "an", "instance", "of", None), LinkKind.INSTANTIATION, None),
    (("is", "an", None), LinkKind.SPECIALIZATION, EntityKind.OBJECT),
    (("is", None), LinkKind.SPECIALIZATION, EntityKind.PROCESS),
    (("relates", "to", None, "as", None), LinkKind.TAGGED, None),
    (("relates", "bidirectionally", "to", None, "as", None), LinkKind.TAGGED_BIDIRECTIONAL, None),
    (("consumes", None), LinkKind.CONSUMPTION, None),
    (("yields", None), LinkKind.RESULT, None),
    (("affects", None), LinkKind.EFFECT, None),
    (("handles", None), LinkKind.AGENT, None),
    (("requires", None), LinkKind.INSTRUMENT, None),
)
_KNOWN_VERBS = {template[0][0] for template in _TEMPLATES}


def _tokenize(text: str) -> list[_Token]:
    """Decode only escaped quotes/backslashes; preserve literal string contents."""
    result = []
    i = 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        if text[i] == '"':
            i += 1
            chars = []
            while i < len(text) and text[i] != '"':
                char = text[i]
                if char == "\\":
                    i += 1
                    if i == len(text) or text[i] not in ('"', "\\"):
                        raise ValueError("Strings support only escaped quotes and backslashes.")
                    char = text[i]
                if unicodedata.category(char) == "Cc":
                    raise ValueError("Control characters are not allowed inside strings.")
                chars.append(char)
                i += 1
            if i == len(text):
                raise ValueError("Unterminated quoted string.")
            i += 1
            value = "".join(chars)
            if not value or value != value.strip():
                raise ValueError("Strings must be nonempty with no leading/trailing whitespace.")
            result.append(_Token(value, True))
        elif text[i] in ".,":
            result.append(_Token(text[i]))
            i += 1
        else:
            start = i
            while i < len(text) and not text[i].isspace() and text[i] not in '\".,':
                i += 1
            result.append(_Token(text[start:i]))
    return result


def _matches(tokens: list[_Token], pattern: tuple) -> bool:
    return len(tokens) == len(pattern) and all(
        token.quoted if expected is None else (not token.quoted and token.value == expected)
        for token, expected in zip(tokens, pattern)
    )


def _declaration(tokens: list[_Token], source: SourceLocation) -> Entity:
    if len(tokens) < 2 or not tokens[1].quoted:
        raise ValueError("An entity declaration requires a quoted name.")
    remaining = tokens[2:]
    essence = Essence.INFORMATICAL
    affiliation = Affiliation.SYSTEMIC
    if remaining and not remaining[0].quoted and remaining[0].value in {e.value for e in Essence}:
        essence = Essence(remaining.pop(0).value)
    if remaining and not remaining[0].quoted and remaining[0].value in {a.value for a in Affiliation}:
        affiliation = Affiliation(remaining.pop(0).value)
    if remaining:
        raise ValueError("Invalid declaration attribute or attribute order.")
    return Entity(tokens[1].value, EntityKind(tokens[0].value), source, essence, affiliation)


def _statement(tokens: list[_Token], source: SourceLocation) -> Statement:
    if not tokens:
        raise ValueError("Empty statement.")
    if not tokens[0].quoted and tokens[0].value in {"object", "process"}:
        return _declaration(tokens, source)
    for pattern, kind, specialization_type in _TEMPLATES:
        if _matches(tokens, (None, *pattern)):
            values = [token.value for token in tokens if token.quoted]
            if kind is None:
                return ObjectState(values[0], values[1], source)
            label = values[2] if len(values) == 3 else None
            return LinkStatement(Link(kind, values[0], values[1], source, label), specialization_type)

    # Valid template followed by a list is an unsupported feature, not a
    # partially accepted relationship. Discard the entire statement.
    for pattern, _, _ in _TEMPLATES:
        length = len(pattern) + 1
        if (len(tokens) > length and _matches(tokens[:length], (None, *pattern))
                and not tokens[length].quoted and tokens[length].value in {",", "and", "or"}):
            raise _Unsupported("Lists of states or relationship endpoints are unsupported.")
    if len(tokens) > 1 and not tokens[1].quoted and tokens[1].value in _KNOWN_VERBS:
        raise ValueError("Malformed supported statement; check quoted names and required keywords.")
    raise _Unsupported("Statement is outside the supported syntax; skipped in full.")


def parse_text(text: str, source_path: str = "<string>") -> ParseResult:
    """Parse text and resolve references; return no model if any error occurs."""
    statements = []
    diagnostics = []
    # Split only on newlines: other literal control characters must remain
    # visible to the string lexer. Strip CR only as part of a CRLF terminator.
    for line_number, raw in enumerate(text.split("\n"), 1):
        if raw.endswith("\r"):
            raw = raw[:-1]
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        source = SourceLocation(source_path, line_number)
        try:
            tokens = _tokenize(raw)
            if not tokens or tokens[-1] != _Token("."):
                raise ValueError("Statement must end with a period.")
            statement = _statement(tokens[:-1], source)
            statements.append(statement)
        except _Unsupported as exc:
            diagnostics.append(Diagnostic("W001", Severity.WARNING, str(exc), source))
        except ValueError as exc:
            diagnostics.append(Diagnostic("E001", Severity.ERROR, str(exc), source))
    return validate(statements, diagnostics)


def parse_file(path: str | Path) -> ParseResult:
    """Read UTF-8 input; filesystem and decoding errors propagate to the caller."""
    path = Path(path)
    return parse_text(path.read_text(encoding="utf-8"), str(path))
