---
name: arka-flutter-app
description: Updates, syncs and rebuilds the ARKA Schmuck Flutter app (repo arka-mobile-app) to match arkaschmuck.de: categories, menu, legal pages, payments, slides, logo; delivers APK + iOS.
---

# ARKA Flutter App: sync with arkaschmuck.de and rebuild

The ARKA Schmuck shop app (Android + iOS, Flutter) lives in the GitHub repo
**janakiram2161/arka-mobile-app**. Running this skill means: check the website,
bring the app in line with it (plus any extra wishes the user names), build it on
GitHub, verify it, and hand over the new APK and iOS build.

Always answer the user in the language they write in. App texts are German.

## What is already live and what needs syncing

| Website content | How the app gets it | Skill action |
|---|---|---|
| Products, prices, sale prices, stock, descriptions, product images, variants | Loaded live from the WooCommerce Store API (`/wp-json/wc/store/v1`) every time the app opens | Only verify (site check) – never copy product data into the app |
| Categories (names, counts, pictures) | Live from Store API | Verify; update `hiddenCategorySlugs` and the slide category IDs if categories were renamed/removed |
| Legal pages (AGB, Datenschutz, Impressum, Versand & Zahlung, Widerruf) | Live via WP REST `/wp-json/wp/v2/pages/{id}`, rendered natively | Update the page IDs in `AppConfig.legalPages` if they changed; add new legal pages if the footer got new ones |
| Payment methods, coupons, shipping, checkout texts | The website's own checkout, shown in-app (website header/footer hidden by CSS) | Verify handover + that the hide-CSS selectors still match; new gateways work automatically |
| Website menu (SALE, BESTSELLERS, NEUHEITEN, categories …) | **Not automatic** | Mirror it in the app (see step 4) |
| Home banners / slides | URLs in `AppConfig.slides` | Update if the website banners changed |
| Logo | `assets/images/arka_logo_dark.png` / `arka_logo_light.png` | Only change if the user supplies a new logo |

## Fixed facts

- Two GitHub repos: **janakiram2161/arka-mobile-app** (the app) and **janakiram2161/arka-skills** (this skill: `arka-flutter-app/SKILL.md`, `arka-flutter-app/scripts/site_check.py`, `arka-flutter-app/assets/` with the logo files, and the workflow `.github/workflows/site-check.yml`). Skill tooling never goes into the app repo.

- Website: https://arkaschmuck.de – WordPress + WooCommerce, theme Alukas (PressLayouts, CSS prefix `pls-`), Elementor, LiteSpeed Cache. WordPress connector site ID **249659224** (self-hosted, Jetpack).
- Shop is a **Kleinunternehmer (§ 19 UStG)**: the app must never say "inkl. MwSt."; it says "Kein Ausweis der USt. gem. § 19 UStG, zzgl. Versand".
- Known IDs (verify with the site check, they can change): legal pages Versand and Zahlung 1786, Widerrufsbelehrung 1792, AGB 1765, Datenschutzerklärung 2193, Impressum 1776. Other pages: Teilnahmebedingungen 2138, Cookies Einstellungen 2147, Cart 28 `/cart/`, Checkout 29 `/checkout/`, My account 30, Order tracking 486. Categories: Armbänder 83, Ringe 84, Combos 85, Ohrringe 87, Ketten 88, Zubehör 89 (often empty), Geschenkkarte 98, Uncategorized 15 (hidden). Product tags used by the website menu: `bestsellers`, `new`.
- Logo: the user's ARKA lettermark (black on white). Source file `assets/brand/arka_logo_source.png`; app versions `assets/images/arka_logo_dark.png` (dark, transparent) and `assets/images/arka_logo_light.png` (white, transparent). App icon is generated from the dark logo on white by `tool/make_icon.py`. Never replace the logo with a text wordmark.

## Repo layout (key files)

- `lib/config.dart` – `AppConfig` (site URL, paths, `legalPages`, `slides`, `hiddenCategorySlugs`), brand colours, `ArkaWordmark` (logo image), `arkaAppBar`.
- `lib/api/store_api.dart` – Store API client (products, categories, product by id; supports category, search, on_sale, orderBy, exclude).
- `lib/models/models.dart`, `lib/state/stores.dart` (cart, wishlist, `rootTab`).
- `lib/screens/`: home (slides + categories + Neu eingetroffen + Im Angebot), shop, product_list (paged grid + sort), product, search, wishlist, cart, checkout, legal_page, web_page, more.
- `lib/screens/web_page_screen.dart` – `appWebCss` (hides website chrome), `classifyShopLink` (keeps legal links in-app, sends website-cart links back to the app cart).
- `lib/screens/checkout_screen.dart` – loads `/wp-json/wc/store/v1/cart`, injects JS that clears the shop cart and adds the app cart via Store API (Nonce header), then `location.replace('/checkout/')`.
- `tool/setup.sh` – `flutter create` (android/ios are generated, not committed), `flutter pub add` packages, app name, INTERNET permission, icon.
- `tool/preview_shots.py` – web-preview screenshots; screens are opened with `?screen=home|shop|more|cart|wishlist|legal-<id>|product-<id>` (handled by `_previewScreen()` in `lib/main.dart`, web only).
- `.github/workflows/build.yml` – on push to `main`: Android APK (analyze + tests + build), iOS unsigned build, web preview screenshots, GitHub release `build-<run number>` with `ARKA-Schmuck.apk` and `ARKA-Schmuck-iOS-unsigned.ipa`. Logs go to branches `ci-log-android`, `ci-log-ios`, screenshots to `ci-preview`.

## Environment constraints (important)

The Claude workspace **cannot reach** arkaschmuck.de, pub.dev, Google/Maven/Gradle or the Flutter SDK download (proxy 403). Do not try to install Flutter locally. Everything that needs the website or Flutter runs on **GitHub Actions**, and results come back through git branches and the public GitHub API:

- `api.github.com` works without a token while the repos are public. If it became private and the API answers 404, rely on `git fetch` of the `ci-*` branches only (works with the add_repo credentials) and ask the user to download the APK from the GitHub Releases page.
- Deleting remote branches through the proxy fails – leave helper branches alone.
- The WordPress connector works for reading pages, media, categories, plugins (plugin list may come from the Jetpack sync copy).

## Steps

Create a task list with these steps and tick them off.

### 1. Get the repos

Call `add_repo` with access `push` for `janakiram2161/arka-mobile-app` and for `janakiram2161/arka-skills` (one at a time). Clone them to `/home/claude/arka-mobile-app` and `/home/claude/arka-skills` as add_repo instructs (if a clone already exists and `git -C … rev-parse HEAD` works, `git pull origin main` instead) and call `register_repo_root` for each. Read `lib/config.dart` and `README.md` of the app before changing anything.

### 2. Check the website (site check on GitHub)

```bash
cd /home/claude/arka-skills
git fetch -q origin main && git checkout -q -B site-check-run origin/main
git -c user.name=ci -c user.email=ci@users.noreply.github.com commit -q --allow-empty -m "Run site check"
git push -qf origin site-check-run:site-check && git checkout -q main
# poll until completed
curl -s "https://api.github.com/repos/janakiram2161/arka-skills/actions/runs?per_page=1&branch=site-check" | python3 -c "import sys,json;r=json.load(sys.stdin)['workflow_runs'][0];print(r['status'],r['conclusion'],r['head_sha'][:7])"
# read results
git fetch -q origin ci-site-check && rm -rf /tmp/sc && mkdir /tmp/sc && git --work-tree=/tmp/sc checkout origin/ci-site-check -- . && git reset -q
cat /tmp/sc/report.md
```

The report lists: product count and types, categories (id, slug, count), legal pages found by slug (id, modified date), checkout handover result and final URL, payment methods, totals, **app CSS selectors with 0 matches**, website menu (header + footer), home banner URLs (files in `/tmp/sc/img/`). Look at `/tmp/sc/checkout.png` (checkout as the app shows it) and `/tmp/sc/checkout_raw.png` with the Read tool. Also use the WordPress connector (site 249659224) for anything the report does not cover, e.g. `plugin.list` for new payment/shipping plugins or `pages.list` for new pages.

The site check workflow (in arka-skills) checks out both repos and runs `arka-flutter-app/scripts/site_check.py` inside the app checkout; it reads `appWebCss` from `lib/screens/web_page_screen.dart` of the app's `main` branch, so push app CSS changes to `main` before re-checking, and keep that constant's name and `'''` string format. If arka-mobile-app is ever made private, the workflow's app checkout needs a token (repo secret) – tell the user.

### 3. Compare and decide what to change

Write down, before editing, a short list "website now → app now → change". Typical findings and fixes:

- **Legal page ID changed / page missing** → update `AppConfig.legalPages` (id, title, path). A new legal link in the website footer (e.g. Teilnahmebedingungen) → add it to `legalPages` and to the "Rechtliches" group in `more_screen.dart`.
- **Category renamed, added, removed** → nothing for lists (live), but fix `AppConfig.slides` category IDs and `hiddenCategorySlugs` (hide empty/internal ones).
- **Checkout handover failed** (`items_count` not equal to the items added, final URL not `/checkout/`) → investigate before building: Store API route, Nonce/Cart-Token headers, cache plugin. Do not ship a broken checkout.
- **CSS selectors with 0 matches** that matter (promo bar, header, footer, mobile navbar, cookie root) → look at `checkout_raw.png`, find the new selectors (extend PROBE in `arka-skills/arka-flutter-app/scripts/site_check.py` if needed and push that to arka-skills `main` first), update `appWebCss`. Unimportant zero-match fallbacks (gtranslate, breadcrumb, elementor-location-*) can stay.
- **New payment method** → works automatically in the checkout web view; mention it in the summary. Redirect-based methods (Klarna, EPS, iDEAL, PayPal) stay in the app because non-shop hosts are allowed in `classifyShopLink`.
- **Prices / VAT wording** → keep the § 19 UStG text unless the Impressum no longer mentions Kleinunternehmerregelung; then switch to "inkl. MwSt., zzgl. Versand".
- **Home banners changed** → update `AppConfig.slides` (4 slides unless the user wants another number): pick banners from `/tmp/sc/img/`, view them, keep text on the banner visible via `alignment`. Flutter cannot decode **AVIF** – only use png/jpg/webp URLs (for an AVIF-only banner use a WordPress-generated size in another format via the WordPress connector `media.list`, or another banner).

### 4. Website menu in the app

The website menu (report section "Menu") currently has HOME, SHOP/Kategorien, SALE (Launch Sale, 30/50/70 %, per category), BESTSELLERS (tag `bestsellers`), NEUHEITEN (tag `new`). Mirror its top-level structure in the app the first time (and whenever it changes):

- SALE → product list with `onSale: true` (already exists as "Im Angebot").
- BESTSELLERS / NEUHEITEN → product lists filtered by product tag: add a `tag` parameter to `StoreApi.products` (Store API accepts `tag` = tag ID or slug) and to `PagedProductGrid` / `openProductList`.
- Show them as entries/sections on the Shop tab (above the categories) and, if useful, as sections on the start page.
- Discount sub-filters like `?discount=30` are website-specific filters; map them to on-sale lists unless the user asks for exact percentages.

### 5. User's extra wishes

Apply whatever else the user asked for in this call. Keep everything German, use the ARKA colours in `ArkaColors`, the logo via `ArkaWordmark`.

### 6. Coding rules (learned from previous builds)

- Never call `setState` inside `initState` (use direct assignment or `WidgetsBinding.instance.addPostFrameCallback`).
- Don't use ThemeData component themes (`cardTheme`, `appBarTheme` …) – their types change between Flutter versions; style widgets directly.
- Use `Color(0x…)` constants instead of `withOpacity`/`withValues`.
- New packages: add them to the `flutter pub add` line in `tool/setup.sh` (pubspec only lists flutter itself; versions resolve at build time). Assets go under `assets/images/` (already registered in pubspec).
- Add unit tests to `test/widget_test.dart` for new pure logic (link handling, parsing).
- Add a preview screenshot entry in `tool/preview_shots.py` (and a `?screen=` case in `_previewScreen()`) for every new screen.

### 7. Build on GitHub

Commit with a clear message (attribution lines as configured) and `git push origin main`. Then poll the run:

```bash
RUN=$(curl -s "https://api.github.com/repos/janakiram2161/arka-mobile-app/actions/runs?per_page=1&branch=main" | python3 -c "import sys,json;r=json.load(sys.stdin)['workflow_runs'][0];print(r['id'])")
curl -s "https://api.github.com/repos/janakiram2161/arka-mobile-app/actions/runs/$RUN/jobs" | python3 -c "import sys,json;[print(j['name'],j['status'],j['conclusion']) for j in json.load(sys.stdin)['jobs']]"
```

Android takes ~7 min, iOS ~6 min, preview ~4 min. On failure read the log: `git fetch -q origin ci-log-android ci-log-ios && git show origin/ci-log-android:build-android.log | grep -nE "error|Error|FAIL|issues found"`. Fix and push again until Android, iOS and "Publish test build" are green. Check that analyze says "No issues found" and all tests pass.

### 8. Verify

- Screenshots: `git fetch -q origin ci-preview` → checkout into `/tmp/pv`, combine the PNGs side by side with Pillow and look at them (Read tool). Check logo, slides, changed screens, German texts, no "inkl. MwSt.".
- Download from the release: `https://github.com/janakiram2161/arka-mobile-app/releases/download/build-<N>/ARKA-Schmuck.apk` and `…/ARKA-Schmuck-iOS-unsigned.ipa` (curl -L works while the repo is public). Optionally unzip the APK and look at the 192×192 launcher icon (`res/*.png`, the RGB one) to confirm the ARKA logo icon.
- If the change touched the checkout, run the site check again after merging and look at `checkout.png`.

### 9. Deliver

Send `ARKA-Schmuck.apk` and `ARKA-Schmuck-iOS-unsigned.ipa` with SendUserFile (display `attach`), plus the release link. Then summarise briefly:

- what changed on the website since last time (from the site check),
- what was changed in the app,
- what the user should test on the phone (checkout with PayPal/Klarna if payment changed),
- iOS: the .ipa is unsigned; installing on an iPhone needs an Apple Developer account (99 USD/year) and signing (e.g. Codemagic → TestFlight). Offer to set that up once the account exists.

## If the user gives a new logo

Copy it to `assets/brand/arka_logo_source.png` in the app repo (and replace `arka-flutter-app/assets/arka_logo_source.png` in arka-skills), then regenerate both app logo files (logo assumed dark on a light background):

```python
from PIL import Image, ImageOps
src = Image.open('assets/brand/arka_logo_source.png').convert('RGBA')
alpha = ImageOps.invert(ImageOps.grayscale(src))
alpha = alpha.crop(alpha.point(lambda a: 255 if a > 20 else 0).getbbox())
w, h = alpha.size; pad = int(h * 0.12)
for color, name in [((28, 27, 25), 'arka_logo_dark.png'), ((255, 255, 255), 'arka_logo_light.png')]:
    im = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), color + (0,))
    solid = Image.new('RGBA', (w, h), color + (255,)); solid.putalpha(alpha)
    im.alpha_composite(solid, (pad, pad)); im.save('assets/images/' + name)
```

Preview both on light and dark backgrounds before committing, and copy the two new files to `arka-flutter-app/assets/` in arka-skills too. The app icon is rebuilt automatically from `arka_logo_dark.png` during the GitHub build.