# Command-line interface

From the repository root, activate the virtual environment and run:

```bash
source .venv/bin/activate
python -m opm_graphviz examples/supported.opl -o build/supported.svg --dot
```

This parses the OPL file, validates the model, and writes `build/supported.svg`
and `build/supported.dot`. Edits to the input OPL are reflected on the next run.
Open the SVG in a browser to see the final diagram, including physical shadows.

## Arguments

```text
python -m opm_graphviz INPUT [-o SVG] [--dot] [--no-legend]
```

| Argument | Behavior |
| --- | --- |
| `INPUT` | UTF-8 OPL file to read. |
| `-o SVG`, `--output SVG` | SVG destination; defaults to the input path with its suffix changed to `.svg`. |
| `--dot` | Also write DOT beside the SVG using the same stem and a `.dot` suffix. |
| `--no-legend` | Omit the legend from both SVG and DOT. |
| `-h`, `--help` | Display usage. |

No package installation or new Python dependency is needed beyond the existing
requirements. Run from the repository root. Graphviz's system `dot` executable
must be on PATH. The command does not launch a viewer automatically.

## Diagnostics and exit status

Diagnostics go to stderr in `path:line: SEVERITY CODE: explanation` format.
Successful output paths go to stdout.

| Exit code | Meaning |
| --- | --- |
| `0` | Rendering succeeded, possibly with warnings; also used for help. |
| `1` | Input syntax/semantic errors, unreadable or non-UTF-8 input, rendering failure, or output filesystem failure. |
| `2` | Invalid command usage, output extension, or paths that would overwrite the input or alias each other. |

Unsupported statements produce W001 warnings. The supported subset is rendered
and stderr explicitly reports that the diagram is incomplete, with the number
of skipped statements. Duplicate links produce W002 and are rendered only once;
these warnings alone do not make a diagram incomplete.

Any parsing or validation error prevents rendering. Existing outputs remain
untouched. Missing Graphviz and other rendering failures produce concise errors
without a Python traceback. Expected input/output filesystem failures are also
reported without tracebacks.

The supplied legend appears below the diagram inside a thin black box by default.
Its PNG is embedded in the final SVG, so the SVG can be moved or shared alone.
DOT references the original image by absolute path and requires that asset.

## Output behavior

- Only SVG is the final image format for this CLI. DOT is optional source output;
  rendering DOT directly does not include post-processed shadows or SVG metadata.
- Parent directories are created as needed after input validation succeeds.
- Existing outputs are replaced on successful generation. Input/output aliases,
  including symlinks and hard links, are rejected before writing.
- SVG and optional DOT are prepared in temporary files before replacement. Each
  final file replacement is atomic, but the pair is not a filesystem transaction:
  a failure during the second replacement can leave the first file updated.
- Failed parse or render attempts do not remove older output files. A pre-existing
  diagram may therefore be stale after a failed run; use the exit code.

## Examples

```bash
# SVG only, next to the input file:
python -m opm_graphviz examples/supported.opl

# SVG plus DOT in build/:
python -m opm_graphviz examples/supported.opl -o build/supported.svg --dot

# Report the intentionally invalid example; no outputs are written:
python -m opm_graphviz examples/diagnostics.opl -o build/diagnostics.svg
```

The earlier `python -m examples.render_supported` command still renders the
hand-constructed model. Use this CLI to render changes made to `.opl` files.
