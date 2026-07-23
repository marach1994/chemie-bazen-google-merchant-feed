# Dokumentace — Google Nákupy feed pro Chemie-Bazen.cz

> **Účel repozitáře:** Vlastní transformace produktového feedu pro **Google Nákupy [CZ]**,
> která nahrazuje **Mergado projekt ID 224446**. Běží zdarma na GitHub Actions + GitHub Pages.
>
> Tento dokument je psaný tak, aby v něm rychle zorientoval **člověk** (co se s feedem děje,
> jak něco změnit) i **LLM / AI asistent** (přesné mapování pravidlo → kód → konfigurace,
> zdroje pravdy, invarianty). Pokud něco měníš, uprav i tuto dokumentaci.

---

## 1. Rychlý přehled (TL;DR)

| Co | Hodnota |
|---|---|
| Nahrazuje | Mergado projekt **224446** „Google Nákupy [cz]", shop 34764 |
| Zdrojový feed (vstup) | `https://www.chemie-bazen.cz/google/export/products.xml` |
| Formát vstupu i výstupu | Google RSS 2.0 s namespace `g:` (`google.cz`) |
| Počet produktů | ~2 200 |
| Výstupní feed (živý) | `https://marach1994.github.io/chemie-bazen-google-merchant-feed/google-nakupy.xml` |
| Frekvence aktualizace | každou hodinu v `:10` (cron v GitHub Actions) |
| Kde se mění pravidla | **`rules.yaml`** (konfigurace) — NE v Mergadu |
| Kde je logika | **`transform.py`** (kód, mění se jen zřídka) |

**Princip:** stáhni zdrojový feed → aplikuj pravidla → zapiš `output/google-nakupy.xml` → publikuj na Pages → Google si ho stáhne.

---

## 2. Architektura

```
┌─────────────────────┐     ┌──────────────┐     ┌───────────────────────┐
│ E-shop (Shoptet)    │     │ GitHub       │     │ GitHub Pages          │
│ products.xml        │────▶│ Actions      │────▶│ google-nakupy.xml     │──▶ Google
│ (google.cz formát)  │     │ transform.py │     │ (veřejná URL)         │    Merchant
└─────────────────────┘     └──────────────┘     └───────────────────────┘
        vstup               každou hodinu :10           výstup
```

Zásadní rozhodnutí návrhu: **konfigurace je oddělená od kódu.**

- **`rules.yaml`** — VŠECHNA pravidla jako data (seznamy ID, fráze, přepínače). Tady se dělají změny. Zvládne to upravit i netechnický člověk.
- **`transform.py`** — logika, která pravidla čte a aplikuje. Mění se jen když přibude *nový typ* transformace, ne při běžné údržbě.

---

## 3. Co přesně feed dělá — transformační pipeline

Feed je ve stejném formátu na vstupu i výstupu (`google.cz`), takže se **produkty jen upravují**, nic se nekonvertuje. Operace se aplikují **v pořadí podle priorit pravidel z Mergada (1 → 9)**. Na pořadí záleží: u produktů, jejichž `g:id` spadá do více množin, se dřívější operace projeví v pozdější (např. GTIN se smaže dřív, než by se kopíroval → kopie nevznikne).

### Mapovací tabulka: Mergado pravidlo → krok v kódu → klíč v konfiguraci

| Priorita | Mergado pravidlo | Co dělá (lidsky) | Krok v `transform.py` | Klíč v `rules.yaml` |
|---:|---|---|---|---|
| 1 | mergado desc => g:desc | Popis `<description>` přejmenuje na `<g:description>` (Google vyžaduje g:) | P1 | `description_to_g: true` |
| 2 | Zamítnuté produkty | Smaže `g:gtin` **a** `g:brand` | P2 | `rejected_clear_gtin_brand` |
| 3 | GTIN → MPN | Zkopíruje `g:gtin` → `g:mpn` (aktuální hodnotu) | P3 | `gtin_to_mpn` |
| 4 | Smazat GTIN | Smaže `g:gtin` | P4 | `gtin_to_mpn` (stejná množina) |
| 5 | Hadice — identifier TRUE | Nastaví `g:identifier_exists = TRUE` | P5 | `hadice_id_to_mpn` |
| 6 | Hadice — ID → MPN | Zkopíruje `g:id` → `g:mpn` | P6 | `hadice_id_to_mpn` (stejná množina) |
| 7 | Nesprávná hodnota | Nastaví `g:identifier_exists = FALSE` | P7 | `wrong_identifier` |
| 8 | Smazat BRAND | Smaže `g:brand` | P8 | `wrong_identifier` (stejná množina) |
| 9 | Odstranění úvodní věty | Z `g:description` smaže úvodní frázi | P9 | `description_strip` |

> **Pozn. k prioritě 5–6 (množina „Hadice"):** tato ID aktuálně ve feedu **nejsou** (0 shod), pravidlo je tedy fakticky nečinné. Ponecháno kvůli věrnosti — kdyby se produkty vrátily, chová se stejně jako Mergado.
>
> **Pozn. k prioritě 9:** fráze `"Názor bazénového specialisty - recenze "` má na konci **mezeru**. V praxi po slově „recenze" následuje nový řádek, ne mezera, takže se shoda skoro nikdy netrefí — a stejně to má i výstup Mergada. Je to záměrná věrná kopie chování (efekt = téměř žádný).

### Sémantika operací (invarianty — DŮLEŽITÉ pro správné úpravy)

Tyto vlastnosti byly ověřeny proti reálnému výstupu Mergada. Když upravuješ kód, musí platit dál:

1. **„Smazat" = odstranit element úplně**, ne nastavit prázdnou hodnotu.
   `<g:brand>` po smazání v XML není (ne `<g:brand></g:brand>`).
2. **„Kopírovat" bere aktuální hodnotu** v okamžiku daného kroku. Pokud zdrojový element
   mezitím zmizel (smazán dřívějším krokem) nebo je prázdný, cíl **nevznikne**.
3. **Pořadí priorit se musí dodržet.** Překryvy množin:
   - `rejected_clear_gtin_brand` ∩ `gtin_to_mpn`: GTIN se smaže v P2, takže P3 už nemá co kopírovat → `g:mpn` nevznikne. (Ověřeno na reálných ID jako `10852030`, `99996224`, `911320500`.)
4. **Tělo popisu se nijak nemění** kromě odstranění fráze z priority 9. `g:description` = přesná kopie zdrojového `<description>`.

---

## 4. Jak co změnit (cookbook)

Skoro všechny běžné úpravy = editace `rules.yaml`. Po změně se při dalším běhu (nebo ručním spuštění workflow) projeví automaticky.

### ➤ Přidat/odebrat produkt z existujícího pravidla
Najdi příslušný seznam v `rules.yaml` a přidej/odeber `g:id` produktu (řetězec v uvozovkách).

```yaml
# Příklad: chci u dalšího produktu smazat GTIN i značku
rejected_clear_gtin_brand:
  - "9991461"
  - "NOVE-ID-123"   # ← přidaný řádek
```

Množiny a jejich význam:
| Klíč | Efekt na produkty v seznamu |
|---|---|
| `rejected_clear_gtin_brand` | smaže `g:gtin` + `g:brand` |
| `gtin_to_mpn` | zkopíruje `g:gtin`→`g:mpn`, pak `g:gtin` smaže |
| `hadice_id_to_mpn` | nastaví `identifier_exists=TRUE`, zkopíruje `g:id`→`g:mpn` |
| `wrong_identifier` | nastaví `identifier_exists=FALSE`, smaže `g:brand` |

### ➤ Změnit úvodní frázi, která se maže z popisů
```yaml
description_strip: "Nová fráze k odstranění "
```
Maže se **přesně** zadaný řetězec (včetně mezer). Prázdná hodnota = nic se nemaže.

### ➤ Vypnout přejmenování description → g:description
```yaml
description_to_g: false
```

### ➤ Změnit zdrojový feed
```yaml
feed_url: "https://..."
```

### ➤ Přidat úplně nový typ transformace (vyžaduje úpravu kódu)
Nový typ pravidla, který se nedá vyjádřit existujícími klíči (např. zaokrouhlování cen,
přidání `custom_label`), se přidá jako nový krok do smyčky v `transform.py` — vlož ho na
správné místo podle priority a přidej odpovídající klíč do `rules.yaml`. Zachovej pořadí P1–P9.

### ➤ Změnit frekvenci aktualizace
V `.github/workflows/transform-feed.yml`, řádek `cron:`.

---

## 5. Referenční popis `rules.yaml`

| Klíč | Typ | Význam |
|---|---|---|
| `feed_url` | string | URL zdrojového feedu |
| `description_to_g` | bool | Priorita 1 — přejmenovat `<description>` na `<g:description>` |
| `description_strip` | string | Priorita 9 — přesná fráze k odstranění z popisu |
| `rejected_clear_gtin_brand` | seznam ID | Priorita 2 |
| `gtin_to_mpn` | seznam ID | Priorita 3 + 4 |
| `hadice_id_to_mpn` | seznam ID | Priorita 5 + 6 (aktuálně 0 shod) |
| `wrong_identifier` | seznam ID | Priorita 7 + 8 |

Množiny se porovnávají proti hodnotě elementu `<g:id>` každého produktu.

---

## 6. Ověřování správnosti

Feed byl ověřen porovnáním s reálným výstupem Mergada **produkt po produktu**: **0 rozdílů**
ve všech měněných polích (`g:gtin`, `g:mpn`, `g:brand`, `g:identifier_exists`, přítomnost
`g:description`) na všech společných produktech.

**Jak ověření zopakovat** (dokud Mergado projekt ještě běží):

1. Stáhni reálný výstup Mergada:
   `https://feeds.mergado.com/chemie-bazen-cz-google-nakupy-cz-d69a445e4041045c89984ccbd8c93057.xml`
2. Spusť `python transform.py` → `output/google-nakupy.xml`
3. Načti oba XML, indexuj produkty podle `g:id`, porovnej sledovaná pole.

> Rozdíly v **obsahu popisů** (~130) nejsou chyba — jde o (a) časový drift, kdy obchod
> upravil popisky mezi Mergado synchronizací a naším během, a (b) ~18 ručně editovaných
> popisů (viz níže). Tělo popisu skript nemodifikuje.

---

## 7. Známá omezení

### Ručně editované popisy (18 produktů) — NEREPRODUKOVÁNO
V Mergadu existuje ~18 produktů (query „Ruční úprava pro dynamický remarketing"), jejichž
`g:description` byl **ručně přepsán přímo v Mergadu** (mimo jakékoli pravidlo — na úrovni
produktu). Šlo o zkrácení popisů: odstranění úvodní věty, odstranění bezpečnostních/právních
bloků na konci a normalizaci mezer. Týká se to hlavně chemikálií s nebezpečnostními větami
(bromové tablety, pH mínus, chlorový granulát, vločkovač, kyselina solná…).

Tyto ruční texty **nový feed zatím nepřebírá** — používá popis přímo z e-shopu. Pokud mají
zůstat, je potřeba je vytáhnout z výstupu Mergada (dokud běží) a doplnit do konfigurace jako
sekci `description_overrides` (id → text) + odpovídající krok v `transform.py`.

Dotčená ID: `CODE-29`, `8594019369251`, `12345`, `CODE-482`, `CODE-578`, `911222500`,
`CODE-15`, `911426000`, `CODE-470`, `CODE-582`, `80161`, `CODE-30` (už není ve feedu),
`CODE-14`, `8594019369248`, `03105`, `CODE-16`, `8594019369249`, `8594019369250`, `80160`.

---

## 8. Zdroje pravdy (pro rekonstrukci / audit)

| Zdroj | Kde |
|---|---|
| Mergado projekt | ID `224446`, shop `34764`, účet `chemiebazen` |
| Mergado REST API | `https://api.mergado.com/projects/224446/rules/` (Bearer PAT token) |
| Živý výstup Mergada | `https://feeds.mergado.com/chemie-bazen-cz-google-nakupy-cz-d69a445e4041045c89984ccbd8c93057.xml` |
| Slug projektu | `chemie-bazen-cz-google-nakupy-cz-d69a445e4041045c89984ccbd8c93057` |

> **Pozn. pro LLM/agenta:** Konfigurace pravidel s `element_path` a jedním cílem (typ
> `rewriting`) v Mergado API **nevrací** obsah (`data: null`) — hodnoty jako „TRUE"/„FALSE"
> nebo „smazat" byly odvozeny z názvu pravidla a **ověřeny proti živému výstupu**. Ruční
> úpravy produktů (typ `product`, priorita 10) přes API nejsou vůbec čitelné; jediný způsob,
> jak je získat, je porovnat zdroj s výstupem Mergada.

---

## 9. Mapa souborů

```
chemie-bazen-google-merchant-feed/
├── transform.py                      # logika transformace (kroky P1–P9)
├── rules.yaml                        # VŠECHNA pravidla jako konfigurace ← tady se edituje
├── requirements.txt                  # requests, PyYAML
├── README.md                         # stručný přehled
├── DOKUMENTACE.md                    # tento soubor
├── .gitignore                        # ignoruje output/, __pycache__, .env
├── .github/workflows/
│   └── transform-feed.yml            # cron :10 + build + deploy na Pages
└── output/                           # (generováno, negitováno) google-nakupy.xml
```

---

## 10. Spuštění a nasazení

### Lokálně
```bash
pip install -r requirements.txt
python transform.py
# výsledek: output/google-nakupy.xml
```

### Automaticky (GitHub Actions)
- Běží každou hodinu v `:10` + lze spustit ručně (Actions → „Run workflow").
- Workflow: build (`transform.py`) → upload artefaktu → deploy na GitHub Pages.
- Výstup: `https://marach1994.github.io/chemie-bazen-google-merchant-feed/google-nakupy.xml`

### Poznámka k prvnímu nasazení
Po úplně prvním pushi se workflow nemusí hned zaregistrovat (GitHub ho chvíli „nevidí").
Pomůže prázdný commit / drobná změna workflow souboru a push znovu.

---

## 11. Přechod z Mergada (provozní checklist)

1. **Google Merchant Center** → zdroj dat → změnit URL stahování na novou (Pages URL výše).
2. **Několik dní nechat běžet paralelně** s Mergadem, sledovat diagnostiku v Merchant Center
   (počty schválených/zamítnutých produktů se nesmí změnit).
3. Teprve pak **pozastavit Mergado projekt 224446**.
4. Zvážit doplnění 18 ručních popisů (viz sekce 7), pokud jsou pro remarketing důležité.
