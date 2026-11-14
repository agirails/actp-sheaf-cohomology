#!/usr/bin/env python3
"""Render the two self-contained README heroes from the executable toy models.

Run from any directory: python3 docs/render_readme_hero.py
No hand-entered accounting values, remote assets, JavaScript, or kernel models.
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from route_agreement import analyse, evaluate, load  # noqa: E402

ASSETS = ROOT / "docs" / "assets"
ROUTES = [["deliver", "settle"], ["deliver", "dispute", "uphold_provider"]]
THEMES = {
    "dark": dict(bg="#080f20", ink="#f0f5ff", muted="#a7b9d3", line="#30425e",
                 node="#101e35", blue="#69c9ff", violet="#c5a4ff", good="#7de4c2",
                 warn="#ffc27a", grid="#16243b", shade="#132c46"),
    "light": dict(bg="#f5f9ff", ink="#152946", muted="#4c617d", line="#bccbde",
                  node="#ffffff", blue="#00669c", violet="#7446b4", good="#006b50",
                  warn="#985000", grid="#e2ebf6", shade="#e3effc"),
}


def models():
    result = []
    for name in ("toy_fee_routes.yaml", "toy_fee_routes_leaky.yaml"):
        model = load(str(ROOT / "models" / name))
        values = [evaluate(model, route, {"amount": 1}) for route in ROUTES]
        report = analyse(model)
        result.append(dict(model=name, routes=ROUTES, fee=[str(v["fee"]) for v in values],
                           delta=str(values[1]["fee"] - values[0]["fee"]),
                           routes_agree=report["routes_agree"], h0=report["h0"], h1=report["h1"]))
    return result


def fee_label(fraction):
    value = Fraction(fraction)
    sign = "−" if value < 0 else ""
    numerator = abs(value.numerator)
    if numerator == 0:
        return "0"
    term = "a" if numerator == 1 else f"{numerator}a"
    return sign + term + (f"/{value.denominator}" if value.denominator != 1 else "")


def panel(y, case, prefix, colors, animated):
    agrees = case["routes_agree"]
    accent = colors["good" if agrees else "warn"]
    first, second = map(fee_label, case["fee"])
    title = "The routes agree." if agrees else "A seeded fee mismatch."
    status = "Same fee. One consistent value." if agrees else "Different fees. The loop is the witness."
    direct = "M350 162 L860 162"
    disputed = "M350 162 C410 162 440 294 600 294 C760 294 800 162 860 162"
    loop = "M350 162 L860 162 C800 162 760 294 600 294 C440 294 410 162 350 162"
    result = f"fee = {first}" if agrees else "Δfee = " + fee_label(case["delta"])
    # The packet body travels with its value; static route labels remain readable.
    packets = []
    for route, label, cls, points in [("direct", first, "blue", "0;0;1;1"),
                                       ("disputed", second, "violet", "0;0;1;1")]:
        packets.append(f'''
        <g class="packet moving {route}" aria-hidden="true">
          <animateMotion dur="8s" repeatCount="indefinite" calcMode="linear"
            keyTimes="0;0.16;0.64;1" keyPoints="{points}">
            <mpath href="#{prefix}-{route}"/>
          </animateMotion>
          <rect x="-49" y="-23" width="98" height="46" rx="23" fill="{colors['node']}" stroke="{colors[cls]}" stroke-width="2"/>
          <text class="packet-value {cls}" text-anchor="middle" y="9">{label}</text>
        </g>''')
    nodes = []
    for x, cy, label in [(106, 162, "COMMITTED"), (350, 162, "DELIVERED"),
                          (600, 294, "DISPUTED"), (860, 162, "SETTLED")]:
        nodes.append(f'''<g>
          <circle cx="{x}" cy="{cy}" r="12" fill="{colors['bg']}" stroke="{colors['line']}" stroke-width="2"/>
          <circle cx="{x}" cy="{cy}" r="4" fill="{colors['muted']}"/>
          <text x="{x}" y="{cy+49}" text-anchor="middle" class="state">{label}</text>
        </g>''')
    return f'''
    <g transform="translate(0 {y})" class="case {'sound' if agrees else 'mismatch'}">
      <circle cx="51" cy="30" r="6" fill="{accent}"/>
      <text x="70" y="40" class="case-title">{title}</text>
      <text x="48" y="80" class="muted caption">{status}</text>
      <path d="M106 162 H350" class="rail"/>
      <path id="{prefix}-direct" d="{direct}" class="rail"/>
      <path id="{prefix}-disputed" d="{disputed}" class="rail"/>
      <path d="{direct}" class="route-blue"/>
      <path d="{disputed}" class="route-violet"/>
      <path d="{loop}" class="loop {'agreement-loop' if agrees else 'difference-loop'}" stroke="{accent}"/>
      <path d="M222 157 L232 162 L222 167 M707 157 L717 162 L707 167 M475 258 L483 269 L470 267 M753 237 L760 225 L747 229"
        class="arrows"/>
      <text x="584" y="129" text-anchor="middle" class="route-label blue">direct · {first}</text>
      <text x="600" y="249" text-anchor="middle" class="route-label violet">via dispute · {second}</text>
      {''.join(nodes)}
      <g class="arrival" aria-hidden="true">
        <circle cx="860" cy="162" r="27" fill="none" stroke="{accent}" stroke-width="2"/>
        <circle cx="860" cy="162" r="17" fill="{accent}" fill-opacity="0.16"/>
        <circle cx="860" cy="162" r="6" fill="{accent}"/>
      </g>
      {''.join(packets) if animated else ''}
      <path d="M790 353 H939" stroke="{accent}" stroke-width="1" opacity="0.5"/>
      <text x="940" y="385" text-anchor="end" class="result" fill="{accent}">{result}</text>
    </g>'''


def svg(theme, cases, animated=True):
    c = THEMES[theme]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
      width="1000" height="1090" viewBox="0 0 1000 1090" class="{'animated' if animated else 'static'}" role="img" aria-labelledby="title desc">
  <title id="title">Route agreement: one destination, two routes</title>
  <desc id="desc">Two toy state machines go from COMMITTED through DELIVERED to SETTLED, directly or through DISPUTED.
  In the sound model both fees are amount/100 and merge. In the seeded mismatch the dispute fee is amount/200,
  the direct fee remains amount/100, and the highlighted loop witnesses a difference of minus amount/200.</desc>
  <!-- Generated by docs/render_readme_hero.py from the two toy fee models. -->
  <defs>
    <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">
      <circle cx="1" cy="1" r="0.8" fill="{c['grid']}"/>
    </pattern>
    <radialGradient id="wash"><stop stop-color="{c['shade']}" stop-opacity="0.65"/><stop offset="1" stop-color="{c['bg']}" stop-opacity="0"/></radialGradient>
    <linearGradient id="blue"><stop stop-color="{c['blue']}" stop-opacity="0.2"/><stop offset="1" stop-color="{c['blue']}" stop-opacity="0.8"/></linearGradient>
    <linearGradient id="violet"><stop stop-color="{c['violet']}" stop-opacity="0.25"/><stop offset="1" stop-color="{c['violet']}" stop-opacity="0.85"/></linearGradient>
  </defs>
  <style>
    text {{font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill:{c['ink']};}}
    .heading {{font-size:57px;font-weight:650;letter-spacing:-2px;}}
    .case-title {{font-size:34px;font-weight:600;letter-spacing:-0.7px;}}
    .caption {{font-size:27px;}}
    .muted {{fill:{c['muted']};}}
    .state {{font-size:28px;font-weight:600;letter-spacing:0.4px;}}
    .route-label {{font-size:28px;}}
    .blue {{fill:{c['blue']};}} .violet {{fill:{c['violet']};}}
    .result,.packet-value {{font-family:'SFMono-Regular',Consolas,'Liberation Mono',monospace;font-size:28px;}}
    .sound .result {{fill:{c['good']};}} .mismatch .result {{fill:{c['warn']};}}
    .rail {{fill:none;stroke:{c['line']};stroke-width:2;}}
    .route-blue {{fill:none;stroke:url(#blue);stroke-width:3;}}
    .route-violet {{fill:none;stroke:url(#violet);stroke-width:3;}}
    .arrows {{fill:none;stroke:{c['muted']};stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;}}
    .loop {{fill:none;stroke-width:5;stroke-linecap:round;}}
    .difference-loop {{opacity:0.95;}} .agreement-loop {{opacity:0.35;}}
    .animated .difference-loop {{animation:reveal-loop 8s infinite;}}
    .animated .agreement-loop {{animation:merge-loop 8s infinite;}}
    .packet {{opacity:0;}} .animated .packet {{animation:journey 8s infinite;}}
    .animated .arrival {{animation:arrive 8s infinite;}}
    @keyframes journey {{0%,15%{{opacity:0;}}18%,60%{{opacity:1;}}65%,100%{{opacity:0;}}}}
    @keyframes arrive {{0%,60%{{opacity:0.15;}}67%,88%{{opacity:1;}}100%{{opacity:0.15;}}}}
    @keyframes reveal-loop {{0%,62%{{opacity:0.10;stroke-width:3;}}69%,88%{{opacity:0.95;stroke-width:6;}}100%{{opacity:0.10;stroke-width:3;}}}}
    @keyframes merge-loop {{0%,62%{{opacity:0.08;}}69%,88%{{opacity:0.35;}}100%{{opacity:0.08;}}}}
    @media(prefers-reduced-motion:reduce) {{
      .moving{{display:none;}} .animated .loop,.animated .arrival{{animation:none;}}
      .difference-loop{{opacity:0.95;}} .agreement-loop{{opacity:0.35;}} .arrival{{opacity:1;}}
    }}
  </style>
  <rect width="1000" height="1090" rx="20" fill="{c['bg']}"/>
  <rect width="1000" height="1090" rx="20" fill="url(#grid)"/>
  <ellipse cx="780" cy="440" rx="520" ry="500" fill="url(#wash)"/>
  <text x="48" y="80" class="heading">One destination. Two routes.</text>
  <text x="48" y="126" class="caption muted">Does the accounting survive the journey?</text>
  <path d="M48 164 H952" stroke="{c['line']}"/>
  {panel(188, cases[0], 'sound', c, animated)}
  <path d="M48 610 H952" stroke="{c['line']}"/>
  {panel(637, cases[1], 'seeded', c, animated)}
  <text x="48" y="1060" class="muted" font-size="24">Toy models only. Exact rational arithmetic. a = amount.</text>
</svg>
'''


def main():
    cases = models()
    ASSETS.mkdir(exist_ok=True)
    for theme in THEMES:
        (ASSETS / f"route-agreement-{theme}.svg").write_text(svg(theme, cases), encoding="utf-8")
        (ASSETS / f"route-agreement-{theme}-static.svg").write_text(svg(theme, cases, animated=False), encoding="utf-8")
    (ASSETS / "route-agreement-values.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(cases, indent=2))


if __name__ == "__main__":
    main()
