# OPL-like input syntax — draft v0.1

Status: proposed implementation contract.  Scope comes from README.md.

## 1. Files, names, and statements

- Input is UTF-8 with a `.opl` extension.
- One statement per nonblank line; every statement ends with a period.
- A line whose first non-whitespace character is `#` is a comment. Inline comments
  and multiline statements are not supported.
- Indentation and whitespace between tokens are insignificant. Keywords are
  lowercase and case-sensitive; quoted names and labels are case-sensitive.
- Every name and tagged-link label is a double-quoted string. Strings support
  only `\"` for a literal quotation mark and `\\` for a literal backslash.
  Empty strings, leading/trailing whitespace inside strings, and literal control
  characters are invalid. Internal spaces are preserved.
- Objects and processes share one global name namespace. States are local to
  their owning object: two objects can both have a state named "ready".
- Forward references are allowed. Read all declarations before resolving links.
- No entities are inferred or created from relationship statements.

In the templates below, NAME, STATE, and LABEL denote quoted strings, brackets
mean optional syntax, and alternatives separated by `|` mean choose one.
Brackets and uppercase placeholders do not appear in input.

## 2. Entity declarations

```text
object NAME [physical|informatical] [systemic|environmental].
process NAME [physical|informatical] [systemic|environmental].
```

Optional attributes must occur in the order shown. Omitted essence defaults to
`informatical`; omitted affiliation defaults to `systemic`.

`human` and `inanimate` are not object metadata; they are used only in characterizing
agent and instrument links. If omitted, the default is `inanimate`.

```text
object "Order".
object "Operator" physical environmental.
object "Computer" physical systemic.
process "Order Handling" informatical systemic.
```

An entity must have exactly one declaration. A second declaration is an error,
even when identical. Attributes cannot be modified by later statements.

## 3. Object states

```text
NAME has state STATE.
```

The owner must be a declared object. Each statement declares one possible state
inside that object, in source order. State names must be unique within an owner.
This does not select a current, initial, or final state. States are not global
entities and cannot be relationship endpoints in this release. State transitions
and state-qualified relationships are outside the selected scope.

## 4. Structural relationships

All endpoints must refer to declared objects or processes.

| Template | Required types | Graphical endpoint |
| --- | --- | --- |
| A consists of B. | A and B = objects, or A and B = processes | Solid normal arrow at A. |
| A exhibits B. | A and B = objects or processes, in any combination | Tee arrow at A. |
| B is an A. | A and B = objects | Open normal arrow at A. |
| B is A. | A and B = processes | Open normal arrow at A. |
| B is an instance of A. | A and B = objects, or A and B = processes | Curve arrow at A. |
| A relates to B as LABEL. | A and B = objects, or A and B = processes | Vee arrow at B, with LABEL as text. |
| A relates bidirectionally to B as LABEL. | A and B = objects, or A and B = processes | Lvee arrows at both A and B, with LABEL as text. |

A and B are quoted names. `an` is a fixed keyword in object specialization, even
when the name starts with a consonant. This deliberately follows the template in
the README rather than adding article selection. For example:

```text
"Priority Order" is an "Order".
"Priority Handling" is "Order Handling".
"Order 001" is an instance of "Order".
```

Use one relationship per statement; lists of parts or features are unsupported.
Tagged relationships require the explicit `relates` syntax. Unknown English verbs
must not silently become tagged links. A bidirectional relation does not create
two independent labels. Self-links are rejected in this draft.

Preserve semantic roles in the internal model, independently of where Graphviz
places arrowheads.

## 5. Procedural relationships

| Template | Required types | Graphical endpoint |
| --- | --- | --- |
| P consumes O. | P = process; O = object | Hollow arrow at P; object to process. |
| P yields O. | P = process; O = object | Hollow arrow at O; process to object. |
| P affects O. | P = process; O = object | Hollow arrows at both O and P; one effect link. |
| O handles P. | O = human object; P = process | Filled dot at P. |
| P requires O. | P = process; O = inanimate object | Hollow dot at P. |

Neither the effect link nor the tagged bidirectional link declares state changes.

## 6. Parsing and diagnostics

Process input in three stages: parse supported statements; collect declarations;
resolve references and validate relationships. Preserve the source line for each
model element and diagnostic. A declaration can follow its first reference.

Diagnostic format:

```text
path:line: SEVERITY CODE: explanation
```

| Code | Severity | Condition |
| --- | --- | --- |
| W001 | WARNING | Statement uses an unsupported construct; skip the entire statement. |
| W002 | WARNING | Exact duplicate relationship; retain one link. |
| E001 | ERROR | Malformed supported statement: missing period, invalid string, missing operand, or invalid declaration attribute. |
| E002 | ERROR | Duplicate entity declaration or duplicate state within one object. |
| E003 | ERROR | Undefined entity reference. |
| E004 | ERROR | Wrong endpoint type or state owner type. |
| E006 | ERROR | Self-link. |

The parser recognizes the supported templates above. A statement that starts a
supported template but fails its required syntax is E001. A statement using a
feature or verb outside those templates is W001. In particular, `changes ...
from ... to ...`, `can be ...`, and `zooms into ...` are unsupported in this draft.
Malformed string quoting or a missing statement terminator is E001 regardless of
whether the intended feature is supported. Report one primary syntax diagnostic
per rejected line and do not try to validate that line further.

Do not render if any ERROR occurs. With warnings only, render the supported
portion and emit an explicit summary that the diagram is incomplete when W001
occurred, including the number of skipped statements. Unsupported statements
must never create entities or links. Continue collecting independent diagnostics;
avoid reporting endpoint-dependent errors when that endpoint is undefined.

Relationship identity includes kind, semantic endpoints, and label where relevant.
For bidirectional tagged links, reversed endpoints with the same label are a
duplicate. Reversed endpoints of directed tagged links are distinct. State
declarations and entity declarations are not relationship duplicates.

## 7. Example files and acceptance criteria

- `examples/supported.opl`: valid coverage example; expect no diagnostics.
  Expect 13 entities (8 objects, 5 processes), 3 states, and 19 links. It covers all
  essence/affiliation combinations, all allowed structural type combinations,
  both tagged directions, all procedural kinds, defaults, and a forward reference.
- `examples/diagnostics.opl`: deliberately invalid input. Expected diagnostics are
  listed below. No diagram should be emitted because it contains errors.

| Line | Expected | Reason |
| --- | --- | --- |
| 6 | W001 | State transition is outside scope. |
| 7 | W001 | In-zooming is outside scope. |
| 8 | E003 | "Missing" is not declared. |
| 9 | E004 | A process cannot own an object state. |
| 10 | E004 | An object cannot be the consuming process. |
| 11 | None | Valid agent link; human/inanimate object metadata is not checked. |
| 12 | None | Valid instrument link; human/inanimate object metadata is not checked. |
| 13 | E002 | "Order" is declared twice. |
| 14 | E001 | Missing final period. |
| 15 | E006 | Self-link. |
| 17 | W002 | Repeats the link on line 16. |

The valid `consumes` statement on line 16 and the invalid one on line 10 are
separate: rejected statements are never inserted into the model. For a warning-only
check, use declarations on lines 1–4 plus lines 6–7; expect two W001 warnings and
an incomplete-diagram summary, but no errors.