"""Gerador de ralos (grelha) — duas peças compatíveis para montagem:

 • SUPERIOR: tampa aparente (L × W) com malha ortogonal de oblongos 25×12 mm
   (orientados no comprimento) + 1 oblongo central horizontal 33×7 mm.
 • INFERIOR: chapa de apoio (encaixe em trilho) com a MESMA malha de oblongos
   nas MESMAS coordenadas, contorno externo reduzido + 1 furo circular Ø6,3 mm
   deslocado 13,3 mm para a esquerda do eixo central.

Regras FIXAS (nunca mudam):
  - oblongo padrão .............. 25 × 12 mm
  - espaço livre longitudinal ... 30 mm  -> passo entre colunas = 55 mm
  - margem lateral superior ..... >= 65 mm (borda da chapa -> borda do furo), iguais
  - margem topo/base superior ... 23 mm (fixa)
  - gap entre fileiras .......... > 5 mm e < 25 mm (uniforme). Usa-se o MENOR número
    de fileiras cujo gap fique < 25 mm (gap mais folgado), como no padrão real.
  - oblongo central superior .... 33 × 7 mm (centralizado)
  - margem lateral inferior ..... 30 mm (borda do furo -> borda da chapa)
  - margem topo/base inferior ... 12 mm
  - furo circular inferior ...... Ø6,3 mm, centrado na largura, 13,3 mm à esquerda

DXF: os oblongos são emitidos como ARCO + LINHA reais (idêntico ao padrão),
contorno como LWPOLYLINE e o furo como CIRCLE.
"""
import io
import math
import ezdxf

# ---- constantes fixas (mm) -------------------------------------------------
OBL_C = 25.0
OBL_W = 12.0
GAP_LONG = 30.0
PASSO_COL = OBL_C + GAP_LONG          # 55
MARG_LAT_SUP = 65.0
MARG_TB_SUP = 23.0
GAP_ROW_MIN = 5.0
GAP_ROW_MAX = 25.0
OBL_CENTRAL_C = 33.0
OBL_CENTRAL_W = 7.0
MARG_LAT_INF = 30.0
MARG_TB_INF = 12.0
FURO_INF_D = 6.3
FURO_INF_DX = -13.3
CLEAR_CENTRAL = 3.0

INOX_DENS = 7.93e-3


# ---- geometria -------------------------------------------------------------
def _slot_pts(cx, cy, comp, larg, ang=0.0, seg=20):
    """Oblongo (stadium) como polígono fechado — usado só para a PRÉVIA."""
    r = larg / 2.0
    L = max(comp - larg, 0.0)
    a = math.radians(ang)
    loc = []
    for i in range(seg + 1):
        th = -math.pi / 2 + math.pi * i / seg
        loc.append((L / 2 + r * math.cos(th), r * math.sin(th)))
    for i in range(seg + 1):
        th = math.pi / 2 + math.pi * i / seg
        loc.append((-L / 2 + r * math.cos(th), r * math.sin(th)))
    return [(cx + x * math.cos(a) - y * math.sin(a),
             cy + x * math.sin(a) + y * math.cos(a)) for x, y in loc]


def _rect_pts(w, h, cx=0.0, cy=0.0):
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
            (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def _area_oblongo(comp, larg):
    r = larg / 2.0
    return max(comp - larg, 0.0) * larg + math.pi * r * r


# ---- cálculo da malha ------------------------------------------------------
def calcular_colunas(L):
    span_max = L - 2.0 * (MARG_LAT_SUP + OBL_C / 2.0)   # = L - 155
    if span_max < -1e-6:
        return 0, 0.0
    n = int(span_max // PASSO_COL) + 1
    span = (n - 1) * PASSO_COL
    marg_centro = (L - span) / 2.0
    return n, marg_centro


def calcular_fileiras(W):
    """MENOR número de fileiras cujo gap fique < 25 mm (e > 5 mm), uniforme."""
    span = W - 2.0 * (MARG_TB_SUP + OBL_W / 2.0)        # = W - 58
    if span < 1e-6:
        return 1, 0.0
    for n in range(2, 2000):
        pitch = span / (n - 1)
        gap = pitch - OBL_W
        if gap < GAP_ROW_MAX:
            if gap > GAP_ROW_MIN:
                return n, pitch
            return 1, 0.0
    return 1, 0.0


def _malha_oblongos(L, W):
    n_c, marg_c = calcular_colunas(L)
    n_r, pitch_r = calcular_fileiras(W)
    if n_c < 1 or n_r < 1:
        raise ValueError("Dimensões pequenas demais para a malha de furos.")

    span_c = (n_c - 1) * PASSO_COL
    xs = [(-span_c / 2.0 + k * PASSO_COL) for k in range(n_c)]

    if n_r == 1:
        ys = [0.0]
        gap_r = 0.0
    else:
        y_top = W / 2.0 - (MARG_TB_SUP + OBL_W / 2.0)
        ys = [y_top - j * pitch_r for j in range(n_r)]
        gap_r = pitch_r - OBL_W

    hx = OBL_CENTRAL_C / 2.0 + OBL_C / 2.0 + CLEAR_CENTRAL
    hy = OBL_CENTRAL_W / 2.0 + OBL_W / 2.0 + CLEAR_CENTRAL
    centros = []
    removidos = 0
    for y in ys:
        for x in xs:
            if abs(x) < hx and abs(y) < hy:
                removidos += 1
                continue
            centros.append((x, y))
    info = {
        "n_colunas": n_c, "n_fileiras": n_r,
        "passo_coluna": PASSO_COL, "passo_fileira": (pitch_r if n_r > 1 else 0.0),
        "gap_fileira": gap_r, "margem_lateral_sup": marg_c - OBL_C / 2.0,
        "span_colunas": span_c, "ys": ys, "xs": xs, "removidos_centro": removidos,
        "n_oblongos_malha": len(centros),
    }
    return centros, info


# ---- geração das peças -----------------------------------------------------
def gerar(L, W, esp=1.5, nome="Ralo"):
    L = float(L); W = float(W)
    centros, info = _malha_oblongos(L, W)

    furos_malha = [("slot", x, y, OBL_C, OBL_W, 0.0) for (x, y) in centros]
    area_malha = len(centros) * _area_oblongo(OBL_C, OBL_W)

    holes_sup = list(furos_malha)
    holes_sup.append(("slot", 0.0, 0.0, OBL_CENTRAL_C, OBL_CENTRAL_W, 0.0))
    area_sup = L * W - area_malha - _area_oblongo(OBL_CENTRAL_C, OBL_CENTRAL_W)
    prims_sup = {
        "outer": ("poly", _rect_pts(L, W)), "holes": holes_sup, "deco": [], "dobras": [],
        "bbox": (L, W), "area": max(area_sup, 0.0),
        "name": f"{nome}_superior", "esp": float(esp),
    }

    L_inf = info["span_colunas"] + OBL_C + 2.0 * MARG_LAT_INF
    ys = info["ys"]
    y_ext = max(abs(y) for y in ys) if ys else 0.0
    W_inf = 2.0 * (y_ext + OBL_W / 2.0 + MARG_TB_INF)
    holes_inf = list(furos_malha)
    holes_inf.append(("circle", FURO_INF_DX, 0.0, FURO_INF_D / 2.0))
    area_inf = L_inf * W_inf - area_malha - math.pi * (FURO_INF_D / 2.0) ** 2
    prims_inf = {
        "outer": ("poly", _rect_pts(L_inf, W_inf)), "holes": holes_inf, "deco": [], "dobras": [],
        "bbox": (L_inf, W_inf), "area": max(area_inf, 0.0),
        "name": f"{nome}_inferior", "esp": float(esp),
    }

    info.update({
        "L": L, "W": W, "L_inferior": round(L_inf, 1), "W_inferior": round(W_inf, 1),
        "total_oblongos_sup": len(holes_sup), "total_oblongos_inf": len(furos_malha),
    })
    return {"sup": prims_sup, "inf": prims_inf, "info": info}


# ---- prévia (converte slots em polígonos p/ flanges.preview_png/pdf) -------
def preview_prims(prims):
    holes = []
    for h in prims["holes"]:
        if h[0] == "slot":
            _, cx, cy, comp, larg, ang = h
            holes.append(("poly", _slot_pts(cx, cy, comp, larg, ang)))
        else:
            holes.append(h)
    p = dict(prims)
    p["holes"] = holes
    return p


# ---- DXF com ARCO + LINHA reais (idêntico ao padrão) -----------------------
def _emit_slot(msp, cx, cy, comp, larg, ang, layer):
    r = larg / 2.0
    half = max(comp - larg, 0.0) / 2.0
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)

    def rot(x, y):
        return (cx + x * ca - y * sa, cy + x * sa + y * ca)

    cR = rot(half, 0.0); cL = rot(-half, 0.0)
    pRt = rot(half, r); pRb = rot(half, -r)
    pLt = rot(-half, r); pLb = rot(-half, -r)
    msp.add_line(pLt, pRt, dxfattribs={"layer": layer})
    msp.add_line(pRb, pLb, dxfattribs={"layer": layer})
    msp.add_arc(cR, r, ang - 90, ang + 90, dxfattribs={"layer": layer})
    msp.add_arc(cL, r, ang + 90, ang + 270, dxfattribs={"layer": layer})


def dxf_bytes(items):
    doc = ezdxf.new(setup=True)
    doc.layers.add("CORTE", color=1)
    doc.layers.add("FUROS", color=5)
    msp = doc.modelspace()
    for prims, dx, dy in items:
        o = prims["outer"]
        if o[0] == "circle":
            msp.add_circle((o[1] + dx, o[2] + dy), o[3], dxfattribs={"layer": "CORTE"})
        else:
            msp.add_lwpolyline([(x + dx, y + dy) for x, y in o[1]], close=True,
                               dxfattribs={"layer": "CORTE"})
        for h in prims["holes"]:
            if h[0] == "slot":
                _, cx, cy, comp, larg, ang = h
                _emit_slot(msp, cx + dx, cy + dy, comp, larg, ang, "FUROS")
            elif h[0] == "circle":
                msp.add_circle((h[1] + dx, h[2] + dy), h[3], dxfattribs={"layer": "FUROS"})
            else:
                msp.add_lwpolyline([(x + dx, y + dy) for x, y in h[1]], close=True,
                                   dxfattribs={"layer": "FUROS"})
    s = io.StringIO(); doc.write(s)
    return s.getvalue().encode("utf-8")
