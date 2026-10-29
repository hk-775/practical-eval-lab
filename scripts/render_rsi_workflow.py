"""Export static companions of the recorded viewer's improvement loop."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

from benchmarks.recursive_improvement.reporting import workflow_svg

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/architecture/rsi-improvement-loop"
NODES = ((20, "Observe failures"), (210, "Propose edits"), (400, "Execute"),
         (590, "Verify"), (780, "Retain version"))
CAPTION = "Accepted optimizer edits guide the next generation"


def svg():
    value = workflow_svg().replace(
        '<svg class="workflow"',
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="150" class="workflow"', 1)
    style = (
        "<style>svg{background:#F8F5F0}rect{fill:#0D1B2A}"
        "text{fill:#F8F5F0;font:650 14px Arial,sans-serif}"
        "text.loop-label{fill:#546474;font-size:12px;font-weight:400}"
        ".flow-line{fill:none;stroke:#007B95;stroke-width:2;stroke-dasharray:5 5}</style>"
    )
    return value.replace("<defs>", style + "<defs>", 1) + "\n"


def drawio():
    document = ET.Element("mxfile", host="app.diagrams.net")
    diagram = ET.SubElement(document, "diagram", id="rsi-improvement-loop",
                            name="Bounded improvement loop")
    model = ET.SubElement(diagram, "mxGraphModel", page="1", pageScale="1",
                          pageWidth="960", pageHeight="150", background="#F8F5F0")
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    for index, (x, label) in enumerate(NODES):
        cell = ET.SubElement(root, "mxCell", id=f"node-{index}", value=label, vertex="1", parent="1",
                             style="rounded=1;arcSize=15;fillColor=#0D1B2A;strokeColor=none;"
                                   "fontColor=#F8F5F0;fontFamily=Arial;fontSize=14;fontStyle=1;")
        ET.SubElement(cell, "mxGeometry", x=str(x), y="35", width="160", height="54",
                      attrib={"as": "geometry"})
    paths = [[(start + 3, 62), (start + 26, 62)] for start in (180, 370, 560, 750)]
    paths.append([(860, 94), (860, 120), (100, 120), (100, 96)])
    for index, points in enumerate(paths):
        cell = ET.SubElement(root, "mxCell", id=f"edge-{index}", edge="1", parent="1",
                             style="rounded=0;endArrow=block;endFill=1;strokeColor=#007B95;"
                                   "strokeWidth=2;dashed=1;dashPattern=5 5;")
        geometry = ET.SubElement(cell, "mxGeometry", relative="1", attrib={"as": "geometry"})
        for tag, (x, y) in (("sourcePoint", points[0]), ("targetPoint", points[-1])):
            ET.SubElement(geometry, "mxPoint", x=str(x), y=str(y), attrib={"as": tag})
        if len(points) > 2:
            middle = ET.SubElement(geometry, "Array", attrib={"as": "points"})
            for x, y in points[1:-1]:
                ET.SubElement(middle, "mxPoint", x=str(x), y=str(y))
    cell = ET.SubElement(root, "mxCell", id="caption", value=CAPTION, vertex="1", parent="1",
                         style="text;fillColor=none;strokeColor=none;fontColor=#546474;"
                               "fontFamily=Arial;fontSize=12;align=center;")
    ET.SubElement(cell, "mxGeometry", x="80", y="127", width="800", height="23",
                  attrib={"as": "geometry"})
    ET.indent(document)
    return ET.tostring(document, encoding="unicode", xml_declaration=True) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", action="store_true", help="Render a PNG using isolated Chromium")
    args = parser.parse_args()
    TARGET.with_suffix(".svg").write_text(svg(), encoding="utf-8")
    TARGET.with_suffix(".drawio").write_text(drawio(), encoding="utf-8")
    if args.png:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 960, "height": 150}, device_scale_factor=2)
                page.set_content('<body style="margin:0;background:#F8F5F0">' + svg() + "</body>")
                page.locator("svg").screenshot(path=str(TARGET.with_suffix(".png")))
            finally:
                browser.close()
    print("Exported RSI workflow companions")


if __name__ == "__main__":
    main()
