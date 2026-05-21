# KLADA_PRINCIP.md

> **Status:** návrh v1, čeká na schválení Mirkem přes Plánovač
> **Vznik:** 21.5.2026 v projektu XML_Procentov, sparring s Plánovačem přes Mirka
> **Závaznost:** po schválení = závazné pravidlo pro `polotovar/variants.py` a všechny budoucí transformace v kládě (translator, pricing, validator)
> **Audity, ze kterých dokument vychází:**
> - `C:\work\atos-polotovar\krok0\mapa_atos_feedu.md` (1.5.2026, 5 551 produktů, autoritativní)
> - `C:\work\atos-polotovar\krok0\keys_frequency.csv` (182 raw klíčů ze sloučeného attrs + desc zdroje)
> - `C:\work\atos-polotovar\krok0\HANDOFF_PRO_UTULI.md` (architektura sdílení polotovaru)
> - Empirické probes z 21.5.2026 nad živým ATOS XML (uložené log výstupy v hlášení Plánovači)

---

## ⚠ Princip Mirka (čti první, drž po celou dobu)

**Oprava se nedělá per varianta. Oprava se dělá per zdroj.**

Chyby v ATOS feedu se opakují konzistentně — když ATOS přiřadí kódu `VOGUE 9` chybějící `material_composition`, dělá to napříč všemi 32 variantami, které ten kód používají. Když princip klády opraví **jeden zdroj** (jeden záznam ve slovniku, jeden regex, jeden whitelist atributu), opraví tím **automaticky** všechny varianty, které ten zdroj sdílejí.

Empirický důkaz (probe 3, 21.5.2026, celý ATOS feed): 381 variant (6,86 %) skončí s `Materiál = neuvedeno`. Pochází z **35 unikátních kódů Kolor**, které chybí ve slovniku `barvy_kody`. Doplnit 35 záznamů do slovniku = automaticky opravit 381 variant. Poměr 1 : 11.

**Acceptance criteria se měří per zdrojové selhání, ne per variantu.** Jeden záznam v `unknown_codes.json` = jedna oprava. Validační skript hlásí počty na obou osách (zdrojů i variant), ale ostrá metrika ke Quality Gate je per zdroj.

---

## Sekce 1 — Princip klády

Surový ATOS feed je **kláda** — nezkrocený dřevěný špalek s vlákny, suky a kůrou. Polotovar (kanonický JSON v `out/polotovar_atos_*.json`) je **opracovaný špalek** — sjednocené atributy, českým textem, ve CZK, s pevnou strukturou variant. Mezi tím leží **kláda jako analytická vrstva** — soubor pravidel, který surová data **obohacuje** o všechno, co jde ze zdrojů odvodit, dřív než z nich vyřízne polotovar.

Mirkova formulace (NotebookLM, parafráze ověřena 21.5.2026):

> Kláda je místo, kde se surovina (nekonzistentní ATOS feed) obohacuje na konzistentní produkt. Všechny chybějící informace, které jdou odvodit — z kódu, z textu, ze slovníku — mají být doplněny v kládě. Placeholder `"-"` je selhání tohoto principu.

Kláda **nesmí** používat zástupnou hodnotu `"-"`. Když primární zdroj selže, kláda projde fallback řetězec definovaný v sekci 2 v pořadí priority a použije první funkční zdroj. Když selžou všechny, fallback hodnota je lidský termín `"neuvedeno"` (ne pomlčka), s povinným zápisem do `validation_warnings.json` a započtením do Quality Gate.

Oprava klády **per zdroj, ne per varianta** (princip Mirka): když fallback funguje špatně, opravuje se zdroj — slovník, regex, whitelist — ne varianta. Jedna oprava propaguje na N variant.

---

## Sekce 2 — Tabulka výstupních atributů

Tabulka pokrývá všechny atributy, které kláda produkuje do polotovaru v2.0 (`polotovar/schema.py`). Sloupec **Vrstva** = kde v kódu žije logika (parser_atos.py / translator.py / pricing.py / variants.py / validator.py).

### 2.1 Variantní úroveň (`Variant` v schema.py)

| Atribut | Primární zdroj | Fallback 1 | Fallback 2 | Fallback 3 | Fallback 4 | Fallback hodnota | Vrstva |
|---|---|---|---|---|---|---|---|
| **Materiál** *(typ čalounění, ne složení)* | `attrs.Materiał` | `Kolor` → `slovnik.barvy_kody[kód].material` | `attrs.material_composition` | URL slug regex (`mikrofaza\|velvet\|eko-skora\|tkanina\|boucle\|poliester`) | `<desc>` regex (`VELVET`, `Mikrofaz`, `Eko-?skór`, `100% Poliester`, `boucle`, `plecionka`) | `"neuvedeno"` + WARN | variants.py |
| **Barva** | `Kolor` → `slovnik.barvy_kody[kód].cz` | `attrs.Kolor` *(přímá hodnota, pokud kód není ve slovniku ale je sám čitelný)* | `<desc>` regex `Kolor:`, `kolor materiału:` | regex z `<name>` (poslední token za pomlčkou) | — | `"neuvedeno"` + WARN | variants.py |
| `id` | `<o id>` atribut | — | — | — | — | BLOCK | parser_atos.py |
| `price_czk` | `<o price>` × `KOEFICIENT_PLN_NA_CZK` × `cenove_overridy.csv` | — | — | — | — | BLOCK | pricing.py |
| `availability` | `<o avail>` → `in_stock\|out_of_stock\|preorder` | `<o stock>` > 0 → `in_stock` | — | — | — | `out_of_stock` | parser_atos.py |
| `stock_quantity` | `<o stock>` | — | — | — | — | `0` | parser_atos.py |
| `image_link` | `<imgs><main url=…>` | první `<imgs><i url=…>` | — | — | — | BLOCK | parser_atos.py |
| `additional_image_links` | všechna `<imgs><i url=…>` | — | — | — | — | `[]` | parser_atos.py |
| `ean` | URL regex `-{1,2}(\d{13})\.html` | `attrs.EAN` (13 cifer) | `attrs.Kod_producenta` | — | — | `None` + WARN | parser_atos.py |
| `url` | `<o url>` atribut | — | — | — | — | BLOCK | parser_atos.py |

### 2.2 Master úroveň (`Product` v schema.py)

| Atribut | Primární zdroj | Fallback 1 | Fallback 2 | Fallback 3 | Fallback hodnota | Vrstva |
|---|---|---|---|---|---|---|
| `id`, `item_group_id` | `item_group_key` z parseru (cat_path[1] nebo URL slug) | — | — | — | BLOCK | parser_atos.py |
| `title_cz` | `slovnik.namespaces.kategorie[item_group_key]` | regex z `cat_path` (kapitalizace) | — | — | BLOCK | translator.py |
| `description_cz` | `DESCRIPTIONS_CZ[product_id]` (interní KB Mirka) | Google Translate `desc_pl` (sanitized HTML → text) | — | — | `desc_pl` 1:1 + WARN | translator.py |
| `category_path_cz` | per-segment lookup `slovnik.namespaces.kategorie[segment]` | regex z `cat_path_pl` (kapitalizace) | — | — | `cat_path_pl` 1:1 + WARN | translator.py |
| `price_czk` | min(`Variant.price_czk` napříč všemi variantami) | — | — | — | BLOCK | variants.py |
| `image_link` | první varianta s `image_link` (preferuje main=1) | — | — | — | BLOCK | variants.py |
| `availability` | `in_stock` pokud ≥ 1 varianta in_stock | první variant.availability | — | — | `out_of_stock` | variants.py |
| `attrs_cz` *(parametrické)* | `attrs` z první varianty kromě těch v `variant_attribute_whitelist` | — | — | — | `[]` | variants.py |
| `brand` | `attrs.Producent` | `"ATOS"` *(empirický invariant: 5551/5551)* | — | — | `"ATOS"` (audit záznam) | parser_atos.py |
| `gtin` | URL regex EAN-13 | `attrs.EAN` | — | — | `None` + WARN | parser_atos.py |
| `dimensions` | `attrs.{Wysokość\|Szerokość\|Głębokość} całkowita [cm]` *(normalizováno přes synonym table)* | regex z `<desc>` HTML | — | — | `None` + WARN | parser_atos.py |
| `weight_kg` | `attrs.Waga [kg]` | regex `Waga:\s*([\d,.]+)\s*kg` v `<desc>` | — | — | `None` + WARN | parser_atos.py |
| `color`, `material` *(OPT info pole)* | převzato z variant.variant_attributes většinové hodnoty | — | — | — | `None` | variants.py |

### 2.3 Pokrytí zdrojů v ATOS feedu (5 551 produktů, audit 1.5.2026)

| Atribut | Primární `<attrs>` | Sekundární `<desc>` | Slovník `barvy_kody` (Procentov) |
|---|---:|---:|---:|
| `Producent`, `Kod_producenta`, `EAN` | 100,0 % | — | — |
| `Kolor` | 94,5 % (5 244) | +1,0 % (55) = 95,5 % | 53 ze 88 unikátních kódů (60 %) |
| `material_composition` | 89,9 % (4 990) | — | — |
| `Materiał` *(typ čalounění)* | 17,0 % (942) | +0,6 % (34) = 17,6 % | propaguje se přes `barvy_kody[kód].material` |
| Rozměry (Wysokość/Szerokość/Głębokość) | 63–78 % | dodatečně 25–84 % z desc | — |
| `Waga [kg]` | 29,7 % | 39,1 % v desc | — |

### 2.4 Fallback řetězec pro `Materiál` — empirický výsledek na celém feedu

Probe 3 (21.5.2026, 5 551 variant, slovník stav `barvy_kody` = 53 záznamů):

| Úroveň | Použit počet variant | % feedu |
|---|---:|---:|
| 1. `attrs.Materiał` | 942 | 16,97 % |
| 2. `Kolor` → slovník | 3 874 | **69,79 %** ← nejvíce platí Mirkův princip klády |
| 3. `attrs.material_composition` | 190 | 3,42 % |
| 4. URL slug regex | 2 | 0,04 % |
| 5. `<desc>` regex | 162 | 2,92 % |
| 6. **`"neuvedeno"`** | **381** | **6,86 %** ← **NAD práh 0,5 %**, Quality Gate FAIL |

**Akční položka před přepnutím z Milo na celý ATOS:** doplnit `slovnik.namespaces.barvy_kody` o 35 chybějících kódů (top: VOGUE 3/9/11/13/14/15/17 = 192 variant, Vega02/26/83/99 = 96 variant, Rolf2/7/10/14 = 64 variant, drobné). Po doplnění klesne `"neuvedeno"` z 381 na očekávaných < 28 variant (= pod 0,5 % práh).

---

## Sekce 3 — Pravidla slovníku

### 3.1 Slovník je znalostní báze, ne překladač

`slovnik/slovnik.json` má tři vrstvy:

1. **`namespaces.atributy`** — překlad jmen atributů (PL → CZ): `Kolor → Barva`, `Materiał → Materiál`, `Waga [kg] → Hmotnost [kg]`. Read-only pro variants.py.
2. **`namespaces.hodnoty`** — překlad textových hodnot: `EKO-SKÓRA → Ekokůže`, `MIKROFAZA → Mikrovlákno`. Aplikováno na `value_pl` pokud není match v `barvy_kody`.
3. **`namespaces.barvy_kody`** — **znalostní báze, ne jen překladač**. Klíč = kód v ATOS feedu (`BL75`, `MG02`, `1 MIKROFAZA`, `5D`, `VOGUE 9`, …). Struktura:
   ```json
   "MG02": {
     "pl": "sliwka",
     "cz": "Švestková",
     "material": "Velvet"
   }
   ```
   Pole `material` má **rovnocennou autoritu** s `cz`. Když primární `attrs.Materiał` chybí, kláda **musí** sáhnout do `barvy_kody[kód].material` — není to nouzový fallback, je to ekvivalentní zdroj.

### 3.2 Kdy se slovník čte

Slovník se načte při startu pipeline jednou do paměti (dict lookup O(1)). Žádné lazy loading per atribut. Soubor je malý (~25 KB), latency nula.

### 3.3 Co se stane při neznámém kódu

Kód, který není v `barvy_kody`:

1. Záznam do `out/unknown_codes.json` ve struktuře:
   ```json
   {
     "VOGUE 9": {
       "first_seen_at": "2026-05-21T08:00:00Z",
       "variant_count": 32,
       "atributy_obsahujici_kod": ["Kolor"],
       "example_variant_ids": ["6467", "6468", "6469"],
       "example_name_pl": "Krzesło Colin noga czarna Vogue 9"
     }
   }
   ```
   **Deduplicia per `(atribut, kód)`, ne per varianta** (princip Mirka). Pole `variant_count` = počet variant, které kód použily v tomto běhu.

2. Záznam do `out/validation_warnings.json` jako WARN-3 (slovník miss) — pro každou variantu jeden záznam s `variant_id` a použitým fallback levelem.

3. Pokud `material` nelze odvodit, kláda pokračuje fallback levelem 3 (`material_composition`) → 4 (URL) → 5 (desc) → 6 (`neuvedeno`).

### 3.4 Workflow rozšíření slovníku

Trigger: po každém běhu pipeline existuje `out/unknown_codes.json`. Workflow má 5 kroků a **žádný z nich neprobíhá ručně Mirkem v editoru slovníku**:

1. Pipeline doběhne → `out/unknown_codes.json` agreguje neznámé kódy.
2. Claude v projektu XML_Procentov (toto vlákno) si načte `unknown_codes.json` a `name_pl` + `desc_pl` pro vzorové varianty každého kódu.
3. Claude vygeneruje **návrhovou tabulku** (PL→CZ + odvození `material` z URL slug + popis + Kolor sufix) a předloží ji Mirkovi v chatu jako jeden atomický úkol (per slovníkový namespace, ne per kód).
4. Mirek schvaluje **celý batch** (po jedné dávce, lightweight approval). Žádné per-kód schvalování.
5. Claude zapíše do `slovnik/slovnik.json` přes `zapis_soubor` + commit přes git workflow (skill repo pravidlo).

Audit záznam: každý nový kód dostane v `audit` sekci `{"_source": "review", "_reviewed_by": "mirek", "_updated_at": "..."}`. Diff je v `git log`.

**Eskalace:** pokud Claude nedokáže `material` odvodit ani z URL/desc/name kombinace, kód se zapíše do `unknown_codes.json` s `material: null` a v návrhové tabulce explicitně označí jako „vyžaduje rozhodnutí Mirka". Mirek pak rozhodne (`"Tkanina"`, `"Velvet"`, nebo `"neuvedeno"` napevno).

---

## Sekce 4 — Pravidla placeholderu

### 4.1 Žádná pomlčka, jen lidský termín

Hodnota `"-"` je **zakázána** ve všech polích polotovaru (variantní i parametrické). Když fallback řetězec selže až do úrovně 6, hodnota je `"neuvedeno"` (Materiál), `"neuvedeno"` (Barva), `None` pro OPT pole (EAN, dimensions, weight_kg).

### 4.2 Každý fallback je auditovaný

Jakákoli úroveň fallback od #2 níž **zapisuje** do `out/validation_warnings.json`:

```json
{
  "rule": "FALLBACK-USED",
  "variant_id": "6467",
  "atribut": "Materiál",
  "fallback_level_used": "2_kolor_dict",
  "fallback_levels_tried": ["1_attrs_materiał"],
  "resolved_value": "Velvet",
  "source_detail": "barvy_kody['MG02'].material"
}
```

Audit trail = před každým nasazením lze odpovědět na otázku „proč tahle varianta má `Materiál = Velvet`, když to není v `attrs`?". 

### 4.3 Quality Gate — práh 0,5 % per atribut

Mirkovo pravidlo: **„Pod 0,5 % variant z celého feedu neřeším. Nad 0,5 % řeším."**

Měření: per atribut, na úrovni celého exportovaného feedu (nebo aktivního filtru kategorie, pokud běh není full feed).

- Práh: 0,5 % z 5 551 variant = **27,8 → zaokrouhleno 28 variant**.
- Měřená metrika: počet variant, které pro daný atribut skončily na fallback levelu 6 (`"neuvedeno"` nebo `None`).
- **Per atribut, ne per kategorie** — kategorie s malým počtem variant (Lampy: 2 produkty) by jinak triggerovala FAIL při jednom missu (50 %).

Pravidla:

| Stav | Verdikt | Akce |
|---|---|---|
| 0 variant `neuvedeno` u atributu | PASS | žádná akce, feed pokračuje |
| 1–28 variant `neuvedeno` (≤ 0,5 %) | PASS s WARN | feed pokračuje, WARN log do `validation_warnings.json`, `unknown_codes.json` agreguje |
| > 28 variant `neuvedeno` (> 0,5 %) | **BLOCK** | feed se neuploaduje, `validation_errors.json` obsahuje souhrn, pipeline exit 1, Healthchecks alert |

Při BLOCK pro `Materiál` se navrhuje akce: doplnit slovník o kódy z `unknown_codes.json` (princip Mirka — jedna oprava řeší desítky variant).

### 4.4 Co se NEpovažuje za placeholder

- `"out_of_stock"` u `availability` — to je legitimní hodnota
- `None` u OPT polí (EAN, weight_kg) — schema je dovoluje
- `attrs.material_composition = "100% Poliester"` použité jako `Materiál` — to je legitimní fallback, ne placeholder. Hodnota je informativní, jen méně specifická než `attrs.Materiał = "VELVET"`.

---

## Sekce 5 — Acceptance criteria (měřitelná skriptem)

Vytvoří se nový soubor `polotovar/validator_klada.py` s těmito kontrolami. Každá je booleanovsky vyhodnotitelná na výstupu pipeline. Skript běží jako součást `polotovar/generate.py` v gate fázi (před zápisem polotovaru).

### 5.1 Per-atribut kompletnost

- [ ] **AK-K1** Pro Milo kategorii: 0 variant s `Materiál == "neuvedeno"`, pokud `Kolor` je ve slovniku `barvy_kody`. *(Měření: probe 3 ukázal 100% pokrytí Milo Kolor → 0 missů očekáváno.)*
- [ ] **AK-K2** Pro Milo kategorii: 0 variant s `Barva == "neuvedeno"`. *(Stejný důvod — slovník Milo úplný.)*
- [ ] **AK-K3** Pro celý feed: < 28 variant s `Materiál == "neuvedeno"` (práh 0,5 %).
- [ ] **AK-K4** Pro celý feed: < 28 variant s `Barva == "neuvedeno"`.
- [ ] **AK-K5** 0 variant s hodnotou `"-"` v jakémkoli poli polotovaru (regex grep přes serializovaný JSON polotovaru).

### 5.2 Auditovatelnost

- [ ] **AK-K6** `out/validation_warnings.json` existuje a obsahuje záznam `FALLBACK-USED` pro každou variantu, která použila fallback level ≥ 2.
- [ ] **AK-K7** `out/unknown_codes.json` existuje a obsahuje agregovaný záznam pro každý unikátní neznámý kód (dedupe per `(atribut, kód)`, ne per varianta).
- [ ] **AK-K8** Validační report (`out/validation_summary.json`) hlásí per atribut: počet variant na primárním zdroji, počet na každém fallback levelu, počet `neuvedeno`, % z feedu, verdict (PASS/WARN/BLOCK).

### 5.3 Princip „oprava per zdroj"

- [ ] **AK-K9** *Regresní test:* přidání jediného fiktivního kódu (`TEST_FAKE_99`) do `slovnik.namespaces.barvy_kody` a sestavení falešného ATOS XML s N variantami používajícími tento kód → po opětovném běhu pipeline všech N variant má `Materiál = TEST_FAKE_99.material`. Princip propaguje 1 : N.
- [ ] **AK-K10** Validator hlásí dvě metriky: počet selhání zdrojů (≤ desítky) a počet postižených variant (může být stovky). Mirkovi UI ukazuje obě, ale Quality Gate používá per-variant metriku proti prahu 0,5 %.

### 5.4 Negativní kontrakty (co nesmí nastat)

- [ ] **AK-K11** Žádná varianta v polotovaru nemá `value_cz == "-"`.
- [ ] **AK-K12** Žádná varianta nemá v `variant_attributes` Atribut s `is_variant=True` a `value_cz == value_pl` (znamenalo by, že překlad neproběhl ani na fallback úrovni).
- [ ] **AK-K13** Žádné polské diakritiky v polích `title_cz`, `description_cz`, `category_path_cz`, `value_cz` (kontrolováno BLOCK-9 z existujícího validátoru).

---

## Appendix — Změny v novějším auditu (1.5.2026) vs. starší (29.4.2026)

| Položka | Starší (29.4.) | Novější (1.5.) | Změna v dokumentu |
|---|---|---|---|
| Pokrytí `Materiał` | 942 (17,0 %, jen attrs) | 976 (17,6 %, attrs + 34 z desc) | Sekce 2.3 ukazuje obě čísla |
| Pokrytí `Kolor` | 5244 (94,5 %, jen attrs) | 5299 (95,5 %, attrs + 55 z desc) | Sekce 2.3, fallback 2 pro Barvu má `<desc>` regex |
| Pseudo-rodiny | nezmíněno | 306 rodin podle URL prefixu, medián 19 variant | Souvisí s `item_group_id` v sekci 2.2 |
| Synonyma | nezmíněno | 33 skupin (`[cm]` vs. bez, lowercase vs. capitalized) | Sekce 2.2 zmiňuje normalizaci přes synonym table |
| `<desc>` jako fallback | implicitně | explicitně potvrzeno (attrs primární, desc fallback) | Princip celé sekce 2 |
| Unicode replacement char `�` | nezměřeno | 0× v desc | Žádné encoding problémy, dokument se tím nezabývá |

Žádný rozdíl nezměnil odpovědi na 4 otázky z Plánovače (Q1 fallback hodnota `"neuvedeno"`, Q2 práh per atribut, Q3 `unknown_codes.json` per-běh s deduplicí per zdroj, Q4 workflow Claude→Mirek schvaluje batch). Novější audit jen **zpřesnil** čísla a přidal `<desc>` jako legitimní fallback úroveň (sekce 2.1, fallback 5 pro Materiál a fallback 2 pro Barvu).
