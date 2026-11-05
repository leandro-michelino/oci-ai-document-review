#!/usr/bin/env python3
"""Build the repository banner and GitHub social preview as editable SVG and PNG."""

from html import escape
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs/assets"


def svg(version, social=False):
    height = 800 if social else 500
    cards_y = 540 if social else 285
    title = (
        '<text x="72" y="260" class="title">OCI AI</text>'
        '<text x="72" y="350" class="title">Document Review</text>'
        if social
        else '<text x="72" y="170" class="title">OCI AI Document Review</text>'
    )
    subtitle_y = 422 if social else 226
    cards = []
    stages = [
        ("Upload + preserve", "Private Object Storage"),
        ("OCR + extraction", "Local text + Document Understanding"),
        ("AI + risk routing", "Generative AI + compliance catalog"),
        ("Human decision", "Review, workflow and audit"),
    ]
    for index, (label, detail) in enumerate(stages):
        x = 72 + index * 376
        cards.append(
            f'<rect x="{x}" y="{cards_y}" width="300" height="110" rx="14" fill="white" stroke="#9eb8b2"/>'
        )
        cards.append(
            f'<text x="{x+20}" y="{cards_y+41}" class="stage">{escape(label)}</text>'
        )
        cards.append(
            f'<text x="{x+20}" y="{cards_y+76}" class="detail">{escape(detail)}</text>'
        )
        if index < 3:
            cards.append(
                f'<path d="M {x+315} {cards_y+55} H {x+359}" stroke="#305c60" stroke-width="3" marker-end="url(#arrow)"/>'
            )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{1280 if social else 1600}" height="{640 if social else 500}" viewBox="0 0 1600 {height}" role="img" aria-labelledby="title description">
<title id="title">OCI AI Document Review {escape(version)}</title>
<desc id="description">Oracle Cloud Infrastructure reference application for document extraction, AI review and human decisions.</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L7,4 L0,8" fill="none" stroke="#305c60" stroke-width="1.5"/></marker></defs>
<style>text{{font-family:Arial,Helvetica,sans-serif;fill:#312d2a}}.title{{font-size:{80 if social else 68}px;font-weight:700;letter-spacing:-1px}}.stage{{font-size:23px;font-weight:700}}.detail{{font-size:14px;fill:#4c6666}}</style>
<rect width="1600" height="{height}" fill="#f5f2ed"/>
<rect width="1600" height="10" fill="#c74634"/>
<circle cx="1550" cy="{height-5}" r="180" fill="#e6ebe4"/>
<text x="72" y="77" font-size="21" fill="#305c60">ORACLE CLOUD INFRASTRUCTURE</text>
<rect x="1306" y="45" width="218" height="45" rx="22" fill="#c74634"/>
<text x="1415" y="75" text-anchor="middle" font-size="21" font-weight="700" style="fill:white">{escape(version)} · MVP</text>
{title}
<text x="72" y="{subtitle_y}" font-size="24" style="fill:#4c6666">From business documents to evidence-led human review.</text>
{''.join(cards)}
<text x="72" y="{height-50}" font-size="18">Streamlit · Terraform · Ansible · Editable draw.io architecture</text>
<text x="1524" y="{height-50}" text-anchor="end" font-size="18" style="fill:#4c6666">Leandro Michelino | ACE</text>
</svg>"""


def main():
    import cairosvg

    version = runpy.run_path(str(ROOT / "src/version.py"))["VERSION_LABEL"]
    for social, name in [
        (False, "oci-ai-document-review-banner"),
        (True, "oci-ai-document-review-social-preview"),
    ]:
        source = ASSETS / f"{name}.svg"
        source.write_text(svg(version, social) + "\n")
        cairosvg.svg2png(url=str(source), write_to=str(ASSETS / f"{name}.png"))
        print(f"Generated {name}.svg and {name}.png")


if __name__ == "__main__":
    main()
