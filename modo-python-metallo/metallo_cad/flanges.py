"""
Gerador de FLANGES planas em DXF (para corte a laser) + nesting simples.

Formas: quadrada, redonda, retangular.
- tamanho externo
- furo central concêntrico opcional (redondo/quadrado/retangular)
- furos de parafuso: quantidade, formato (redondo/oblongo/quadrado),
  distância da borda e tamanho
- compensação de corte (kerf) e espessura da chapa (p/ peso)

Nesting: monta uma biblioteca de até 10 modelos (com quantidade) e encaixa
todas as peças numa chapa só (empacotamento por caixa, em fileiras), gerando
um único DXF + prévia.

Tudo 2D — não depende do CadQuery.
"""
from __future__ import annotations
import io
import re
import math
import ezdxf

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle as _MCircle, Polygon as _MPoly, Rectangle as _MRect

INOX_DENS = 7.93e-3   # g/mm³ (aço inox 304)


# ----------------------------------------------------------------- geometria
def _rect_pts(w, h, cx=0.0, cy=0.0):
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
            (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def _rrect_pts(w, h, r, cx=0.0, cy=0.0, seg=10):
    r = max(min(r, w / 2 - 0.1, h / 2 - 0.1), 0.0)
    if r <= 0:
        return _rect_pts(w, h, cx, cy)
    hw, hh = w / 2, h / 2
    cs = [(hw - r, hh - r), (-hw + r, hh - r), (-hw + r, -hh + r), (hw - r, -hh + r)]
    a0 = [0, 90, 180, 270]
    pts = []
    for (ccx, ccy), base in zip(cs, a0):
        for k in range(seg + 1):
            ang = math.radians(base + 90 * k / seg)
            pts.append((cx + ccx + r * math.cos(ang), cy + ccy + r * math.sin(ang)))
    return pts


def _slot_pts(cx, cy, comprimento, largura, ang_deg, seg=16):
    """Furo oblongo (stadium) centrado em (cx,cy), eixo longo = comprimento."""
    r = largura / 2.0
    L = max(comprimento - largura, 0.0)
    a = math.radians(ang_deg)
    loc = []
    # semicircunferência direita (-90°→+90°)
    for i in range(seg + 1):
        th = -math.pi / 2 + math.pi * i / seg
        loc.append((L / 2 + r * math.cos(th), r * math.sin(th)))
    # semicircunferência esquerda (+90°→+270°)
    for i in range(seg + 1):
        th = math.pi / 2 + math.pi * i / seg
        loc.append((-L / 2 + r * math.cos(th), r * math.sin(th)))
    return [(cx + x * math.cos(a) - y * math.sin(a),
             cy + x * math.sin(a) + y * math.cos(a)) for x, y in loc]


def _bolt_centers(shape, outer, n, dist):
    """Centros dos furos de parafuso (peça centrada em 0,0)."""
    n = max(int(n), 0)
    if n == 0:
        return []
    if shape == "redondo":
        R = outer["D"] / 2.0
        rb = max(R - dist, 1.0)
        return [(rb * math.cos(math.radians(90 - i * 360.0 / n)),
                 rb * math.sin(math.radians(90 - i * 360.0 / n))) for i in range(n)]
    # quadrada / retangular -> cantos (e meios das bordas se n==8)
    W = outer.get("W", outer.get("S")); H = outer.get("H", outer.get("S"))
    cx = W / 2.0 - dist; cy = H / 2.0 - dist
    cantos = [(-cx, -cy), (cx, -cy), (cx, cy), (-cx, cy)]
    if n >= 8:
        meios = [(0, -cy), (cx, 0), (0, cy), (-cx, 0)]
        return (cantos + meios)[:n]
    return cantos[:n] if n <= 4 else cantos


def flange_prims(peca):
    """Converte os parâmetros do flange em primitivos 2D centrados em (0,0).
    Retorna dict: outer, holes (lista), bbox (w,h), area (líquida mm²), name."""
    shape = peca["shape"]
    comp = float(peca.get("comp", 0.0))         # kerf: cresce todo contorno em comp/2
    holes = []

    # ----- contorno externo (cresce comp/2 por lado -> dim += comp)
    if shape == "redondo":
        D = float(peca["D"]) + comp
        outer = ("circle", 0.0, 0.0, D / 2.0)
        bbox = (D, D); a_out = math.pi * (D / 2.0) ** 2
        outer_geo = {"D": float(peca["D"])}
    elif shape == "quadrado":
        S = float(peca["S"]) + comp
        outer = ("poly", _rect_pts(S, S)); bbox = (S, S); a_out = S * S
        outer_geo = {"S": float(peca["S"])}
    else:  # retangular
        W = float(peca["W"]) + comp; H = float(peca["H"]) + comp
        outer = ("poly", _rect_pts(W, H)); bbox = (W, H); a_out = W * H
        outer_geo = {"W": float(peca["W"]), "H": float(peca["H"])}

    # ----- furo central opcional
    a_holes = 0.0
    ct = peca.get("centro")
    if ct:
        cs = ct["shape"]
        if cs == "redondo":
            d = float(ct["d"]) + comp
            holes.append(("circle", 0.0, 0.0, d / 2.0)); a_holes += math.pi * (d / 2) ** 2
        elif cs == "quadrado":
            s = float(ct["s"]) + comp
            holes.append(("poly", _rect_pts(s, s))); a_holes += s * s
        else:
            w = float(ct["w"]) + comp; h = float(ct["h"]) + comp
            holes.append(("poly", _rect_pts(w, h))); a_holes += w * h

    # ----- furos de parafuso
    f = peca.get("furo")
    if f and int(f.get("n", 0)) > 0:
        centers = _bolt_centers(shape, outer_geo, int(f["n"]), float(f["dist"]))
        fs = f["shape"]
        girar = f.get("girar") or []
        for i, (hx, hy) in enumerate(centers):
            if fs == "redondo":
                d = float(f["d"]) + comp
                holes.append(("circle", hx, hy, d / 2.0)); a_holes += math.pi * (d / 2) ** 2
            elif fs == "quadrado":
                s = float(f["d"]) + comp
                holes.append(("poly", _rect_pts(s, s, hx, hy))); a_holes += s * s
            else:  # oblongo
                base_d = float(f.get("d", 10.0))
                comprimento = float(f.get("len", base_d)) + comp
                largura = float(f.get("wid", base_d / 2.0)) + comp
                ang = math.degrees(math.atan2(hy, hx)) if f.get("radial", True) else 0.0
                if i < len(girar) and girar[i]:
                    ang += 90.0                      # gira este furo individualmente
                holes.append(("poly", _slot_pts(hx, hy, comprimento, largura, ang)))
                a_holes += largura * max(comprimento - largura, 0) + math.pi * (largura / 2) ** 2

    return {"outer": outer, "holes": holes, "bbox": bbox,
            "area": max(a_out - a_holes, 0.0), "name": peca.get("name", "flange"),
            "esp": float(peca.get("esp", 0.0))}


def peso_kg(prims):
    return prims["area"] * prims["esp"] * INOX_DENS / 1000.0


# ----------------------------------------------------------------- DXF
def _emit_dxf(msp, prim, dx, dy, layer):
    if prim[0] == "circle":
        _, cx, cy, r = prim
        msp.add_circle((cx + dx, cy + dy), r, dxfattribs={"layer": layer})
    else:
        pts = [(x + dx, y + dy) for (x, y) in prim[1]]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})


def dxf_bytes(items):
    """items: lista de (prims, dx, dy). Gera DXF (CORTE + FUROS + DECORACAO + DOBRA)."""
    doc = ezdxf.new(setup=True)
    doc.layers.add("CORTE", color=1)
    doc.layers.add("FUROS", color=5)
    doc.layers.add("DECORACAO", color=3)
    doc.layers.add("DOBRA", color=4)
    msp = doc.modelspace()
    for prims, dx, dy in items:
        _emit_dxf(msp, prims["outer"], dx, dy, "CORTE")
        for h in prims["holes"]:
            _emit_dxf(msp, h, dx, dy, "FUROS")
        for d in prims.get("deco", []):
            msp.add_lwpolyline([(x + dx, y + dy) for x, y in d[1]], dxfattribs={"layer": "DECORACAO"})
        for f in prims.get("dobras", []):
            msp.add_lwpolyline([(x + dx, y + dy) for x, y in f[1]], dxfattribs={"layer": "DOBRA"})
    s = io.StringIO(); doc.write(s)
    return s.getvalue().encode("utf-8")


# ----------------------------------------------------------------- prévia (PNG)
def _draw_prims(ax, prims, dx, dy):
    cor = prims.get("cor")
    o = prims["outer"]
    if o[0] == "circle":
        ax.add_patch(_MCircle((o[1] + dx, o[2] + dy), o[3], fill=bool(cor),
                              fc=cor or "none", ec=(cor or "#c00"), lw=1.2))
    else:
        ax.add_patch(_MPoly([(x + dx, y + dy) for x, y in o[1]], fill=bool(cor),
                            fc=cor or "none", ec=("#222" if cor else "#c00"), lw=1.2))
    for h in prims["holes"]:
        if h[0] == "circle":
            ax.add_patch(_MCircle((h[1] + dx, h[2] + dy), h[3], fill=bool(cor),
                                  fc=("white" if cor else "none"), ec=("#888" if cor else "#06c"), lw=0.8))
        else:
            ax.add_patch(_MPoly([(x + dx, y + dy) for x, y in h[1]], fill=bool(cor),
                                fc=("white" if cor else "none"), ec=("#888" if cor else "#06c"), lw=0.8))
    for d in prims.get("deco", []):
        pts = [(x + dx, y + dy) for x, y in d[1]]
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                color=("white" if cor else "#06c"), lw=1.0, solid_capstyle="round")
    for f in prims.get("dobras", []):
        pts = [(x + dx, y + dy) for x, y in f[1]]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color="#0a0", lw=0.7, ls="--")


def preview_png(prims):
    w, h = prims["bbox"]
    fig = plt.figure(figsize=(4.2, 4.2), dpi=120)
    ax = fig.add_axes([0.06, 0.06, 0.88, 0.88]); ax.set_aspect("equal")
    _draw_prims(ax, prims, 0, 0)
    m = max(w, h) * 0.58
    ax.set_xlim(-m, m); ax.set_ylim(-m, m); ax.axis("off")
    buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True); plt.close(fig)
    return buf.getvalue()


def preview_pdf(prims, esp=0.0, material="Inox 304", obs=""):
    """Desenho técnico simples da peça plana em PDF (A4 paisagem) com cotas gerais,
    contagem de furos/recortes, peso e carimbo curto."""
    from matplotlib.backends.backend_pdf import PdfPages
    w, h = prims["bbox"]
    buf = io.BytesIO()
    with PdfPages(buf) as pp:
        fig = plt.figure(figsize=(11.69, 8.27))            # A4 paisagem
        ax = fig.add_axes([0.06, 0.16, 0.9, 0.78]); ax.set_aspect("equal")
        _draw_prims(ax, prims, 0, 0)
        mx = max(w, h) * 0.62
        ax.set_xlim(-w / 2 - mx * 0.12, w / 2 + mx * 0.12)
        ax.set_ylim(-h / 2 - mx * 0.12, h / 2 + mx * 0.12)
        # cotas gerais
        yb = -h / 2 - mx * 0.06
        ax.annotate("", (-w / 2, yb), (w / 2, yb), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax.text(0, yb - mx * 0.03, f"{w:g} mm", ha="center", va="top", fontsize=9)
        xb = -w / 2 - mx * 0.06
        ax.annotate("", (xb, -h / 2), (xb, h / 2), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax.text(xb - mx * 0.02, 0, f"{h:g} mm", ha="right", va="center", rotation=90, fontsize=9)
        ax.axis("off")
        nfuros = len(prims.get("holes", []))
        peso = peso_kg(prims) if esp else 0.0
        info = (f"{prims.get('name','peça')}   |   {w:g} × {h:g} mm   |   "
                f"recortes/furos: {nfuros}" + (f"   |   esp. {esp:g} mm   |   ~{peso:.2f} kg (inox 304)" if esp else ""))
        fig.text(0.06, 0.085, info, fontsize=9)
        fig.text(0.06, 0.05, "METALLO / CONCETTO — peça plana para corte a laser" + (f"   ·   {obs}" if obs else ""),
                 fontsize=8, color="0.3")
        pp.savefig(fig); plt.close(fig)
    return buf.getvalue()


# ----------------------------------------------------------------- nesting
def nest(pecas_qty, sheet_w=1200.0, gap=8.0, margin=12.0):
    """pecas_qty: lista de (prims, qtd). Empacota por caixa em fileiras.
    Retorna (placed, sheet_w, sheet_h, aproveitamento%)."""
    insts = []
    for prims, qt in pecas_qty:
        insts.extend([prims] * max(int(qt), 0))
    insts.sort(key=lambda p: -p["bbox"][1])
    usable = sheet_w - 2 * margin
    x = margin; y = margin; rowH = 0.0; placed = []
    for p in insts:
        w, h = p["bbox"]
        if x > margin and (x - margin + w) > usable:
            x = margin; y += rowH + gap; rowH = 0.0
        placed.append((p, x + w / 2.0, y + h / 2.0))
        x += w + gap; rowH = max(rowH, h)
    sheet_h = y + rowH + margin
    area_pecas = sum(p["area"] for p, _, _ in placed)
    aprov = 100.0 * area_pecas / (sheet_w * sheet_h) if sheet_h > 0 else 0.0
    return placed, sheet_w, sheet_h, aprov


def nest_dxf_bytes(placed):
    return dxf_bytes([(p, dx, dy) for (p, dx, dy) in placed])


def nest_preview_png(placed, sheet_w, sheet_h):
    fig = plt.figure(figsize=(7.0, 7.0 * min(sheet_h / sheet_w, 2.2)), dpi=110)
    ax = fig.add_axes([0.04, 0.04, 0.92, 0.92]); ax.set_aspect("equal")
    ax.add_patch(_MRect((0, 0), sheet_w, sheet_h, fill=False, ec="#333", lw=1.4))
    for (p, dx, dy) in placed:
        _draw_prims(ax, p, dx, dy)
    ax.set_xlim(-20, sheet_w + 20); ax.set_ylim(-20, sheet_h + 20)
    ax.invert_yaxis(); ax.axis("off")
    buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True); plt.close(fig)
    return buf.getvalue()


# ----------------------------------------------------------------- peça por descrição (multi-forma)
def _poly_regular_pts(n, R, rot_deg=0.0, cx=0.0, cy=0.0):
    rot = math.radians(rot_deg)
    return [(cx + R * math.cos(rot + 2 * math.pi * k / n),
             cy + R * math.sin(rot + 2 * math.pi * k / n)) for k in range(int(n))]


def _bolt_circle_centers(n, pcd):
    R = pcd / 2.0
    return [(R * math.cos(2 * math.pi * k / n + math.pi / 2.0),
             R * math.sin(2 * math.pi * k / n + math.pi / 2.0)) for k in range(int(n))]


def _grid_centers(C, W, cols, rows, margem):
    cols = max(int(cols), 1); rows = max(int(rows), 1)
    xs = [(-C / 2 + margem + (C - 2 * margem) * (i / (cols - 1)) if cols > 1 else 0.0) for i in range(cols)]
    ys = [(-W / 2 + margem + (W - 2 * margem) * (j / (rows - 1)) if rows > 1 else 0.0) for j in range(rows)]
    return [(x, y) for y in ys for x in xs]


def peca_por_descricao(spec):
    """Gera prims (outer/holes/bbox/area/name/esp) a partir de uma 'spec' de forma.
    forma: 'retangulo' | 'disco' | 'anel' | 'poligono'.
    furos: {'padrao': 'linha'|'grade'|'circulo'|'cantos', 'n','d','pcd','cols','rows','dist'}."""
    forma = spec.get("forma", "retangulo")
    comp = float(spec.get("comp", 0.0))
    esp = float(spec.get("esp", 0.0))
    name = spec.get("name", "peca")
    holes = []; a_holes = 0.0

    if forma == "disco":
        D = float(spec["diametro"]) + comp
        outer = ("circle", 0.0, 0.0, D / 2.0); bbox = (D, D); a_out = math.pi * (D / 2) ** 2
        R_out = float(spec["diametro"]) / 2.0
    elif forma == "anel":
        D = float(spec["diametro"]) + comp
        outer = ("circle", 0.0, 0.0, D / 2.0); bbox = (D, D); a_out = math.pi * (D / 2) ** 2
        di = float(spec["diametro_int"]) + comp
        holes.append(("circle", 0.0, 0.0, di / 2.0)); a_holes += math.pi * (di / 2) ** 2
        R_out = float(spec["diametro"]) / 2.0
    elif forma == "poligono":
        nl = int(spec.get("lados", 6))
        med = float(spec["medida"]); tipo = spec.get("medida_tipo", "entre_faces")
        if tipo == "entre_faces":
            R = (med / 2.0) / math.cos(math.pi / nl)
        else:                                   # circulo / vertice = diâmetro de vértice
            R = med / 2.0
        R += comp / 2.0
        rot = 90.0 + (180.0 / nl if nl % 2 == 0 else 0.0)   # face para cima
        pts = _poly_regular_pts(nl, R, rot)
        outer = ("poly", pts)
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        bbox = (max(xs) - min(xs), max(ys) - min(ys))
        a_out = 0.5 * nl * R * R * math.sin(2 * math.pi / nl)
        R_out = R
    else:                                       # retangulo
        C = float(spec.get("comprimento", spec.get("largura", 100.0))) + comp
        W = float(spec.get("largura", spec.get("comprimento", 100.0))) + comp
        outer = ("poly", _rect_pts(C, W)); bbox = (C, W); a_out = C * W
        R_out = min(C, W) / 2.0

    # furo central opcional
    if spec.get("furo_central"):
        d = float(spec["furo_central"]) + comp
        holes.append(("circle", 0.0, 0.0, d / 2.0)); a_holes += math.pi * (d / 2) ** 2

    # padrão de furação
    fr = spec.get("furos")
    if fr and int(fr.get("n", 0)) > 0:
        n = int(fr["n"]); d = float(fr.get("d", 6.0)) + comp; rr = d / 2.0
        padrao = fr.get("padrao", "linha")
        C, W = bbox
        if padrao == "circulo":
            pcd = float(fr.get("pcd") or (R_out * 2 * 0.7))
            centers = _bolt_circle_centers(n, pcd)
        elif padrao == "grade":
            cols = int(fr.get("cols") or n); rows = int(fr.get("rows") or 1)
            centers = _grid_centers(C, W, cols, rows, float(fr.get("dist", min(C, W) * 0.15)))
        elif padrao == "cantos":
            dist = float(fr.get("dist", min(C, W) * 0.12))
            centers = [(-C / 2 + dist, -W / 2 + dist), (C / 2 - dist, -W / 2 + dist),
                       (C / 2 - dist, W / 2 - dist), (-C / 2 + dist, W / 2 - dist)][:max(n, 1)]
        else:                                   # linha (ao longo do comprimento, equidistante)
            centers = [(-C / 2 + C * (i + 1) / (n + 1), 0.0) for i in range(n)]
        for (hx, hy) in centers:
            holes.append(("circle", hx, hy, rr)); a_holes += math.pi * rr * rr

    # recortes retangulares em grade (chapa perfurada) — preenche a chapa
    rec = spec.get("recorte")
    if rec and forma == "retangulo":
        cw = float(rec["w"]) + comp                 # ao longo do comprimento (X)
        ch = float(rec["h"]) + comp                 # ao longo da largura (Y)
        g = float(rec.get("gap", 10.0))
        C, W = bbox
        nx = int((C - g) // (cw + g)) if cw + g > 0 else 0
        ny = int((W - g) // (ch + g)) if ch + g > 0 else 0
        nx = max(nx, 1); ny = max(ny, 1)
        m_user = rec.get("margem")
        if m_user:                                  # margem fixa informada
            nx = max(int((C - 2 * float(m_user) + g) // (cw + g)), 1)
            ny = max(int((W - 2 * float(m_user) + g) // (ch + g)), 1)
        span_x = nx * cw + (nx - 1) * g
        span_y = ny * ch + (ny - 1) * g
        x0 = -span_x / 2 + cw / 2
        y0 = -span_y / 2 + ch / 2
        for j in range(ny):
            for i in range(nx):
                hx = x0 + i * (cw + g); hy = y0 + j * (ch + g)
                holes.append(("poly", _rect_pts(cw, ch, hx, hy)))
                a_holes += cw * ch
        spec["_grid"] = (nx, ny)                     # p/ exibir contagem

    return {"outer": outer, "holes": holes, "bbox": bbox,
            "area": max(a_out - a_holes, 0.0), "name": name, "esp": esp}


def chapa_furos_prims(comprimento, largura, n, d, comp=0.0, esp=0.0, name="chapa"):
    """Compat.: chapa retangular com N furos em linha equidistante."""
    return peca_por_descricao({"forma": "retangulo", "comprimento": comprimento, "largura": largura,
                               "comp": comp, "esp": esp, "name": name,
                               "furos": {"padrao": "linha", "n": int(n), "d": float(d)}})


import os as _os
_FONT_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "assets", "fonts")
FONTES_PLACA = {
    "Fina (Poppins Light)": _os.path.join(_FONT_DIR, "Poppins-Light.ttf"),
    "Elegante (Julius)": _os.path.join(_FONT_DIR, "JuliusSansOne-Regular.ttf"),
    "Neutra (Questrial)": _os.path.join(_FONT_DIR, "Questrial-Regular.ttf"),
    "Geométrica (Poppins)": _os.path.join(_FONT_DIR, "Poppins-SemiBold.ttf"),
    "Serifada (Lora)": _os.path.join(_FONT_DIR, "Lora.ttf"),
    "Condensada (Bebas)": _os.path.join(_FONT_DIR, "BebasNeue-Regular.ttf"),
    "Robusta (Archivo Black)": _os.path.join(_FONT_DIR, "ArchivoBlack-Regular.ttf"),
}


def _texto_contornos(texto, prop=None, fonte=None):
    """Contornos (paths) do texto via matplotlib, prontos para corte/gravação.
    'fonte' pode ser um caminho de arquivo .ttf (embutido no kit — funciona em
    qualquer servidor) ou um nome de família instalada."""
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    if prop is None:
        try:
            if fonte and _os.path.sep in str(fonte) and _os.path.exists(fonte):
                prop = FontProperties(fname=fonte)
            elif fonte:
                prop = FontProperties(family=fonte, weight="bold")
            else:
                prop = FontProperties(family="DejaVu Sans", weight="bold")
        except Exception:
            prop = FontProperties(family="DejaVu Sans", weight="bold")
    tp = TextPath((0, 0), texto, size=1000.0, prop=prop)
    return [[(float(x), float(y)) for x, y in poly] for poly in tp.to_polygons() if len(poly) >= 3]


def _pt_in_ring(pt, ring):
    x, y = pt; dentro = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]; x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                dentro = not dentro
    return dentro


def _cruza_x(ring, X):
    """Cruzamentos do anel com a reta vertical x=X -> lista de (y, indice_da_aresta, ponto)."""
    out = []
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]; x2, y2 = ring[(i + 1) % n]
        if (x1 - X) * (x2 - X) < 0:
            tt = (X - x1) / (x2 - x1)
            out.append((y1 + tt * (y2 - y1), i, (X, y1 + tt * (y2 - y1))))
    return out


def _arcos(ring, ia, pa, ib, pb):
    """Divide o anel em dois arcos entre os pontos pa (na aresta ia) e pb (aresta ib).
    Retorna (arco1, arco2), cada um comecando em pa e terminando em pb."""
    n = len(ring)
    a1 = [pa]
    k = (ia + 1) % n
    while True:
        a1.append(ring[k])
        if k == ib:
            break
        k = (k + 1) % n
        if len(a1) > 2 * n + 4:
            return None, None
    a1.append(pb)
    a2 = [pa]
    k = ia
    while True:
        a2.append(ring[k])
        if k == (ib + 1) % n:
            break
        k = (k - 1) % n
        if len(a2) > 2 * n + 4:
            return None, None
    a2.append(pb)
    return a1, a2


def _comp_arco(a):
    return sum(math.hypot(a[i + 1][0] - a[i][0], a[i + 1][1] - a[i][1]) for i in range(len(a) - 1))


def _ponte_uma(externo, furo, w, topo=True, xshift=0.0):
    """Emenda 'furo' (anel interno) ao anel 'externo' com uma ponte vertical de
    largura w, atravessando a parede ACIMA (topo=True) ou ABAIXO do furo.
    Retorna o novo anel unico, ou None se nao der com seguranca."""
    sgn = 1.0 if topo else -1.0
    # ancora: vertice do furo mais alto (ou mais baixo) -> funciona p/ miolos
    # triangulares (A, 4) e redondos (0, 6, 8, 9)
    anc = max(furo, key=lambda p: sgn * p[1])
    xs = [p[0] for p in furo]
    xc = min(max(anc[0] + xshift, min(xs) + w), max(xs) - w) + 0.0037
    xl, xr = xc - w / 2.0, xc + w / 2.0
    cf_l = _cruza_x(furo, xl); cf_r = _cruza_x(furo, xr)
    ce_l = _cruza_x(externo, xl); ce_r = _cruza_x(externo, xr)
    if not (cf_l and cf_r and ce_l and ce_r):
        return None
    yl_f, il_f, pl_f = max(cf_l, key=lambda c: sgn * c[0])
    yr_f, ir_f, pr_f = max(cf_r, key=lambda c: sgn * c[0])
    alem_l = [c for c in ce_l if sgn * c[0] > sgn * yl_f]
    alem_r = [c for c in ce_r if sgn * c[0] > sgn * yr_f]
    if not (alem_l and alem_r):
        return None
    yl_e, il_e, pl_e = min(alem_l, key=lambda c: sgn * c[0])
    yr_e, ir_e, pr_e = min(alem_r, key=lambda c: sgn * c[0])

    def _sai_do_canal(arco):
        return any((p[0] < xl - 1e-6) or (p[0] > xr + 1e-6) for p in arco[1:-1]) or len(arco) <= 2

    e1, e2 = _arcos(externo, il_e, pl_e, ir_e, pr_e)
    if e1 is None:
        return None
    # manter o arco do EXTERNO que SAI do canal (contorna por fora);
    # remover o trecho de parede que fica dentro do canal
    if _sai_do_canal(e1) and not _sai_do_canal(e2):
        arco_ext = e1
    elif _sai_do_canal(e2) and not _sai_do_canal(e1):
        arco_ext = e2
    else:
        arco_ext = e1 if _comp_arco(e1) >= _comp_arco(e2) else e2
    f1, f2 = _arcos(furo, il_f, pl_f, ir_f, pr_f)
    if f1 is None:
        return None
    if _sai_do_canal(f1) and not _sai_do_canal(f2):
        arco_fur = f1
    elif _sai_do_canal(f2) and not _sai_do_canal(f1):
        arco_fur = f2
    else:
        arco_fur = f1 if _comp_arco(f1) >= _comp_arco(f2) else f2
    novo = [pl_e, pl_f] + arco_fur[1:-1] + [pr_f, pr_e] + list(reversed(arco_ext))[1:-1]
    return [(float(x), float(y)) for x, y in novo]


def _aplicar_pontes(polys, bridge_w, topo=True):
    """Adiciona PONTES (stencil) aos vazados internos dos caracteres, para que as
    ilhas (miolo do 0, 4, 6, 8, 9, A...) nao caiam ao cortar. Python puro, sem
    dependencias. Miolos empilhados no mesmo caractere (8) alternam a direcao da
    ponte (cima/baixo) para os canais nao se cruzarem."""
    if not bridge_w or bridge_w <= 0:
        return polys
    try:
        aneis = [list(p) for p in polys if len(p) >= 3]
        if not aneis:
            return polys
        prof = []
        for i, r in enumerate(aneis):
            pt = r[0]
            d = sum(1 for jj, o in enumerate(aneis) if jj != i and _pt_in_ring(pt, o))
            prof.append(d)
        externos = [i for i, d in enumerate(prof) if d % 2 == 0]
        furos = [i for i, d in enumerate(prof) if d % 2 == 1]
        out = []
        usados = set()
        for ie in externos:
            anel = list(aneis[ie])
            meus = [jf for jf in furos if _pt_in_ring(aneis[jf][0], aneis[ie])
                    and prof[jf] == prof[ie] + 1]
            # do miolo mais alto para o mais baixo, alternando cima/baixo
            meus.sort(key=lambda jf: -max(p[1] for p in aneis[jf]))
            for k, jf in enumerate(meus):
                para_cima = (k % 2 == 0) if topo else (k % 2 == 1)
                fxs = [p[0] for p in aneis[jf]]
                larg = (max(fxs) - min(fxs)) or 1.0
                shift = [0.0, 0.34, -0.34, 0.58, -0.58][k % 5] * larg
                emendado = _ponte_uma(anel, aneis[jf], float(bridge_w), topo=para_cima, xshift=shift)
                if emendado is None:
                    emendado = _ponte_uma(anel, aneis[jf], float(bridge_w), topo=not para_cima, xshift=shift)
                if emendado is None:
                    emendado = _ponte_uma(anel, aneis[jf], float(bridge_w), topo=para_cima, xshift=-shift)
                if emendado is not None:
                    anel = emendado
                    usados.add(jf)
            out.append(anel)
        for jf in furos:
            if jf not in usados:
                out.append(aneis[jf])
        return out
    except Exception:
        return polys



def placa_numerica_prims(L, W, texto, font_frac=0.62, n_furos=2, d_furo=6.0,
                         margem_furo=18.0, raio=0.0, comp=0.0, esp=0.0, name="placa"):
    """Placa retangular (número residencial) com o texto VAZADO (recortado) e furos
    de fixação. Tamanhos em mm. Retorna prims (mesma estrutura das demais peças)."""
    C = float(L) + comp; H = float(W) + comp
    if raio and raio > 0:
        outer = ("poly", _rrect_pts(C, H, min(raio, min(C, H) / 2 - 0.1)))
    else:
        outer = ("poly", _rect_pts(C, H))
    holes = []; a_holes = 0.0

    contornos = _texto_contornos(str(texto)) if str(texto).strip() else []
    if contornos:
        xs = [p[0] for c in contornos for p in c]; ys = [p[1] for c in contornos for p in c]
        tw = max(xs) - min(xs); th = max(ys) - min(ys)
        cxt = (max(xs) + min(xs)) / 2; cyt = (max(ys) + min(ys)) / 2
        alvo_h = font_frac * H
        alvo_w = C - 2 * margem_furo - max(d_furo, 8)    # deixa espaço lateral p/ furos
        sc = min(alvo_h / th if th else 1, alvo_w / tw if tw else 1)
        for c in contornos:
            pts = [((x - cxt) * sc, (y - cyt) * sc) for x, y in c]
            holes.append(("poly", pts))
        # área aproximada do texto (não crítica)
        a_holes += tw * th * sc * sc * 0.35

    # furos de fixação (frontais)
    nf = int(n_furos)
    if nf > 0 and d_furo > 0:
        r = d_furo / 2.0
        if nf <= 2:
            xs_f = [-C / 2 + margem_furo, C / 2 - margem_furo][:nf] if nf == 2 else [0.0]
            for hx in xs_f:
                holes.append(("circle", hx, H / 2 - margem_furo, r)); a_holes += math.pi * r * r
        else:
            cantos = [(-C / 2 + margem_furo, H / 2 - margem_furo), (C / 2 - margem_furo, H / 2 - margem_furo),
                      (C / 2 - margem_furo, -H / 2 + margem_furo), (-C / 2 + margem_furo, -H / 2 + margem_furo)]
            for (hx, hy) in cantos[:nf]:
                holes.append(("circle", hx, hy, r)); a_holes += math.pi * r * r

    return {"outer": outer, "holes": holes, "bbox": (C, H),
            "area": max(C * H - a_holes, 0.0), "name": name, "esp": float(esp)}


def render_dxf_png(dxf_bytes):
    """Preview PNG de um DXF qualquer (linhas, círculos, arcos, polilinhas)."""
    import matplotlib.patches as mpatches
    doc = ezdxf.read(io.StringIO(dxf_bytes.decode("utf-8", "ignore")))
    msp = doc.modelspace()
    fig = plt.figure(figsize=(5.0, 5.0), dpi=110)
    ax = fig.add_axes([0.04, 0.04, 0.92, 0.92]); ax.set_aspect("equal")
    xs, ys = [], []

    def acc(px, py):
        xs.append(px); ys.append(py)

    for e in msp:
        t = e.dxftype()
        try:
            if t == "LINE":
                ax.plot([e.dxf.start.x, e.dxf.end.x], [e.dxf.start.y, e.dxf.end.y], "k", lw=0.8)
                acc(e.dxf.start.x, e.dxf.start.y); acc(e.dxf.end.x, e.dxf.end.y)
            elif t == "CIRCLE":
                ax.add_patch(mpatches.Circle((e.dxf.center.x, e.dxf.center.y), e.dxf.radius,
                                             fill=False, ec="#1565C0", lw=0.8))
                acc(e.dxf.center.x - e.dxf.radius, e.dxf.center.y - e.dxf.radius)
                acc(e.dxf.center.x + e.dxf.radius, e.dxf.center.y + e.dxf.radius)
            elif t == "ARC":
                ax.add_patch(mpatches.Arc((e.dxf.center.x, e.dxf.center.y), 2 * e.dxf.radius, 2 * e.dxf.radius,
                                          theta1=e.dxf.start_angle, theta2=e.dxf.end_angle, ec="k", lw=0.8))
                acc(e.dxf.center.x - e.dxf.radius, e.dxf.center.y - e.dxf.radius)
                acc(e.dxf.center.x + e.dxf.radius, e.dxf.center.y + e.dxf.radius)
            elif t == "LWPOLYLINE":
                pts = list(e.get_points("xy"))
                if e.closed and pts:
                    pts = pts + [pts[0]]
                ax.plot([p[0] for p in pts], [p[1] for p in pts], "k", lw=0.8)
                for p in pts:
                    acc(p[0], p[1])
            elif t == "POLYLINE":
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                ax.plot([p[0] for p in pts], [p[1] for p in pts], "k", lw=0.8)
                for p in pts:
                    acc(p[0], p[1])
        except Exception:
            pass
    if xs:
        mx = (max(max(xs) - min(xs), max(ys) - min(ys)) or 10) * 0.06
        ax.set_xlim(min(xs) - mx, max(xs) + mx); ax.set_ylim(min(ys) - mx, max(ys) + mx)
    ax.axis("off")
    buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True); plt.close(fig)
    return buf.getvalue()


ACABAMENTOS = {"Corten": "#9c5527", "Grafite": "#3b3b3b", "Preto": "#141414", "Branco": "#eeeeee", "Prata": "#c6c8cc",
               "Champagne": "#c8b694", "Marrom": "#5b3a26", "Cobre / Corten": "#a85a2e",
               "Bronze": "#6d5736"}

MODELOS_PLACA = ["Cacos", "Ondas", "Arcos", "Pixels", "Treliça", "Bauhaus", "Círculos", "Colmeia", "Ripas", "Chevrons", "Folhas", "Raios", "Vitral", "Ladrilho", "Bambu", "Sem padrão"]


def _padrao_deco(modelo, x0, y0, w, h, seed=1):
    """Padrões DECORATIVOS autorais dentro da banda (x0,y0,w,h). Retorna ('line', pts)."""
    import math as _m
    import random
    rnd = random.Random(seed)
    out = []
    m = (modelo or "").lower()

    if "caco" in m or "traç" in m or "trac" in m:        # cacos / estilhaços triangulares
        pts = [(x0 + w * i / 6 + rnd.uniform(-w * 0.04, w * 0.04),
                y0 + h * (0.15 + 0.7 * rnd.random())) for i in range(7)]
        borda = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        nodes = pts + borda
        for i in range(len(pts) - 1):
            out.append(("line", [pts[i], pts[i + 1]]))
        for _ in range(int(w / max(h, 1)) + 7):
            a, b = rnd.sample(nodes, 2)
            out.append(("line", [a, b]))

    elif "ripa" in m or "linha" in m:                    # ripas diagonais paralelas
        step = max(h * 0.42, 10)
        x = x0 - h
        while x < x0 + w:
            out.append(("line", [(max(x, x0), y0), (min(x + h, x0 + w), y0 + h)]))
            x += step

    elif "onda" in m:                                    # ondas suaves
        for r in range(3):
            yy = y0 + h * (r + 0.5) / 3
            out.append(("line", [(x0 + w * t / 48, yy + h * 0.16 * _m.sin(t / 48 * 4 * _m.pi + r))
                                 for t in range(49)]))

    elif "treli" in m or "grade" in m:                   # treliça (X)
        step = max(h * 0.8, 16)
        x = x0
        while x < x0 + w:
            out.append(("line", [(x, y0), (min(x + step, x0 + w), y0 + h)]))
            out.append(("line", [(min(x + step, x0 + w), y0), (x, y0 + h)]))
            x += step

    elif "canto" in m:                                   # cantoneiras
        c = min(w, h) * 0.6
        out += [("line", [(x0, y0 + c), (x0, y0), (x0 + c, y0)]),
                ("line", [(x0 + w - c, y0), (x0 + w, y0), (x0 + w, y0 + c)]),
                ("line", [(x0, y0 + h - c), (x0, y0 + h), (x0 + c, y0 + h)]),
                ("line", [(x0 + w - c, y0 + h), (x0 + w, y0 + h), (x0 + w, y0 + h - c)])]

    elif "folha" in m:                                   # folhas / orgânico (pétalas)
        nf = max(int(w / (h * 0.9)), 3)
        for i in range(nf):
            cx = x0 + w * (i + 0.5) / nf; cy = y0 + h * 0.5
            a = h * 0.42; b = h * 0.20
            ang = rnd.uniform(-0.5, 0.5)
            folha = []
            for t in range(0, 361, 18):
                rad = _m.radians(t)
                ex = a * _m.cos(rad); ey = b * _m.sin(rad)
                folha.append((cx + ex * _m.cos(ang) - ey * _m.sin(ang),
                              cy + ex * _m.sin(ang) + ey * _m.cos(ang)))
            out.append(("line", folha))

    elif "colmeia" in m or "hex" in m:                   # favo de mel
        r = h * 0.30
        dx = r * 1.5; dy = r * _m.sqrt(3)
        row = 0; y = y0 + r
        while y < y0 + h:
            x = x0 + (r if row % 2 else r * 1.75)
            while x < x0 + w:
                hexp = [(x + r * _m.cos(_m.radians(60 * k)), y + r * _m.sin(_m.radians(60 * k)))
                        for k in range(7)]
                out.append(("line", hexp)); x += dx * 2
            y += dy / 2; row += 1

    elif "bambu" in m:                                   # ripado vertical (bambu)
        n = max(int(w / (h * 0.32)), 4)
        for i in range(1, n):
            xx = x0 + w * i / n
            out.append(("line", [(xx, y0 + h * 0.05), (xx, y0 + h * 0.95)]))
            for k in (0.3, 0.6):
                out.append(("line", [(xx - w * 0.012, y0 + h * k), (xx + w * 0.012, y0 + h * k)]))

    elif "vértic" in m or "vertic" in m:                 # malha de vértices (triangulação)
        nodes = [(x0 + rnd.uniform(0, w), y0 + rnd.uniform(0, h)) for _ in range(9)]
        nodes += [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        nodes.sort()
        for i in range(len(nodes) - 1):
            out.append(("line", [nodes[i], nodes[i + 1]]))
            if i + 2 < len(nodes):
                out.append(("line", [nodes[i], nodes[i + 2]]))
    return out


def _texto_polys(s, fonte=None, tracking=0.0, caixa_alta=False):
    """Poligonos do texto com TRACKING (espacejamento entre letras), por caractere.
    Retorna (polys, largura, altura) em unidades da fonte (size=1000)."""
    if caixa_alta:
        s = str(s).upper()
    ref = _texto_contornos("0", fonte=fonte)
    if ref:
        ys = [p[1] for c in ref for p in c]
        em_h = (max(ys) - min(ys)) or 700.0
        xs = [p[0] for c in ref for p in c]
        em_w = (max(xs) - min(xs)) or 500.0
    else:
        em_h, em_w = 700.0, 500.0
    gap = tracking * em_h
    polys = []
    x = 0.0
    ymin_g, ymax_g = 1e18, -1e18
    for ch in str(s):
        if ch == " ":
            x += em_w * 0.62 + gap
            continue
        cont = _texto_contornos(ch, fonte=fonte)
        if not cont:
            x += em_w * 0.62 + gap
            continue
        xs = [p[0] for c in cont for p in c]
        x0, x1 = min(xs), max(xs)
        for c in cont:
            polys.append([(px - x0 + x, py) for px, py in c])
        ys = [p[1] for c in cont for p in c]
        ymin_g = min(ymin_g, min(ys)); ymax_g = max(ymax_g, max(ys))
        x += (x1 - x0) + gap
    if not polys:
        return [], 0.0, 0.0
    w = x - gap
    return polys, w, (ymax_g - ymin_g if ymax_g > ymin_g else em_h)


def _rrect_line(cx, cy, w, h, r):
    pts = _rrect_pts(w, h, max(r, 0.1))
    pts = [(x + cx, y + cy) for x, y in pts]
    return ("line", pts + [pts[0]])


def _clip_rect(poly, x0, y0, x1, y1):
    """Recorta o poligono ao retangulo (Sutherland-Hodgman)."""
    def clip(pts, dentro, inter):
        out = []
        n = len(pts)
        for k in range(n):
            a = pts[k]; b = pts[(k + 1) % n]
            da, db = dentro(a), dentro(b)
            if da:
                out.append(a)
                if not db:
                    out.append(inter(a, b))
            elif db:
                out.append(inter(a, b))
        return out
    p = list(poly)
    for dentro, inter in [
        (lambda q: q[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
        (lambda q: q[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
        (lambda q: q[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
        (lambda q: q[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1)),
    ]:
        if len(p) < 3:
            return []
        p = clip(p, dentro, inter)
    return p if len(p) >= 3 else []


def _faixa_padrao(nome, x0, x1, y0, y1, seed=1, avoid=()):
    """Padroes VAZADOS autorais para as faixas do totem. Retorna lista de
    poligonos (furos) totalmente dentro da faixa, com nervuras continuas."""
    import random
    import math as _m
    rnd = random.Random(int(seed))
    W = x1 - x0; H = y1 - y0
    holes = []
    if W <= 8 or H <= 8:
        return holes

    def _ok(cx, cy, r):
        for ax, ay, ar in avoid:
            if (cx - ax) ** 2 + (cy - ay) ** 2 < (ar + r) ** 2:
                return False
        return True

    if nome == "Pixels":
        cell = max(W / 15.0, 6.0)
        s = cell * 0.72
        nx = int(W // cell); ny = max(int(H // cell), 2)
        ox = x0 + (W - nx * cell) / 2.0; oy = y0 + (H - ny * cell) / 2.0
        for iy in range(ny):
            for ix in range(nx):
                if rnd.random() > 0.78:
                    continue
                cx = ox + (ix + 0.5) * cell; cy = oy + (iy + 0.5) * cell
                if not _ok(cx, cy, s * 0.75):
                    continue
                holes.append([(cx - s / 2, cy - s / 2), (cx + s / 2, cy - s / 2),
                              (cx + s / 2, cy + s / 2), (cx - s / 2, cy + s / 2)])

    elif nome == "Treliça":
        cell = max(W / 8.0, 10.0)
        ny = max(int(H // (cell * 0.66)), 2)
        for iy in range(ny):
            cy = y0 + (iy + 0.5) * (H / ny)
            desl = (cell / 2.0) if iy % 2 else 0.0
            nx = int((W - desl) // cell)
            for ix in range(nx):
                cx = x0 + desl + (ix + 0.5) * cell
                dx = cell * 0.36; dy = (H / ny) * 0.36
                if cx - dx < x0 or cx + dx > x1:
                    continue
                if not _ok(cx, cy, max(dx, dy)):
                    continue
                holes.append([(cx, cy - dy), (cx + dx, cy), (cx, cy + dy), (cx - dx, cy)])

    elif nome == "Arcos":
        # leques de quartos de circulo concentricos, a partir de um canto da faixa
        canto_cima = (y1 > 0)
        cx = x0 if (seed % 2 == 0) else x1
        cy = y1 if canto_cima else y0
        sx = 1.0 if cx == x0 else -1.0
        sy = -1.0 if canto_cima else 1.0
        passo = H / 5.2; w = passo * 0.52
        r = passo * 0.9
        rmax = _m.hypot(W, H)
        while r + w < rmax:
            t0 = 0.0; t1 = _m.pi / 2.0
            # limites da faixa
            if r > W:
                t0 = max(t0, _m.acos(min(W / r, 1.0)))
            if r > H:
                t1 = min(t1, _m.asin(min(H / r, 1.0)))
            if t1 - t0 > 0.06:
                pts = []
                n = max(int(14 * (t1 - t0)), 6)
                for k in range(n + 1):
                    tt = t0 + (t1 - t0) * k / n
                    pts.append((cx + sx * (r + w) * _m.cos(tt), cy + sy * (r + w) * _m.sin(tt)))
                for k in range(n + 1):
                    tt = t1 - (t1 - t0) * k / n
                    pts.append((cx + sx * r * _m.cos(tt), cy + sy * r * _m.sin(tt)))
                pts = [(min(max(px, x0 + 1), x1 - 1), min(max(py, y0 + 1), y1 - 1)) for px, py in pts]
                cxx = sum(p[0] for p in pts) / len(pts); cyy = sum(p[1] for p in pts) / len(pts)
                if _ok(cxx, cyy, w):
                    holes.append(pts)
            r += passo

    elif nome == "Ondas":
        linhas = max(int(H / (W / 7.5)), 4)
        passo = H / linhas
        mx = W * 0.015
        for k in range(linhas):
            yb = y0 + (k + 0.5) * passo
            f = rnd.uniform(1.1, 2.1); fase = rnd.uniform(0, 6.28)
            f2 = rnd.uniform(0.8, 1.6); fase2 = rnd.uniform(0, 6.28)
            amp = passo * 0.20
            th0 = passo * 0.58
            topo = []; base = []
            n = 40
            for s in range(n + 1):
                xx = x0 + mx + (W - 2 * mx) * s / n
                yy = yb + amp * _m.sin(2 * _m.pi * f * s / n + fase)
                tt = th0 * (0.42 + 0.58 * (0.5 + 0.5 * _m.sin(2 * _m.pi * f2 * s / n + fase2)))
                topo.append((xx, min(yy + tt / 2, y1 - 1)))
                base.append((xx, max(yy - tt / 2, y0 + 1)))
            holes.append(topo + base[::-1])

    elif nome == "Cacos":
        ny = 3
        nx = max(int(W / (H / ny) * 0.9), 4)
        jit = min(W / nx, H / ny) * 0.30
        P = {}
        for iy in range(ny + 1):
            for ix in range(nx + 1):
                px = x0 + ix * W / nx; py = y0 + iy * H / ny
                jx = 0.0 if ix in (0, nx) else rnd.uniform(-jit, jit)
                jy = 0.0 if iy in (0, ny) else rnd.uniform(-jit, jit)
                P[(ix, iy)] = (px + jx, py + jy)
        for iy in range(ny):
            for ix in range(nx):
                a = P[(ix, iy)]; b = P[(ix + 1, iy)]
                c = P[(ix + 1, iy + 1)]; d = P[(ix, iy + 1)]
                tris = [(a, b, c), (a, c, d)] if rnd.random() < 0.5 else [(a, b, d), (b, c, d)]
                for tri in tris:
                    gx = sum(p[0] for p in tri) / 3.0; gy = sum(p[1] for p in tri) / 3.0
                    kf = 0.80
                    sh = [(gx + (p[0] - gx) * kf, gy + (p[1] - gy) * kf) for p in tri]
                    if _ok(gx, gy, max(abs(p[0] - gx) + abs(p[1] - gy) for p in tri) * 0.5):
                        holes.append(sh)

    elif nome == "Bauhaus":
        cell = max(W / 3.0, 24.0)
        nx = max(int(W // cell), 2); ny = max(int(H // cell), 1)
        ox = x0 + (W - nx * cell) / 2.0; oy = y0 + (H - ny * cell) / 2.0
        for iy in range(ny):
            for ix in range(nx):
                cx = ox + (ix + 0.5) * cell; cy = oy + (iy + 0.5) * cell
                r = cell * 0.40
                if not _ok(cx, cy, r):
                    continue
                mot = rnd.choice(["circ", "meia", "quarto", "listras", "circ", "meia"])
                if mot == "circ":
                    holes.append([(cx + r * _m.cos(2 * _m.pi * k / 28),
                                   cy + r * _m.sin(2 * _m.pi * k / 28)) for k in range(28)])
                elif mot == "meia":
                    a0 = rnd.choice([0.0, _m.pi / 2, _m.pi, 3 * _m.pi / 2])
                    pts = [(cx + r * _m.cos(a0 + _m.pi * k / 16),
                            cy + r * _m.sin(a0 + _m.pi * k / 16)) for k in range(17)]
                    holes.append(pts)
                elif mot == "quarto":
                    a0 = rnd.choice([0.0, _m.pi / 2, _m.pi, 3 * _m.pi / 2])
                    pts = [(cx, cy)] + [(cx + r * 1.12 * _m.cos(a0 + (_m.pi / 2) * k / 10),
                                         cy + r * 1.12 * _m.sin(a0 + (_m.pi / 2) * k / 10)) for k in range(11)]
                    holes.append(pts)
                else:
                    nl = 4; hh = (2 * r) / (2 * nl - 1)
                    for k in range(nl):
                        yy = cy - r + (2 * k) * hh
                        holes.append([(cx - r, yy), (cx + r, yy), (cx + r, yy + hh), (cx - r, yy + hh)])

    elif nome == "Círculos":
        cell = max(W / 7.0, 12.0)
        ny = max(int(H // (cell * 0.9)), 2)
        for iy in range(ny):
            cy = y0 + (iy + 0.5) * (H / ny)
            desl = (cell / 2.0) if iy % 2 else 0.0
            nx = int((W - desl) // cell)
            for ix in range(nx):
                cx = x0 + desl + (ix + 0.5) * cell
                r = cell * (0.36 if (ix + iy) % 2 else 0.24)
                if cx - r < x0 or cx + r > x1 or cy - r < y0 or cy + r > y1:
                    continue
                if not _ok(cx, cy, r):
                    continue
                holes.append([(cx + r * _m.cos(2 * _m.pi * k / 22),
                               cy + r * _m.sin(2 * _m.pi * k / 22)) for k in range(22)])

    elif nome == "Colmeia":
        rh = max(W / 11.0, 8.0)
        dx = rh * 1.86; dy = rh * 1.60
        ny = max(int(H // dy), 2)
        for iy in range(ny):
            cy = y0 + rh + iy * dy
            desl = (dx / 2.0) if iy % 2 else 0.0
            nx = int((W - desl) // dx)
            for ix in range(nx):
                cx = x0 + rh * 1.1 + desl + ix * dx
                if cx + rh > x1 or cy + rh > y1 or cy - rh < y0:
                    continue
                if not _ok(cx, cy, rh):
                    continue
                holes.append([(cx + rh * 0.92 * _m.cos(_m.pi / 6 + _m.pi * k / 3),
                               cy + rh * 0.92 * _m.sin(_m.pi / 6 + _m.pi * k / 3)) for k in range(6)])

    elif nome == "Ripas":
        passo = max(W / 8.0, 12.0); wl = passo * 0.46
        d0 = -(H + W)
        while d0 < (H + W):
            quad = [(x0 + d0, y0 - 5), (x0 + d0 + wl, y0 - 5),
                    (x0 + d0 + wl + H + 10, y1 + 5), (x0 + d0 + H + 10, y1 + 5)]
            c = _clip_rect(quad, x0, y0, x1, y1)
            if len(c) >= 3:
                gx = sum(p[0] for p in c) / len(c); gy = sum(p[1] for p in c) / len(c)
                if _ok(gx, gy, wl):
                    holes.append(c)
            d0 += passo

    elif nome == "Chevrons":
        linhas = max(int(H / (W / 5.0)), 3)
        passo = H / linhas; th = passo * 0.42; queda = passo * 0.8
        for k in range(linhas + 1):
            yb = y1 - k * passo
            topo = [(x0, yb), ((x0 + x1) / 2, yb - queda), (x1, yb)]
            base = [(x1, yb - th), ((x0 + x1) / 2, yb - queda - th), (x0, yb - th)]
            c = _clip_rect(topo + base, x0, y0, x1, y1)
            if len(c) >= 3:
                holes.append(c)

    elif nome == "Folhas":
        cell = max(W / 5.0, 18.0)
        ny = max(int(H // (cell * 0.8)), 2)
        for iy in range(ny):
            cy = y0 + (iy + 0.5) * (H / ny)
            desl = (cell / 2.0) if iy % 2 else 0.0
            nx = int((W - desl) // cell)
            for ix in range(nx):
                cx = x0 + desl + (ix + 0.5) * cell
                Lf = cell * 0.82; wf = cell * 0.26
                ang = _m.radians(35 if (ix + iy) % 2 else -35)
                ca, sa = _m.cos(ang), _m.sin(ang)
                pts = []
                for k in range(13):
                    tt = _m.pi * k / 12
                    pts.append((Lf / 2 * _m.cos(tt), wf * _m.sin(tt)))
                for k in range(13):
                    tt = _m.pi * k / 12
                    pts.append((-Lf / 2 * _m.cos(tt), -wf * _m.sin(tt)))
                pts = [(cx + px * ca - py * sa, cy + px * sa + py * ca) for px, py in pts]
                if any(px < x0 or px > x1 or py < y0 or py > y1 for px, py in pts):
                    continue
                if not _ok(cx, cy, Lf / 2):
                    continue
                holes.append(pts)

    elif nome == "Raios":
        cx = (x0 + x1) / 2.0
        cima = (y1 > 0)
        cy = (y0 - H * 0.35) if cima else (y1 + H * 0.35)
        n = 9
        for k in range(n):
            ang = _m.pi * (0.18 + 0.64 * k / (n - 1))
            dx_, dy_ = _m.cos(ang), (_m.sin(ang) if cima else -_m.sin(ang))
            r0, r1 = H * 0.42, H * 1.9
            w0, w1 = W * 0.012, W * 0.052
            px, py = -dy_, dx_
            quad = [(cx + dx_ * r0 - px * w0, cy + dy_ * r0 - py * w0),
                    (cx + dx_ * r0 + px * w0, cy + dy_ * r0 + py * w0),
                    (cx + dx_ * r1 + px * w1, cy + dy_ * r1 + py * w1),
                    (cx + dx_ * r1 - px * w1, cy + dy_ * r1 - py * w1)]
            c = _clip_rect(quad, x0, y0, x1, y1)
            if len(c) >= 3:
                gx = sum(p[0] for p in c) / len(c); gy = sum(p[1] for p in c) / len(c)
                if _ok(gx, gy, w1):
                    holes.append(c)

    elif nome == "Vitral":
        ny = 3
        nx = max(int(W / (H / ny) * 0.9), 4)
        jit = min(W / nx, H / ny) * 0.32
        P = {}
        for iy in range(ny + 1):
            for ix in range(nx + 1):
                px = x0 + ix * W / nx; py = y0 + iy * H / ny
                jx = 0.0 if ix in (0, nx) else rnd.uniform(-jit, jit)
                jy = 0.0 if iy in (0, ny) else rnd.uniform(-jit, jit)
                P[(ix, iy)] = (px + jx, py + jy)
        for iy in range(ny):
            for ix in range(nx):
                quad = [P[(ix, iy)], P[(ix + 1, iy)], P[(ix + 1, iy + 1)], P[(ix, iy + 1)]]
                gx = sum(p[0] for p in quad) / 4.0; gy = sum(p[1] for p in quad) / 4.0
                kf = 0.82
                sh = [(gx + (p[0] - gx) * kf, gy + (p[1] - gy) * kf) for p in quad]
                if _ok(gx, gy, max(abs(p[0] - gx) + abs(p[1] - gy) for p in quad) * 0.5):
                    holes.append(sh)

    elif nome == "Ladrilho":
        cell = max(W / 8.0, 12.0)
        nx = int(W // cell); ny = max(int(H // cell), 2)
        ox = x0 + (W - nx * cell) / 2.0; oy = y0 + (H - ny * cell) / 2.0
        for iy in range(ny):
            for ix in range(nx):
                cx = ox + (ix + 0.5) * cell; cy = oy + (iy + 0.5) * cell
                if not _ok(cx, cy, cell * 0.4):
                    continue
                if (ix + iy) % 2 == 0:
                    s = cell * 0.36
                    holes.append([(cx - s, cy - s), (cx + s, cy - s), (cx + s, cy + s), (cx - s, cy + s)])
                else:
                    r = cell * 0.20
                    holes.append([(cx + r * _m.cos(2 * _m.pi * k / 18),
                                   cy + r * _m.sin(2 * _m.pi * k / 18)) for k in range(18)])

    elif nome == "Bambu":
        pitch = max(W / 12.0, 9.0)
        nx = int(W // pitch)
        ox = x0 + (W - nx * pitch) / 2.0
        for ix in range(nx):
            cx = ox + (ix + 0.5) * pitch
            wl = pitch * rnd.uniform(0.34, 0.5)
            yy = y0 + rnd.uniform(0, H * 0.14)
            while yy < y1 - 6:
                seg = rnd.uniform(H * 0.16, H * 0.42)
                fim = min(yy + seg, y1 - 1)
                if fim - yy > 6 and _ok(cx, (yy + fim) / 2, wl):
                    holes.append([(cx - wl / 2, yy), (cx + wl / 2, yy),
                                  (cx + wl / 2, fim), (cx - wl / 2, fim)])
                yy = fim + rnd.uniform(H * 0.07, H * 0.16)
    return holes


def placa_residencial_prims(L, W, numero, texto="CASA", layout="totem", modelo="Cacos",
                            cor=None, n_furos=0, d_furo=5.0, raio=6.0, dobras=False,
                            comp=0.0, esp=0.0, name="placa", fonte=None, ponte=0.0):
    """Placa residencial estilo TOTEM: faixas de padrao vazado no topo e na base,
    miolo calmo com palavra fina espacejada, regua e numero grande em tipografia
    leve. Padroes autorais parametricos: Cacos / Ondas / Arcos / Pixels / Trelica."""
    C = float(L) + comp; H = float(W) + comp
    r_out = max(min(float(raio or 0), min(C, H) / 2 - 0.1), 0.0)
    outer = ("poly", _rrect_pts(C, H, r_out) if r_out > 0 else _rect_pts(C, H))
    holes = []; deco = []
    numero = str(numero).strip()
    palavra = str(texto or "").strip()
    fino = fonte or FONTES_PLACA.get("Fina (Poppins Light)")

    bm = max(C * 0.045, 4.0)                       # respiro lateral das faixas
    MARGEM_TB = 16.0                               # borda macica topo/base (sem perfurar)
    vertical = H >= C * 1.15
    fb = (0.26 if vertical else 0.30)              # fracao de altura de cada faixa
    band_h = max(H * fb, MARGEM_TB + 40.0)

    # furos de fixacao frontais — abaixo da margem de 16 mm; reservam espaco no padrao
    avoid = []
    furos_c = []
    if int(n_furos or 0) > 0 and d_furo and d_furo > 0:
        rr = float(d_furo) / 2.0
        fy = H / 2 - MARGEM_TB - rr * 2.4
        if int(n_furos) >= 3:
            fx = C / 2 - max(bm + rr * 2.4, 12.0)
            furos_c = [(-fx, fy), (fx, fy), (fx, -fy), (-fx, -fy)][: int(n_furos)]
        else:
            furos_c = [(0.0, fy), (0.0, -fy)][: max(int(n_furos), 1)]
        avoid = [(fxx, fyy, rr * 3.2) for fxx, fyy in furos_c]

    sem_padrao = (modelo or "").lower().startswith("sem")
    if not sem_padrao:
        seed = (sum(ord(c) for c in (numero + palavra)) % 97) + 11
        holes += [("poly", p) for p in _faixa_padrao(
            modelo, -C / 2 + bm, C / 2 - bm, H / 2 - band_h, H / 2 - MARGEM_TB, seed=seed, avoid=avoid)]
        holes += [("poly", p) for p in _faixa_padrao(
            modelo, -C / 2 + bm, C / 2 - bm, -H / 2 + MARGEM_TB, -H / 2 + band_h, seed=seed + 1, avoid=avoid)]
        z_top = H / 2 - band_h
        z_bot = -H / 2 + band_h
    else:
        z_top = H / 2 - MARGEM_TB - bm
        z_bot = -H / 2 + MARGEM_TB + bm
    zona = z_top - z_bot

    def coloca(s, cy, alvo_h, max_w, tracking=0.0, caixa=False, fnt=None, com_ponte=True, ponte_w=None):
        polys, tw, th = _texto_polys(s, fonte=(fnt or fino), tracking=tracking, caixa_alta=caixa)
        if not polys:
            return 0.0
        sc = min(alvo_h / th if th else 1.0, max_w / tw if tw else 1.0)
        xs = [p[0] for c in polys for p in c]; ys = [p[1] for c in polys for p in c]
        cxt = (max(xs) + min(xs)) / 2.0; cyt = (max(ys) + min(ys)) / 2.0
        out = [[((x - cxt) * sc + 0.0, (y - cyt) * sc + cy) for x, y in c] for c in polys]
        if com_ponte and ponte and ponte > 0:
            out = _aplicar_pontes(out, float(ponte_w if ponte_w else ponte), topo=True)
        for pp in out:
            holes.append(("poly", pp))
        return th * sc

    lw = C * 0.64
    h_pal = min(zona * 0.16, C * 0.135) if palavra else 0.0
    h_rg = max(C * 0.007, 1.5) if palavra else 0.0
    h_num = min(zona * 0.46, C * 0.56)
    g1 = zona * 0.05; g2 = zona * 0.07
    total = h_pal + (g1 + h_rg + g2 if palavra else 0.0) + h_num
    y = (z_top + z_bot) / 2 + total / 2
    if palavra:
        # palavra com ponte fina, proporcional ao corpo da letra
        p_pal = min(float(ponte or 0), max(h_pal * 0.16, 1.2)) if ponte else 0.0
        coloca(palavra, y - h_pal / 2, h_pal, lw, tracking=0.62, caixa=True,
               com_ponte=True, ponte_w=p_pal)
        y -= h_pal + g1
        holes.append(("poly", _rect_pts(lw, h_rg, 0, y - h_rg / 2)))
        y -= h_rg + g2
    coloca(numero, y - h_num / 2, h_num, C * 0.76, tracking=0.045)

    for fx, fy in furos_c:
        holes.append(("circle", fx, fy, float(d_furo) / 2.0))

    prims = {"outer": outer, "holes": holes, "deco": deco, "bbox": (C, H),
             "area": C * H, "name": name, "esp": float(esp)}
    if dobras:
        ab = max(C * 0.075, 15.0)
        prims["dobras"] = [("line", [(-C / 2 + ab, -H / 2), (-C / 2 + ab, H / 2)]),
                           ("line", [(C / 2 - ab, -H / 2), (C / 2 - ab, H / 2)])]
    if cor:
        prims["cor"] = cor
    return prims


def _luminancia(hexc):
    try:
        h = str(hexc).lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    except Exception:
        return 0.2


def placa_mock_png(prims, fundo="#eef0f3", parede="#f7f8fa"):
    """Prévia REALISTA da placa: chapa preenchida na cor do acabamento, recortes
    vazados mostrando a parede atrás, frisos gravados e sombra suave."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch, Circle
    cor = prims.get("cor") or "#3b3b3b"
    lum = _luminancia(cor)
    grava = (1, 1, 1, 0.5) if lum < 0.55 else (0, 0, 0, 0.4)
    borda = "#0d0d0d" if lum > 0.5 else "#000000"
    C, H = prims["bbox"]
    fig, ax = plt.subplots(figsize=(7.2, 7.2 * min(H / C, 1.4) if C >= H else 7.2 * H / C))
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_facecolor(parede); fig.patch.set_facecolor(parede)
    # sombra
    verts = []; codes = []

    def _area_sinal(pts):
        s = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % len(pts)]
            s += x1 * y2 - x2 * y1
        return s

    def add_ring(pts, ccw=True):
        pts = list(pts)
        if (_area_sinal(pts) > 0) != ccw:
            pts = pts[::-1]
        verts.extend(pts + [pts[0]])
        codes.extend([Path.MOVETO] + [Path.LINETO] * (len(pts) - 1) + [Path.CLOSEPOLY])

    outer_pts = prims["outer"][1]
    sombra = Path([(x + C * 0.012, y - C * 0.016) for x, y in outer_pts] + [outer_pts[0]],
                  [Path.MOVETO] + [Path.LINETO] * (len(outer_pts) - 1) + [Path.CLOSEPOLY])
    ax.add_patch(PathPatch(sombra, facecolor=(0, 0, 0, 0.18), edgecolor="none", zorder=1))
    add_ring(outer_pts, ccw=True)
    circ = []
    for h in prims["holes"]:
        if h[0] == "poly":
            add_ring(h[1], ccw=False)
        elif h[0] == "circle":
            circ.append(h)
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=cor,
                           edgecolor=borda, lw=1.0, zorder=2))
    # textura tipo corten: gradiente vertical + ruído, recortado na chapa
    try:
        import numpy as _np
        from matplotlib.colors import to_rgb
        base = _np.array(to_rgb(cor))
        ny_, nx_ = 220, 160
        gy = _np.linspace(1.14, 0.82, ny_)[:, None]
        rndim = _np.random.default_rng(7).normal(0, 0.05, (ny_, nx_))
        blot = _np.random.default_rng(3).normal(0, 1, (ny_ // 8, nx_ // 8))
        blot = _np.kron(blot, _np.ones((8, 8)))[:ny_, :nx_] * 0.045
        fator = _np.clip(gy + rndim + blot, 0.62, 1.32)
        img = _np.clip(base[None, None, :] * fator[:, :, None], 0, 1)
        im = ax.imshow(img, extent=(-C / 2, C / 2, -H / 2, H / 2), origin="lower",
                       zorder=2.5, interpolation="bilinear")
        im.set_clip_path(PathPatch(Path(verts, codes), transform=ax.transData))
    except Exception:
        pass
    # furos de fixacao (parafuso)
    for _, hx, hy, hr in circ:
        ax.add_patch(Circle((hx, hy), hr, facecolor=parede, edgecolor=(0, 0, 0, 0.35),
                            lw=0.8, zorder=3))
    # gravacao (frisos/reguas)
    for d in prims.get("deco", []):
        pts = d[1]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "-", color=grava,
                lw=1.4, zorder=4, solid_capstyle="round")
    m = max(C, H) * 0.09
    ax.set_xlim(-C / 2 - m, C / 2 + m); ax.set_ylim(-H / 2 - m, H / 2 + m)
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return b.getvalue()


def copiar_dxf(dxf_bytes):
    """Recopia um DXF enviado pelo usuário, idêntico (mesma estrutura), validando que abre."""
    doc = ezdxf.read(io.StringIO(dxf_bytes.decode("utf-8", "ignore")))
    msp = doc.modelspace()
    n = len(list(msp))
    # bbox aproximado p/ preview/nesting
    xs, ys = [], []
    for e in msp:
        try:
            if e.dxftype() == "LINE":
                xs += [e.dxf.start.x, e.dxf.end.x]; ys += [e.dxf.start.y, e.dxf.end.y]
            elif e.dxftype() == "CIRCLE":
                xs += [e.dxf.center.x - e.dxf.radius, e.dxf.center.x + e.dxf.radius]
                ys += [e.dxf.center.y - e.dxf.radius, e.dxf.center.y + e.dxf.radius]
            elif e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                for p in e.get_points("xy") if e.dxftype() == "LWPOLYLINE" else [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]:
                    xs.append(p[0]); ys.append(p[1])
        except Exception:
            pass
    bbox = ((max(xs) - min(xs)) if xs else 0.0, (max(ys) - min(ys)) if ys else 0.0)
    return {"n_entidades": n, "bbox": bbox}


_NLADOS = {"triang": 3, "triâng": 3, "quadr": 4, "pentag": 5, "pentág": 5, "hexag": 6, "hexág": 6,
           "sextav": 6, "heptag": 7, "octog": 8, "octóg": 8, "oitav": 8}


def parse_descricao(texto):
    """Interpreta uma descrição livre. Reconhece forma (retângulo, disco, anel/arruela,
    polígono), dimensões, furo central e padrão de furação (linha, círculo/PCD)."""
    t = (texto or "").lower().replace(",", ".")
    out = {"equi": "equidist" in t}

    # ---- caso especial: chapa perfurada (grade de recortes retangulares)
    metros = "metro" in t
    dims_all = re.findall(r"(\d+\.?\d*)\s*(?:mm|m|metros?)?\s*(?:x|×)\s*(\d+\.?\d*)", t)
    if any(w in t for w in ("recorte", "perfurad", "vazad", "perfura")) and dims_all:
        out["forma"] = "retangulo"
        pw, ph = float(dims_all[0][0]), float(dims_all[0][1])
        if metros:
            out["unidade"] = "metros"; pw *= 1000.0; ph *= 1000.0
        out["comprimento"], out["largura"] = pw, ph
        if len(dims_all) >= 2:
            a, b = float(dims_all[1][0]), float(dims_all[1][1])
        else:
            a, b = 100.0, 50.0
        mo = re.search(r"sentido\s+d[eo]\s+(\d+\.?\d*)\s*mm?\s+no\s+comprimento", t)
        if mo:
            cdim = float(mo.group(1)); rcw, rch = cdim, (b if abs(a - cdim) < 1e-6 else a)
        else:
            rcw, rch = max(a, b), min(a, b)
        gp = (re.search(r"(?:distante[s]?|espa[çc]\w*|afastad\w*)\s*(?:em|de|por)?\s*(\d+\.?\d*)\s*mm", t)
              or re.search(r"(\d+\.?\d*)\s*mm\s+entre", t))
        out["recorte"] = {"w": rcw, "h": rch, "gap": float(gp.group(1)) if gp else 10.0}
        return out

    nums = [float(x) for x in re.findall(r"\d+\.?\d*", t)]
    dim2 = re.search(r"(\d+\.?\d*)\s*(?:mm)?\s*(?:x|×|por)\s*(\d+\.?\d*)", t)
    mn = re.search(r"(\d+)\s*furos?", t)
    n_furos = int(mn.group(1)) if mn else 0
    # diâmetro do furo (perto de 'furo' ou após 'diâmetro/ø')
    d_furo = None
    md = re.search(r"furos?[^\d]*(?:de\s*)?(?:di[aâ]metro|ø|⌀)?\s*(?:de\s*)?(\d+\.?\d*)\s*mm", t)
    if md:
        d_furo = float(md.group(1))
    else:
        md2 = re.search(r"(?:di[aâ]metro|diam\.?|ø|⌀)\s*(?:de\s*)?(\d+\.?\d*)", t)
        if md2 and n_furos:
            d_furo = float(md2.group(1))
    # PCD / círculo de furação
    pcd = None
    mp = re.search(r"(?:c[ií]rculo(?:\s*de\s*fura[çc][aã]o)?|pcd|furac[aã]o)\s*(?:de\s*)?(\d+\.?\d*)", t)
    if mp:
        pcd = float(mp.group(1))

    nl = next((v for k, v in _NLADOS.items() if k in t), None)
    if any(w in t for w in ("arruela", "anel", "aro", "argola", "coroa", "virola", "gola")):
        out["forma"] = "anel"
        ds = sorted({x for x in nums}, reverse=True)
        if len(ds) >= 2:
            out["diametro"], out["diametro_int"] = ds[0], ds[1]
    elif nl or any(w in t for w in ("pol[íi]gono", "polig")):
        out["forma"] = "poligono"; out["lados"] = nl or 6
        mfaces = re.search(r"(?:entre\s*faces|chave|across)\s*(?:de\s*)?(\d+\.?\d*)", t)
        if mfaces:
            out["medida"] = float(mfaces.group(1)); out["medida_tipo"] = "entre_faces"
        elif nums:
            out["medida"] = max(nums); out["medida_tipo"] = "entre_faces"
    elif any(w in t for w in ("disco", "c[íi]rculo", "circulo", "redond", "bolacha",
                              "tampa", "rodela", "tampão", "tampao", "flange cega")) and not dim2:
        out["forma"] = "disco"
        cand = [x for x in nums if d_furo is None or abs(x - d_furo) > 1e-6]
        if cand:
            out["diametro"] = max(cand)
    else:
        out["forma"] = "retangulo"
        if dim2:
            out["comprimento"] = float(dim2.group(1)); out["largura"] = float(dim2.group(2))

    if n_furos:
        padrao = "circulo" if (pcd or "círculo" in t or "circulo" in t or "pcd" in t) else "linha"
        fr = {"padrao": padrao, "n": n_furos, "d": d_furo or 6.0}
        if pcd:
            fr["pcd"] = pcd
        out["furos"] = fr

    # furo central / no centro (não confundir com o furo interno do anel)
    if out.get("forma") != "anel":
        mc = re.search(r"furo\s*(?:central|no\s*centro)\s*(?:de\s*)?(?:di[aâ]metro\s*)?(?:de\s*)?(\d+\.?\d*)", t)
        if mc:
            out["furo_central"] = float(mc.group(1))
    return out
