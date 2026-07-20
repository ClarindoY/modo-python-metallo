"""Gerador de PECA PLANA — formatos padroes ou contorno livre + furos.

Formatos: Retangulo (raio), Retangulo chanfrado, Disco, Anel, Oblongo, L, U,
Trapezio, Triangulo, Poligono regular e LIVRE (lista de coordenadas).
Furos: redondo, oblongo, retangular — unitarios ou em padrao (linha, grade,
circulo de furacao). Saidas no esquema padrao (flanges): DXF CORTE/FUROS,
previa, folha PDF e etiqueta. Python puro.
"""
import io
import math

INOX_DENS = 7.93e-6  # kg/mm3

FORMATOS = ["Retângulo", "Retângulo chanfrado", "Disco", "Anel", "Oblongo",
            "L", "U", "Trapézio", "Triângulo", "Polígono regular",
            "Livre (coordenadas)"]


def _circ(cx, cy, r, n=72):
    return [(cx + r * math.cos(2 * math.pi * k / n),
             cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _rrect(w, h, r):
    r = max(min(r, w / 2 - 0.01, h / 2 - 0.01), 0.0)
    if r <= 0:
        return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    pts = []
    cantos = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
              (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]
    for cx, cy, a0 in cantos:
        for k in range(13):
            a = math.radians(a0 + 90 * k / 12)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _oblongo(cx, cy, comp, larg, ang=0.0):
    r = larg / 2.0
    L2 = max(comp / 2.0 - r, 0.0)
    pts = []
    for k in range(13):
        a = math.radians(-90 + 180 * k / 12)
        pts.append((L2 + r * math.cos(a), r * math.sin(a)))
    for k in range(13):
        a = math.radians(90 + 180 * k / 12)
        pts.append((-L2 + r * math.cos(a), r * math.sin(a)))
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def _centraliza(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    cx = (max(xs) + min(xs)) / 2.0; cy = (max(ys) + min(ys)) / 2.0
    return [(x - cx, y - cy) for x, y in pts]


def parse_coords(txt):
    """Aceita 'x,y; x,y; ...' ou uma linha por ponto. Retorna lista de pontos."""
    pts = []
    for tok in str(txt).replace("\n", ";").split(";"):
        tok = tok.strip()
        if not tok:
            continue
        ab = tok.replace(",", " ").split()
        if len(ab) >= 2:
            pts.append((float(ab[0]), float(ab[1])))
    return pts


def contorno(formato, p):
    """Retorna (pontos_do_contorno_centralizado, furos_intrinsecos)."""
    f = formato
    extra = []
    if f == "Retângulo":
        o = _rrect(p["C"], p["L"], p.get("raio", 0.0))
    elif f == "Retângulo chanfrado":
        C, L, ch = p["C"], p["L"], max(p.get("chanfro", 10.0), 0.0)
        ch = min(ch, C / 2 - 0.01, L / 2 - 0.01)
        o = [(-C / 2 + ch, -L / 2), (C / 2 - ch, -L / 2), (C / 2, -L / 2 + ch),
             (C / 2, L / 2 - ch), (C / 2 - ch, L / 2), (-C / 2 + ch, L / 2),
             (-C / 2, L / 2 - ch), (-C / 2, -L / 2 + ch)]
    elif f == "Disco":
        o = _circ(0, 0, p["D"] / 2.0)
    elif f == "Anel":
        o = _circ(0, 0, p["D"] / 2.0)
        extra = [("circle", 0.0, 0.0, p["d_int"] / 2.0)]
    elif f == "Oblongo":
        o = _oblongo(0, 0, p["C"], p["L"])
    elif f == "L":
        C, L, pa, pb = p["C"], p["L"], p["perna_v"], p["perna_h"]
        o = _centraliza([(0, 0), (C, 0), (C, pb), (pa, pb), (pa, L), (0, L)])
    elif f == "U":
        C, L, aw, ah = p["C"], p["L"], p["ab_larg"], p["ab_prof"]
        aw = min(aw, C - 2); ah = min(ah, L - 2)
        o = _centraliza([(0, 0), (C, 0), (C, L), (C / 2 + aw / 2, L),
                         (C / 2 + aw / 2, L - ah), (C / 2 - aw / 2, L - ah),
                         (C / 2 - aw / 2, L), (0, L)])
    elif f == "Trapézio":
        o = _centraliza([(-p["B"] / 2, 0), (p["B"] / 2, 0),
                         (p["b"] / 2, p["h"]), (-p["b"] / 2, p["h"])])
    elif f == "Triângulo":
        o = _centraliza([(-p["base"] / 2, 0), (p["base"] / 2, 0), (0, p["h"])])
    elif f == "Polígono regular":
        n = max(int(p["n"]), 3)
        o = _circ(0, 0, p["D"] / 2.0, n)
    else:  # Livre
        o = parse_coords(p.get("coords", ""))
        if len(o) < 3:
            raise ValueError("Contorno livre precisa de pelo menos 3 pontos (x,y; x,y; ...).")
        o = _centraliza(o)
    return o, extra


def _pt_in(pt, ring):
    x, y = pt; dentro = False; n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]; x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                dentro = not dentro
    return dentro


def expandir_furos(furos):
    """Expande a lista de furos (inclui padroes) em primitivas individuais."""
    out = []
    for f in furos or []:
        t = f.get("tipo")
        if t == "redondo":
            out.append(("circle", f["x"], f["y"], f["d"] / 2.0))
        elif t == "oblongo":
            out.append(("poly", _oblongo(f["x"], f["y"], f["comp"], f["larg"], f.get("ang", 0.0))))
        elif t == "retangular":
            c2, l2 = f["c"] / 2.0, f["l"] / 2.0
            ang = math.radians(f.get("ang", 0.0))
            ca, sa = math.cos(ang), math.sin(ang)
            base = [(-c2, -l2), (c2, -l2), (c2, l2), (-c2, l2)]
            out.append(("poly", [(f["x"] + x * ca - y * sa, f["y"] + x * sa + y * ca)
                                 for x, y in base]))
        elif t == "linha":
            ang = math.radians(f.get("ang", 0.0))
            for k in range(max(int(f["n"]), 1)):
                out.append(("circle", f["x"] + k * f["passo"] * math.cos(ang),
                            f["y"] + k * f["passo"] * math.sin(ang), f["d"] / 2.0))
        elif t == "grade":
            for iy in range(max(int(f["ny"]), 1)):
                for ix in range(max(int(f["nx"]), 1)):
                    out.append(("circle", f["x"] + ix * f["px"],
                                f["y"] + iy * f["py"], f["d"] / 2.0))
        elif t == "circulo_furos":
            n = max(int(f["n"]), 1)
            for k in range(n):
                a = math.radians(f.get("ang0", 0.0)) + 2 * math.pi * k / n
                out.append(("circle", f["x"] + f["Dc"] / 2.0 * math.cos(a),
                            f["y"] + f["Dc"] / 2.0 * math.sin(a), f["d"] / 2.0))
    return out


def descreve_furo(f):
    t = f.get("tipo")
    if t == "redondo":
        return f"Furo Ø{f['d']:g} em ({f['x']:g}, {f['y']:g})"
    if t == "oblongo":
        return f"Oblongo {f['comp']:g}×{f['larg']:g} em ({f['x']:g}, {f['y']:g}) {f.get('ang', 0):g}°"
    if t == "retangular":
        return f"Retangular {f['c']:g}×{f['l']:g} em ({f['x']:g}, {f['y']:g}) {f.get('ang', 0):g}°"
    if t == "linha":
        return f"Linha: {int(f['n'])}× Ø{f['d']:g} passo {f['passo']:g} a {f.get('ang', 0):g}° desde ({f['x']:g}, {f['y']:g})"
    if t == "grade":
        return f"Grade {int(f['nx'])}×{int(f['ny'])} Ø{f['d']:g} passos {f['px']:g}/{f['py']:g} desde ({f['x']:g}, {f['y']:g})"
    if t == "circulo_furos":
        return f"Círc. furação: {int(f['n'])}× Ø{f['d']:g} em ØC {f['Dc']:g} centro ({f['x']:g}, {f['y']:g})"
    return str(f)


def _area(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def montar(formato, params, furos, esp=1.2, nome="Peca_plana"):
    o, extra = contorno(formato, params)
    holes = list(extra) + expandir_furos(furos)
    avisos = []
    for h in holes:
        c = (h[1], h[2]) if h[0] == "circle" else (
            sum(p[0] for p in h[1]) / len(h[1]), sum(p[1] for p in h[1]) / len(h[1]))
        if not _pt_in(c, o):
            avisos.append(f"furo com centro FORA do contorno em ({c[0]:.0f}, {c[1]:.0f})")
    a = _area(o)
    for h in holes:
        a -= (math.pi * h[3] ** 2) if h[0] == "circle" else _area(h[1])
    xs = [p[0] for p in o]; ys = [p[1] for p in o]
    W = max(xs) - min(xs); H = max(ys) - min(ys)
    peso = a * float(esp) * INOX_DENS
    return {"outer": ("poly", o), "holes": holes, "deco": [], "bbox": (W, H),
            "area": a, "name": nome, "esp": float(esp),
            "info": {"formato": formato, "n_furos": len(holes), "area_liq": a,
                     "peso": peso, "avisos": avisos}}
