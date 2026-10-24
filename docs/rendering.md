# Rendering proof of concept

The renderer consumes a `Model`, constructed programmatically or returned by the
[OPL parser](parsing.md). This example still constructs its model programmatically.
The model and syntax rules remain unchanged.

## Running the example

Use the virtual environment, from the repository root:

```bash
python -m examples.render_supported
python -m unittest discover -s tests -v
```

The example writes `build/supported.svg` and `build/supported.dot`. Open the SVG
in a browser for the complete diagram. To choose a different destination:

```bash
python -m examples.render_supported /tmp/supported.svg
```

The existing Python `graphviz` dependency and a system Graphviz installation
providing `dot` are required. There are no new Python dependencies. Missing `dot`
or rendering failures raise Graphviz exceptions. Rendering tests skip explicitly
when `dot` is unavailable. Development verification used Graphviz 2.43.0.

## API

```python
from pathlib import Path
from examples.supported_model import build_model
from opm_graphviz.render import render_svg, to_dot

model = build_model()
dot = to_dot(model)
render_svg(model, Path("build/supported.svg"))
```

`to_dot` returns a `graphviz.Digraph`. `render_svg` runs Graphviz, adds shadows and
source metadata, creates missing output directories, and writes the final SVG.
An existing output file is replaced only after rendering succeeds. The example
also writes DOT for inspecting layout and marker attributes.

## Depictions

Objects use green rectangular outlines, processes blue ellipses, and states grey
rounded rectangles. Outlines are two points wide; environmental entities use
dashes. Physical entities receive a three-point offset grey vector shadow behind
the outer shape. Text and states do not inherit their owner's shadow or dashes.
Physical and environmental styling can be combined.

Objects with states are Graphviz clusters, with their names inside at the top.
States occupy a row in declaration order. Compound edges terminate at the object
boundary, not the state used internally as a routing anchor. Invisible ordering
edges control the state row and are not model relationships.

Model endpoints keep statement order. The table lists tail (subject) and head
(target) markers, independently of how layout places the entities:

| Kind | Tail | Head |
| --- | --- | --- |
| Aggregation | normal | none |
| Exhibition | tee | none |
| Specialization | none | onormal |
| Instantiation | none | curve |
| Tagged single | none | vee |
| Tagged bidirectional | lvee | lvee |
| Consumption | onormal | none |
| Result | none | onormal |
| Effect | onormal | onormal |
| Agent | none | dot |
| Instrument | odot | none |

Tagged links use light grey (`#999999`) dotted lines and light grey arrowheads. Only tagged links display
a label; label text retains the default dark color. Their text is preserved literally, including
quotes, ampersands, angle brackets, colons, and backslashes. Synthetic entity and
state IDs prevent names from being interpreted as Graphviz syntax.

SVG groups carry `opm-entity`, `opm-state`, or `opm-link` classes, synthetic IDs,
and source file/line metadata. Entities also carry their kind and attributes;
links carry their kind and semantic endpoints; states identify their owners.

## Scope and limitations

- Shadows are added after Graphviz renders SVG. Rendering the DOT directly will
  omit shadows and the extra source metadata. Use `render_svg` for final output.
- Automatic layout can produce crossings and crowded marker junctions in dense
  models. This prototype has no interactive editing or saved node positions.
- A single row of states can make an object wide. Wrapping states is deferred.
- Layout coordinates depend on Graphviz and installed fonts. Tests check symbols,
  containment, metadata, and label fidelity rather than exact pixel snapshots.
- `validate_integrity` runs before rendering. Use the parser API for complete
  validation of OPL input before passing its model to the renderer. The renderer rejects missing tagged labels and
  labels on other link types to avoid silently losing supplied information.
- The example covers 13 entities, 3 states, 19 links, all 11 link kinds, and all
  essence/affiliation combinations for objects and processes. Additional tests
  cover state-containing objects under all four styling combinations.
