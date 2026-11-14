# README visuals: brief

The README has one placeholder, `<!-- HERO -->`, for an animated diagram. Reference for the technique: animated SVG files, one light and one dark, switched with `<picture><source media="(prefers-color-scheme: dark)">` (GitHub renders SVG animation in `<img>`; no JavaScript).

What the hero should show, in one loop of about eight seconds:
1. A small state machine: COMMITTED, DELIVERED, DISPUTED, SETTLED.
2. A value travelling from DELIVERED to SETTLED along the direct route, and a second value along the route through DISPUTED.
3. In the sound case both arrive carrying the same fee and merge. In the seeded-defect case they arrive carrying different fees, and the loop they form is highlighted.

Constraints: every number shown must come from `route_agreement.py` output on `models/toy_fee_routes.yaml` and `models/toy_fee_routes_leaky.yaml`; alt text states the content in words; files live in `docs/assets/`.

## Implemented hero

`python3 docs/render_readme_hero.py` regenerates the light/dark animated SVGs,
the light/dark static variants, and `docs/assets/route-agreement-values.json`.
The renderer calls `route_agreement.evaluate` on both toy routes with unit
amount, and `analyse` on both models. It prints the exact rational results:
sound fees `1/100`, `1/100`; seeded fees `1/100`, `1/200`; difference `-1/200`.
The diagrams use `a` for the amount. No currency or production claim is implied.

The eight-second loop carries the two values together, merges the equal fees,
and highlights the unequal route loop. Labels and results stay visible in every
frame. There are no scripts, fonts to download, or external SVG resources.
`<picture>` selects a static file when reduced motion is requested, before
selecting the light/dark animated file. This avoids relying on an image's
internal media query inheriting reduced-motion preferences from its host page.

Local visual verification covered embedded images in Chromium at desktop,
tablet and phone widths, both themes, travel/arrival frames, and both static
sources. GitHub's deployed rendering is not claimed by that local check.
