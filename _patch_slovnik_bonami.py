"""Patch slovnik.json - oprava prekladů dle Bonami terminologie (schváleno Mirek 12.5.2026)."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

PATH = r"C:\work\xml-feedy\procentov\slovnik\slovnik.json"

OPRAVY = {
    "Głębokość całkowita [cm]":  "Hloubka [cm]",
    "Szerokość całkowita [cm]":  "Šířka [cm]",
    "Wysokość całkowita [cm]":   "Výška [cm]",
    "Maksymalna waga obciążenia [kg]": "Nosnost [kg]",
}

with open(PATH, encoding="utf-8") as f:
    data = json.load(f)

atributy = data["namespaces"]["atributy"]
for klic, nova_hodnota in OPRAVY.items():
    if klic in atributy:
        stara = atributy[klic]
        atributy[klic] = nova_hodnota
        print(f"[OK] {klic!r}: {stara!r} → {nova_hodnota!r}")
    else:
        print(f"[SKIP] {klic!r} nenalezen")

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("[DONE] slovnik.json uložen")
