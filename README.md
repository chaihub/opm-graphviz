# opm-graphviz

A diagram generator + renderer for Object Process Language (OPL) descriptions. See OPM description at https://en.wikipedia.org/wiki/Object_Process_Methodology . It uses the graphviz package for generating diagrams; see https://www.graphviz.org/ .

## Supported OPM Features
1. Entities: Object (O), Object State (OS) necessarily inside an Object, Process (P)
   - Objects and Processes can be either Physical or Informatical ("Essence" property)
   - Objects and Processes can be either Systemic or Environmental ("Affiliation" property)
   - Depiction:
      - Object = Rectangle, bold green outline, name inside
      - Object State = Rounded rectangle, bold grey outline, name inside
      - Process = Oval, bold blue outline, name inside
      - Physical Objects and Processes have a shadow around the outline
      - Environmental Objects and Processes have a dashed outline
2. Structural Links between Entities:
   - Aggregation/Participation (A consists of B) [A,B = O,O or P,P]
   - Exhibition/Characterization (A exhibits B) [A,B = O,O or O,P or P,O or P,P]
   - Generaliztion/Specialization (B is an A [A,B = O,O]) (B is A [A,B = P,P])
   - Classification/Instantiation (B is an instance of A) [A,B = O,O or P,P]
   - User-tagged single / bidirectional (as per text given by user) [A,B = O,O or P,P]
   - Depiction:
      - Aggregation/Participation = open box at A
      - Exhibition/Characterization = tee arrow at A
      - Generaliztion/Specialization = open diamond at A
      - Classification/Instantiation =  curve arrow at A
      - User-tagged one-way relation (as per text given by user) = light grey dotted line with a light grey vee arrow at B and text
      - User-tagged bidirectional relation (as per text given by user) = light grey dotted line with light grey lvee arrows at A and B and text
3. Procedural Links between Entities:
   - Transforming Links:
      - Consumption (B consumes A) [A,B = O,P]
      - Result (B yields A) [A,B = O,P]
      - Effect (B affects A) [A,B = O,P]
      - Depiction:
         - Consumption = filled arrow at B
         - Result = filled arrow at A
         - Effect = open arrow at A,B
   - Enabling Links:
      - Agent (A handles B) [A,B = O,P where A is human]
      - Instrument (B requires A) [A,B = O,P where A is inanimate]
      - Depiction:
         - Agent = filled dot at B
         - Instrument = open dot at B

An OPL-like text description of the diagram is parsed and rendered. A warning is generated for every statement that is out of this scope.

Scope is one diagram; no hierarchy, state transitions, or state-qualified links.

The visual constructs defined in OPM have been retained wherever possible, except when constrained by graphviz capabilities and making them more meaningful to me.

Conventions:
- In a collection of diagrams representing the same system, no two Objects or Processes (including child entities) should have the same name. E.g. there should not be an "Initialize" Process as a child of two different Processes, unless it is identical.
- Sequencing of child Processes is identified by the numeric index in the child's name, e.g. "1 Initialize_sim", "2 Execute_sim", etc.

Any feature not explicitly mentioned above is unsupported.

## Draft Input Syntax

See the [draft syntax specification](docs/syntax.md), the
[valid coverage example](examples/supported.opl), and the
[diagnostic example](examples/diagnostics.opl). The parser and validator implement
this input contract; a rendering proof of concept is available below.

## Command-Line Rendering

From the repository root with the virtual environment activated:

```bash
python -m opm_graphviz examples/supported.opl -o build/supported.svg --dot
```

This reads the OPL file and writes SVG plus optional DOT output. Omit `--dot`
for SVG only; omit `-o` to write beside the input file. Changes to the OPL file
are reflected the next time this command runs.

Diagnostics include file and line numbers. Unsupported statements produce an
explicit incomplete-diagram warning; errors prevent rendering. See the
[CLI documentation](docs/cli.md) for options and exit codes.

## Internal Model

See [model documentation](docs/model.md) for data structures and endpoint
conventions. From the repository root with the virtual environment activated:

```bash
python -m examples.supported_model
python -m unittest discover -s tests -v
```

## Rendering Proof of Concept

Render the programmatic example from the repository root with the virtual
environment activated:

```bash
python -m examples.render_supported
```

This writes [the SVG diagram](build/supported.svg) and its DOT source to `build/`.
The example uses the internal model directly; it does not parse OPL input.
The system Graphviz `dot` executable must be installed.
See [rendering documentation](docs/rendering.md) for the API, symbol mapping,
and limitations. Generated files in `build/` are Git-ignored.

## Parsing OPL Input

The parser reads UTF-8 OPL files and returns a validated model plus diagnostics:

```python
from opm_graphviz.parser import parse_file

result = parse_file("examples/supported.opl")
for diagnostic in result.diagnostics:
    print(diagnostic)
print(result.summary)
model = result.require_model()
```

Errors prevent model output. Unsupported statements generate warnings and an
incomplete-diagram summary. See [parser documentation](docs/parsing.md) for the
API and an example of rendering the parsed model. For terminal usage, see the
[CLI documentation](docs/cli.md).

## Testing

Run the full suite from the repository root with the virtual environment activated:

```bash
python -m unittest discover -s tests -v
```

Graphviz's `dot` executable must be available for the rendering tests; otherwise
those checks are skipped. See [test coverage](docs/testing.md) for the scope and
verification limits.

## TODO
- [x] Write a short syntax specification and example input. Include one example of every selected feature, plus unsupported and invalid statements with their expected diagnostics.
- [x] Create a minimal internal model. Represent entities, states, typed links, and source locations independently of Graphviz. This will also support your later model-to-code comparisons.
- [x] Build a rendering proof of concept from that model. Produce one SVG containing every symbol and styling combination. Review visual correctness before adding parsing.
- [x] Implement the parser and validator. Parse declarations and relationships, resolve references, then check the endpoint restrictions in the README.
- [x] Connect a small CLI. Generate SVG and optionally DOT, reporting diagnostics with line numbers. Clearly report when unsupported statements make the diagram incomplete.
- [x] Add focused tests. Check relationship direction, state ownership, invalid references, unsupported statements, and successful SVG rendering.
- [x] Add legend to generated graphs. Use the supplied image inside a thin black box below the diagram; `--no-legend` omits it.

## License
MIT