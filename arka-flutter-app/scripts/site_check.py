"""Checks arkaschmuck.de against what the ARKA app expects and writes a report.

Part of the arka-flutter-app skill (repo arka-skills). Run with the working
directory set to a checkout of arka-mobile-app (it reads lib/screens/web_page_screen.dart).

Runs on GitHub (the build workspace cannot reach the shop). Output in site-check/:
  report.json       – categories, legal pages, payment methods, menu, banners,
                      checkout handover result, which app CSS selectors still match
  report.md         – the same as a readable summary
  checkout.png      – checkout as the app shows it (app CSS applied)
  checkout_raw.png  – checkout without app CSS
  img/              – home-page banner images (for choosing slides)
"""
import json
import os
import re
import traceback

import requests
from playwright.sync_api import sync_playwright

SITE = "https://arkaschmuck.de"
OUT = "site-check"
UA = "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
LEGAL_SLUGS = ["versand-and-zahlung", "widerrufsbelehrung", "agb", "datenschutzerklarung", "impressum"]

os.makedirs(f"{OUT}/img", exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = UA
report = {"errors": []}


def app_css():
    """Reads appWebCss from lib/screens/web_page_screen.dart."""
    src = open("lib/screens/web_page_screen.dart", encoding="utf-8").read()
    m = re.search(r"const String appWebCss = '''(.*?)''';", src, re.S)
    return m.group(1) if m else ""


def css_selectors(css):
    sels = []
    for block in re.findall(r"([^{}]+)\{[^}]*display:\s*none", css):
        sels += [s.strip() for s in block.split(",") if s.strip()]
    return sels


# ---------- Store API ----------
try:
    r = S.get(f"{SITE}/wp-json/wc/store/v1/products/categories", params={"per_page": 100}, timeout=30)
    report["categories"] = [
        {"id": c["id"], "name": c["name"], "slug": c["slug"], "count": c["count"], "parent": c["parent"],
         "image": (c.get("image") or {}).get("src")}
        for c in r.json()
    ]
    r = S.get(f"{SITE}/wp-json/wc/store/v1/products", params={"per_page": 100, "orderby": "date"}, timeout=60)
    prods = r.json()
    report["products_total"] = int(r.headers.get("x-wp-total", len(prods)))
    types = {}
    for p in prods:
        types[p["type"]] = types.get(p["type"], 0) + 1
    report["product_types_newest_100"] = types
    report["newest_products"] = [{"id": p["id"], "name": p["name"], "price": p["prices"]["price"]} for p in prods[:5]]
    test_items = [p for p in prods if p["type"] == "simple" and p["is_purchasable"] and p["is_in_stock"]][:2]
except Exception as exc:  # noqa: BLE001
    report["errors"].append(f"store api: {exc}")
    test_items = []

# ---------- Legal pages (by slug, so changed IDs are noticed) ----------
report["legal_pages"] = []
for slug in LEGAL_SLUGS:
    try:
        r = S.get(f"{SITE}/wp-json/wp/v2/pages", params={"slug": slug, "_fields": "id,title,modified,link,content"}, timeout=30)
        items = r.json()
        if not items:
            report["legal_pages"].append({"slug": slug, "found": False})
            continue
        p = items[0]
        text = re.sub(r"<[^>]+>", " ", p["content"]["rendered"])
        report["legal_pages"].append({
            "slug": slug, "found": True, "id": p["id"], "title": p["title"]["rendered"],
            "modified": p["modified"], "link": p["link"], "text_chars": len(" ".join(text.split())),
        })
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"legal {slug}: {exc}")

BOOT = r"""
async (items) => {
  const base = '/wp-json/wc/store/v1'; let nonce = ''; const log = [];
  const pick = (r) => { const n = r.headers.get('Nonce'); if (n) nonce = n; };
  const h = () => ({'Content-Type':'application/json','Accept':'application/json','Nonce':nonce});
  let r = await fetch(base + '/cart', {credentials:'same-origin'}); pick(r); log.push('GET cart ' + r.status);
  r = await fetch(base + '/cart/items', {method:'DELETE', credentials:'same-origin', headers:h()}); pick(r); log.push('DELETE ' + r.status);
  for (const it of items) {
    r = await fetch(base + '/cart/add-item', {method:'POST', credentials:'same-origin', headers:h(), body: JSON.stringify(it)}); pick(r);
    log.push('ADD ' + it.id + ' ' + r.status);
  }
  r = await fetch(base + '/cart', {credentials:'same-origin'}); const j = await r.json(); log.push('items_count=' + j.items_count);
  return log;
}"""

PROBE = r"""
(selectors) => {
  const out = {payment_methods: [], selectors: {}, totals: []};
  document.querySelectorAll('ul.wc_payment_methods li, .wc-block-components-radio-control__option').forEach(li => {
    const input = li.querySelector('input');
    const label = li.querySelector('label') || li;
    out.payment_methods.push({id: input ? input.value : '', label: (label.innerText || '').trim().split('\n')[0]});
  });
  for (const s of selectors) { try { out.selectors[s] = document.querySelectorAll(s).length; } catch (e) { out.selectors[s] = 'invalid'; } }
  document.querySelectorAll('.order-total, .cart-subtotal, .woocommerce-shipping-totals').forEach(e => out.totals.push(e.innerText.replace(/\s+/g, ' ').trim()));
  out.has_cookie_banner_root = !!document.querySelector('#wpconsent-root');
  return out;
}"""

MENU = r"""
() => {
  const seen = new Set(); const items = [];
  document.querySelectorAll('#header .menu-item > a, .pls-mobile-menu .menu-item > a, #footer a').forEach(a => {
    const t = (a.innerText || '').trim(); const href = a.href;
    if (!t || seen.has(t + href)) return; seen.add(t + href);
    items.push({text: t, href: href, area: a.closest('#footer') ? 'footer' : 'header'});
  });
  const imgs = new Set();
  document.querySelectorAll('#main-content img').forEach(i => { const s = i.currentSrc || i.src; if (s && s.includes('/uploads/') && i.naturalWidth >= 400) imgs.add(s); });
  document.querySelectorAll('#main-content *').forEach(e => {
    const bg = getComputedStyle(e).backgroundImage; const m = bg && bg.match(/url\("?([^")]+)"?\)/);
    if (m && m[1].includes('/uploads/')) imgs.add(m[1]);
  });
  return {menu: items, banners: [...imgs]};
}"""

css = app_css()
selectors = css_selectors(css)
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    # Home page: menu + banners
    try:
        ctx = browser.new_context(**pw.devices["Pixel 7"], locale="de-DE")
        page = ctx.new_page()
        page.goto(SITE + "/", wait_until="load", timeout=90000)
        page.wait_for_timeout(4000)
        home = page.evaluate(MENU)
        report["menu"] = home["menu"]
        report["home_banners"] = home["banners"]
        for url in home["banners"][:20]:
            try:
                data = S.get(url, timeout=30).content
                open(f"{OUT}/img/" + url.rsplit("/", 1)[-1].split("?")[0], "wb").write(data)
            except Exception:  # noqa: BLE001
                pass
        ctx.close()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"home: {exc}")
    # Checkout handover exactly like the app
    try:
        ctx = browser.new_context(**pw.devices["Pixel 7"], locale="de-DE")
        page = ctx.new_page()
        page.goto(SITE + "/wp-json/wc/store/v1/cart", wait_until="domcontentloaded", timeout=60000)
        items = [{"id": p["id"], "quantity": 1} for p in test_items]
        report["checkout_handover"] = page.evaluate(BOOT, items)
        page.goto(SITE + "/checkout/", wait_until="load", timeout=90000)
        page.wait_for_timeout(5000)
        report["checkout_final_url"] = page.url
        page.screenshot(path=f"{OUT}/checkout_raw.png")
        report["checkout"] = page.evaluate(PROBE, selectors)
        page.add_style_tag(content=css)
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{OUT}/checkout.png")
        page.screenshot(path=f"{OUT}/checkout_full.png", full_page=True)
        page.evaluate("async () => { const r = await fetch('/wp-json/wc/store/v1/cart'); const n = r.headers.get('Nonce'); await fetch('/wp-json/wc/store/v1/cart/items', {method:'DELETE', headers:{'Nonce': n}}); }")
        ctx.close()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"checkout: {exc}")
        traceback.print_exc()
    browser.close()

json.dump(report, open(f"{OUT}/report.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

md = ["# Site check arkaschmuck.de", ""]
md.append(f"Products: {report.get('products_total')} | types (newest 100): {report.get('product_types_newest_100')}")
md.append("\n## Categories")
for c in report.get("categories", []):
    md.append(f"- {c['id']} {c['name']} ({c['slug']}) count={c['count']} parent={c['parent']}")
md.append("\n## Legal pages")
for p in report.get("legal_pages", []):
    md.append(f"- {p}")
md.append("\n## Checkout")
md.append(f"- handover: {report.get('checkout_handover')}")
md.append(f"- final url: {report.get('checkout_final_url')}")
ch = report.get("checkout", {})
md.append(f"- payment methods: {ch.get('payment_methods')}")
md.append(f"- totals: {ch.get('totals')}")
md.append(f"- app CSS selectors with 0 matches: {[s for s, n in ch.get('selectors', {}).items() if n == 0]}")
md.append("\n## Menu")
for m in report.get("menu", []):
    md.append(f"- [{m['area']}] {m['text']} -> {m['href']}")
md.append("\n## Home banners")
for b in report.get("home_banners", []):
    md.append(f"- {b}")
md.append(f"\n## Errors\n{report['errors']}")
open(f"{OUT}/report.md", "w", encoding="utf-8").write("\n".join(md))
print("\n".join(md))
