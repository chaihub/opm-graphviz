# opm-graphviz

A diagram generator + renderer for Object Process Language (OPL) descriptions. See OPM description at https://en.wikipedia.org/wiki/Object_Process_Methodology .

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
      - Aggregation/Participation = solid normal arrow at A
      - Exhibition/Characterization = tee arrow at A
      - Generaliztion/Specialization = open normal arrow at A
      - Classification/Instantiation =  curve arrow at A
      - User-tagged single (as per text given by user) = vee arrow at B with text
      - User-tagged bidirectional (as per text given by user) = lvee arrow at A and B with text
3. Procedural Links between Entities:
   - Transforming Links:
      - Consumption (B consumes A) [A,B = O,P]
      - Result (B yields A) [A,B = O,P]
      - Effect (B affects A) [A,B = O,P]
      - Depiction:
         - Consumption = Hollow arrow at B
         - Result = Hollow arrow at A
         - Effect = Hollow arrow at A,B
   - Enabling Links:
      - Agent (A handles B) [A,B = O,P where A is human]
      - Instrument (B requires A) [A,B = O,P where A is inanimate]
      - Depiction:
         - Agent = Filled dot at B
         - Instrument = Hollow dot at B

An OPL-like text description of the diagram is parsed and rendered. A warning is generated for every statement that is out of this scope.

Scope is one diagram; no hierarchy, state transitions, or state-qualified links.

Any feature not explicitly mentioned above is unsupported.

## Draft Input Syntax

See the [draft syntax specification](docs/syntax.md), the
[valid coverage example](examples/supported.opl), and the
[diagnostic example](examples/diagnostics.opl). These propose the input contract;
the parser and renderer are not implemented yet.

## Internal Model

See [model documentation](docs/model.md) for data structures and endpoint
conventions. From the repository root with the virtual environment activated:

```bash
python -m examples.supported_model
python -m unittest discover -s tests -v
```

## TODO
[x] - Write a short syntax specification and example input. Include one example of every selected feature, plus unsupported and invalid statements with their expected diagnostics.
- [x] Create a minimal internal model. Represent entities, states, typed links, and source locations independently of Graphviz. This will also support your later model-to-code comparisons.
- Build a rendering proof of concept from that model. Produce one SVG containing every symbol and styling combination. Review visual correctness before adding parsing.
- Implement the parser and validator. Parse declarations and relationships, resolve references, then check the endpoint restrictions in the README.
- Connect a small CLI. Generate SVG and optionally DOT, reporting diagnostics with line numbers. Clearly report when unsupported statements make the diagram incomplete.
- Add focused tests. Check relationship direction, state ownership, invalid references, unsupported statements, and successful SVG rendering.

## License
MIT