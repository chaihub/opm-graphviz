# Testing

From the repository root, activate the virtual environment and run:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

The suite uses standard-library `unittest`; no extra test dependencies are needed.
Install the system Graphviz package so `dot` is on PATH to run rendering checks.
Tests that need real rendering are explicitly skipped when `dot` is unavailable;
a passing run with skips does not verify rendering. The missing-Graphviz CLI test
runs with an empty PATH deliberately and verifies the resulting error message.

## Coverage of the focused-testing TODO

| Requirement | Coverage |
| --- | --- |
| Relationship direction | Every link kind's markers; parsed subject/target names traced through Graphviz endpoints; reversed declaration order; cluster boundary attachments. |
| State ownership | Existing object owners required; local state-name uniqueness; identical state names under different objects retain separate SVG identities and layout membership. |
| Invalid references | Missing link endpoints and state owners; case sensitivity; forward references; errors prevent a renderable model and preserve existing CLI outputs. |
| Unsupported statements | Full-statement skipping, W001 diagnostics, skipped counts, incomplete-diagram summaries, and no unsupported states or links in generated SVG. |
| Successful SVG rendering | Full example with 13 entities, 3 states, and 19 links; all entity styling combinations; literal text escaping; metadata; actual CLI SVG and optional DOT generation. |

Additional regression checks cover dotted `#999999` tagged links with dark labels,
duplicate relationships producing only one rendered link, error exit codes,
input/output path collisions, and render failures preserving existing output.

## Test files

- `tests/test_model.py`: model integrity and programmatic fixture correspondence.
- `tests/test_parser.py`: syntax, semantic validation, documented diagnostics,
  and parsing through rendering.
- `tests/test_render.py`: generated Graphviz layout and SVG properties, including
  semantic endpoints, state containment, marker shapes, colors, and shadows.
- `tests/test_cli.py`: subprocess invocation, exit status, diagnostics, and files.

Tests use temporary directories and do not rewrite example OPL or build artifacts.
Rendering assertions check structure and semantic placement rather than full SVG
snapshots, which would vary with Graphviz versions and installed fonts. Automated
checks complement visual review; they do not establish optimal diagram layout.

Legend tests check the thin black border, embedded PNG bytes, aspect-ratio setting,
placement below entities and clusters, unchanged model counts, missing-asset
behavior, and CLI opt-out in both SVG and DOT.
