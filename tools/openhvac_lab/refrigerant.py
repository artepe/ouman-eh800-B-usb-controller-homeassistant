"""Generate a read-only log(p)-h SVG from independently verified cycle points.

This is a schematic polyline in log(P)-h coordinates. It is NOT a
saturation dome, accurate equipment P-h curve or CoolProp substitute.
"""
from __future__ import annotations
from math import log10
from xml.sax.saxutils import escape
from .core import number


def log_ph_svg(states, *, refrigerant="R290"):
    required = ("suction", "discharge", "condenser_outlet", "expansion_outlet")
    if not isinstance(states, dict) or set(required) - set(states):
        raise ValueError("All four cycle states are required")
    if not isinstance(refrigerant, str) or len(refrigerant) > 28:
        raise ValueError("Invalid refrigerant name")
    data = []
    for key in required:
        point = states[key]
        if not isinstance(point, dict):
            raise ValueError("Each state must be an object")
        h = number(point.get("enthalpy_kj_kg"), key + ".h", minimum=-1000, maximum=2500)
        p = number(point.get("pressure_bar_abs"), key + ".P_abs", minimum=.01, maximum=200)
        data.append((key, h, p))
    enthalpies = [item[1] for item in data]
    logs = [log10(item[2]) for item in data]
    h_min, h_max = min(enthalpies) - 35, max(enthalpies) + 35
    p_min, p_max = min(logs) - .2, max(logs) + .2
    if h_max - h_min < 1 or p_max - p_min < .01:
        raise ValueError("Not enough thermodynamic state spread for a diagram")
    W, H = 820, 500
    left, top, right, bottom = 85, 62, 35, 78
    graph_w, graph_h = W-left-right, H-top-bottom
    x = lambda h: left + (h-h_min) / (h_max-h_min) * graph_w
    y = lambda lp: top + (p_max-lp) / (p_max-p_min) * graph_h
    seq = [data[0], data[1], data[2], data[3], data[0]]
    path = " ".join(
        ("M" if idx == 0 else "L") +
        f" {x(state[1]):.1f},{y(log10(state[2])):.1f}"
        for idx, state in enumerate(seq))
    labels = {
        "suction": "1 Suction",
        "discharge": "2 Discharge",
        "condenser_outlet": "3 Condenser outlet",
        "expansion_outlet": "4 Expansion outlet",
    }
    texts = []
    for i, (key, h, p) in enumerate(data):
        px, py = x(h), y(log10(p))
        texts.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="#33bec0"/>'
            f'<text x="{px+10:.1f}" y="{py-12:.1f}" font-size="12"'
            f' fill="#213c4b">{escape(labels[key])}</text>'
            f'<text x="{px+10:.1f}" y="{py+4:.1f}" font-size="10"'
            f' fill="#435e71">{h:.1f} kJ/kg · {p:.2f} bar(a)</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="Schematic log pressure enthalpy cycle">'
        f'<rect width="{W}" height="{H}" fill="#f9fbfc"/>'
        f'<text x="{left}" y="29" font-size="20" fill="#193b4c">'
        f'OpenHVAC • {escape(refrigerant)} schematic log(p)-h</text>'
        f'<rect x="{left}" y="{top}" width="{graph_w}" height="{graph_h}" '
        f'fill="white" stroke="#9cb4c0"/>'
        f'<path d="{path}" fill="none" stroke="#217896" stroke-width="2.5"/>'
        + "".join(texts)
        + f'<text x="{W/2:.1f}" y="{H-23}" font-size="13" text-anchor="middle"'
          f' fill="#193b4c">Specific enthalpy (kJ/kg)</text>'
          f'<text x="21" y="{H/2}" font-size="13" fill="#193b4c"'
          f' transform="rotate(-90 21 {H/2})">Pressure (bar absolute, log scale)</text>'
          f'<text x="{left}" y="{H-6}" font-size="10" fill="#637685">'
          'Point-to-point schematic only; no saturation dome or automatic control.</text>'
          '</svg>'
    )
