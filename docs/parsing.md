# OPL parser and validator

The parser implements the project grammar in [syntax.md](syntax.md). It uses only
Python's standard library and the existing internal model. It does not infer
missing declarations, accept colloquial aliases, or use an LLM.

## API

Run Python from the repository root with the virtual environment activated:

```python
from pathlib import Path
from opm_graphviz.parser import parse_file, parse_text
from opm_graphviz.render import render_svg

result = parse_file("examples/supported.opl")
for diagnostic in result.diagnostics:
    print(diagnostic)
print(result.summary)

# Raises ValueError if errors prevented model creation. Warnings still permit
# rendering, so always display diagnostics and summary above.
model = result.require_model()
render_svg(model, Path("build/parsed-supported.svg"))
```

`parse_text(text, source_path="<string>")` performs the same operations on a
string. `parse_file(path)` reads UTF-8 and records the supplied path in source
locations. Filesystem and decoding failures propagate as Python exceptions.
Neither parsing API writes files or invokes Graphviz. The programmatic rendering
example remains independent of the parser; the general CLI is the next TODO.

## Results and diagnostics

Both APIs return a `ParseResult` with:

- `model`: the supported model, or `None` if any error occurred.
- `diagnostics`: ordered diagnostics containing code, severity, source location,
  and explanation. String conversion follows `path:line: SEVERITY CODE: message`.
- `has_errors`: whether any error prevents rendering.
- `skipped_statements`: the number of W001 unsupported statements.
- `incomplete`: whether unsupported statements were skipped.
- `summary`: an error summary, an incomplete-diagram warning with the skipped
  count, or a completion message for the supported syntax.
- `require_model()`: return the model or raise `ValueError` with the diagnostics.

Warnings do not suppress the model. W001 discards the entire unsupported
statement without creating implied entities or relationships. W002 retains the
first duplicate relationship. W002 alone does not make a diagram incomplete.
With any error, no partial model is exposed for accidental rendering.

## Processing stages

1. Tokenize each nonblank, non-comment line, decoding only escaped quotation marks
   and backslashes. Check strings and the final period before interpreting syntax.
2. Match exact statement templates. Malformed supported syntax produces E001;
   unsupported constructs produce W001. One rejected line gets one syntax
   diagnostic and is not passed to semantic validation.
3. Collect declarations, retaining the first occurrence for error recovery.
   Duplicate declarations produce E002; entity names share one namespace.
4. Resolve states and links against all declarations, allowing forward references.
   Validate owner types, state uniqueness, endpoint types, and self-links. Missing
   references produce E003 and suppress dependent endpoint checks on that line.
5. Deduplicate valid relationships, preserving the first source location. Only
   bidirectional tagged links treat reversed endpoints as the same relationship.
6. Return diagnostics in source order. Return a model only if there are no errors.

The two specialization spellings retain their object/process distinction until
references are resolved. Entity essence and affiliation default to informatical
and systemic. Agent and instrument relationships check only object/process
endpoints; they do not introduce human/inanimate metadata or E005.

The low-level `validator.validate` operates on parsed declarations, states, and
`LinkStatement` records. Normal callers should use the two parser APIs, which
perform lexical and semantic validation together. `Model.validate_integrity()`
remains a lightweight construction check for programmatically authored models.

## Verification

```bash
python -m unittest discover -s tests -v
```

Tests compare parsed `supported.opl` against the hand-built model, including
source locations, and match `diagnostics.opl` against the specified diagnostic
codes and lines. Additional cases cover every endpoint-type combination, defaults,
forward references, string escaping, unsupported lists, duplicate identity,
case sensitivity, state ownership, errors suppressing model output, warning-only
input, and parsing through actual SVG rendering.
