# HANDOFF — XML Feedy Discovery

**Datum:** 2026-05-06
**Stav:** Discovery fáze 1A dokončena. Připraveni psát Discovery dokument.
**Důvod handoffu:** Kontextové okno plné, pokračujeme v novém vlákně.

---

## 1. Co jsme za toto vlákno udělali

### Process
1. Mirek přerušil execuci Sprint 2 Krok 4 (3-projekt model) s tím, že "lepíme to jak vlaštovčí hnízdo, potřebujeme architektonický návrh, akceptační kritéria, WBS, a validovat to."
2. Místo psání architektury Claude spustil **Discovery 1A** — otevřená otázka "jak se to vůbec dělá", validace přes orchestrátor (5 vendorů) a Perplexity research.
3. Dvě rundy orchestrátoru:
   - **Runda 1:** 4/5 vendorů (Gemini selhal HTTP 503), generická otázka "jak se staví feed pipeline pro PL→CZ dropshipping nábytek"
   - **Runda 2:** 5/5 vendorů, ostré otázky vyžadující konkrétní pozice (Mergado vs Python, hosting, failure modes, rollback, slovník, validace, co nedělat, posouzení současného stavu)
4. **Perplexity research** s 4 dotazy — Mergado limity, PL→CZ cases, validace nástroje, hosting alternativy.
5. Syntéza — silné konsenzy + nedořešené otázky.
6. Mirek doplnil **kritickou změnu zadání**: budoucnost ≠ MVP s jedním feedem, ale **2 e-shopy × 2 dodavatelé × N srovnávačů**.
7. Architektonický návrh upraven — Mergado **zůstává**, ale role se posune (z prostředku pipeline za e-shop pro distribuci do srovnávačů).
8. Vizualizace dvou stavů — současný chaos (5 navazujících technologií) vs cílová "kláda → sochař → socha".

### Klíčový moment vlákna
Mirek použil **vlastní analogii**, která trefila architektonickou podstatu:
- **Surovina** = ATOS XML feed (strom)
- **Polotovar** = připravená kláda v CZ + CZK, slovníkem překladu, sloučenými variantami, validovaná
- **Sochař** = Python skript, který z polotovaru vyřeže výstup pro konkrétní cíl
- **Socha** = finální XML pro Shopyon (a později Heureka, FAVI, Biano)

Tato analogie potvrzuje princip **"separation of concerns"** — polotovar je jeden zdroj pravdy, sochařů může být N (jeden pro každý cíl).

---

## 2. Rozhodnutí (PEVNÉ, neotřesitelná fakta)

### Architektonické principy
1. **ETL pipeline je správný směr** — Extract (dodavatel) → Transform (polotovar) → Load (e-shop). Konsenzus 9/9 (4 runda 1 + 5 runda 2 + Perplexity).
2. **Hranice feed/e-shop je jasná** — překlad, kurz, varianty patří DO feedu. E-shop dostává hotová data.
3. **Slovník překladů jako single source of truth** — JSON soubor v Git repu, ne Mergado dictionary, ne Google Sheet (Sheet maximálně QA layer).
4. **Validace po syncu je prioritní** — bez ní nesmí žádná pipeline jít do produkce.
5. **GitHub Pages jako hosting feedu = OUT** — 5/5 vendorů + Perplexity označili red flag.

### Cílová architektura
**Pět vrstev:**
1. **Suroviny** — ATOS feed, Art Deco feed (PL XML)
2. **Příprava** (Python skripty, jeden per dodavatel) — překlad přes slovník, kurz ČNB × marže, sloučení variant
3. **Polotovar** — kanonický XML/JSON v CZ + CZK, platformově neutrální, validovaný
4. **Sochaři** (Python skripty, jeden per e-shop) — generují výstup pro konkrétní platformu
5. **E-shopy** — Procentov.cz (Shopyon), Utuli.cz (Upgates)

**Mergado role:** AŽ ZA e-shopem, pro distribuci do srovnávačů (Heureka, FAVI, Biano, Glami, Zboží, Ceneo). Mergado má 200+ předpřipravených formátů — psát si je v Pythonu = znovuobjevovat kolo.

### Implementace
- **Kód:** Python, píše Cursor + Claude, Mirek schvaluje a spouští
- **QA překladů:** letmá kontrola, pipeline zastaví běh při neznámém termínu, Mirek doplní slovník
- **Záchranná síť (okamžitě):** validační skript na současný Mergado výstup + verzování feedu (14 dní zpátky)

---

## 3. Nedořešené otázky (NEOTEVŘENÉ, čekají na rozhodnutí)

### Q1: Hosting feedu — Cloudflare R2 vs Hetzner VPS
**Stav:** Mirek chce pochopit "proč R2 zdarma, je to oborové, je to produkční". Claude vysvětlil:
- R2 = konkurence AWS S3, zdarma marketingově, 10 GB + neomezený egress, 99.9% SLA, distribuováno přes Cloudflare CDN
- Oborové ano (indie hackeři, SMB)
- Produkční ano

**Otázka pro Mirka:** R2 (zdarma, ale 15 min Mirkova klikání podle instrukcí) vs Hetzner VPS (~80 Kč/měs, 100% bez Mirkových rukou)?

### Q2: Akceptační kritéria — nesplněný úkol
**Stav:** Mirek to označil jako "nesplněný úkol, určitě dořešit".
**Plán:** Claude navrhne v Discovery dokumentu, dvě úrovně:
- MVP akceptační kritéria (Procentov + ATOS)
- Architektonická akceptační kritéria (unese 4 kombinace + N srovnávačů)

### Q3: RelaxNG/XSD schema pro Shopyon formát 48267
**Stav:** Mirek nezná termín, ale **architektonický požadavek je jasný**:
> "Chci ovládat feed sám, bez Igora. Změny cen, popisku, titulku, obrázku, počet zobrazených parametrů — to si měníme sami."

**Plán:** V Discovery dokumentu sekce "Igor decoupling" — co potřebujeme od Igora (jen specifikaci formátu), co zvládáme sami (vše ostatní).

### Q4: Make.com / n8n jako alternativa k plnému Pythonu
**Stav:** Perplexity přidal toto téma, Claude o tom v cílové architektuře nemluví, protože **Mirek schválil Python (Cursor + Claude píše)**.
**Akce:** Téma uzavřeno, Mergado zůstává pro srovnávače, Python pro pipeline.

---

## 4. Klíčová fakta z validačních zdrojů

### Mergado limity (Perplexity ověřil z forum.mergado.cz a oficiální docs)
- **API neumí založit projekt** — vyžaduje UI klikání
- **Custom formát ignoruje data mimo `<ITEM>`** (CHANNEL-level metadata)
- **Tarify se počítají podle součtu produktů přes všechny exporty** — pro 1000 produktů × 4 exporty = tarif na 4000 produktů
- **Zvýšení tarifu automatické, snížení přes support**
- **Mergado API primárně pro Mergado Store extensions**, ne pro externí orchestraci
- **Performance:** > 500 produktů má znatelně pomalejší přegenerování
- Cenové tarify: Basic ~320 Kč (10k), Standard ~550 Kč (50k), Advanced ~1350 Kč (200k), Mergado Translate **+486 Kč/měs**

### Cloudflare R2
- 10 GB storage zdarma
- 1M Class A operací (zápis) zdarma — Mirek bude na 0.036 % limitu
- 10M Class B operací (čtení) zdarma
- **Nulový egress** (klíčová výhoda oproti S3)
- Atomický upload (buď celý soubor, nebo nic)
- 99.9% SLA, S3-kompatibilní API (Python boto3)

### Healthchecks.io
- 20 cron monitorů zdarma
- Skript pingne URL po dokončení; pokud ping nepřijde v čas → alert
- Komplementární k UptimeRobot (ten kontroluje URL dostupnost)

### ČNB API pro PLN/CZK kurz
- URL: `https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/denni_kurz.txt`
- Zdarma, bez API klíče, oficiální zdroj

### Konsenzy z orchestrátoru runda 2 (5/5 vendorů)
- **Plně Python pipeline** — 4/5 (Gemini, DeepSeek, xAI, OpenAI). Mistral hybrid.
- **Hetzner VPS / Cloudflare R2** — 5/5 (GitHub Pages = red flag)
- **JSON slovník v Git** — 5/5
- **Validace prioritní (MIN/OPT/NICE struktura)** — 5/5
- **UptimeRobot + email alerty** — 5/5
- **Žádný Datadog/Sentry/Airflow/Kubernetes** — 5/5

### Nový pohled (DeepSeek, runda 2)
**Igor SLA 2 dny = architektonický red flag.** Závislost na externím vývojáři pro feed změny je neakceptovatelná.
**Mirek potvrdil:** "Chci feed kompletně ovládat sám."

---

## 5. Finanční dopad (po implementaci cílové architektury)

| Položka | Současný stav | Cílový stav |
|---|---|---|
| Mergado tarif (pipeline pro Procentov+ATOS) | ~320–550 Kč/m | 0 Kč (Mergado až za e-shopem pro srovnávače) |
| Mergado Translate | 486 Kč/m | 0 Kč (slovník v JSON) |
| Hosting feedu | GitHub Pages (zdarma, ale red flag) | Cloudflare R2 nebo Hetzner VPS |
| Monitoring | 0 Kč | 0 Kč (Healthchecks + UptimeRobot) |
| **Pipeline část (Procentov+ATOS):** | **800–1050 Kč/m** | **0–80 Kč/m** |

Mergado pro srovnávače (Heureka, FAVI, Biano…) přijde později — ten výdaj zůstane, ale to je správně.

---

## 6. Co dělat v novém vlákně

### První akce
**Napsat Discovery dokument** podle struktury:
1. Manifest — co stavíme a proč
2. Cílová architektura — diagram + popis + role
3. Hranice odpovědnosti — Python vs Mergado
4. MVP scope — Procentov + ATOS, jen to teď
5. Akceptační kritéria — MVP + architektonická
6. Otevřené otázky — Q1 (R2 vs VPS), Q2 (akcept. kritéria detaily), Q3 (Igor decoupling)
7. Co děláme okamžitě — záchranná síť (validace + verzování) na současný Mergado výstup
8. Cestovní mapa — milníky MVP → 4 kombinace → srovnávače

**Forma:**
- Markdown master v `C:\work\xml-feedy\procentov\DISCOVERY_FEED_ARCHITECTURE.md`
- Notion view (až bude master finální)

**Délka:** 8–12 stran (úmyslně dlouhý — plán domu)

### Co NEDĚLAT
- Začínat dalším orchestrátor kolem
- Přepsávat současný Sprint 1 (produkční)
- Mazat projekt 353162 (Sprint 2 Master)
- Modifikovat Custom format 48267 (globální, čeká Igor)
- Klikat v Mergado UI (Cowork na stand-by)
- Volat Mergado API skripty (čeká architektura)

### Záchranná síť (paralelně, jakmile bude Discovery hotový)
1. Python skript: stáhne výstup ze současného Mergado pipeline, validuje (počet produktů, ceny, well-formed XML), pošle alert při anomálii
2. Verzování: každá nová verze do souboru s timestampem, držet 14 dní zpátky

---

## 7. Soubory a artefakty z tohoto vlákna

### Briefy a výstupy validace
- `C:\Users\Mirek\GDATA\00_DATA_MOZEK\04_INFRA\validace_v36\briefs\brief_xml_feedy_discovery_1A.md`
- `C:\Users\Mirek\GDATA\00_DATA_MOZEK\04_INFRA\validace_v36\briefs\brief_xml_feedy_discovery_1A_runda2.md`
- `C:\Users\Mirek\GDATA\00_DATA_MOZEK\04_INFRA\validace_v36\vystupy\xml_feedy_discovery_1A\` (4 vendor outputs + souhrn)
- `C:\Users\Mirek\GDATA\00_DATA_MOZEK\04_INFRA\validace_v36\vystupy\xml_feedy_discovery_1A_runda2\` (5 vendor outputs + souhrn)

### Perplexity report
Vložen Mirkem v chatu (4 dotazy: Mergado limity, PL→CZ cases, validace, hosting). Není uložen jako soubor.

---

## 8. Krev v žilách (klíčové insighty, které se nesmí ztratit)

1. **"Začali jsme z prostředka."** — Mirek měl pravdu, místo plánu jsme řešili jednotlivé kroky. Discovery 1A vrátil směr.

2. **Polotovar = kláda. Mirek to pojmenoval sám, je to architektonicky správně.** Drž tu analogii v Discovery dokumentu.

3. **Mergado nezrušit, jen přesunout.** Původní doporučení "plně Python, Mergado out" platí pro pipeline (Procentov+ATOS), ale **Mergado má smysl pro distribuci do srovnávačů** kvůli 200+ formátům. Toto je zásadní úprava.

4. **Igor decoupling = architektonický cíl, ne technický detail.** Mirek to potvrdil výslovně.

5. **DRY princip přes 4 kombinace dodavatel-eshop.** Polotovar řeší PL→CZ překlad jednou pro celý život. Stejnou kládu použije Procentov i Utuli.

6. **Validace ne jako "doplníme později", ale jako "bez ní nejde do produkce".** 5/5 vendorů.

7. **Cursor + Claude píše Python.** Mirek je začátečník v programování, ale Cursor mu kód píše a on schvaluje. Tato dělba práce funguje, je odsouhlasená.

8. **Akceptační kritéria nemáme.** Mirek to označil jako nesplněný úkol. Discovery dokument je vyřeší.

---

## 9. Tonalita a styl pro nové vlákno

Mirek (z userPreferences):
- Česky, stručně, bez omáčky
- Pokročilý v e-commerce, začátečník v technice (CLI, programování)
- Žádný overkill, žádné enterprise hračky
- Nadpisy, odrážky, tabulky — ale Mirek řekl "potřebuju vizualizaci, ne další odrážky"
- Vizualizace přes `visualize:show_widget` jakmile budou obrysy
- Krítické a upřímné, žádné lakování na růžovo

Mirek je v procesu otevřeného Discovery, **nepostavil ještě žádný produkt** (ani 10 produktů u Igora). Není pod tlakem. Kvalita > rychlost.
