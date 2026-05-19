"""Sochař Shopyon — polotovar v2.0 → Custom Format 48267 XML.

Cílový formát (Shopyon – Atos VARIANT v2, validován proti Igorovu vzor.xml, tiket 0004071):

<offers>
  <o id="{item_group_id}" price="{master_price_czk}" avail="yes|no" stock="{stock}" url="">
    <name>{title_cz}</name>
    <desc><![CDATA[{description_cz}]]></desc>
    <cat>{category_path_cz | pipe-separated}</cat>
    <params>
      <param><name>Výška [cm]</name><val>69</val></param>  <!-- obecné -->
    </params>
    <imgs>
      <img main="1">url_hlavni</img>
      <img>url_dalsi</img>
    </imgs>
    <variants>
      <variant id="{variant.id}" price="{czk}" avail="yes|no" stock="{stock}">
        <params>
          <param><name>Barva</name><val>tyrkysová</val></param>
          <param><name>Materiál</name><val>Samet</val></param>
        </params>
      </variant>
    </variants>
  </o>
</offers>

AK-1 až AK-8 (Igor, tiket 0004071, 17.4.2026):
  AK-1: variantní params = jen Barva a Materiál
  AK-2: obecné params (rozměry, nosnost) na master úrovni
  AK-3: title_cz = obecný název bez barvy
  AK-4: CDATA pro desc
  AK-5: category oddělovač |
  AK-6: hlavní obrázek = <img main="1">url</img> (dle vzor.xml)
  AK-7: EAN = pokud chybí, vynechat
  AK-8: kód výrobce = do params nebo vynechat

Změny:
  15.5.2026 — Fix AK-6: <main url="..."/> → <img main="1">url</img> dle vzor.xml

Usage:
    python procentov/socha_shopyon.py --polotovar out/polotovar_atos_milo.json --out out/atos_milo.xml
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import argparse
import hashlib
import json
from pathlib import Path

from lxml import etree


# Variantní atributy, které se přesunou do <variant><params>
# Ostatní attrs_cz (is_variant=False) zůstanou na master úrovni
VARIANT_PARAM_NAMES_CZ = {"Barva", "Materiál"}

# Atributy MIMO výstup (interní/technické — nevhodné pro zákazníka)
EXCLUDE_PARAM_NAMES_CZ = {"Kód výrobce", "EAN", "Složení materiálu"}


def avail_str(avail: str) -> str:
    """Převede availability na Shopyon string."""
    return "yes" if avail == "in_stock" else "no"


def build_xml(polotovar_data: dict) -> bytes:
    """Sestaví XML dle Custom Formátu 48267.

    Args:
        polotovar_data: Načtený polotovar JSON (dict)

    Returns:
        XML jako bytes (UTF-8, s XML deklarací)
    """
    root = etree.Element("offers")

    for product in polotovar_data["products"]:
        # === Master produkt <o> ===
        master_price = str(product["price_czk"]["value"])
        master_avail = avail_str(product["availability"])
        master_stock = str(product.get("stock_quantity") or 0)
        # URL: bereme z první varianty, která ji má — pro demo OK
        master_url = ""
        for v in product.get("variants", []):
            if v.get("url"):
                master_url = v["url"]
                break

        o = etree.SubElement(root, "o",
                             id=product["item_group_id"],
                             price=master_price,
                             avail=master_avail,
                             stock=master_stock,
                             url=master_url)

        # <name>
        name_el = etree.SubElement(o, "name")
        name_el.text = product["title_cz"]

        # <desc> s CDATA
        desc_el = etree.SubElement(o, "desc")
        desc_el.text = etree.CDATA(product.get("description_cz") or "Popis bude doplněn")

        # <cat> — kategorie s | oddělovačem (AK-5)
        cat_el = etree.SubElement(o, "cat")
        cat_el.text = " | ".join(product.get("category_path_cz") or [])

        # <params> — obecné parametry na master úrovni (AK-2)
        # attrs_cz kde is_variant=False, mimo excluded set
        general_params = [
            a for a in product.get("attrs_cz", [])
            if not a.get("is_variant", False)
            and a.get("name_cz") not in EXCLUDE_PARAM_NAMES_CZ
        ]
        if general_params:
            params_el = etree.SubElement(o, "params")
            for attr in general_params:
                p = etree.SubElement(params_el, "param")
                n = etree.SubElement(p, "name")
                n.text = attr["name_cz"]
                v = etree.SubElement(p, "val")
                v.text = str(attr["value_cz"])

        # <imgs> — obrázky dle vzor.xml (AK-6):
        #   hlavní: <img main="1">url</img>
        #   ostatní: <img>url</img>
        imgs_el = etree.SubElement(o, "imgs")
        if product.get("image_link"):
            main_img = etree.SubElement(imgs_el, "img")
            main_img.set("main", "1")
            main_img.text = product["image_link"]
        for img in product.get("additional_image_links", []):
            img_url = img.get("url") if isinstance(img, dict) else str(img)
            if img_url:
                img_el = etree.SubElement(imgs_el, "img")
                img_el.text = img_url

        # <variants>
        variants_el = etree.SubElement(o, "variants")
        for variant in product.get("variants", []):
            variant_price = str(variant["price_czk"]["value"])
            variant_avail = avail_str(variant["availability"])
            variant_stock = str(variant.get("stock_quantity") or 0)

            v_el = etree.SubElement(variants_el, "variant",
                                    id=variant["id"],
                                    price=variant_price,
                                    avail=variant_avail,
                                    stock=variant_stock)

            # Přidat EAN jako atribut varianty, pokud existuje (AK-7)
            if variant.get("ean"):
                v_el.set("ean", str(variant["ean"]))

            # <params> — jen variantní attrs (Barva, Materiál) (AK-1)
            variant_params = [
                a for a in variant.get("variant_attributes", [])
                if a.get("is_variant", True)
                and a.get("name_cz") in VARIANT_PARAM_NAMES_CZ
            ]
            if variant_params:
                vp_el = etree.SubElement(v_el, "params")
                for attr in variant_params:
                    p = etree.SubElement(vp_el, "param")
                    n = etree.SubElement(p, "name")
                    n.text = attr["name_cz"]
                    v_val = etree.SubElement(p, "val")
                    v_val.text = str(attr["value_cz"])

    # Serializace — pretty print, XML deklarace, UTF-8
    xml_bytes = etree.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True
    )

    return xml_bytes


def validate_xml(xml_bytes: bytes, expected_products: int) -> dict:
    """Základní strukturální validace výstupního XML.

    Vrací dict s klíči: valid (bool), errors (list), stats (dict).
    """
    errors = []

    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        return {"valid": False, "errors": [f"XML syntax error: {e}"], "stats": {}}

    products = root.findall("o")
    variants_total = sum(len(p.findall(".//variants/variant")) for p in products)
    missing_name = sum(1 for p in products if p.findtext("name") is None)
    missing_desc = sum(1 for p in products if p.find("desc") is None)
    # AK-6: hlavní obrázek = <img main="1"> uvnitř <imgs>
    missing_imgs = sum(1 for p in products if p.find('imgs/img[@main="1"]') is None)

    stats = {
        "products": len(products),
        "variants_total": variants_total,
        "missing_name": missing_name,
        "missing_desc": missing_desc,
        "missing_imgs": missing_imgs,
    }

    if len(products) != expected_products:
        errors.append(f"Počet produktů: {len(products)}, očekáváno {expected_products}")
    if missing_name > 0:
        errors.append(f"Chybí <name> u {missing_name} produktů")
    if missing_desc > 0:
        errors.append(f"Chybí <desc> u {missing_desc} produktů")
    if missing_imgs > 0:
        errors.append(f"Chybí <img main=\"1\"> u {missing_imgs} produktů")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "stats": stats
    }


def main():
    parser = argparse.ArgumentParser(description="Sochař Shopyon — polotovar → XML CF48267")
    parser.add_argument("--polotovar", default="out/polotovar_atos_milo.json", help="Cesta k polotovar JSON")
    parser.add_argument("--out", default="out/atos_milo.xml", help="Výstupní XML soubor")
    args = parser.parse_args()

    polotovar_path = Path(args.polotovar)
    out_path = Path(args.out)

    # [1/4] Načti polotovar
    print(f"[1/4] Načítám polotovar: {polotovar_path}")
    if not polotovar_path.exists():
        print(f"[ERROR] Polotovar neexistuje: {polotovar_path}")
        sys.exit(1)

    with open(polotovar_path, encoding="utf-8") as f:
        polotovar_data = json.load(f)

    product_count = len(polotovar_data.get("products", []))
    variant_count = sum(len(p.get("variants", [])) for p in polotovar_data["products"])
    print(f"[OK] Načteno {product_count} master produktů, {variant_count} variant celkem")

    # [2/4] Sestav XML
    print(f"[2/4] Sestavuji XML (Custom Formát 48267)...")
    try:
        xml_bytes = build_xml(polotovar_data)
    except Exception as e:
        print(f"[ERROR] build_xml selhal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    print(f"[OK] XML sestaveno: {len(xml_bytes):,} bytes")

    # [3/4] Validace
    print(f"[3/4] Validace XML...")
    result = validate_xml(xml_bytes, expected_products=product_count)
    for err in result["errors"]:
        print(f"  [WARN] {err}")
    stats = result["stats"]
    print(f"  Produkty: {stats.get('products')}, varianty: {stats.get('variants_total')}")
    print(f"  Chybí name: {stats.get('missing_name')}, desc: {stats.get('missing_desc')}, imgs: {stats.get('missing_imgs')}")
    if result["valid"]:
        print(f"[OK] Validace prošla")
    else:
        print(f"[WARN] Validace má chyby — kontroluj výstup")

    # [4/4] Zápis
    print(f"[4/4] Ukládám: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: tmp → rename
    tmp_path = out_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "wb") as f:
            f.write(xml_bytes)
        tmp_path.replace(out_path)
    except Exception as e:
        print(f"[ERROR] Zápis selhal: {e}")
        sys.exit(1)

    # Ověření
    if not out_path.exists():
        print(f"[ERROR] Soubor nebyl vytvořen: {out_path}")
        sys.exit(1)
    size = out_path.stat().st_size
    if size == 0:
        print(f"[ERROR] Soubor je prázdný!")
        sys.exit(1)
    sha256 = hashlib.sha256(xml_bytes).hexdigest()

    print(f"[SAVED] {out_path}")
    print(f"  Velikost: {size:,} bytes")
    print(f"  SHA256: {sha256}")
    print(f"\n[SUCCESS] XML vygenerováno: {out_path}")


if __name__ == "__main__":
    main()
