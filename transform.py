#!/usr/bin/env python3
"""Transform Google Nákupy feed for Chemie-Bazen.cz — Mergado replacement.

Reprodukuje pravidla z Mergado projektu 224446. Operace se aplikují ve stejném
pořadí jako priority pravidel v Mergadu (1 → 9); u produktů, jejichž g:id spadá
do více množin, na pořadí záleží (např. smazání GTIN dřív, než by se kopíroval).
"""

import os
import sys
import xml.etree.ElementTree as ET
import yaml
import requests

G_NS = "http://base.google.com/ns/1.0"
ET.register_namespace("g", G_NS)


def g(tag):
    return f"{{{G_NS}}}{tag}"


def get_el(item, tag):
    return item.find(tag)


def set_el(item, tag, value):
    """Vytvoří element (pokud chybí) a nastaví text."""
    el = item.find(tag)
    if el is None:
        el = ET.SubElement(item, tag)
    el.text = value
    return el


def remove_el(item, tag):
    el = item.find(tag)
    if el is not None:
        item.remove(el)


def main():
    with open("rules.yaml", encoding="utf-8") as f:
        rules = yaml.safe_load(f)

    feed_url = rules["feed_url"]
    print(f"Stahování feedu: {feed_url}")
    try:
        resp = requests.get(feed_url, timeout=180)
        resp.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"Chyba stahování feedu: {e}")
    print(f"Staženo: {len(resp.content) / 1024:.0f} KB")

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        sys.exit(f"Chyba parsování XML: {e}")

    channel = root.find("channel")
    if channel is None:
        sys.exit("XML neobsahuje element <channel>")

    items = channel.findall("item")
    print(f"Nalezeno produktů: {len(items)}")

    # Množiny g:id (set pro rychlé vyhledání)
    R = set(rules.get("rejected_clear_gtin_brand", []))
    Gm = set(rules.get("gtin_to_mpn", []))
    H = set(rules.get("hadice_id_to_mpn", []))
    N = set(rules.get("wrong_identifier", []))

    desc_to_g = rules.get("description_to_g", False)
    desc_strip = rules.get("description_strip") or ""

    for item in items:
        pid = (item.findtext(g("id")) or "").strip()

        # ── P1: description → g:description ──────────────────────────────────
        if desc_to_g:
            src_desc = item.find("description")
            if src_desc is not None:
                text = src_desc.text
                item.remove(src_desc)
                if text and text.strip():
                    set_el(item, g("description"), text)

        # ── P2: Zamítnuté produkty — smazat g:gtin + g:brand ─────────────────
        if pid in R:
            remove_el(item, g("gtin"))
            remove_el(item, g("brand"))

        # ── P3: GTIN → MPN (kopíruje aktuální hodnotu; chybí-li, nevznikne) ──
        if pid in Gm:
            gt = item.find(g("gtin"))
            if gt is not None and (gt.text or "").strip():
                set_el(item, g("mpn"), gt.text)
        # ── P4: Smazat GTIN ──────────────────────────────────────────────────
        if pid in Gm:
            remove_el(item, g("gtin"))

        # ── P5: Hadice — identifier_exists = TRUE ────────────────────────────
        if pid in H:
            set_el(item, g("identifier_exists"), "TRUE")
        # ── P6: Hadice — ID → MPN ────────────────────────────────────────────
        if pid in H:
            if pid:
                set_el(item, g("mpn"), pid)

        # ── P7: Nesprávná hodnota — identifier_exists = FALSE ────────────────
        if pid in N:
            set_el(item, g("identifier_exists"), "FALSE")
        # ── P8: Nesprávná hodnota — smazat g:brand ───────────────────────────
        if pid in N:
            remove_el(item, g("brand"))

        # ── P9: odstranit úvodní frázi z g:description ───────────────────────
        if desc_strip:
            gd = item.find(g("description"))
            if gd is not None and gd.text and desc_strip in gd.text:
                gd.text = gd.text.replace(desc_strip, "")

    os.makedirs("output", exist_ok=True)
    out_path = "output/google-nakupy.xml"
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(out_path, xml_declaration=True, encoding="unicode")

    size_kb = os.path.getsize(out_path) / 1024
    print(f"Zapsáno: {out_path} ({size_kb:.0f} KB, {len(items)} produktů)")


if __name__ == "__main__":
    main()
