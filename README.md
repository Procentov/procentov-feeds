# Procentov XML Feed Transformer

## Účel
Python skript pro transformaci polotovaru atos_v1.0 (Sprint 1 - Milo furniture) do Heureka XML feedu s PLN→CZK konverzí.

## Vstup
- **Polotovar**: `C:\work\atos-polotovar\current\polotovar.parquet` (read-only)
- **Cenové overridy**: `cenove_overridy.csv` (manuální korekce)

## Výstup
- **XML feed**: `out\procentov_intermediate.xml` (Heureka formát s ITEMGROUP_ID)

## Setup
```bash
# Vytvoř virtual environment
py -3.12 -m venv .venv

# Nainstaluj dependencies
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Spuštění
```bash
.venv\Scripts\python.exe transformer.py
```

## Cenové overridy (CSV)
Struktura `cenove_overridy.csv`:
```csv
id_produktu,koeficient_override,poznamka,platnost_do
PRD-123,1.05,Seasonální markdown,2026-06-30
```
- `koeficient_override` = multiplikátor na PLN cenu před konverzí (např. 1.05 = +5%)
- Prázdný CSV = žádné overridy, použije se jen kurz PLN→CZK = 11.115

## Fáze transformace
1. Load polotovar (parquet)
2. Filter Sprint 1 (Milo furniture)
3. Load cenové overridy (CSV)
4. Cenová konverze (PLN→CZK + overridy)
5. Generate Heureka XML
6. Validace
7. Zápis výstupu
