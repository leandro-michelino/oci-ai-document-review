#!/usr/bin/env python3
"""Render each native draw.io page to a PNG, independent of CLI page-index changes."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs/assets"
STEM = "oci-ai-document-review-architecture"


def render(drawio: str, scale: float = 1.5):
    document = ET.parse(ASSETS / f"{STEM}.drawio").getroot()
    with tempfile.TemporaryDirectory(prefix="oci-diagram-render-") as temporary:
        for index, page in enumerate(document.findall("diagram")):
            single = ET.Element("mxfile", host="ocidraw", type="device")
            single.append(copy.deepcopy(page))
            source = Path(temporary) / f"{page.get('id')}.drawio"
            ET.ElementTree(single).write(source, encoding="utf-8", xml_declaration=True)
            suffix = "" if index == 0 else f"-{page.get('id')}"
            target = ASSETS / f"{STEM}{suffix}.png"
            # Never mistake a stale export for successful rendering.
            export = Path(temporary) / f"{page.get('id')}.png"
            subprocess.run(
                [
                    drawio,
                    "-x",
                    "-f",
                    "png",
                    "-s",
                    str(scale),
                    "-b",
                    "20",
                    "-o",
                    str(export),
                    str(source),
                    "--no-sandbox",
                    "--disable-gpu",
                ],
                check=True,
                timeout=90,
            )
            if not export.is_file():
                raise RuntimeError(f"draw.io did not produce {page.get('id')}")
            shutil.copyfile(export, target)
            print(target.relative_to(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--drawio",
        default=shutil.which("drawio")
        or "/Applications/draw.io.app/Contents/MacOS/draw.io",
    )
    parser.add_argument("--scale", type=float, default=1.5)
    args = parser.parse_args()
    if not 0 < args.scale <= 5:
        parser.error("Scale must be greater than 0 and no greater than 5.")
    render(args.drawio, args.scale)


if __name__ == "__main__":
    main()
