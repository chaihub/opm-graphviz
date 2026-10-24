"""Graphviz rendering for the supported single-diagram OPM model."""

import base64
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

import graphviz

from .model import Affiliation, EntityKind, Essence, LinkKind, Model

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
XLINK = "http://www.w3.org/1999/xlink"
ET.register_namespace("xlink", XLINK)
_LEGEND_PATH = Path(__file__).resolve().parents[1] / "docs" / "OPM legend.drawio.png"

# Model subject -> target order is preserved. Tail is subject, head is target.
# These are depiction choices from README.md, not generic OPM defaults.
_MARKERS = {
    LinkKind.AGGREGATION: ("normal", "none"),
    LinkKind.EXHIBITION: ("tee", "none"),
    LinkKind.SPECIALIZATION: ("none", "onormal"),
    LinkKind.INSTANTIATION: ("none", "curve"),
    LinkKind.TAGGED: ("none", "vee"),
    LinkKind.TAGGED_BIDIRECTIONAL: ("lvee", "lvee"),
    LinkKind.CONSUMPTION: ("onormal", "none"),
    LinkKind.RESULT: ("none", "onormal"),
    LinkKind.EFFECT: ("onormal", "onormal"),
    LinkKind.AGENT: ("none", "dot"),
    LinkKind.INSTRUMENT: ("odot", "none"),
}
_TAGGED = {LinkKind.TAGGED, LinkKind.TAGGED_BIDIRECTIONAL}


def _text(value: str) -> str:
    # Names are plain text, even if they look like HTML or Graphviz escapes.
    return graphviz.nohtml(graphviz.escape(value))


def to_dot(model: Model, *, include_legend: bool = True) -> graphviz.Digraph:
    """Return DOT with automatic layout and all symbols except physical shadows.

    Requires a model with valid references. Use the parser API to validate OPL
    input first. Synthetic IDs keep names containing colons or markup safe.
    """
    model.validate_integrity()
    dot = graphviz.Digraph("opm", engine="dot", format="svg")
    dot.attr(compound="true", rankdir="TB", bgcolor="white", pad="0.20",
             nodesep="0.45", ranksep="0.70", fontname="DejaVu Sans",
             outputorder="edgesfirst")
    dot.attr("node", fontname="DejaVu Sans", fontsize="12", fontcolor="#18222c",
             margin="0.16,0.10", penwidth="2", fillcolor="white")
    dot.attr("edge", fontname="DejaVu Sans", fontsize="10", color="#374151",
             fontcolor="#374151", penwidth="1.3", arrowsize="0.85")

    states_by_owner = {entity.name: [] for entity in model.entities}
    for index, state in enumerate(model.states):
        states_by_owner[state.owner].append((index, state))

    endpoints = {}
    clusters = {}
    for index, entity in enumerate(model.entities):
        node_id = f"e{index}"
        color = "#228b22" if entity.kind is EntityKind.OBJECT else "#2459b3"
        style = "dashed,filled" if entity.affiliation is Affiliation.ENVIRONMENTAL else "filled"
        attrs = {"id": node_id, "color": color, "style": style, "penwidth": "2",
                 "fillcolor": "white", "class": "opm-entity"}
        states = states_by_owner[entity.name]
        if states:
            cluster_id = f"cluster_{node_id}"
            clusters[entity.name] = cluster_id
            # Edges route toward an internal state but are clipped at the parent
            # boundary. No visible procedural edge attaches to an object state.
            endpoints[entity.name] = f"s{states[0][0]}"
            with dot.subgraph(name=cluster_id) as cluster:
                cluster.attr(**attrs, label=_text(entity.name), labelloc="t",
                             labeljust="c", fontsize="12", fontcolor="#18222c",
                             margin="18")
                with cluster.subgraph() as row:
                    row.attr(rank="same")
                    for state_index, state in states:
                        row.node(f"s{state_index}", label=_text(state.name),
                                 id=f"s{state_index}", shape="box", style="rounded,filled",
                                 color="#777777", **{"class": "opm-state"})
                    # Invisible ordering edges are layout scaffolding, not links.
                    for left, right in zip(states, states[1:]):
                        row.edge(f"s{left[0]}", f"s{right[0]}", style="invis", arrowhead="none")
        else:
            endpoints[entity.name] = node_id
            dot.node(node_id, label=_text(entity.name),
                     shape="box" if entity.kind is EntityKind.OBJECT else "ellipse", **attrs)

    for index, link in enumerate(model.links):
        if link.kind in _TAGGED:
            if not link.label:
                raise ValueError("Tagged links require a nonempty label")
        elif link.label is not None:
            raise ValueError("Only tagged links may carry a label")
        tail, head = _MARKERS[link.kind]
        direction = "both" if tail != "none" and head != "none" else (
            "back" if tail != "none" else "forward")
        attrs = {"id": f"l{index}", "class": "opm-link", "dir": direction,
                 "arrowtail": tail, "arrowhead": head}
        if link.subject in clusters:
            attrs["ltail"] = clusters[link.subject]
        if link.target in clusters:
            attrs["lhead"] = clusters[link.target]
        if link.kind in _TAGGED:
            attrs["color"] = "#999999"
            attrs["style"] = "dotted"
        if link.label is not None:
            attrs["label"] = _text(link.label)
        dot.edge(endpoints[link.subject], endpoints[link.target], **attrs)
    if include_legend:
        if not _LEGEND_PATH.is_file():
            raise FileNotFoundError(f"Legend image not found: {_LEGEND_PATH}")
        with dot.subgraph() as legend:
            legend.attr(rank="sink")
            legend.node("opm_legend", label="", id="opm-legend",
                        shape="box", style="solid,filled", color="black",
                        fillcolor="white", penwidth="1", margin="0.12,0.12",
                        image=str(_LEGEND_PATH), imagescale="true",
                        **{"class": "opm-legend"})
        for endpoint in endpoints.values():
            dot.edge(endpoint, "opm_legend", style="invis", arrowhead="none")
    return dot


def _finish_svg(raw: bytes, model: Model) -> bytes:
    """Annotate SVG and add offset silhouette shadows to outer shapes only.

    Cloned vector geometry avoids browser-specific SVG filter support. The
    original white-filled shape covers the shadow interior, leaving an offset
    outline. Text, states, and arrowheads are never cloned or shadowed.
    """
    root = ET.fromstring(raw)
    groups = {group.get("id"): group for group in root.iter(f"{{{SVG}}}g")}
    if "opm-legend" in groups:
        image = groups["opm-legend"].find(f"{{{SVG}}}image")
        if image is None:
            raise ValueError("Graphviz did not render the legend image")
        encoded = base64.b64encode(_LEGEND_PATH.read_bytes()).decode("ascii")
        image.set(f"{{{XLINK}}}href", f"data:image/png;base64,{encoded}")
    elements = [(f"e{i}", e) for i, e in enumerate(model.entities)]
    elements += [(f"s{i}", s) for i, s in enumerate(model.states)]
    elements += [(f"l{i}", link) for i, link in enumerate(model.links)]
    for element_id, element in elements:
        group = groups[element_id]
        group.set("data-source-path", element.source.path)
        group.set("data-source-line", str(element.source.line))

    for index, entity in enumerate(model.entities):
        group = groups[f"e{index}"]
        group.set("data-name", entity.name)
        group.set("data-kind", entity.kind.value)
        group.set("data-essence", entity.essence.value)
        group.set("data-affiliation", entity.affiliation.value)
        if entity.essence is Essence.PHYSICAL:
            shape = next(child for child in group
                         if child.tag in {f"{{{SVG}}}polygon", f"{{{SVG}}}ellipse", f"{{{SVG}}}path"})
            shadow = deepcopy(shape)
            shadow.attrib.pop("id", None)
            shadow.attrib.pop("stroke-dasharray", None)
            shadow.set("class", "opm-shadow")
            shadow.set("fill", "#475569")
            shadow.set("stroke", "#475569")
            shadow.set("opacity", "0.25")
            shadow.set("transform", "translate(3 3)")
            group.insert(list(group).index(shape), shadow)
    for index, state in enumerate(model.states):
        groups[f"s{index}"].set("data-owner", state.owner)
    for index, link in enumerate(model.links):
        group = groups[f"l{index}"]
        group.set("data-kind", link.kind.value)
        group.set("data-subject", link.subject)
        group.set("data-target", link.target)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def render_svg(model: Model, output: Path, *, include_legend: bool = True) -> Path:
    """Render a complete SVG, including shadows; return the output path.

    Uses the system `dot` executable through the Python graphviz package.
    Output directories are created; an existing output file is replaced only
    after rendering succeeds. Graphviz execution errors propagate to the caller.
    """
    svg = _finish_svg(to_dot(model, include_legend=include_legend).pipe(format="svg"), model)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(svg)
    return output
