# Discovery — Cílová architektura feedů (Procentov + Utuli)

| Pole | Hodnota |
|---|---|
| Datum | 2026-05-06 (rev. 2026-05-11) |
| Autor | Mirek Konečný + Claude (sparring) |
| Status | Sekce A revize 2; Sekce B revize 1 (2026-05-11) |
| Předchozí dokument | `HANDOFF_DISCOVERY_2026-05-06.md` |
| Validace KB | PASS s korekcí (viz A.3) |
| Validace sekce B | 2 kola orchestrátoru (5 vendorů), 8 rozhodnutí pevně zafixováno |

**Co tento dokument je:** plán architektury feed pipeline pro Procentov.cz a Utuli.cz, s odůvodněním a akceptačními kritérii. Je to mapa, ne návod. Návod (jaké soubory, jaký kód, jaký commit) je sekce B v druhém vlákně.

**Co tento dokument není:** popis migrace z nějakého existujícího feed řešení. Žádný produkční feed dnes na Procentov.cz neběží. Procentov.cz dnes prodává 30–40 % ATOS portfolia ručně zadanými produkty bez variant a parametrů. Toto Discovery popisuje **první funkční feed pipeline**, která ruční stav nahradí.

**Změny v revizi 2 (2026-05-11):** Upřesnění výchozího stavu (žádný produkční feed dnes neběží), oprava role Igora (galerista, ne dodavatel feedu), vyhození M0 záchranné sítě (není co zachraňovat), oprava A.2 analogie (přidán galerista), oprava A.5 (Igor není decoupling problém), vyhození Q3 (falešná otázka), přidání iterace v M3 jako standardního kroku.

---

## Sekce A — Interní (pro Mirka)

### A.1 Manifest

**Cíl projektu XML Feedy:** skokové zvýšení **kvality a kvantity** sortimentu na Procentov.cz. Dnes Procentov.cz prodává 30–40 % dostupného ATOS portfolia, produkty zadávané **ručně**, bez variant a parametrů. Cíl: 100 % portfolia, **automaticky přes feed**, s variantami a strukturovanými parametry. Po nasazení feedu se stávající ruční produkty smažou a nahradí daty z pipeline.

Stejnou pipeline pak rozšíříme na druhý e-shop **Utuli.cz** (Upgates platforma) a druhého dodavatele **Art Decoration**. Distribuci do srovnávačů (Heureka, Zboží, Glami, Ceneo pro Procentov; FAVI, Biano pro oba) řeší **Mergado až za e-shopem**.

**Co se nestaví:** přepis e-shopu, vlastní implementace srovnávačových formátů (od toho je Mergado), GUI pro správu feedu (Mirek ovládá repo a CSV), automatické rozhodování o cenách (cenotvorba zůstává explicitní v `cenove_overridy.csv` a koeficientu).

### A.2 Klíčová analogie — kláda, polotovar, sochař, galerista

Surová XML data od dodavatele = **kláda**. Polotovar (CZ + CZK + slovník + sloučené varianty + validováno, platformově neutrální) = **opracovaný špalek**. Skript per e-shop, který bere špalek a tesá z něj formát pro konkrétní cíl = **sochař**. Hotový XML feed pro Shopyon nebo Upgates = **socha**.

A pak je tu **galerista** — Igor (pro Procentov/Shopyon) nebo Upgates platforma (pro Utuli). Galerista dává **akceptační kritéria** (jak má socha vypadat, aby ji přijal na výstavu) a po dodání ji **přijme do galerie** (importér ji zpracuje, produkty se objeví na webu). Galerista se sochou nezhotovuje, neopracovává, neupravuje — jen ji přijímá nebo odmítá podle kritérií. Po vystavení v galerii se může ukázat, že světlo na sochu dopadá jinak, než galerista čekal — pak se buď socha doladí (úprava XML), nebo místnost (úprava importéru/parametrů u galeristy). To je standardní iterativní proces.

**Distribuce do srovnávačů** = po vystavení v hlavní galerii (Procentov.cz) Mergado pořizuje kopie sochy pro další galerie (Heureka, Zboží, …) v jejich vlastních formátových požadavcích.

Tahle analogie drží celý dokument. Když narazíš na technické rozhodnutí, ptej se: *patří to do klády, polotovaru, sochaře, galeristy, nebo distribuce?*

### A.3 Cílová architektura — pět vrstev

```
┌─────────────────────────────────────────────────────────────────┐
│ VRSTVA 1 — KLÁDY (suroviny)                                     │
│ ATOS XML feed (hurtmeble.eu)  +  Art Decoration XML feed        │
│ Read-only, polské, PLN, polské texty, polské atributy           │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ VRSTVA 2 — POLOTOVAR (kanonický špalek)                         │
│ • PL→CZ (slovník v JSON, Git, jediné místo pravdy)              │
│ • PLN→CZK (koeficient + cenove_overridy.csv)                    │
│ • Sloučení variant (master product + N variant)                 │
│ • Validace (schema, povinná pole, EAN, ceny ≠ 0, atd.)          │
│ • Platformově neutrální (ne Shopyon, ne Upgates, ne srovnávač)  │
│ Výstup: jeden kanonický JSON/XML soubor per dodavatel           │
└─────────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ VRSTVA 3 —       │ │ VRSTVA 3 —       │ │ VRSTVA 3 —       │
│ SOCHAŘ Shopyon   │ │ SOCHAŘ Upgates   │ │ (budoucí sochař) │
│ Python skript    │ │ Python skript    │                    │
│ Polotovar →      │ │ Polotovar →      │                    │
│ Shopyon XML      │ │ Upgates XML      │                    │
└──────────────────┘ └──────────────────┘                    
              │             │
              ▼             ▼
┌──────────────────────────────────────────┐
│ VRSTVA 4 — HOSTING + GALERISTA           │
│ Cloudflare R2 (HTTPS, public read-only)  │
│ → Shopyon import (Igorův importér,       │
│    galerista pro Procentov)              │
│ → Upgates import (galerista pro Utuli)   │
└──────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ VRSTVA 5 — DISTRIBUCE DO SROVNÁVAČŮ (Mergado)                   │
│ E-shop XML feed je VSTUPEM do Mergado projektu                  │
│ Mergado out-of-the-box formáty: Heureka, Zboží, Glami, Ceneo    │
│ FAVI, Biano: k ověření (KB nepotvrzuje hotový formát)           │
│ Master Feed technika: jeden vstup → N výstupů, jedno pravidlo   │
└─────────────────────────────────────────────────────────────────┘
```

**Posun proti experimentu Sprint 1.** Ve Sprintu 1 byl Mergado pokus o centrum pipeline — surový ATOS feed → tři řetězené Mergado projekty → výstup pro Shopyon. Cílová architektura: **Python pipeline** od klády po sochu, Mergado **až za** e-shopem jako distribuce pro srovnávače. Mergado řetězec 349778→349884→349905 je tedy ukončený experiment, ne základ produkce.

**Korekce k Discovery 1A.** V handoffu byl použit termín "200+ formátů Mergada" — KB to takhle nepotvrzuje. Realita podle Mergado KB: out-of-the-box podpora pro Heureku, Zboží, Glami, Ceneo (potvrzeno zdroj 042, 144). FAVI a Biano podporu pro doplňování parametrů KB zmiňuje, ale nepotvrzuje, že existuje hotový výstupní formát. **To je třeba ověřit dotazem na fórum / podporu Mergada před tím, než postavíme distribuci pro FAVI a Biano přes Mergado.**

### A.4 Hranice odpovědnosti — co dělá co

| Vrstva | Nástroj | Odpovědnost | Co tam **nepatří** |
|---|---|---|---|
| Polotovar | Python (Cursor + Claude Code) | Translation, kurz, varianty, validace, schema kontrola | Cokoliv platformově specifického, srovnávačové formáty |
| Sochař Shopyon | Python | Mapování polotovaru na Shopyon Custom Format | Translation (to už proběhlo), kurz (to už proběhlo) |
| Sochař Upgates | Python | Mapování polotovaru na Upgates formát | Stejně jako Shopyon |
| Hosting | Cloudflare R2 | Hostování XML, HTTPS, public URL | Cache, CDN logika, edit XML |
| Galerista (E-shop) | Shopyon (Igor) / Upgates | Import XML do databáze produktů + akceptační kritéria | Žádné transformace, jen čistý import |
| Distribuce | Mergado | Per-srovnávač transformace e-shop feedu | Translation, kurz, validace polotovaru |
| Cenotvorba | `cenove_overridy.csv` + koeficient | Override per produkt + globální koeficient | Mergado pravidlo násobící cenu (zakázáno — duplicita!) |
| Slovník PL→CZ | JSON v Git | Verze, historie, blame | Excel sheety, ad-hoc překlady v Mergado |
| Validace | Python validační kontrakt | Blocking gate před publikací | Kontrola ex post v Mergado Audit (jen jako safety net) |
| Monitoring | Healthchecks.io + UptimeRobot | "Feed nezpracoval" + "Feed nedostupný" | Alert na business metriky (PNO, marže) |

**Železné pravidlo cenotvorby (z paměti, lekce z 30 854 Kč incidentu):** kurz PLN→CZK a override žije **pouze** v polotovaru. V Mergado projektu pro distribuci NESMÍ být pravidlo násobící cenu. Pokud by tam bylo, vynásobí se 11.115 dvakrát.

### A.5 Igor a Shopyon — co od něj potřebujeme

**Pochopení role.** Shopyon je platforma (krabice) → e-shop na klíč. Igor je dlouhodobý vývojář, který Shopyon platformu **upravuje na míru** pro každého klienta. Procentov.cz = Igorem na míru upravený Shopyon. Igor je tedy "ten" vývojář Procentova — kdyby do toho sahal někdo jiný, riskujeme, že se nevyzná v Igorových úpravách.

**Pro projekt XML Feedy Igor dělá pouze tohle:**

1. Dává **akceptační kritéria** pro Shopyon importér — specifikaci XML formátu (pole, typy, struktura, povinné věci)
2. Když mu pošleme XML splňující kritéria, **importér ho přečte** a produkty se objeví na webu

**Co Igor NEdělá:**

- Negeneruje feed (to je naše práce, Python pipeline)
- Neupravuje obsah feedu (slovník, ceny, varianty — to je naše práce)
- Je mu jedno, jak ten formát vyrobíme (Python, Mergado, Excel makro, ručně) — záleží jen, že splňuje akceptační kritéria
- Není součástí naší pipeline — je za dveřmi (Shopyon import), čeká, až přijde dodávka

**Iterace po prvním importu.** Když poprvé pošleme feed do Shopyon importéru, je pravděpodobné, že produkty na webu **úplně přesně nesednou** — některé parametry budou v jiné kategorii, varianty se zobrazí jinak, něco bude chybět nebo přebývat. To je normální. Náprava může jít dvěma směry:

- **Náprava na naší straně:** upravíme sochaře Shopyon (jiné mapování polí, jiná struktura) → znovu vygenerujeme XML → znovu pošleme. **My máme kontrolu, žádné čekání.**
- **Náprava na Igorově straně:** Igor upraví importér / parametrické šablony / zobrazení v Shopyonu. Tady čekáme na Igora.

Předem nevíme, kolik z toho bude která strana — záleží, kde rozdíl leží. Je to standardní iterativní proces, ne riziko. Discovery to počítá jako součást M3 (validace v produkci).

**Co potřebujeme pro M2:** mít aktuální specifikaci Shopyon Custom Format (akceptační kritéria importéru). Možná ji už máme z minulé komunikace s Igorem, možná je potřeba si o ni napsat. To je **dokument, ne ticket** — žádné čekání 2 dny na implementaci, jen poslat aktuální verzi specifikace.

### A.6 MVP scope — Procentov + ATOS, jen to teď

V MVP:
- **Jeden dodavatel:** ATOS (hurtmeble.eu).
- **Jeden e-shop:** Procentov.cz (Shopyon).
- **Jedna kategorie:** Milo (10 master produktů, 348 variant) — protože tu už máme zmapovanou ze Sprintu 1 experimentu.
- **Žádný srovnávač:** distribuce do Heureky atd. je M5, ne MVP.

Mimo MVP (záměrně):
- Art Decoration (druhý dodavatel)
- Utuli (druhý e-shop)
- Více kategorií než Milo
- Mergado distribuce do srovnávačů
- FAVI/Biano (čeká na ověření Mergado podpory)

**Důvod tohoto úzkého scope.** Polotovar, sochař, hosting, validace, monitoring — to je 5 nových vrstev najednou. Pokud současně přidáme druhého dodavatele a druhý e-shop, máme 5 nových vrstev × 4 kombinace = 20 míst, kde to může selhat. MVP redukuje na 5 míst. Když 5 míst funguje na Procentov+ATOS+Milo měsíc bez incidentu, **přidání další kombinace stojí dny, ne týdny** (DRY zaplatí).

### A.7 Akceptační kritéria

Akceptační kritéria mají dvě úrovně: **MVP** (dokončení této fáze) a **architektonická** (cílový stav, ke kterému jdeme přes M2–M5). Formát MIN/OPT/NICE odráží konsenzus 5/5 vendorů orchestrátoru: MIN = nepřekročitelné, OPT = chceme, NICE = pokud zbude čas.

#### A.7.1 MVP akceptace (Procentov + ATOS, kategorie Milo)

| Úroveň | Kritérium | Měření |
|---|---|---|
| MIN | Polotovar se generuje z ATOS feedu automaticky | Cron běží, výstup existuje, hash se mění při změně vstupu |
| MIN | 482 variant Milo v polotovaru | `count(variants) == 482` |
| MIN | Všechny ceny v CZK, žádná v PLN | Schema validace odmítne mix měn |
| MIN | Žádný produkt s cenou 0 nebo null | Validační kontrakt blokuje |
| MIN | Sochař Shopyon vyrobí XML, který splňuje Igorova akceptační kritéria | Shopyon importér vrátí 0 chyb |
| MIN | XML hostuje na R2 přes HTTPS, dostupné Shopyon importéru | UptimeRobot zelený 99 % |
| MIN | Při chybě validace se publikace **zablokuje**, ne provede | Logy + alert |
| MIN | Po prvním importu Procentov.cz zobrazuje produkty správně (cena, varianty, parametry) | Manuální kontrola na webu, případně iterace |
| OPT | Slovník PL→CZ má pokrytí ≥ 95 % atributů Milo | `% přeložených / % všech == 95` |
| OPT | Override přes `cenove_overridy.csv` funguje | Test case: ručně přidat řádek, znovu vygenerovat, ověřit |
| OPT | Healthchecks.io alert "feed nezpracoval" funguje | Otestováno simulací výpadku |
| OPT | Diff polotovaru proti minulé verzi (kdo přibyl/odešel) | Generuje se vedle XML |
| NICE | Dashboard "stav posledního zpracování" (HTML stránka, R2) | Zobrazuje čas, počet, chyby |
| NICE | Re-run z minulého polotovaru bez tažení ATOS (cache) | Příkaz `make rebuild-from-cache` |

#### A.7.2 Architektonická akceptace (cílový stav po M5)

| Úroveň | Kritérium | Měření |
|---|---|---|
| MIN | Pipeline unese 4 kombinace (Procentov+ATOS, Procentov+ArtDeco, Utuli+ATOS, Utuli+ArtDeco) | DRY: nový sochař = soubor v repo, žádný copy-paste do polotovaru |
| MIN | Přidání nového srovnávače = jedno Mergado pravidlo, ne ticket | Měřeno čas Mirek-only změny |
| MIN | Slovník PL→CZ je jedno místo pravdy | `grep -r "translation"` vrátí jen `slovnik.json` |
| MIN | Žádné cenové pravidlo v Mergadu (jen v Pythonu) | Code review Mergado konfigurace |
| OPT | Kompletní validace polotovaru pokrývá EAN, váhy, rozměry, povinná pole srovnávačů | Validační kontrakt v repo |
| OPT | Slovník dovoluje per-kategorii override (jiný překlad pro nábytek vs. doplňky) | Schema slovníku to umí |
| OPT | Audit trail: pro každý publikovaný feed je čitelná stopa "co bylo změněno proti předchozí verzi" | Git log polotovaru |
| NICE | Self-service: Mirek si umí přidat nového dodavatele beze změny kódu, jen přes konfig | YAML/JSON konfig per dodavatel |
| NICE | Mergado nahrazený custom Python distribucí pro srovnávače, kde Mergado neumí | Rozhodnutí per srovnávač |

### A.8 Rozhodnutí napevno

| # | Rozhodnutí | Stav | Důvod |
|---|---|---|---|
| 1 | Hosting feedu = Cloudflare R2 | Schváleno (Mirek 6.5.2026) | Zdarma do 10 GB/měsíc, HTTPS automaticky, žádný server k údržbě, žádná Hetzner faktura, public bucket = jednoduchý setup |
| 2 | Slovník PL→CZ = JSON v Git | Schváleno (Discovery 1A) | Verze, blame, žádný UI lock-in, lze otevřít v editoru |
| 3 | Validace = blocking gate před publikací | Schváleno (Discovery 1A, MIN kritérium) | Špatný feed je horší než žádný feed (Shopyon zobrazí chyby uživatelům) |
| 4 | Pipeline jazyk = Python | Schváleno (Discovery 1A) | Mirek + Cursor + Claude Code už běží, Utuli pipeline je už Python |
| 5 | Kurz PLN→CZK = `KOEFICIENT_PLN_NA_CZK` v `transformer.py` + override CSV | Schváleno (lekce z 30 854 Kč incidentu) | Žádné Mergado pravidlo na cenu — duplicita! |
| 6 | Monitoring = Healthchecks.io + UptimeRobot | Navrženo | Healthchecks.io = "cron neproběhl" alert; UptimeRobot = "URL nedostupná" alert. Oba zdarma na náš objem. |
| 7 | Kde žije sochař = stejný repo jako polotovar, jiný adresář | Navrženo | Jednoduchost. Když přibude druhý e-shop, je to nová složka, ne nový repo. |
| 8 | Vstup do Mergada (vrstva 5) = e-shop feed, ne polotovar | Navrženo | Mergado distribuuje to, co e-shop publikuje. Pokud by distribuoval polotovar, obejdeme e-shop a riskujeme nesoulad. |

### A.9 Otevřené otázky (zbylé po Discovery 1A, rev. 2)

| # | Otázka | Status | Kdy rozhodnout |
|---|---|---|---|
| Q5 | Publikace na R2 — ručně, cron, nebo webhook po validaci? | Otevřeno | M2, lze začít s cronem a později přidat webhook |
| Q7 | Mergado podpora pro FAVI a Biano — out-of-the-box format existuje? | Otevřeno | Před M5 (distribuce do srovnávačů) — ověřit dotazem na Mergado support |
| Q8 | Co s Mergado řetězcem 349778→349884→349905 (Sprint 1 experiment)? Vypnout hned, nebo nechat jako historickou referenci? | Otevřeno | M2, doporučení: nechat dostupný (read-only) jako edukační materiál, neudržovat |

*Q3 (Igor decoupling) a Q6 (záchranná síť) byly v rev. 2 vyhozeny — falešné problémy.*

### A.10 Cestovní mapa

Milníky jsou **týdenní**, ne dnové. Solo podnikatel + AI jako sparring = realistický takt. **Žádné M0** — neexistuje produkční pipeline, který by potřeboval záchrannou síť.

#### M1 — Polotovar pro Procentov + ATOS
- **Horizont:** 2 týdny
- **Vstupní brief:** transformer.py už existuje (KOEFICIENT_PLN_NA_CZK = 11.115, override CSV); rozšířit o slovník PL→CZ z JSON, sloučení variant, schema validaci
- **Dependence:** žádné externí, jen Mirek + Cursor + Claude Code
- **Akceptace:** A.7.1 MIN body 1–4 (polotovar generuje, 348 variant, CZK, žádné nuly)

#### M2 — Sochař Shopyon + R2 hosting
- **Horizont:** 1 týden
- **Vstupní brief:** mít aktuální Igorovu specifikaci Shopyon Custom Format; mapování polotovaru na tuto specifikaci; upload na R2 přes API; Shopyon import URL
- **Dependence:** R2 účet, Igorova specifikace formátu *(dokument, ne čekání na implementaci)*
- **Akceptace:** A.7.1 MIN body 5–7 (XML splňuje Igorova kritéria, R2 hostuje, validace blokuje při chybě)

#### M3 — První import, iterace, validace v produkci
- **Horizont:** 1 týden (může být víc, podle toho, kolik iterací)
- **Vstupní brief:** první pokusný import přes Shopyon importér; manuální kontrola na webu (cena, varianty, parametry, kategorie); iterace na naší straně (sochař Shopyon) NEBO na Igorově straně (importér/parametry); monitoring kompletní (Healthchecks.io + UptimeRobot); validační kontrakt rozšířit; README pro polotovar a sochaře
- **Iterace je standard, ne riziko.** Pokud po prvním importu produkty nesedí, doladíme. Pokud sedí na první pokus, máme štěstí — počítáme se 2–3 iteracemi.
- **Akceptace:** A.7.1 MIN bod 8 + OPT body, produkty na Procentov.cz vypadají správně

#### M4 — Druhý sochař (Utuli + ATOS)
- **Horizont:** 1 týden (DRY zaplatí — polotovar už existuje)
- **Vstupní brief:** mapování polotovaru na Upgates formát
- **Dependence:** M3 stabilní (Procentov+ATOS běží spolehlivě)
- **Akceptace:** A.7.2 MIN body 1–2 (DRY pattern, Utuli běží na stejném polotovaru)

#### M5 — Mergado distribuce pro srovnávače (Heureka první)
- **Horizont:** 1 týden per srovnávač, sériově
- **Vstupní brief:** nový Mergado projekt vstupující z Procentov.cz feedu, výstup Heureka format
- **Dependence:** M4 stabilní, Q7 vyřešeno pro daný srovnávač
- **Akceptace:** Heureka feed validní, dataset shoduje s e-shopem

**Celkem:** 5–6 týdnů od konce Discovery k plné architektuře včetně Heureky. Solo + AI takt, ne tým.

### A.11 Krev v žilách (insighty, které se nesmí ztratit)

1. **Mergado není centrum, je periferie pro distribuci.** Discovery 1A tohle pojmenovalo. Když Tě někdy něco vede zpátky k tomu, dát Mergadu víc role, vrať se sem.
2. **Igor je galerista, ne dodavatel feedu.** Dává nám akceptační kritéria pro Shopyon importér, my je splníme. Není součástí pipeline, neimplementuje, není v ní coupled. První import přinese iterace — to je standard, ne problém.
3. **Cenotvorba žije v jednom místě.** Pokud někdo někdy navrhne "dáme to taky do Mergada, ať máme zálohu" — řekni ne. 30 854 Kč ti to připomene.
4. **Slovník PL→CZ je jedna pravda.** Pokud ho chceš vidět v Mergadu jako rozumně zobrazený, generuj export ze slovníku, neudržuj dvě verze.
5. **Polotovar je platformově neutrální.** Pokud do něj kdykoliv vleze pole `shopyon_category_id`, pravidlo je porušené. Patří to do sochaře.
6. **Validace = brzda, ne kontrolka.** Špatný feed neproniká dál.
7. **DRY zaplatí ve M4, ne v M2.** První sochař stojí čas, druhý už ne. Tomu věř a nestávej se zkratkářem v M1–M2.
8. **Tohle je první feed pipeline pro Procentov.cz vůbec, ne náhrada existujícího.** Žádný cutover, žádné riziko rozbití starého — staré jsou ruční produkty, které se po nasazení feedu smažou. Po nasazení skok z 30–40 % portfolia na 100 % s variantami a parametry.

### A.12 Co dál

| Akce | Vlákno | Kdo |
|---|---|---|
| Schválit / upravit tento dokument (sekce A, rev. 2) | toto vlákno | Mirek |
| Sekce B (implementační brief pro Cursor + Claude Code) | nové vlákno | Claude (XML Feedy) |
| Q7 ověření Mergado podpory FAVI/Biano | task v Dispatch DB, spust_skript ask_mergado.py | Claude (XML Feedy) |
| Zápis do Notion DB Rozhodnutí (8 rozhodnutí z A.8) | toto vlákno, po schválení | Claude (XML Feedy) |
| Získat aktuální specifikaci Shopyon Custom Format od Igora | mimo vlákno *(email)* | Mirek, před M2 |

---

## Sekce B — Implementační (pro Cursor + Claude Code)

### B.1 Status a vstupy

| Pole | Hodnota |
|---|---|
| Datum | 2026-05-11 |
| Autor | Claude (XML Feedy vlákno) + Mirek (rozhodnutí) |
| Validace | 2 kola orchestrátoru (5 vendorů: gemini, gpt-4o, deepseek, grok, mistral) |
| Pokrytí | M1 (polotovar) + M2 (sochař Shopyon + R2). M3–M5 jsou samostatná vlákna. |
| Mimo scope | Detailní implementace každé Python funkce *(Cursor si to dotáhne z briefů)*, Q7 ověření Mergada, Igorova email komunikace |

**Vstupy:**
- Sekce A rev. 2 *(zejména A.3, A.4, A.7, A.8)*
- Existující `transformer.py` v `C:\work\xml-feedy\procentov\` *(Heureka generátor, 29.6 KB, čte parquet polotovar v1.0)*
- Existující `cenove_overridy.csv` *(prázdný, hlavička `id_produktu,koeficient_override,poznamka,platnost_do`)*
- Stažený ATOS source feed v `C:\work\mergado-api\atos_source_feed.xml` *(5 551 produktů, Ceneo.pl formát)*
- Historická komunikace s Igorem *(tikety 0029941–43, vzor.xml, Custom Format 48267)*

### B.2 Mapa proti realitě — kde dnes co je

Aktuální stav v `C:\work\xml-feedy\procentov\`:

| Soubor / složka | Co to je | Co s tím v M1/M2 |
|---|---|---|
| `transformer.py` (29.6 KB) | Heureka XML generátor *(sochař, ne polotovar generátor)*. Čte parquet polotovar v1.0, generuje Heureka formát. | **Přejmenovat** na `procentov/socha_heureka.py` *(rozhodnutí R1)*. Slouží jako reference, ale nepoužívá se v M1/M2 pipeline. Aktivuje se až v M5 (případně). |
| `cenove_overridy.csv` (prázdný) | Schema definovaný, hlavička jen | **Zachovat**. M1 polotovar generátor čte tento soubor a aplikuje override per produkt. |
| `requirements.txt`, `.venv/`, `.gitignore` | Python prostředí | **Zachovat**. Rozšířit `requirements.txt` o nové závislosti M1/M2. |
| `out/procentov_intermediate.xml` | Výstup transformer.py | **Zrušit**. Nahrazeno novou strukturou výstupů. |
| `docs/`, `README.md`, `setup_repo*.ps1`, `diag*.ps1` | Discovery dokumenty, setup skripty | **Zachovat** beze změny v M1/M2. |
| `C:\work\atos-polotovar\current\polotovar.parquet` *(mimo aktuální repo)* | Parquet polotovar v1.0 z neznámého upstream skriptu | **Ignorovat**. M1 čte ATOS XML přímo (rozhodnutí R3). Parquet je dead experiment, ne zdroj pravdy. |
| `C:\work\mergado-api\atos_source_feed.xml` | Stažený surový ATOS XML *(reference)* | **Použít jako test fixture** pro parser ATOS XML. |

**Cílový stav repa po M1+M2** *(rozhodnutí R7)*:

```
C:\work\xml-feedy\
├── polotovar\                       # SDÍLENÝ (M1)
│   ├── __init__.py
│   ├── parser_atos.py               # Parse Ceneo.pl XML → in-memory dict
│   ├── translator.py                # Aplikace slovník PL→CZ
│   ├── pricing.py                   # PLN→CZK koeficient + overridy
│   ├── variants.py                  # Sloučení variant na master+N
│   ├── schema.py                    # pydantic model polotovaru v2.0
│   ├── validator.py                 # Blocking gate kontrakt
│   ├── generate.py                  # Hlavní pipeline (orchestrace)
│   └── tests\
│       ├── fixtures\
│       │   └── atos_milo_sample.xml
│       ├── test_parser_atos.py
│       ├── test_translator.py
│       ├── test_pricing.py
│       ├── test_variants.py
│       └── test_validator.py
├── slovnik\                         # SDÍLENÝ (M1)
│   ├── slovnik.json                 # Vlastní slovník PL→CZ
│   ├── slovnik_schema.json          # JSON schema slovníku
│   └── bootstrap.py                 # Extract + Google Translate skript
├── procentov\                       # E-SHOP SPECIFICKÝ (M2)
│   ├── socha_shopyon.py             # Polotovar → Shopyon Custom Format XML
│   ├── socha_heureka.py             # Přejmenovaný transformer.py (M5+)
│   └── tests\
│       └── test_socha_shopyon.py
├── utuli\                           # E-SHOP SPECIFICKÝ (M4, prázdné v M1/M2)
│   └── .gitkeep
├── hosting\                         # SDÍLENÝ (M2)
│   ├── upload_r2.py                 # Upload XML na Cloudflare R2
│   └── config.py                    # R2 bucket, endpoint, custom domain
├── config\
│   ├── procentov.yaml               # Per e-shop konfigurace
│   └── atos.yaml                    # Per dodavatel konfigurace
├── cenove_overridy.csv              # PŘEMÍSTĚN sem (per Procentov+ATOS)
├── out\                             # Lokální výstup (ne v Git)
├── requirements.txt
├── .env.example                     # Vzor pro Windows Env Vars
├── README.md
└── DISCOVERY_FEED_ARCHITECTURE.md
```

**Migrace v M1 (první commit):**
1. Přejmenovat `procentov/transformer.py` → `procentov/socha_heureka.py`
2. Vytvořit prázdné adresáře `polotovar/`, `slovnik/`, `procentov/`, `utuli/`, `hosting/`, `config/`
3. Přemístit `cenove_overridy.csv` do rootu *(zůstává per Procentov+ATOS jen v MVP, později v `config/`)*
4. Commit message: `M1.0: Repo refactor podle R7 multi-eshop struktura`

### B.3 M1 — Polotovar v2.0

#### B.3.1 Schema polotovaru v2.0 (pydantic model)

**Rozhodnutí R8:** Rozšířený MIN set, EAN přesunut do OPT (rozhodnutí B z poslední revize).

```python
# polotovar/schema.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from decimal import Decimal

class PriceCZK(BaseModel):
    """Cena v CZK po aplikaci koeficientu a overridů."""
    value: Decimal = Field(..., gt=0, description="MIN: > 0, blocking")
    currency: Literal["CZK"] = "CZK"
    koeficient_used: Decimal  # Audit: jaký koeficient byl použit
    override_applied: bool = False  # Audit: byl použit override z CSV?

class Image(BaseModel):
    url: str = Field(..., min_length=1)
    is_main: bool = False

class Attribute(BaseModel):
    """Variantní nebo parametrický atribut."""
    name_cz: str = Field(..., min_length=1, description="MIN: blocking")
    name_pl: str  # Audit field
    value_cz: str = Field(..., min_length=1)
    value_pl: str  # Audit field
    is_variant: bool = Field(..., description="True = variantní, False = parametrický")

class Variant(BaseModel):
    """Jedna konkrétní varianta produktu."""
    id: str = Field(..., min_length=1)
    price_czk: PriceCZK
    availability: Literal["in_stock", "out_of_stock", "preorder"]
    stock_quantity: Optional[int] = None
    image_link: str = Field(..., min_length=1, description="MIN: blocking")
    additional_image_links: List[Image] = []  # OPT
    variant_attributes: List[Attribute]  # Co rozlišuje variantu (Barva, Materiál)
    ean: Optional[str] = None  # OPT (rozhodnutí B)
    url: Optional[str] = None  # Pro EAN extrakci a audit

class Product(BaseModel):
    """Master produkt s N variantami."""
    # MIN pole (blocking)
    id: str = Field(..., min_length=1)
    item_group_id: str = Field(..., min_length=1)
    title_cz: str = Field(..., min_length=1)
    description_cz: str = Field(..., min_length=1)
    category_path_cz: List[str] = Field(..., min_items=1)
    price_czk: PriceCZK  # Cena master produktu (nejnižší z variant)
    image_link: str = Field(..., min_length=1)
    availability: Literal["in_stock", "out_of_stock", "preorder"]
    variants: List[Variant] = Field(..., min_items=1)
    attrs_cz: List[Attribute] = Field(..., description="Parametrické atributy společné pro všechny varianty")

    # OPT pole (warning)
    brand: Optional[str] = None
    gtin: Optional[str] = None  # EAN master, OPT
    dimensions: Optional[str] = None
    weight_kg: Optional[Decimal] = None
    color: Optional[str] = None
    material: Optional[str] = None
    additional_image_links: List[Image] = []

    # Audit fields (vždy zachovat)
    title_pl: str
    description_pl: str
    category_path_pl: List[str]
    attrs_raw: List[dict]  # Surová struktura z ATOS pro debug

class Polotovar(BaseModel):
    """Kanonický polotovar pro jeden dodavatel × jednu kategorii."""
    supplier: Literal["atos", "art_decoration"]
    category: str  # např. "milo"
    generated_at: str  # ISO 8601 timestamp
    schema_version: Literal["2.0"] = "2.0"
    products: List[Product]
    
    @validator("products")
    def must_have_products(cls, v):
        if len(v) == 0:
            raise ValueError("Polotovar je prázdný — blocking")
        return v
```

**Klíčový princip:** všechno `_pl` (polské texty, raw atributy) zůstává v polotovaru jako **audit field**, ne primární data. Pokud Cursor/sochař omylem použije `title_pl` místo `title_cz`, vidíme to v code review.

#### B.3.2 Slovník PL→CZ — struktura a workflow

**Lokace:** `slovnik/slovnik.json` (v Git, jediné místo pravdy).

**Schema:**

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-05-11T14:00:00Z",
  "namespaces": {
    "atributy": {
      "Kolor": "Barva",
      "Materiał": "Materiál",
      "Wymiary": "Rozměry",
      "Waga": "Hmotnost",
      "Kod_producenta": "Kód výrobce"
    },
    "hodnoty": {
      "Dąb Sonoma": "Dub Sonoma",
      "Biały Zimny": "Bílá studená",
      "Velvet": "Velvet",
      "MIKROFAZA": "Mikrovlákno"
    },
    "kategorie": {
      "FOTELE": "Křesla",
      "FOTEL MILO": "Křeslo Milo",
      "FOTELE/FOTEL MILO": "Křesla / Křeslo Milo"
    }
  },
  "per_kategorii_override": {
    "FOTELE": {
      "Wymiary": "Rozměry křesla"
    }
  },
  "audit": {
    "Dąb Sonoma": {"_source": "google", "_updated_at": "2026-05-11T14:00:00Z", "_reviewed_by": "mirek"},
    "Velvet": {"_source": "manual", "_updated_at": "2026-05-11T14:05:00Z"}
  }
}
```

**Bootstrap workflow (rozhodnutí R5):**

```bash
# Krok 1: Extract všech unikátních polských stringů z ATOS XML
python slovnik/bootstrap.py extract --xml C:\work\mergado-api\atos_source_feed.xml --category milo --out slovnik/slovnik_milo_extract.json

# Krok 2: Google Translate jako návrh (vyplní null hodnoty)
python slovnik/bootstrap.py translate --in slovnik/slovnik_milo_extract.json --out slovnik/slovnik_milo_draft.json

# Krok 3: Mirek otevře slovnik_milo_draft.json v editoru, zreviduje překlady
#   (cca 50-150 stringů × 10 sekund = 25 minut čisté práce)

# Krok 4: Merge revize do slovnik/slovnik.json
python slovnik/bootstrap.py merge --review slovnik/slovnik_milo_draft.json --target slovnik/slovnik.json
```

**Google Translate API klíč:** Windows Environment Variable `GOOGLE_TRANSLATE_API_KEY` *(per userPreferences, ne v .env souboru)*. Pro Milo (cca 150 stringů × 30 znaků) náklady ~0.1 USD, free tier dostatečný.

#### B.3.3 Parser ATOS XML — Ceneo.pl formát

**Vstup:** `http://hurtmeble.eu/feeds/oferta_hurtowa_PL_PLN.xml` *(přes HTTPS download v GitHub Actions, viz B.3.6)*.

**Realita struktury (z analýzy stažené XML):**

```xml
<offers>
  <o id="..." price="..." stock="..." avail="..." url="...">
    <name>Fotel Milo nogi 20cm białe...</name>
    <cat>FOTELE/FOTEL MILO/.../FOTEL MILO NOGI 20 BIAŁE</cat>
    <desc>...</desc>
    <symbol>3-7-70-9</symbol>
    <imgs>
      <img main="1">https://hurtmeble.eu/.../export.jpg</img>
      <img>https://hurtmeble.eu/.../export.jpg</img>
    </imgs>
    <attrs>
      <attr name="Kolor Płyty Laminowanej">
        <a name="Dąb Sonoma" />
        <a name="Biały Zimny" />
      </attr>
      <attr name="Materiał">
        <a name="Velvet" />
      </attr>
    </attrs>
  </o>
</offers>
```

**Co ATOS XML obsahuje:**
- ✅ `id`, `name`, `cat`, `desc`, `price`, `stock`, `avail`, `url`
- ✅ `imgs` s `main="1"` atributem
- ✅ `attrs` (variantní + parametrické míchané)
- ✅ `symbol` (Kod_producenta)

**Co ATOS XML NEobsahuje:**
- ❌ EAN jako čisté pole *(je v URL, regex extract — rozhodnutí B = OPT)*
- ❌ Cena v CZK *(jen PLN)*
- ❌ CZ překlady *(jen polské texty)*
- ❌ Rozměry, hmotnost jako structured fields *(jen v `attrs` nebo `desc` HTML)*

**Klíčová logika parseru — rozlišení variantních vs. parametrických atributů:**

Z `attrs` skupin v `<attr name="...">` některé jsou variantní (rozdělují varianty), některé parametrické (společné pro všechny varianty produktu). Heuristika:

| Atribut | Klasifikace | Logika |
|---|---|---|
| `Kolor`, `Kolor Płyty Laminowanej`, `Barva` | **Variantní** | Whitelist v `config/atos.yaml` |
| `Materiał`, `Tkanina` | **Variantní** | Whitelist |
| `Wymiary`, `Waga`, `Kod_producenta` | **Parametrické** | Whitelist |
| Cokoliv jiného | **Parametrické** (default safe) | Default fallback |

**Konfigurace v `config/atos.yaml`:**

```yaml
supplier: atos
source_url: http://hurtmeble.eu/feeds/oferta_hurtowa_PL_PLN.xml
variant_attribute_whitelist:
  - Kolor
  - "Kolor Płyty Laminowanej"
  - Barva
  - Materiał
  - Tkanina
parameter_attribute_whitelist:
  - Wymiary
  - Waga
  - Kod_producenta
ean_extraction:
  source: url
  regex: '--(\d{13})\.html'  # EAN 13 čísel mezi -- a .html
  fallback: null
```

**Sloučení variant — algoritmus (revize 2026-05-12):**

Empirická analýza ATOS XML ukázala, že `<cat>` cesta má 4 segmenty:
- segment 0: kategorie zboží (FOTELE, SOFY)
- segment 1: **název produktu** = master karta (FOTEL MILO, SOFA MILO)
- segment 2: materiálová podkategorie (Mikrofaza, Eco Skóra, Velvet) — variantní osa
- segment 3: nohy (výška + barva) — variantní osa

Master produkt na e-shopu = jedna karta "Křeslo Milo" se všemi materiály/barvami/nohami jako variantami (vzor Utuli.cz).

Algoritmus:
1. Parse všech <o> z XML.
2. Normalizace <cat>: re.sub(r'\s+', ' ', cat).strip()
3. Filtr podle category_filter (substring v cat, case-insensitive).
4. item_group_key = cat_path[1] (druhý segment, fallback cat_path[0])
5. cat_path_pl = cat_path[:2] (kategorie + produkt)
6. subcategory_pl = cat_path[2] pokud existuje (materiálová dimenze, použije se v M1.3)
7. Group offers podle item_group_key → list ParsedProduct, seřazeno podle item_group_key.

**Variantní osy** (extrakce do M1.3, ne M1.1):
- Materiál: z segment 2 (Mikrofaza / Eco Skóra / Velvet)
- Barva potahu: z <name> regexem (např. "D1", "D2", "BL75", "MG02")
- Výška noh: z segment 3 (15, 20, nebo nedefinováno)
- Barva noh: z segment 3 (białe, buk, venge, chrom)

**Pro Milo kategorii to dává 2 master karty (FOTEL MILO + SOFA MILO) a 482 variant celkem.**

Pozn.: Discovery 1A puvodne pocitalo s "10 master + 348 variant" — to byl odhad ze Sprint 1 Mergado experimentu, ne empiricky verified. Aktualni cisla 2+482 jsou z primarniho zdroje (ATOS XML 2026-05-12).

**Test fixture:** `polotovar/tests/fixtures/atos_milo_sample.xml` — 10 master produktů Milo *(z `C:\work\mergado-api\atos_source_feed.xml`, filtr na `<o>` v kategorii FOTEL MILO)*.

#### B.3.4 Validační kontrakt — blocking gate

**Struktura:** dvě sady pravidel — **blocking** (zablokuje pipeline) a **warning** (jen log).

**Blocking pravidla** *(rozhodnutí R6: MIN pole z R8 = blocking)*:

| ID | Pravidlo | Důsledek selhání |
|---|---|---|
| BLOCK-1 | Polotovar má ≥ 1 produkt | `exit 1`, žádný zápis |
| BLOCK-2 | Každý produkt má `id`, `item_group_id`, `title_cz`, `description_cz`, `category_path_cz` | `exit 1` |
| BLOCK-3 | Každý produkt má `price_czk.value > 0` *(žádné nuly, žádné null)* | `exit 1` |
| BLOCK-4 | Žádná cena s `currency != "CZK"` | `exit 1` |
| BLOCK-5 | Každý produkt má alespoň 1 variantu | `exit 1` |
| BLOCK-6 | Každý produkt má `image_link` *(neprázdný string)* | `exit 1` |
| BLOCK-7 | Žádné duplicitní `id` ani `item_group_id` napříč produkty | `exit 1` |
| BLOCK-8 | `count(variants) == 482` pro kategorii Milo *(MVP MIN bod 2)* | `exit 1` |
| BLOCK-9 | Žádné polské texty v `title_cz`, `description_cz`, `category_path_cz`, `attrs_cz` *(detekce: polské diakritiky `ą`, `ę`, `ł`, `ś`, `ż`, `ź`)* | `exit 1` |

**Warning pravidla** *(rozhodnutí R6: OPT pole = soft warning)*:

| ID | Pravidlo | Důsledek selhání |
|---|---|---|
| WARN-1 | Každý produkt má `gtin` (EAN) | Log warning, počítadlo |
| WARN-2 | Každý produkt má `brand` | Log warning |
| WARN-3 | Každý produkt má `dimensions` | Log warning |
| WARN-4 | Každá varianta má `ean` | Log warning |
| WARN-5 | Slovník pokrytí ≥ 95 % unikátních atributů | Log warning |

**Output při blocking selhání:**

```
out/validation_errors.json
```

Struktura:

```json
{
  "timestamp": "2026-05-11T14:30:00Z",
  "verdict": "BLOCKED",
  "blocking_errors": [
    {
      "rule": "BLOCK-9",
      "product_id": "1018",
      "field": "title_cz",
      "value": "Fotel Milo nogi 20cm białe...",
      "detail": "Polské diakritiky detekovány (ą, ł)"
    }
  ],
  "warnings": [
    {
      "rule": "WARN-1",
      "product_id": "1023",
      "detail": "Chybí EAN"
    }
  ]
}
```

Tento JSON je **klíčový pro Mirka při debugu** — bez něj je validace černá skříňka.

**Healthchecks.io ping:** úspěch *(verdict == PASS)* = GET na `https://hc-ping.com/<uuid>`. Failure *(verdict == BLOCKED)* = žádný ping → Healthchecks po timeout interval pošle alert email/SMS.

#### B.3.5 Cron — GitHub Actions setup

**Rozhodnutí R4:** GitHub Actions, ne Windows Scheduler.

**Soubor:** `.github/workflows/m1_polotovar.yml`

```yaml
name: M1 Polotovar generation
on:
  schedule:
    - cron: '0 4 * * *'  # Denně 04:00 UTC = 05:00/06:00 Prague
  workflow_dispatch:  # Manuální spuštění z GitHub UI
jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python polotovar/generate.py --supplier atos --category milo
        env:
          GOOGLE_TRANSLATE_API_KEY: ${{ secrets.GOOGLE_TRANSLATE_API_KEY }}
      - name: Healthchecks ping
        if: success()
        run: curl -fsS https://hc-ping.com/${{ secrets.HEALTHCHECKS_M1_UUID }}
      - name: Upload artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: polotovar-output
          path: out/
```

**Secrets v GitHub Actions** *(per userPreferences: ne v .env, ale ve specifickém případě GitHub Actions = GitHub Secrets, což je per-repo bezpečné úložiště)*:
- `GOOGLE_TRANSLATE_API_KEY`
- `HEALTHCHECKS_M1_UUID`
- `R2_ACCESS_KEY_ID` *(pro M2)*
- `R2_SECRET_ACCESS_KEY` *(pro M2)*

**Známé limity GitHub Actions free tier:** 2 000 min/měsíc CPU pro privátní repa, neomezeně pro veřejná. Náš denní běh ~5 min → 150 min/měsíc, daleko pod limitem.

#### B.3.6 Dispatch tasky pro M1

5 tasků v 8-polním kontraktu pro Dispatch DB:

| Task | Body | Status | Priority | Project | Mode | Done_criteria | Result |
|---|---|---|---|---|---|---|---|
| M1.0 Repo refactor | Vytvořit strukturu z B.2 (přejmenovat transformer.py, vytvořit adresáře, přemístit CSV). | New | P1 | XML_Feedy | Claude Code | Adresáře existují, `procentov/socha_heureka.py` existuje, `cenove_overridy.csv` v rootu | — |
| M1.1 Parser ATOS XML | Implementovat `polotovar/parser_atos.py` podle B.3.3, vč. testů. | New | P1 | XML_Feedy | Cursor | Test fixture parsuje na 2 master + 482 variant (Milo: FOTEL MILO 349, SOFA MILO 133), pytest pass | — |
| M1.2 Slovník bootstrap | Implementovat `slovnik/bootstrap.py` (extract + translate + merge), vygenerovat `slovnik.json` pro Milo. | New | P1 | XML_Feedy | Cursor + Mirek (revize) | `slovnik.json` ≥ 95 % pokrytí Milo atributů | — |
| M1.3 Pipeline + validace | Implementovat `polotovar/generate.py`, `pricing.py`, `variants.py`, `validator.py`, `schema.py`. | New | P1 | XML_Feedy | Cursor | `python polotovar/generate.py --supplier atos --category milo` projde, parquet vznikne, A.7.1 MIN body 1–4 splněny | — |
| M1.4 GitHub Actions setup | `.github/workflows/m1_polotovar.yml`, Healthchecks.io check vytvořen, secrets nastaveny. | New | P2 | XML_Feedy | Claude Code | Workflow zelený 3× po sobě v cronu | — |

**Acceptance map na A.7.1:**
- M1.3 splní MIN body 1, 2, 3, 4, 7 *(polotovar generuje, 348 variant, CZK, žádné nuly, validace blokuje)*

### B.4 M2 — Sochař Shopyon + R2 hosting

#### B.4.1 Cloudflare R2 setup

**Předpoklad:** Mirek má Cloudflare účet *(domain procentov.cz tam pravděpodobně už je, ověření v M2.0 tasku)*.

**Konfigurace:**

| Parametr | Hodnota |
|---|---|
| Bucket name | `procentov-feeds` |
| Region | EU *(nejbližší k Shopyon importéru)* |
| Public access | Read-only, GET povolen |
| Custom domain | `feeds.procentov.cz` *(rozhodnutí R2)* — CNAME na R2 bucket |
| API token scope | Read + Write na `procentov-feeds`, žádné delete |
| Storage | Free tier (10 GB) — náš feed cca 5 MB, daleko pod limit |

**DNS setup (Mirek manuálně):**
```
feeds.procentov.cz  CNAME  <r2-bucket-public-url>.r2.dev
```

**Konfigurace v repo (`hosting/config.py`):**

```python
import os

R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = "procentov-feeds"
R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_PUBLIC_BASE = "https://feeds.procentov.cz"  # Custom domain
```

Klíče jsou ve **Windows Environment Variables** lokálně *(per userPreferences)*, ve **GitHub Secrets** pro Actions runner.

#### B.4.2 Sochař Shopyon — mapování polotovar → Custom Format 48267

**Cílový formát** *(Custom Format 48267 "Shopyon – Atos VARIANT v2", validovaný proti Igorovu `vzor.xml` z tiketu 17.4)*:

```xml
<offers>
  <o id="{master_id}" price="{master_price_czk}" stock="{master_stock}" avail="{master_avail}" url="{master_url}">
    <name>{title_cz}</name>
    <cat>{category_path_cz_joined_with_pipe}</cat>
    <desc><![CDATA[{description_cz}]]></desc>
    <imgs>
      <img main="1">{main_image_url}</img>
      <img>{additional_image_url}</img>
    </imgs>
    <attrs>
      <attr name="Rozměry"><a name="{dimensions}" /></attr>
      <attr name="Hmotnost"><a name="{weight_kg}" /></attr>
    </attrs>
    <variants>
      <variant id="{variant_id}" price="{variant_price_czk}" stock="{variant_stock}" avail="{variant_avail}">
        <params>
          <param><n>Barva</n><val>{color_cz}</val></param>
          <param><n>Materiál</n><val>{material_cz}</val></param>
        </params>
      </variant>
    </variants>
  </o>
</offers>
```

**Mapování polotovar → Shopyon XML:**

| Shopyon XML element | Polotovar field | Poznámka |
|---|---|---|
| `<o id="...">` | `Product.id` | |
| `<o price="...">` | `Product.price_czk.value` | Master cena = nejnižší variant |
| `<o stock="...">` | sum varianty stock_quantity | |
| `<o avail="...">` | `Product.availability` | Dostupný = aspoň 1 varianta in_stock |
| `<o url="...">` | derive z item_group_id | |
| `<name>` | `Product.title_cz` | **Obecný název** (AK-4 z Igora) |
| `<cat>` | `Product.category_path_cz` joined with `\|` | **Oddělovač `\|`** (AK-6 z Igora) |
| `<desc>` | `Product.description_cz` v CDATA | **CDATA** (požadavek z 24.4 odpovědi Igora) |
| `<img main="1">` | `Product.image_link` | **AK-7** z Igora |
| `<img>` | `Product.additional_image_links` | |
| `<attrs><attr>` | `Product.attrs_cz` | **POUZE parametrické** (rozměry, hmotnost) — AK-3 |
| `<variants><variant id>` | `Variant.id` | |
| `<variant price>` | `Variant.price_czk.value` | |
| `<variant stock>` | `Variant.stock_quantity` | |
| `<variant avail>` | `Variant.availability` | |
| `<params><param>` | `Variant.variant_attributes` | **POUZE variantní** (Barva, Materiál) — AK-1 |

**Konzistence s Igorovými AK** *(z tiketu 17.4 a 24.4)*:
- AK-1 ✅ Variantní params jen Barva + Materiál
- AK-3 ✅ Obecné params (rozměry, hmotnost) na úrovni `<o>`
- AK-4 ✅ Obecný `<name>` produktu
- AK-5 ✅ Distribuce variant funguje *(z polotovaru jednoznačně)*
- AK-6 ✅ Oddělovač kategorií `|`
- AK-7 ✅ `<img main="1">`
- CDATA pro popisy ✅
- EAN ⚠️ OPT, ve variant pokud existuje

#### B.4.3 Upload script — R2 push

**Soubor:** `hosting/upload_r2.py`

**Atomic upload pattern** *(R2 nepodporuje atomic rename — používáme Copy + Delete)*:

```
1. Vygeneruj XML lokálně do out/procentov_shopyon.xml
2. Validate XML *(well-formed, ne prázdný, > 1 KB)*
3. Upload na R2 jako `procentov_shopyon_tmp_{timestamp}.xml`
4. Verify HEAD request *(R2 vrátí ETag, ověřit shodu s lokálním SHA256)*
5. Copy R2 object: `procentov_shopyon_tmp_{timestamp}.xml` → `procentov_shopyon.xml` *(production key)*
6. Delete `procentov_shopyon_tmp_{timestamp}.xml`
7. Archive: copy `procentov_shopyon.xml` → `archive/procentov_shopyon_{date}.xml`
8. Cleanup: smazat archive starší než 30 dnů
9. Healthchecks.io ping úspěch
```

**Výsledek:** Shopyon importér vidí na `https://feeds.procentov.cz/procentov_shopyon.xml` **vždy validní XML** *(nikdy half-written)*.

#### B.4.4 Shopyon import URL switch

**Postup:**
1. Mirek pošle Igorovi URL `https://feeds.procentov.cz/procentov_shopyon.xml` *(přes helpdesk.shopyon.cz tiket)*
2. Igor nakonfiguruje **demo Shopyon importér** (`procentov.demo-shopyon.cz`, tiket 0004071) na čtení této URL
3. Demo import proběhne, ověříme na demo webu, že produkty se objevily
4. **Produkce zatím NEpřepínáme.** Produkční Shopyon importér přepneme až po M3 (iterace + validace).

#### B.4.5 End-to-end test (M2 dokončení)

**Scénář:**
1. Přidat ručně řádek do `cenove_overridy.csv`:
   `1018,1.5,Test override M2,2026-12-31`
2. Spustit pipeline lokálně: `python polotovar/generate.py && python procentov/socha_shopyon.py && python hosting/upload_r2.py`
3. Ověřit: `curl https://feeds.procentov.cz/procentov_shopyon.xml | grep 'id="1018"'` — cena musí být **starou × 1.5 × 11.115** (PLN × koeficient × override)
4. Trigger Igorův demo importér *(nebo počkat na příští periodický import)*
5. Otevřít `procentov.demo-shopyon.cz/produkt/fotel-milo-...` — cena na webu odpovídá override
6. **Úklid:** smazat testovací řádek z CSV, znovu vygenerovat, ověřit původní cena

**Acceptance:** A.7.1 MIN body 5, 6, 7 *(sochař vyrobí validní XML, R2 hostuje přes HTTPS, validace blokuje)*.

#### B.4.6 Dispatch tasky pro M2

6 tasků:

| Task | Body | Status | Priority | Project | Mode | Done_criteria | Result |
|---|---|---|---|---|---|---|---|
| M2.0 R2 setup | Vytvořit bucket `procentov-feeds`, API token, nastavit CNAME `feeds.procentov.cz`. | New | P1 | XML_Feedy | Mirek (Cloudflare UI) + Claude Code (konfigurace) | `curl https://feeds.procentov.cz/test.txt` vrací uploadovaný test soubor | — |
| M2.1 Igorova specifikace | Mirek kontaktuje Igora, potvrdí, že Custom Format 48267 platí i pro přímý XML import *(nebo dostane aktualizaci)*. | New | P1 | XML_Feedy | Mirek (email) | Specifikace přiložena k M2.2 task | — |
| M2.2 Sochař Shopyon | Implementovat `procentov/socha_shopyon.py` podle B.4.2 mapování + testy. | New | P1 | XML_Feedy | Cursor | Test fixture polotovar → XML, XML matchuje Custom Format 48267 strukturou | — |
| M2.3 Upload script | Implementovat `hosting/upload_r2.py` podle B.4.3 atomic patternu. | New | P1 | XML_Feedy | Cursor | XML na `feeds.procentov.cz` accessible, archive funguje | — |
| M2.4 Demo Shopyon napojení | Poslat URL Igorovi, ověřit demo import. | New | P1 | XML_Feedy | Mirek (komunikace) | Demo importér čte z R2, produkty na demo webu | — |
| M2.5 E2E test | Provést scénář z B.4.5. | New | P1 | XML_Feedy | Mirek + Claude (verify) | A.7.1 MIN body 5, 6, 7 splněny | — |

### B.5 Brief pro Cursor / Claude Code (delegace)

#### B.5.1 Pattern přílohy k Dispatch tasku

Každý Dispatch task pro M1/M2 dostane **brief jako přílohu** v Notion task page nebo MD v repo. Brief obsahuje:

1. **Kontext** — odkaz na sekci Discovery (`B.3.3` nebo `A.4`)
2. **Vstupy** — konkrétní soubory, parametry, formáty
3. **Výstup** — konkrétní soubor, schema, místo v repo
4. **Acceptance criteria** — odkaz na A.7.1 MIN bod
5. **Routing** — Cursor / Claude Code / Mirek
6. **Test fixtures** — pokud existují, cesty

#### B.5.2 Příklad briefu — M1.1 Parser ATOS XML

```markdown
# Brief: M1.1 — Parser ATOS XML

**Kontext:** Discovery `B.3.3`, sekce A.4 (polotovar je platformově neutrální).

**Vstup:**
- ATOS source XML: `http://hurtmeble.eu/feeds/oferta_hurtowa_PL_PLN.xml` (download v parseru)
- Test fixture: `polotovar/tests/fixtures/atos_milo_sample.xml`
- Konfigurace: `config/atos.yaml` (variant_attribute_whitelist, parameter_attribute_whitelist, ean_extraction)

**Výstup:**
- `polotovar/parser_atos.py` — funkce `parse(xml_path: str, category_filter: str) -> List[ParsedProduct]`
- `polotovar/tests/test_parser_atos.py` — pytest

**Acceptance:**
- Test fixture parsuje na 10 master + 348 variant *(MIN bod 2)*
- Variantní vs. parametrické atributy rozdělené podle whitelist
- EAN extrahován z URL přes regex, pokud regex selže = None *(žádný hard fail, OPT pole)*
- pytest pass

**Routing:** Cursor (interactive coding s testy)

**Mimo scope:** Translation, pricing, validation, schema mapping na pydantic. To je M1.3.
```

#### B.5.3 KB validace gate — NEAPLIKUJE SE pro M1/M2

**Sekce B.5.3 záměrně prázdná.** M1 a M2 jsou **mimo Mergado scope** — Python pipeline, sochař, R2. Žádná Mergado pravidla, žádné Mergado projekty, žádné Custom Formáty editace.

**KB validace gate se aktivuje pro M5** *(Mergado distribuce do srovnávačů)*. Tam každý task **MUSÍ projít** `ask_mergado.py` před implementací.

### B.6 Co B nepokrývá (explicitní out-of-scope)

| Téma | Kam to patří |
|---|---|
| M3 (první import, iterace v produkci, monitoring + UptimeRobot) | Samostatné vlákno po M2 dokončení |
| M4 (Utuli + Upgates sochař) | Samostatné vlákno po M3 dokončení |
| M5 (Mergado distribuce do Heureka/Glami/...) | Samostatné vlákno + KB validace gate |
| Q7 (FAVI/Biano Mergado podpora) | Samostatný task v Dispatch DB, ask_mergado.py + případně forum.mergado.cz |
| Igor email/ticket komunikace | Mirek sám, mimo brief |
| Diff polotovaru proti minulé verzi *(OPT, A.7.1)* | Přesun do M3 *(vendoři konsenzus: pro MVP zbytečné)* |
| Audit trail Git log polotovaru *(OPT, A.7.2)* | Přesun do M3 |
| Dashboard "stav posledního zpracování" *(NICE, A.7.1)* | Případně M3+ |
| Mergado řetězec 349778→349884→349905 — vypnutí/zachování *(Q8)* | Mirek rozhodne v M2 nebo M3, nemá vliv na implementaci |

### B.7 Risk register

Vendoři orchestrátoru (2 kola, 5 vendorů) označili tyto rizika. Sekce B je řeší pojistkami:

| Riziko | Pojistka v B |
|---|---|
| Slovník neúplný → blocking validace zablokuje feed | `WARN-5` ne BLOCK; MIN pole z R8 = blocking, OPT = soft warning *(rozhodnutí R6)* |
| ATOS XML formát změna *(dodavatel přidá pole, přejmenuje)* | XSD validace surového XML v parseru, fail-fast s konkrétní chybou |
| Křehkost sloučení variant *(změna URL formátu)* | Test fixture verifikuje 10 master + 348 variant, regrese chytne změnu |
| GitHub Actions limity *(6h CPU/měsíc privátní)* | Repo veřejný *(neomezeně)*, denní běh ~5 min daleko pod limit |
| Google Translate cost | Free tier ~0.1 USD pro Milo, monitoring kvóty v M3 |
| R2 atomic rename nepodporován | Atomic upload pattern *(temp + verify + copy + delete)* v B.4.3 |
| Windows Env Vars nesynchronizované s Vrátným po změně | Diagnostika přes 3řádkový Python skript *(per userPreferences)*, restart Vrátný + Tunel |
| CSV overridy syntaxe *(desetinná čárka, chybějící ID)* | Schema validace CSV před aplikací *(pydantic model OverrideRow)* |
| EAN regex selže pro některé produkty | OPT pole *(rozhodnutí B)*, WARN-1 počítá výskyt, M3 vyhodnotí, zda zpřísnit |
| Igorova specifikace nedorazí včas | M2.1 task = email Igorovi, blocker M2.2; pokud nedorazí do 2 dnů, použít známý Custom Format 48267 + doladit 1 commitem |

### B.8 Závěrečný checklist před delegací

- [x] Mirek schválil osnovu sekce B *(2026-05-11, V2 validace)*
- [x] 8 rozhodnutí R1–R8 schváleno *(2 kola orchestrátoru, viz changelog)*
- [x] Faktické otázky B, C, E zodpovězeny *(z předchozích konverzací)*
- [ ] Mirek schválil Dispatch tasky M1.0–M1.4 a M2.0–M2.5
- [ ] M2.1 task spuštěn *(Mirek pošle Igorovi email/tiket)*
- [ ] M2.0 task spuštěn *(Mirek nastaví R2 + DNS)*
- [ ] Repo refactor M1.0 proveden *(Claude Code task)*

**Po tomto checklistu:** Mirek schvaluje Dispatch tasky, exekutoři (Cursor + Claude Code + Mirek pro UI věci) jedou bez dalších dotazů v rámci scope. **Schvalování po atomických úkolech, ne po krocích** *(per userPreferences)*.

---

## Appendix — KB validace

**Otázka KB (6.5.2026):**

> Lze v Mergadu použít jako vstupní zdroj vlastní XML feed (např. hostovaný na Cloudflare R2) a transformovat jej do výstupních srovnávačových formátů (Heureka, FAVI, Biano, Glami, Zboží, Ceneo)? Má Mergado out-of-the-box předpřipravené formáty pro tyto srovnávače, nebo je nutné pro každý dělat custom formát? Jaké jsou hlavní výhody použití Mergada pro distribuci do srovnávačů oproti psaní vlastních Python generátorů?

**Verdikt:** PASS s korekcí. Out-of-the-box podpora potvrzena pro Heureku, Zboží, Glami, Ceneo (zdroje 042, 144). FAVI/Biano: KB potvrzuje "pomoc s parametry", nepotvrzuje hotový výstupní formát → otázka Q7 v A.9.

**Klíčové výhody Mergada pro distribuci** (zdroj 050, 128, 092, 043, 144): automatizace bez programování, Master Feed (jeden vstup → N výstupů), Audit zdarma, Mergado Store ekosystém (Translate, Pricing/Bidding Fox, Image Editor), žádné zásahy do e-shopu, dokumentace + podpora.

**Korekce do Discovery dokumentu** (proti handoffu z 1A): formulace „200+ formátů" nahrazena přesnějším „out-of-the-box pro hlavní srovnávače, FAVI/Biano k ověření".

---

## Changelog

**Rev. 3 (2026-05-12)** — M1.3: oprava 348→482 variant Milo (empirie z M1.1 parseru):
- A.7.1 MIN bod 2: "348 variant" → "482 variant" (empirická validace z ATOS XML)
- B.3.4 BLOCK-8: `count(variants) == 348` → `count(variants) == 482`
- Důvod: původní odhad 348 byl z Sprint 1 Mergado experimentu, reálná hodnota z parseru ATOS XML je 482 variant pro kategorii Milo

**Rev. 2 (2026-05-11)** — Korekce po zpřesnění výchozího stavu od Mirka:
- A.1 Manifest: cíl = skokové zvýšení kvality+kvantity, ne modernizace existující pipeline
- A.2 Analogie: přidán **galerista** (Igor/Shopyon, Upgates)
- A.3 Vrstva 4: přejmenována na "Hosting + Galerista" pro konzistenci
- A.5: **přepsáno celé** — Igor je galerista (akceptační kritéria), ne dodavatel feedu; není v pipeline; iterace po prvním importu je standard
- A.7.1: přidán MIN bod 8 (kontrola po prvním importu)
- A.9: vyhozeny Q3 *(Igor decoupling, falešná otázka)* a Q6 *(záchranná síť, není co zachraňovat)*
- A.10: vyhozeno M0 *(záchranná síť)*; M3 přepsáno jako "první import + iterace"
- A.11 bod 2: opraveno na "Igor je galerista"; přidán bod 8 (první feed pipeline pro Procentov vůbec)
- Hlavička: opraveny zmínky o "vlaštovčím hnízdě" a "produkčním pipeline"

**Sekce B rev. 1 (2026-05-11)** — Doplnění implementačního briefu:
- 2 kola orchestrátoru *(5 vendorů)* — V1: osnova; V2: 6 rozhodnutí
- 8 rozhodnutí R1–R8 zafixováno:
  - **R1** transformer.py → přejmenovat na `socha_heureka.py`, nový `socha_shopyon.py` (4:1)
  - **R2** R2 doména → `feeds.procentov.cz` (4:1)
  - **R3** Zdroj dat M1 → ATOS XML přímo, parquet v1.0 ignorovat (5:0)
  - **R4** Cron → GitHub Actions (5:0)
  - **R5** Bootstrap slovníku → extract + Google Translate + ruční revize (4:1)
  - **R6** Fallback → MIN pole blocking, OPT soft warning (řízeno schématem)
  - **R7** Repo struktura → multi-eshop hned, `xml-feedy/polotovar/` + `xml-feedy/procentov/` (4:1)
  - **R8** Schema MIN/OPT → rozšířený MIN, EAN přesunut do OPT (Mirkovo finální rozhodnutí)
- Faktická data ze starších konverzací:
  - ATOS distribuce = HTTPS URL `http://hurtmeble.eu/feeds/oferta_hurtowa_PL_PLN.xml`
  - Igorova specifikace = Custom Format 48267 (validovaný vzor.xml z 17.4)
  - ATOS XML vzorek = `C:\work\mergado-api\atos_source_feed.xml`
- Sekce B vyhozeno: B.3.7 Diff *(přesun do M3)*, B.5.3 KB validace gate *(mimo M1/M2 scope)*
- Sekce B přidáno: error reporting (`validation_errors.json`), explicitní validační tabulka, sloučení variant algoritmus, risk register, AK-1 až AK-7 mapování v sochaři
