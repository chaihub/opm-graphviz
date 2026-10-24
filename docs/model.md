# Internal model

`opm_graphviz/model.py` represents one diagram using standard-library dataclasses
and enums. It needs no Graphviz import or executable. Python 3.10 or newer is
required for the type annotations.

- `Entity` stores a globally unique, case-sensitive name, kind, essence,
  affiliation, and declaration source location. Defaults match `syntax.md`.
- `ObjectState` stores an owner name, local state name, and source location.
  It represents a possible state, not a selected or initial state.
- `Link` stores one of 11 kinds, subject and target entity names, an optional
  tagged-link label, and source location. Its docstring specifies endpoint roles.
- `SourceLocation` stores an input path and a one-based line number.
- `Model` contains tuples in source order within each category. Records are
  frozen. Construct a new model for changes rather than mutating records.

Link endpoints follow statement order. For `"Printing" consumes "Order Record"`,
subject is `Printing` and target is `Order Record`; a future renderer must place
its arrow according to the depiction rules, not assume subject-to-target arrows.
The effect kind remains one relationship. Bidirectional tagged links likewise
remain one relationship with one shared label.

After assembling the model, call `validate_integrity()`. It checks unique entity
names, existing link endpoints, existing object-typed state owners, and unique
state names per owner. Forward references work because checks run against all
entities after construction. It raises `ValueError` on the first problem.

This check deliberately does not replace the [parser and semantic
validator](parsing.md). It does not check link type combinations, duplicate links, self-links,
label rules, or lexical syntax, and does not produce OPL diagnostic codes.
Human/inanimate metadata and rendering styles are absent from the data model.

## Programmatic example

From the repository root, using the virtual environment:

```bash
python -m examples.supported_model
python -m unittest discover -s tests -v
```

`examples/supported_model.py` constructs the existing `supported.opl` example by
hand, with 13 entities, 3 states, and 19 links. It does not parse the OPL file.
Source locations point to that file, including the later declaration of Delivery.
The tests check fixture coverage and source correspondence so edits to the OPL
example that affect the programmatic counterpart are detected.
