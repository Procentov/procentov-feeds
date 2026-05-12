# Brief: Krok C — description_cz překlad přes Claude API

## Kontext
Workspace: C:\work\xml-feedy\procentov\
Pipeline: parser_atos → variants.py → validator.py → generate.py
Problém: validator BLOCK-9 padá protože description_cz = surový PL HTML text z dodavatele

## Úkol 1: translate_description() v translator.py

Přidej funkci na konec souboru polotovar/translator.py:

```python
def translate_description(desc_pl: str, product_name: str = "") -> str:
    """Přeloží PL HTML description na CZ plain text přes Claude API.
    
    Steps:
    1. Strip HTML tagů (BeautifulSoup nebo re)
    2. Přeložit přes Anthropic API (claude-sonnet-4-20250514)
    3. Vrátit CZ plain text
    
    Pokud API selže nebo text je prázdný, vrátí prázdný string "".
    NIKDY nevracet polský text — raději prázdný string, validator to chytne jako BLOCK-2.
    """
```

Implementační požadavky:
- Použij `anthropic` Python SDK (import anthropic)
- Model: claude-sonnet-4-20250514, max_tokens=500
- System prompt: "Jsi překladač nábytku PL→CZ. Překládáš popis produktu z polštiny do češtiny. Piš přirozenou českou větnou skladbu vhodnou pro e-shop. Vrať POUZE přeložený text, žádný komentář, žádné uvozovky."
- User message: f"Přelož tento popis křesla/pohovky do češtiny:\n\n{plain_text}"
- Pokud plain_text po strippingu HTML je kratší než 10 znaků → vrať ""
- Obalit celé volání try/except, při chybě print("[WARNING] Claude API překlad selhal: {e}") a vrát ""
- ANTHROPIC_API_KEY se čte automaticky ze SDK (z env vars), NEPŘEDÁVEJ ho explicitně

## Úkol 2: Oprava barvy_kody lookup v translator.py

Funkce translate_attribute_value() hledá hodnoty jen v namespace `hodnoty`.
Barvy (MG02, BL06, 1D, atd.) jsou ale v namespace `barvy_kody`.

Oprav translate_attribute_value() tak aby:
1. Nejdřív hledala v `hodnoty` (stávající logika)
2. Pak hledala v `barvy_kody` — pokud nalezeno, vrátí entry['cz']
3. Pokud pořád nenalezeno → fallback + warning (stávající)

## Úkol 3: Použití translate_description() ve variants.py

V souboru polotovar/variants.py najdi řádek:
```python
description_cz = first_offer.desc_pl  # TODO: prelozit pres slovnik nebo fallback
```

Nahraď za:
```python
description_cz = translate_description(first_offer.desc_pl, title_cz)
```

A přidej import navrch variants.py:
```python
from polotovar.translator import translate_description
```
(přidej k existujícímu importu z translator)

## Úkol 4: Spustit pytest

Po implementaci spusť:
```
cd C:\work\xml-feedy\procentov
python -m pytest polotovar/ -v
```
Všechny testy musí PASS. Pokud test_translator.py testuje translate_attribute_value pro barvy — uprav test aby očekával cz hodnotu z barvy_kody, ne PL fallback.

## Úkol 5: Spustit run_generate.py

```
cd C:\work\xml-feedy\procentov
python run_generate.py
```
Očekávaný výstup: [SUCCESS] verdict=PASS

## Úkol 6: Git commit

```
cd C:\work\xml-feedy\procentov
git add -A
git commit -m "M1.3 finalizace: regex fix + slovnik rozsireni + description preklad"
```

## Důležité
- Neměň schema.py ani validator.py
- Neměň pricing.py (PLN→CZK koeficient žije POUZE tam)
- sys.stdout.reconfigure(encoding='utf-8') je už v translator.py — nezdvojuj
- Při výstupu používej UTF-8 (cp1250 způsobí problémy)
