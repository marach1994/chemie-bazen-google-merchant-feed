# Chemie-Bazen.cz — Google Nákupy feed

Vlastní transformace produktového feedu pro **Google Nákupy [CZ]** — náhrada za
Mergado projekt ID 224446. Běží zdarma na GitHub Actions + GitHub Pages.

## Jak to funguje

1. `transform.py` stáhne zdrojový feed z e-shopu.
2. Aplikuje pravidla z `rules.yaml` (ve stejném pořadí jako priority v Mergadu).
3. Zapíše výsledek do `output/google-nakupy.xml`.
4. GitHub Actions (`.github/workflows/transform-feed.yml`) to spouští každou hodinu
   a publikuje výsledek na GitHub Pages.

Zdroj: `https://www.chemie-bazen.cz/google/export/products.xml`

## Pravidla (reprodukce Mergado projektu 224446)

Pořadí odpovídá prioritám 1–9 v Mergadu:

| # | Co dělá | Množina produktů |
|---|---------|------------------|
| 1 | `<description>` → `<g:description>` | všechny |
| 2 | smazat `g:gtin` + `g:brand` | „Zamítnuté produkty" |
| 3 | zkopírovat `g:gtin` → `g:mpn` | „ID: GTIN → MPN" |
| 4 | smazat `g:gtin` | „ID: GTIN → MPN" |
| 5 | `g:identifier_exists` = TRUE | „Hadice" (aktuálně 0 shod) |
| 6 | zkopírovat `g:id` → `g:mpn` | „Hadice" |
| 7 | `g:identifier_exists` = FALSE | „Nesprávná hodnota" |
| 8 | smazat `g:brand` | „Nesprávná hodnota" |
| 9 | odstranit úvodní frázi z popisu | všechny (v praxi téměř nikdy nesedí) |

Všechny množiny ID i fráze jsou v `rules.yaml` — kód se nemění, konfigurace ano.

## Ověřeno proti Mergadu

Výstup byl porovnán s reálným výstupem Mergada (`feeds.mergado.com`) produkt po
produktu: **0 rozdílů** v polích `g:gtin`, `g:mpn`, `g:brand`, `g:identifier_exists`
a v přítomnosti `g:description` na všech společných produktech.

### Známé omezení

Query „Ruční úprava pro dynamický remarketing" (~18 produktů) obsahuje **ručně
editované popisy** přímo v Mergadu, ne odvozené z pravidla. Ty tato náhrada
nereprodukuje — pokud jsou potřeba, je nutné je doplnit ručně do konfigurace.

## Lokální spuštění

```bash
pip install -r requirements.txt
python transform.py
# výsledek: output/google-nakupy.xml
```
