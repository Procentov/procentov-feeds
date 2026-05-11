#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Procentov XML Feed Transformer - Sprint 1 (Milo furniture)

Účel:
    Načte polotovar atos_v1.0 (parquet), filtruje na Sprint 1 kategorie (Milo furniture),
    aplikuje fixní kurz PLN→CZK a cenové overridy z CSV, vyplivne intermediate XML
    v Heureka formátu s ITEMGROUP_ID.

Vstup:
    - C:/work/atos-polotovar/current/polotovar.parquet (10 MB, 348 variant Sprint 1)
    - C:/work/xml-feedy/procentov/cenove_overridy.csv (manuální cenové korekce)

Výstup:
    - C:/work/xml-feedy/procentov/out/procentov_intermediate.xml (Heureka XML feed)

Kurz:
    KOEFICIENT_PLN_NA_CZK = 11.115 (Sprint 1 hodnota, aktualizuj při pohybu kurzu >2 %)
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict

import pandas as pd
import pyarrow.parquet as pq
from lxml import etree

# ===== KONSTANTY =====

KOEFICIENT_PLN_NA_CZK = 11.115  # Sprint 1 hodnota, aktualizuj při pohybu kurzu >2 %
POLOTOVAR_PARQUET = r"C:\work\atos-polotovar\current\polotovar.parquet"
OVERRIDY_CSV = r"C:\work\xml-feedy\procentov\cenove_overridy.csv"
OUT_XML = r"C:\work\xml-feedy\procentov\out\procentov_intermediate.xml"
SPRINT1_KATEGORIE = "Fotel Milo"  # Filtr: 10 master groups (různé nohy), 348 variant (zjištěno fáze 2b)

# ===== LOGGING SETUP =====

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


# ===== FUNKCE =====

def load_polotovar() -> pd.DataFrame:
    """
    Načte polotovar parquet soubor.

    Returns:
        DataFrame s atos_v1.0 schématem

    Raises:
        FileNotFoundError: Pokud polotovar neexistuje
    """
    polotovar_path = Path(POLOTOVAR_PARQUET)
    if not polotovar_path.exists():
        raise FileNotFoundError(
            f"Polotovar nenalezen: {POLOTOVAR_PARQUET}\n"
            f"Zkontroluj, že běží upstream pipeline a soubor existuje."
        )

    logger.info(f"Nacitam polotovar: {POLOTOVAR_PARQUET}")
    start_time = time.time()

    # Načtení přes pyarrow (rychlejší pro parquet)
    table = pq.read_table(POLOTOVAR_PARQUET)
    df = table.to_pandas()

    elapsed = time.time() - start_time
    logger.info(f"  -> Nacteno {len(df)} zaznamu za {elapsed:.2f}s")

    return df


def filter_sprint1(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtruje DataFrame na Sprint 1 kategorie (Milo furniture).

    Cíl: 10 master groups, ~348 variant.

    Args:
        df: Vstupní DataFrame s celým polotovarem

    Returns:
        Filtrovaný DataFrame (očekáváno ~348 variant)
    """
    logger.info("Explorace: hledam Milo furniture...")
    start_time = time.time()

    # Strategie A: category_path_pl (list kategorií)
    # Pokud je category_path_pl list, musíme projít všechny elementy
    def has_milo_in_categories(cat_list):
        if cat_list is None or not isinstance(cat_list, list):
            return False
        return any("milo" in str(cat).lower() for cat in cat_list)

    mask_a = df['category_path_pl'].apply(has_milo_in_categories)
    count_a_variants = mask_a.sum()
    count_a_groups = df[mask_a]['item_group_id'].nunique() if count_a_variants > 0 else 0
    logger.info(f"  Strategie A (category_path_pl): {count_a_variants} variant, {count_a_groups} groups")

    # Strategie B: title_pl (název produktu) - zkus jen "Fotel Milo" (křesla)
    mask_b = df['title_pl'].str.contains('milo', case=False, na=False, regex=False)
    count_b_variants = mask_b.sum()
    count_b_groups = df[mask_b]['item_group_id'].nunique() if count_b_variants > 0 else 0
    logger.info(f"  Strategie B (title_pl 'milo'): {count_b_variants} variant, {count_b_groups} groups")

    # Strategie B2: title_pl - jen "Fotel Milo" (bez sof)
    mask_b2 = df['title_pl'].str.contains('fotel milo', case=False, na=False, regex=False)
    count_b2_variants = mask_b2.sum()
    count_b2_groups = df[mask_b2]['item_group_id'].nunique() if count_b2_variants > 0 else 0
    logger.info(f"  Strategie B2 (title_pl 'fotel milo'): {count_b2_variants} variant, {count_b2_groups} groups")

    # Strategie C: link (URL slug)
    mask_c = df['link'].str.contains('milo', case=False, na=False, regex=False)
    count_c_variants = mask_c.sum()
    count_c_groups = df[mask_c]['item_group_id'].nunique() if count_c_variants > 0 else 0
    logger.info(f"  Strategie C (link URL): {count_c_variants} variant, {count_c_groups} groups")

    # Strategie D: attrs_raw (může mít kategorii jako atribut)
    def has_milo_in_attrs(attrs):
        if attrs is None or not isinstance(attrs, dict):
            return False
        return any("milo" in str(v).lower() for v in attrs.values())

    mask_d = df['attrs_raw'].apply(has_milo_in_attrs)
    count_d_variants = mask_d.sum()
    count_d_groups = df[mask_d]['item_group_id'].nunique() if count_d_variants > 0 else 0
    logger.info(f"  Strategie D (attrs_raw): {count_d_variants} variant, {count_d_groups} groups")

    # Vyber vítěznou strategii: ta, která má 10 groups a ~348 variant
    strategies = [
        ('category_path_pl', mask_a, count_a_variants, count_a_groups),
        ('title_pl (milo)', mask_b, count_b_variants, count_b_groups),
        ('title_pl (fotel milo)', mask_b2, count_b2_variants, count_b2_groups),
        ('link', mask_c, count_c_variants, count_c_groups),
        ('attrs_raw', mask_d, count_d_variants, count_d_groups),
    ]

    # Hledáme strategii s 10 groups
    winner = None
    for name, mask, variants, groups in strategies:
        if groups == 10:
            winner = (name, mask, variants, groups)
            logger.info(f"  [OK] VITEZ: {name} - {variants} variant, {groups} groups")
            break

    if winner is None:
        # Žádná strategie nedala přesně 10 groups - vybereme nejbližší
        logger.warning("Zadna strategie nedala presne 10 groups! Vyberam nejblizsi...")
        # Seřadíme podle vzdálenosti od 10 groups
        strategies_sorted = sorted(strategies, key=lambda x: abs(x[3] - 10))
        winner = strategies_sorted[0]
        name, mask, variants, groups = winner
        logger.warning(f"  BEST MATCH: {name} - {variants} variant, {groups} groups (cil byl 10)")

    # Aplikuj vítěznou strategii
    name, mask, variants, groups = winner
    df_filtered = df[mask].copy()

    elapsed = time.time() - start_time
    logger.info(f"Filtrovano za {elapsed:.2f}s: {len(df_filtered)} variant, {groups} master groups")

    return df_filtered


def load_overridy() -> Dict[str, dict]:
    """
    Načte cenové overridy z CSV.

    Returns:
        Slovník {id_produktu: {koeficient_override: float, poznamka: str, platnost_do: str}}
    """
    from datetime import datetime, date

    overridy_path = Path(OVERRIDY_CSV)

    if not overridy_path.exists():
        logger.warning(f"CSV s overridy nenalezen: {OVERRIDY_CSV}, pouziju jen kurz PLN->CZK")
        return {}

    logger.info(f"Nacitam cenove overridy: {OVERRIDY_CSV}")

    try:
        df_overridy = pd.read_csv(OVERRIDY_CSV, encoding='utf-8')

        # Kontrola prázdného CSV (jen hlavička)
        if len(df_overridy) == 0:
            logger.info("  -> CSV je prazdne (zadne overridy)")
            return {}

        # Validace sloupců
        required_cols = ['id_produktu', 'koeficient_override', 'poznamka', 'platnost_do']
        missing_cols = [col for col in required_cols if col not in df_overridy.columns]
        if missing_cols:
            logger.warning(f"  -> CSV chybi sloupce: {missing_cols}, ignoruji overridy")
            return {}

        # Filtruj platné overridy (nenulové koeficienty)
        df_valid = df_overridy[
            (df_overridy['koeficient_override'].notna()) &
            (df_overridy['koeficient_override'] > 0)
        ].copy()

        # Dnešní datum
        today = date.today()

        # Filtruj podle platnost_do
        active_count = 0
        expired_count = 0
        overridy = {}

        for _, row in df_valid.iterrows():
            try:
                # Parse platnost_do
                platnost_do_str = str(row['platnost_do']).strip()
                platnost_do = datetime.strptime(platnost_do_str, '%Y-%m-%d').date()

                if platnost_do >= today:
                    # Override je aktivní
                    overridy[str(row['id_produktu'])] = {
                        'koeficient_override': float(row['koeficient_override']),
                        'poznamka': str(row['poznamka']) if pd.notna(row['poznamka']) else '',
                        'platnost_do': platnost_do_str
                    }
                    active_count += 1
                else:
                    expired_count += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"  -> Neplatny format datumu pro id {row['id_produktu']}: {e}")
                continue

        logger.info(f"  -> Nacteno {active_count} aktivnich overridu (expirovano: {expired_count})")

        return overridy

    except Exception as e:
        logger.warning(f"  -> Chyba pri cteni overridu: {e}, pouziju jen kurz PLN->CZK")
        return {}


def apply_price_conversion(df: pd.DataFrame, overridy: Dict[str, dict]) -> pd.DataFrame:
    """
    Aplikuje PLN→CZK konverzi a cenové overridy.

    Args:
        df: DataFrame s původními cenami v PLN
        overridy: Slovník s cenovými overridy {id_produktu: {koeficient_override, ...}}

    Returns:
        DataFrame s konvertovanými cenami v CZK
    """
    logger.info("Aplikuji cenovou konverzi PLN->CZK...")
    df = df.copy()

    # Extrahuj PLN cenu z dict struktury
    def extract_price_pln(price_obj):
        """Extrahuje hodnotu ceny z dict {'value': X, 'currency': 'PLN'}"""
        if price_obj is None or not isinstance(price_obj, dict):
            return None
        return price_obj.get('value')

    df['price_pln'] = df['price'].apply(extract_price_pln)

    # Kontrola chybějících cen
    missing_prices = df['price_pln'].isna().sum()
    if missing_prices > 0:
        logger.warning(f"  -> {missing_prices} zaznamu ma chybejici cenu PLN!")

    # Aplikuj kurz a overridy
    def compute_price_czk(row):
        """Vypočte cenu v CZK s respektováním overridů"""
        price_pln = row['price_pln']
        if pd.isna(price_pln):
            return None

        product_id = str(row['id'])

        # Pokud existuje override, použij jeho koeficient
        if product_id in overridy:
            koef = overridy[product_id]['koeficient_override']
            return round(price_pln * koef, 2)
        else:
            # Jinak použij standardní kurz PLN→CZK
            return round(price_pln * KOEFICIENT_PLN_NA_CZK, 2)

    df['price_czk'] = df.apply(compute_price_czk, axis=1)

    # Spočítej koeficienty pro logging
    def get_koeficient(row):
        """Vrátí použitý koeficient (override nebo default)"""
        product_id = str(row['id'])
        if product_id in overridy:
            return overridy[product_id]['koeficient_override']
        else:
            return KOEFICIENT_PLN_NA_CZK

    df['koeficient_used'] = df.apply(get_koeficient, axis=1)

    # Statistiky
    overrides_applied = sum(1 for pid in df['id'].astype(str) if str(pid) in overridy)
    default_kurz_count = len(df) - overrides_applied

    logger.info(f"  -> Konvertovano {len(df)} cen:")
    logger.info(f"     - Default kurz (PLN*{KOEFICIENT_PLN_NA_CZK}): {default_kurz_count} variant")
    logger.info(f"     - Override koeficient: {overrides_applied} variant")

    # Vzorek 3 řádků
    sample = df[['id', 'price_pln', 'koeficient_used', 'price_czk']].head(3)
    logger.info("  -> Vzorek (prvni 3 radky):")
    for _, row in sample.iterrows():
        logger.info(f"     id={row['id']}, price_pln={row['price_pln']:.2f}, koef={row['koeficient_used']:.3f}, price_czk={row['price_czk']:.2f}")

    # Celkové statistiky
    valid_prices = df['price_czk'].notna().sum()
    min_price = df['price_czk'].min()
    max_price = df['price_czk'].max()
    avg_price = df['price_czk'].mean()

    logger.info(f"  -> Rozsah cen CZK: {min_price:.2f} - {max_price:.2f} (prumer: {avg_price:.2f})")

    return df


def generate_heureka_xml(df: pd.DataFrame) -> bytes:
    """
    Generuje Heureka XML feed z DataFrame.

    Args:
        df: DataFrame s konvertovanými daty

    Returns:
        XML jako bytes
    """
    logger.info("Generuji Heureka XML feed...")

    # Vytvoř root element
    root = etree.Element("SHOP")

    # Pro každou variantu vytvoř SHOPITEM
    for idx, row in df.iterrows():
        shopitem = etree.SubElement(root, "SHOPITEM")

        # Povinné elementy
        # ITEM_ID
        item_id = etree.SubElement(shopitem, "ITEM_ID")
        item_id.text = str(row['id']) if pd.notna(row['id']) else ''

        # PRODUCTNAME (title_pl)
        productname = etree.SubElement(shopitem, "PRODUCTNAME")
        productname.text = str(row['title_pl']) if pd.notna(row['title_pl']) else ''

        # DESCRIPTION (description_pl_text - text verze bez HTML)
        description = etree.SubElement(shopitem, "DESCRIPTION")
        desc_text = str(row['description_pl_text']) if pd.notna(row['description_pl_text']) else ''
        # Ořízni na prvních 2000 znaků (Heureka limit)
        description.text = desc_text[:2000]

        # URL (link)
        url = etree.SubElement(shopitem, "URL")
        url.text = str(row['link']) if pd.notna(row['link']) else ''

        # IMGURL (image_link)
        imgurl = etree.SubElement(shopitem, "IMGURL")
        imgurl.text = str(row['image_link']) if pd.notna(row['image_link']) else ''

        # IMGURL_ALTERNATIVE (additional_image_link) - další obrázky
        additional_imgs = row['additional_image_link']
        if additional_imgs is not None and not (isinstance(additional_imgs, float) and pd.isna(additional_imgs)):
            # Může být list, tuple nebo numpy array
            try:
                if hasattr(additional_imgs, '__iter__') and not isinstance(additional_imgs, str):
                    for img_url in additional_imgs:
                        if img_url and str(img_url).strip():
                            imgurl_alt = etree.SubElement(shopitem, "IMGURL_ALTERNATIVE")
                            imgurl_alt.text = str(img_url)
            except (TypeError, ValueError):
                pass  # Ignoruj problematické hodnoty

        # PRICE_VAT (price_czk) - cena včetně DPH v CZK
        price_vat = etree.SubElement(shopitem, "PRICE_VAT")
        if pd.notna(row['price_czk']):
            price_vat.text = f"{row['price_czk']:.2f}"
        else:
            price_vat.text = '0.00'

        # MANUFACTURER (brand)
        manufacturer = etree.SubElement(shopitem, "MANUFACTURER")
        manufacturer.text = str(row['brand']) if pd.notna(row['brand']) else ''

        # CATEGORYTEXT (category_path_pl - spojíme do stringu)
        categorytext = etree.SubElement(shopitem, "CATEGORYTEXT")
        cat_path = row['category_path_pl']
        if cat_path is not None and not (isinstance(cat_path, float) and pd.isna(cat_path)):
            try:
                if hasattr(cat_path, '__iter__') and not isinstance(cat_path, str):
                    categorytext.text = ' | '.join(str(cat) for cat in cat_path if cat)
                else:
                    categorytext.text = str(cat_path) if cat_path else ''
            except (TypeError, ValueError):
                categorytext.text = ''
        else:
            categorytext.text = ''

        # EAN (gtin)
        ean = etree.SubElement(shopitem, "EAN")
        ean.text = str(row['gtin']) if pd.notna(row['gtin']) and str(row['gtin']) != '' else ''

        # PRODUCTNO (mpn)
        productno = etree.SubElement(shopitem, "PRODUCTNO")
        productno.text = str(row['mpn']) if pd.notna(row['mpn']) else ''

        # ITEMGROUP_ID (item_group_id) - KLÍČOVÉ pro varianty!
        itemgroup_id = etree.SubElement(shopitem, "ITEMGROUP_ID")
        itemgroup_id.text = str(row['item_group_id']) if pd.notna(row['item_group_id']) else ''

        # DELIVERY_DATE (availability)
        delivery_date = etree.SubElement(shopitem, "DELIVERY_DATE")
        availability = str(row['availability']) if pd.notna(row['availability']) else ''
        # Mapování availability na počet dní
        if availability == 'in_stock':
            delivery_date.text = '0'  # skladem = 0 dní
        elif availability == 'out_of_stock':
            delivery_date.text = '14'  # nedostupné = 14 dní (odhad)
        else:
            delivery_date.text = '7'  # ostatní = 7 dní

        # PARAMetry (z attrs_raw + další atributy)
        # attrs_raw je list tuples: [('Producent', 'ATOS'), ('Kod_producenta', '1-10-71-1'), ...]
        attrs = row['attrs_raw']
        if attrs is not None and not (isinstance(attrs, float) and pd.isna(attrs)):
            try:
                if hasattr(attrs, '__iter__') and not isinstance(attrs, str):
                    for item in attrs:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            attr_name, attr_val = item[0], item[1]
                            if attr_val and str(attr_val).strip():
                                param = etree.SubElement(shopitem, "PARAM")
                                param_name = etree.SubElement(param, "PARAM_NAME")
                                param_name.text = str(attr_name)
                                val = etree.SubElement(param, "VAL")
                                val.text = str(attr_val)
            except (TypeError, ValueError, IndexError):
                pass  # Ignoruj problematické attrs

        # Přidej další parametry z columns: color, material
        if pd.notna(row['color']) and str(row['color']).strip():
            param = etree.SubElement(shopitem, "PARAM")
            param_name = etree.SubElement(param, "PARAM_NAME")
            param_name.text = "Barva"
            val = etree.SubElement(param, "VAL")
            val.text = str(row['color'])

        if pd.notna(row['material']) and str(row['material']).strip():
            param = etree.SubElement(shopitem, "PARAM")
            param_name = etree.SubElement(param, "PARAM_NAME")
            param_name.text = "Materiál"
            val = etree.SubElement(param, "VAL")
            val.text = str(row['material'])

        # dimensions (pokud je dict)
        dims = row['dimensions']
        if dims is not None and not (isinstance(dims, float) and pd.isna(dims)):
            try:
                if isinstance(dims, dict):
                    for dim_key, dim_val in dims.items():
                        if dim_val is not None and not (isinstance(dim_val, float) and pd.isna(dim_val)) and str(dim_val).strip() != '':
                            param = etree.SubElement(shopitem, "PARAM")
                            param_name = etree.SubElement(param, "PARAM_NAME")
                            # Překlad klíče na čitelný název
                            dim_labels = {
                                'depth_seat': 'Hloubka sedáku [cm]',
                                'width_seat': 'Šířka sedáku [cm]',
                                'depth_total': 'Celková hloubka [cm]',
                                'width_total': 'Celková šířka [cm]',
                                'height_total': 'Celková výška [cm]',
                                'height_backrest': 'Výška opěradla [cm]',
                                'height_to_seat': 'Výška k sedáku [cm]'
                            }
                            param_name.text = dim_labels.get(dim_key, dim_key)
                            val = etree.SubElement(param, "VAL")
                            val.text = str(dim_val)
            except (TypeError, ValueError, AttributeError):
                pass  # Ignoruj problematické dimensions

    # Serializace do XML
    xml_bytes = etree.tostring(
        root,
        encoding='utf-8',
        xml_declaration=True,
        pretty_print=True
    )

    logger.info(f"  -> Vygenerovano XML: {len(df)} SHOPITEM elementu ({len(xml_bytes)} bytes)")

    return xml_bytes


def validate(df: pd.DataFrame, xml_bytes: bytes) -> dict:
    """
    Validuje výstupní data a XML strukturu.

    Args:
        df: Zpracovaný DataFrame
        xml_bytes: Vygenerované XML

    Returns:
        Validační report (dict s klíči: valid, errors, warnings, stats)
    """
    logger.info("Validuji vystupni XML...")

    # Parse XML zpět
    root = etree.fromstring(xml_bytes)

    # Spočti SHOPITEM elementy
    shopitems = root.findall('.//SHOPITEM')
    total_items = len(shopitems)

    # Spočti unikátní ITEMGROUP_ID
    itemgroup_ids = set()
    missing_ean = 0
    missing_image = 0
    missing_price = 0
    missing_title = 0

    for item in shopitems:
        # ITEMGROUP_ID
        itemgroup_id_elem = item.find('ITEMGROUP_ID')
        if itemgroup_id_elem is not None and itemgroup_id_elem.text:
            itemgroup_ids.add(itemgroup_id_elem.text)

        # EAN
        ean_elem = item.find('EAN')
        if ean_elem is None or not ean_elem.text or ean_elem.text.strip() == '':
            missing_ean += 1

        # IMGURL
        imgurl_elem = item.find('IMGURL')
        if imgurl_elem is None or not imgurl_elem.text or imgurl_elem.text.strip() == '':
            missing_image += 1

        # PRICE_VAT
        price_elem = item.find('PRICE_VAT')
        if price_elem is None or not price_elem.text or price_elem.text.strip() == '' or float(price_elem.text) == 0:
            missing_price += 1

        # PRODUCTNAME
        productname_elem = item.find('PRODUCTNAME')
        if productname_elem is None or not productname_elem.text or productname_elem.text.strip() == '':
            missing_title += 1

    master_groups = len(itemgroup_ids)

    # Vzorek cen (3 řádky z DataFrame)
    sample_prices = []
    for idx, row in df.head(3).iterrows():
        sample_prices.append({
            'id': str(row['id']),
            'price_pln': float(row['price_pln']) if pd.notna(row['price_pln']) else None,
            'price_czk': float(row['price_czk']) if pd.notna(row['price_czk']) else None,
            'koeficient': float(row['koeficient_used']) if 'koeficient_used' in row and pd.notna(row['koeficient_used']) else KOEFICIENT_PLN_NA_CZK
        })

    # Acceptance kritéria pro fázi 2c
    ak_2c_1 = total_items == 348
    ak_2c_2 = master_groups == 10
    ak_2c_3 = missing_image == 0
    ak_2c_4 = missing_price == 0
    ak_2c_5 = missing_title == 0
    ak_2c_6 = missing_ean <= 9

    # Logování výsledků
    logger.info(f"  -> Total items: {total_items}")
    logger.info(f"  -> Master groups: {master_groups}")
    logger.info(f"  -> Missing EAN: {missing_ean}")
    logger.info(f"  -> Missing image: {missing_image}")
    logger.info(f"  -> Missing price: {missing_price}")
    logger.info(f"  -> Missing title: {missing_title}")
    logger.info("")
    logger.info("=== VALIDACE ACCEPTANCE KRITERII (Faze 2c) ===")

    if ak_2c_1:
        logger.info(f"  [OK] AK-2c-1: total_items == 348 ({total_items})")
    else:
        logger.warning(f"  [FAIL] AK-2c-1: total_items == 348 (skutecne: {total_items})")

    if ak_2c_2:
        logger.info(f"  [OK] AK-2c-2: master_groups == 10 ({master_groups})")
    else:
        logger.warning(f"  [FAIL] AK-2c-2: master_groups == 10 (skutecne: {master_groups})")

    if ak_2c_3:
        logger.info(f"  [OK] AK-2c-3: missing_image == 0")
    else:
        logger.warning(f"  [FAIL] AK-2c-3: missing_image == 0 (skutecne: {missing_image})")

    if ak_2c_4:
        logger.info(f"  [OK] AK-2c-4: missing_price == 0")
    else:
        logger.warning(f"  [FAIL] AK-2c-4: missing_price == 0 (skutecne: {missing_price})")

    if ak_2c_5:
        logger.info(f"  [OK] AK-2c-5: missing_title == 0")
    else:
        logger.warning(f"  [FAIL] AK-2c-5: missing_title == 0 (skutecne: {missing_title})")

    if ak_2c_6:
        logger.info(f"  [OK] AK-2c-6: missing_ean <= 9 ({missing_ean})")
    else:
        logger.warning(f"  [FAIL] AK-2c-6: missing_ean <= 9 (skutecne: {missing_ean})")

    # Sestavení reportu
    report = {
        'total_items': total_items,
        'master_groups': master_groups,
        'missing_ean': missing_ean,
        'missing_image': missing_image,
        'missing_price': missing_price,
        'missing_title': missing_title,
        'sample_prices': sample_prices,
        'ak_passed': {
            'ak_2c_1': ak_2c_1,
            'ak_2c_2': ak_2c_2,
            'ak_2c_3': ak_2c_3,
            'ak_2c_4': ak_2c_4,
            'ak_2c_5': ak_2c_5,
            'ak_2c_6': ak_2c_6
        }
    }

    return report


def main():
    """
    Hlavní orchestrace transformace - Fáze 2c (kompletní pipeline s XML výstupem).
    """
    import hashlib
    import os

    logger.info("=== Procentov XML Transformer START (Faze 2c) ===")
    logger.info(f"Koeficient PLN->CZK: {KOEFICIENT_PLN_NA_CZK}")
    logger.info(f"Sprint 1 kategorie: {SPRINT1_KATEGORIE}")
    logger.info("")

    warnings = []
    overall_start = time.time()

    # === FÁZE 1: LOAD POLOTOVAR ===
    try:
        logger.info("Faze 1: Nacteni polotovaru...")
        phase_start = time.time()
        df = load_polotovar()
        phase_elapsed = time.time() - phase_start
        logger.info(f"  -> Faze 1 dokoncena za {phase_elapsed:.2f}s")
        logger.info("")
    except FileNotFoundError as e:
        logger.error(f"CHYBA: {e}")
        return {"status": "fail", "error": str(e)}

    # === FÁZE 2: FILTER SPRINT 1 ===
    logger.info("Faze 2: Filtrovani Sprint 1...")
    phase_start = time.time()
    df_filtered = filter_sprint1(df)
    phase_elapsed = time.time() - phase_start
    logger.info(f"  -> Faze 2 dokoncena za {phase_elapsed:.2f}s")
    logger.info("")

    # === FÁZE 3: LOAD OVERRIDY ===
    logger.info("Faze 3: Nacteni cenovych overridu...")
    phase_start = time.time()
    overridy = load_overridy()
    phase_elapsed = time.time() - phase_start
    logger.info(f"  -> Faze 3 dokoncena za {phase_elapsed:.2f}s")
    logger.info("")

    # === FÁZE 4: KONVERZE CEN PLN→CZK ===
    logger.info("Faze 4: Cenova konverze PLN->CZK...")
    phase_start = time.time()
    df_converted = apply_price_conversion(df_filtered, overridy)
    phase_elapsed = time.time() - phase_start
    logger.info(f"  -> Faze 4 dokoncena za {phase_elapsed:.2f}s")
    logger.info("")

    # === FÁZE 5: GENEROVÁNÍ HEUREKA XML ===
    logger.info("Faze 5: Generovani Heureka XML...")
    phase_start = time.time()
    xml_bytes = generate_heureka_xml(df_converted)
    phase_elapsed = time.time() - phase_start
    logger.info(f"  -> Faze 5 dokoncena za {phase_elapsed:.2f}s")
    logger.info("")

    # === FÁZE 6: VALIDACE ===
    logger.info("Faze 6: Validace vystupu...")
    phase_start = time.time()
    validation_report = validate(df_converted, xml_bytes)
    phase_elapsed = time.time() - phase_start
    logger.info(f"  -> Faze 6 dokoncena za {phase_elapsed:.2f}s")
    logger.info("")

    # Kontrola AK
    all_ak_passed = all(validation_report['ak_passed'].values())
    if not all_ak_passed:
        warnings.append("Nektera acceptance kriteria nesplnena (viz vyse)")

    # === FÁZE 7: ZÁPIS XML SOUBORU ===
    logger.info("Faze 7: Zapis XML souboru...")
    phase_start = time.time()

    # Zajisti existenci výstupního adresáře
    out_path = Path(OUT_XML)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Zápis
    with open(OUT_XML, 'wb') as f:
        f.write(xml_bytes)

    phase_elapsed = time.time() - phase_start

    # Ověř existenci a velikost
    if not os.path.exists(OUT_XML):
        logger.error(f"  [FAIL] Soubor nebyl vytvoren: {OUT_XML}")
        return {"status": "fail", "error": "XML soubor nebyl vytvoren"}

    out_xml_size = os.path.getsize(OUT_XML)
    if out_xml_size == 0:
        logger.error(f"  [FAIL] XML soubor je prazdny!")
        return {"status": "fail", "error": "XML soubor je prazdny"}

    # Spočti SHA256
    sha256_hash = hashlib.sha256(xml_bytes).hexdigest()

    logger.info(f"  -> XML zapsano: {OUT_XML}")
    logger.info(f"  -> Velikost: {out_xml_size:,} bytes ({out_xml_size / 1024:.1f} KB)")
    logger.info(f"  -> SHA256: {sha256_hash}")
    logger.info(f"  -> Faze 7 dokoncena za {phase_elapsed:.2f}s")
    logger.info("")

    # === VÝSTUPNÍ REPORT ===
    overall_elapsed = time.time() - overall_start

    logger.info("=== FAZE 2c DOKONCENA ===")
    logger.info(f"  Celkovy cas: {overall_elapsed:.2f}s")

    if warnings:
        logger.warning(f"  WARNINGS: {len(warnings)} problemu")
        for w in warnings:
            logger.warning(f"    - {w}")
    else:
        logger.info("  [OK] Vsechna AK splnena!")

    logger.info("")
    logger.info("=== Procentov XML Transformer STOP (Faze 2c) ===")

    # Výstupní JSON report
    report = {
        "status": "ok" if not warnings else "ok_with_warnings",
        "out_xml_path": OUT_XML,
        "out_xml_size_bytes": out_xml_size,
        "sha256": sha256_hash,
        "validation_report": validation_report,
        "warnings": warnings,
        "elapsed_seconds": round(overall_elapsed, 2)
    }

    # Vypsat JSON report
    logger.info("")
    logger.info("=== JSON REPORT ===")
    logger.info(json.dumps(report, indent=2, ensure_ascii=False))

    return report


if __name__ == "__main__":
    main()
