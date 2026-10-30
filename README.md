# ARKA Skills

Claude skills for **ARKA Schmuck** (arkaschmuck.de).

## arka-flutter-app

Keeps the ARKA Schmuck mobile app ([arka-mobile-app](https://github.com/janakiram2161/arka-mobile-app),
Flutter, Android + iOS) in line with the website and rebuilds it.

| Path | Content |
|---|---|
| `arka-flutter-app/SKILL.md` | The skill: checks the website, updates the app, builds and delivers APK + iOS |
| `arka-flutter-app/scripts/site_check.py` | Website check: categories, legal pages, payment methods, menu, banners, checkout handover |
| `arka-flutter-app/assets/` | ARKA logo: source image plus the dark and white versions used in the app |
| `.github/workflows/site-check.yml` | Runs the website check on GitHub (push to branch `site-check`); report goes to branch `ci-site-check` |

Products, prices, descriptions and product pictures don't need syncing: the app loads them live from the shop.
