"""Validate native diagram references, source coverage and explicit connector geometry."""

import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def test_all_native_pages_have_valid_connectors_and_cover_terraform():
    root = ET.parse(
        ROOT / "docs/assets/oci-ai-document-review-architecture.drawio"
    ).getroot()
    report = json.loads((ROOT / "docs/architecture_connections.json").read_text())
    declared = set()
    for path in (ROOT / "terraform").glob("*.tf"):
        declared.update(
            f"{kind}.{name}"
            for kind, name in re.findall(
                r'resource\s+"([^"]+)"\s+"([^"]+)"', path.read_text()
            )
        )
    represented = set()
    pages = root.findall("diagram")
    assert len(pages) == 4
    assert len({p.get("id") for p in pages}) == 4
    for page, page_report in zip(pages, report["pages"], strict=True):
        cells = page.findall(".//mxCell")
        byid = {c.get("id"): c for c in cells}
        assert len(cells) == len(byid)
        edges = [c for c in cells if c.get("edge") == "1"]
        assert len(edges) == len(page_report["connections"])
        assert page_report["layout_warnings"] == []
        for cell in cells:
            represented.update(cell.get("resourceRefs", "").split())
        for edge in edges:
            assert edge.get("source") in byid and edge.get("target") in byid
            assert edge.get("sourceEvidence")
            for name in re.findall(
                r"(?:src|terraform|functions|docs|oda|ansible)/[\w./-]+\.(?:py|tf|md|yaml|yml)",
                edge.get("sourceEvidence"),
            ):
                assert (ROOT / name).is_file(), name
    assert represented == declared == set(report["declared_resources"])
    assert report["unrepresented_resources"] == []


def test_explicit_connector_segments_are_orthogonal():
    root = ET.parse(
        ROOT / "docs/assets/oci-ai-document-review-architecture.drawio"
    ).getroot()
    for page in root.findall("diagram"):
        byid = {c.get("id"): c for c in page.findall(".//mxCell")}

        def geometry(identifier):
            cell = byid[identifier]
            g = cell.find("mxGeometry")
            x, y, w, h = (
                float(g.get(key, "0")) for key in ("x", "y", "width", "height")
            )
            parent = cell.get("parent")
            if parent not in {None, "0", "1"}:
                px, py, _, _ = geometry(parent)
                x += px
                y += py
            return x, y, w, h

        for edge in byid.values():
            points = edge.findall('./mxGeometry/Array[@as="points"]/mxPoint')
            if not points:
                continue
            style = dict(
                item.split("=", 1)
                for item in edge.get("style").split(";")
                if "=" in item
            )
            anchors = []
            for end, port in (("source", "exit"), ("target", "entry")):
                x, y, w, h = geometry(edge.get(end))
                anchors.append(
                    (x + float(style[port + "X"]) * w, y + float(style[port + "Y"]) * h)
                )
            route = [
                anchors[0],
                *[(float(p.get("x")), float(p.get("y"))) for p in points],
                anchors[1],
            ]
            for a, b in zip(route, route[1:]):
                assert abs(a[0] - b[0]) < 0.1 or abs(a[1] - b[1]) < 0.1, (
                    page.get("id"),
                    edge.get("value"),
                    a,
                    b,
                )
