"""SVG semicircular risk gauge (0-100) with tier colouring."""

import math


def gauge_html(score: int) -> str:
    score = max(0, min(100, int(score)))
    color = "#22c55e" if score < 40 else "#f59e0b" if score < 75 else "#ef4444"
    tier = "LOW" if score < 40 else "MEDIUM" if score < 75 else "HIGH"
    cx, cy, r = 110, 118, 85

    def pt(angle_deg):
        rad = math.radians(angle_deg)
        return cx + r * math.cos(rad), cy - r * math.sin(rad)

    x1, y1 = pt(180)
    x2, y2 = pt(0)
    bg = f"M {x1:.1f} {y1:.1f} A {r} {r} 0 0 1 {x2:.1f} {y2:.1f}"
    sweep = 1.8 * score
    ex, ey = pt(180 - sweep)
    fg = f"M {x1:.1f} {y1:.1f} A {r} {r} 0 {1 if sweep > 180 else 0} 1 {ex:.1f} {ey:.1f}"

    return f"""
    <svg viewBox="0 0 220 132" class="risk-gauge">
      <path d="{bg}" fill="none" stroke="#1e293b" stroke-width="16" stroke-linecap="round"/>
      <path d="{fg}" fill="none" stroke="{color}" stroke-width="16" stroke-linecap="round"/>
      <text x="110" y="96" text-anchor="middle" class="gauge-score" fill="{color}">{score}</text>
      <text x="110" y="120" text-anchor="middle" class="gauge-tier">{tier} RISK</text>
    </svg>"""
