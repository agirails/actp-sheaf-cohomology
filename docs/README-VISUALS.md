# README visuals: brief

The README has one placeholder, `<!-- HERO -->`, for an animated diagram. Reference for the technique: animated SVG files, one light and one dark, switched with `<picture><source media="(prefers-color-scheme: dark)">` (GitHub renders SVG animation in `<img>`; no JavaScript).

What the hero should show, in one loop of about eight seconds:
1. A small state machine: COMMITTED, DELIVERED, DISPUTED, SETTLED.
2. A value travelling from DELIVERED to SETTLED along the direct route, and a second value along the route through DISPUTED.
3. In the sound case both arrive carrying the same fee and merge. In the seeded-defect case they arrive carrying different fees, and the loop they form is highlighted.

Constraints: every number shown must come from `route_agreement.py` output on `models/toy_fee_routes.yaml` and `models/toy_fee_routes_leaky.yaml`; alt text states the content in words; files live in `docs/assets/`.
