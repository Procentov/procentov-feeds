"""Manual run only — vygeneruje Milo fixture z plneho ATOS feedu."""
import xml.etree.ElementTree as ET
from pathlib import Path

# Paths
source_xml = Path(r"C:\work\mergado-api\atos_source_feed.xml")
output_xml = Path(__file__).parent / "atos_milo_sample.xml"

print(f"Reading source XML: {source_xml}")
tree = ET.parse(source_xml)
root = tree.getroot()

print(f"Creating new root element...")
new_root = ET.Element(root.tag)

milo_count = 0
for o in root.iter("o"):
    cat = o.findtext("cat", "") or ""
    if "MILO" in cat.upper():
        new_root.append(o)
        milo_count += 1

print(f"Found {milo_count} Milo offers")
print(f"Writing fixture to: {output_xml}")

ET.ElementTree(new_root).write(
    output_xml,
    encoding="utf-8",
    xml_declaration=True
)

print("Done!")
