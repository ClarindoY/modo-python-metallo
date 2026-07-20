"""Bancada de inox — geração paramétrica conforme especificação de fabricação.

Vista superior. Frente = lado do operador; Fundo = oposto. O "Espelho Frontal" é
desenhado fisicamente no FUNDO da bancada (após dobra fica atrás).

Medidas do usuário = EXTERNAS (acabadas). As internas são calculadas:
  profundidade_interna = externa - 20 (dobra do espelho) quando há espelho no fundo;
  comprimento_interno  = externo  - 20 por lateral que tiver espelho.

Cada lado pode ter ESPELHO (dobra ↑: altura + dobra 20 + retorno 10) ou
ABA (dobra ↓: aba + retorno 10, com esquadria no retorno).

Relevo nos cantos (automático):
  - ESPELHO×ESPELHO  -> esquadria (canto preenchido + dobra 45°): topo contínuo.
  - ESPELHO×ABA      -> rasgo de alívio (fenda curta rente à dobra do espelho).
  - ABA×ABA          -> recorte de canto (vazio) + esquadria nos retornos.

Sem dependências externas além de ezdxf/matplotlib.
"""
import io
import math
import ezdxf

# -------- parâmetros padrão de fabricação (especificação) --------
ESPELHO_ALTURA = 100.0
DOBRA_ESP = 20.0
RETORNO_ESP = 10.0
ABA_PADRAO = 40.0
ABA_MIN = 10.0
RETORNO_ABA = 10.0
DIST_MIN_CUBAS = 40.0
RASGO_PADRAO = 50.0
INOX_DENS = 7.93e-6

EDGES = ("frente", "dir", "fundo", "esq")
LABELS = {"fundo": "Fundo", "frente": "Frente", "esq": "Esquerda", "dir": "Direita"}
OPCOES_ESPELHO = {
    "Espelho Frontal (fundo)": ("fundo",),
    "Frontal + Lateral Esquerda": ("fundo", "esq"),
    "Frontal + Lateral Direita": ("fundo", "dir"),
    "Frontal + Laterais Esq. e Dir.": ("fundo", "esq", "dir"),
    "Sem espelho (lisa)": (),
}


def _cuba_pts(cx, cy, w, h, raio):
    hw, hh = w / 2.0, h / 2.0
    r = max(min(raio, hw - 1, hh - 1), 0.0)
    if r <= 0:
        return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
    pts = []
    for (ox, oy, a0) in [(cx + hw - r, cy + hh - r, 0), (cx - hw + r, cy + hh - r, 90),
                         (cx - hw + r, cy - hh + r, 180), (cx + hw - r, cy - hh + r, 270)]:
        for k in range(9):
            a = math.radians(a0 + 90 * k / 8)
            pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return pts


def _interna(Cext, Pext, espset, dobra_fora=True):
    d = DOBRA_ESP if dobra_fora else 0.0
    W = Cext - d * (("esq" in espset) + ("dir" in espset))
    D = Pext - d * (1 if "fundo" in espset else 0)
    return W, D


def _outline(W, D, tipo, Le, c, rg=50.0):
    """Contorno externo (Python puro). Retorna (pontos, miters[], n_fendas).

    Cantos:
      aba×aba          -> recorte com chanfro 45° (c).
      espelho×espelho  -> esquadria 45° (linha de dobra diagonal).
      espelho×aba      -> FENDA de alívio no contorno (modelo do catálogo):
                          rasgo rg×1 mm rente à dobra do espelho, pelo lado da
                          tampa, com a ponta do espelho recuada 1 mm — permite
                          a dobra (espelho sobe, aba desce)."""
    FE = 1.0   # recuo da ponta do espelho em relação à dobra lateral
    FR = 1.0   # altura da fenda
    xPL, xPR, yPF, yPB = -W / 2, W / 2, -D / 2, D / 2
    yFo = yPF - Le["frente"]; yBo = yPB + Le["fundo"]
    xLo = xPL - Le["esq"]; xRo = xPR + Le["dir"]
    EE_TR = (tipo["fundo"] == "espelho" and tipo["dir"] == "espelho")
    EE_TL = (tipo["fundo"] == "espelho" and tipo["esq"] == "espelho")
    miters = []
    p = []
    fendas = 0

    def fenda(F, u, n, cheg_aba):
        """Sequência da fenda no canto: F=canto da tampa (cruzamento das dobras),
        u=direção ao longo da dobra do espelho (para dentro do vão), n=normal
        para dentro da tampa. cheg_aba=True quando o traçado chega pela aba."""
        nonlocal fendas
        fendas += 1
        seq = [F,
               (F[0] + n[0] * FR, F[1] + n[1] * FR),
               (F[0] + n[0] * FR + u[0] * (FE + rg), F[1] + n[1] * FR + u[1] * (FE + rg)),
               (F[0] + u[0] * (FE + rg), F[1] + u[1] * (FE + rg)),
               (F[0] + u[0] * FE, F[1] + u[1] * FE)]
        return seq if cheg_aba else seq[::-1]

    tF, tR, tB, tL = tipo["frente"], tipo["dir"], tipo["fundo"], tipo["esq"]

    # ---------------- frente (sempre aba): BL -> BR ----------------
    cfl = c if tL == "aba" else 0.0
    cfr = c if tR == "aba" else 0.0
    if tL == "espelho":
        # BL: esq espelho × frente aba — fenda vertical (chega pelo espelho)
        p += fenda((xPL, yPF), (0, 1), (1, 0), cheg_aba=False)
    p += [(xPL, yPF), (xPL, yFo + cfl), (xPL + cfl, yFo),
          (xPR - cfr, yFo), (xPR, yFo + cfr), (xPR, yPF)]
    # ---------------- direita: BR -> TR ----------------
    if tR == "espelho":
        # BR: dir espelho × frente aba — fenda (chega pela aba da frente)
        p += fenda((xPR, yPF), (0, 1), (-1, 0), cheg_aba=True)
        p += [(xRo, yPF + FE)]
        if EE_TR:
            # canto espelho×espelho: recorte em L com ORELHAS POSITIVAS 45° —
            # a borda externa de cada espelho segue reta pela zona de
            # dobra+retorno (30 mm) além do cruzamento e volta a 45° até a
            # linha de dobra da altura; fecha na dobra com pequena solda.
            _ch = DOBRA_ESP + RETORNO_ESP
            _alt_d = Le["dir"] - _ch
            _alt_b = Le["fundo"] - _ch
            p += [(xRo, yPB + _ch), (xPR + _alt_d, yPB), (xPR, yPB),
                  (xPR, yPB + _alt_b), (xPR + _ch, yBo)]
        else:
            # TR: dir espelho × fundo aba — fenda (chega pelo espelho)
            p += [(xRo, yPB - FE)]
            p += fenda((xPR, yPB), (0, -1), (-1, 0), cheg_aba=False)
            p += [(xRo2 := xPR, yPB)]  # ancora no fold p/ seguir o fundo
    else:
        cf2 = c if tF == "aba" else 0.0
        cb2 = c if tB == "aba" else 0.0
        p += [(xRo - cf2, yPF), (xRo, yPF + cf2)]
        if tB == "espelho":
            p += [(xRo, yPB)]     # aba sobe reta até a dobra do espelho (sem chanfro)
        else:
            p += [(xRo, yPB - cb2), (xRo - cb2, yPB)]
    # ---------------- fundo: TR -> TL ----------------
    if tB == "espelho":
        if not EE_TR:
            if tR == "aba":
                p += fenda((xPR, yPB), (-1, 0), (0, -1), cheg_aba=True)
            p += [(xPR - FE if tR == "aba" else xPR, yBo)]
        # (EE_TR: a orelha já entregou o traçado em (xPR + 30, yBo))
        topL = (xPL - (DOBRA_ESP + RETORNO_ESP)) if EE_TL else (xPL + (FE if tL == "aba" else 0.0))
        p += [(topL, yBo)]
        if EE_TL:
            _ch = DOBRA_ESP + RETORNO_ESP
            _alt_b = Le["fundo"] - _ch
            _alt_e = Le["esq"] - _ch
            p += [(xPL, yPB + _alt_b), (xPL, yPB),
                  (xPL - _alt_e, yPB), (xLo, yPB + _ch)]
        else:
            if tL == "aba":
                p += fenda((xPL, yPB), (1, 0), (0, -1), cheg_aba=False)
            p += [(xPL, yPB)]
    else:
        # fundo é ABA: banda completa com chanfros nos cantos aba×aba
        cbl = c if tL == "aba" else 0.0
        cbr = c if tR == "aba" else 0.0
        p += [(xPR, yPB), (xPR, yBo - cbr), (xPR - cbr, yBo),
              (xPL + cbl, yBo), (xPL, yBo - cbl), (xPL, yPB)]
    # ---------------- esquerda: TL -> BL ----------------
    if tL == "espelho":
        if EE_TL:
            pass  # recorte em L ja emitido no bloco do fundo
        else:
            # TL: esq espelho × fundo aba — fenda (chega pela aba do fundo)
            p += fenda((xPL, yPB), (0, -1), (1, 0), cheg_aba=True)
            p += [(xLo, yPB - FE)]
        p += [(xLo, yPF + FE)]
    else:
        cbl = c if tB == "aba" else 0.0
        cfl2 = c if tF == "aba" else 0.0
        if tB == "espelho":
            p += [(xLo, yPB)]     # reta até a dobra do espelho (sem chanfro)
        else:
            p += [(xLo + cbl, yPB), (xLo, yPB - cbl)]
        p += [(xLo, yPF + cfl2), (xLo + cfl2, yPF), (xPL, yPF)]

    out = []
    for q in p:
        if not out or abs(q[0] - out[-1][0]) > 1e-6 or abs(q[1] - out[-1][1]) > 1e-6:
            out.append((round(q[0], 3), round(q[1], 3)))
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-6 and abs(out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out, miters, fendas


def gerar(comprimento, profundidade, esp=1.2, espelhos=("fundo",),
          espelho_altura=ESPELHO_ALTURA, aba=ABA_PADRAO, rasgo=RASGO_PADRAO,
          dobra_fora=True, cubas=None, name="Bancada"):
    Cext = float(comprimento); Pext = float(profundidade)
    espset = set(e for e in (espelhos or ()) if e in ("fundo", "esq", "dir"))
    W, D = _interna(Cext, Pext, espset, dobra_fora)
    tipo = {s: ("espelho" if s in espset else "aba") for s in EDGES}
    Le = {s: (float(espelho_altura) + DOBRA_ESP + RETORNO_ESP if tipo[s] == "espelho"
              else float(aba) + RETORNO_ABA) for s in EDGES}
    cch = RETORNO_ABA

    rg = max(min(float(rasgo), min(W, D) / 2 - 1), 0.0)
    outer, miters, n_fendas = _outline(W, D, tipo, Le, cch, rg=rg)
    rasgos = []   # a fenda de alívio agora é parte do CONTORNO (modelo do catálogo)

    # dobras: base de cada lado + dobras internas do espelho/aba
    dobras = []
    ax = {"frente": ("h", -D / 2, -1), "fundo": ("h", D / 2, +1),
          "esq": ("v", -W / 2, -1), "dir": ("v", W / 2, +1)}
    for s in EDGES:
        if Le[s] <= 0:
            continue
        ori, base, sgn = ax[s]
        if ori == "h":
            dobras.append(("line", [(-W / 2, base), (W / 2, base)]))
            if tipo[s] == "espelho":
                dobras.append(("line", [(-W / 2, base + sgn * espelho_altura), (W / 2, base + sgn * espelho_altura)]))
                dobras.append(("line", [(-W / 2, base + sgn * (espelho_altura + DOBRA_ESP)), (W / 2, base + sgn * (espelho_altura + DOBRA_ESP))]))
            else:
                dobras.append(("line", [(-W / 2, base + sgn * float(aba)), (W / 2, base + sgn * float(aba))]))
        else:
            dobras.append(("line", [(base, -D / 2), (base, D / 2)]))
            if tipo[s] == "espelho":
                dobras.append(("line", [(base + sgn * espelho_altura, -D / 2), (base + sgn * espelho_altura, D / 2)]))
                dobras.append(("line", [(base + sgn * (espelho_altura + DOBRA_ESP), -D / 2), (base + sgn * (espelho_altura + DOBRA_ESP), D / 2)]))
            else:
                dobras.append(("line", [(base + sgn * float(aba), -D / 2), (base + sgn * float(aba), D / 2)]))
    # esquadria espelho×espelho é CORTE (o laser separa o canto em dois
    # triângulos que se encontram a 45° depois da dobra — junta pra solda)
    rasgos += miters

    # cubas
    holes = []; area_cubas = 0.0
    for cub in (cubas or []):
        cx, cy, cw, chh, raio = cub
        holes.append(("poly", _cuba_pts(cx, cy, cw, chh, raio)))
        area_cubas += cw * chh

    Wd = W + Le["esq"] + Le["dir"]; Hd = D + Le["frente"] + Le["fundo"]
    cdef = [("frente", "esq", (-W / 2, -D / 2)), ("frente", "dir", (W / 2, -D / 2)),
            ("fundo", "dir", (W / 2, D / 2)), ("fundo", "esq", (-W / 2, D / 2))]
    vazio = 0.0
    for ea, eb, pc in cdef:
        vazio += Le[ea] * Le[eb]
    area = Wd * Hd - vazio - area_cubas
    # medida FINAL montada: painel + avanço da dobra do espelho (só quando vira PRA FORA)
    ov = {s: (DOBRA_ESP if (tipo[s] == "espelho" and dobra_fora) else 0.0) for s in EDGES}
    final_C = W + ov["esq"] + ov["dir"]
    final_P = D + ov["fundo"] + ov["frente"]
    info = {
        "comprimento_ext": Cext, "profundidade_ext": Pext,
        "comprimento_int": round(W, 1), "profundidade_int": round(D, 1),
        "final_comprimento": round(final_C, 1), "final_profundidade": round(final_P, 1),
        "altura_montada": (float(espelho_altura) if espset else 0.0), "aba_desce": float(aba),
        "dobra_fora": bool(dobra_fora),
        "espelhos": sorted(espset), "espelho_altura": float(espelho_altura),
        "aba": float(aba), "rasgo": round(rg, 1), "cubas": len(cubas or []),
        "Wd": round(Wd, 1), "Hd": round(Hd, 1), "n_rasgos": int(n_fendas),
        "n_esquadrias": len(miters), "lisa": (len(espset) == 0), "tipo": tipo,
    }
    return {"outer": ("poly", outer), "holes": holes, "rasgos": rasgos, "dobras": dobras,
            "deco": [], "bbox": (Wd, Hd), "area": max(area, 0.0),
            "name": name, "esp": float(esp), "info": info}


def posicionar_cubas(W_int, D_int, cubas_spec, centralizado=True, distribuir=True, eixos=None):
    """Centros (cx,cy) das cubas no painel (centrado em 0,0), posicionadas pelo EIXO.
    Retorna (lista, erros). cy=0 (centro do painel na profundidade)."""
    n = len(cubas_spec)
    erros = []; cubas = []
    if n == 0:
        return cubas, erros
    if centralizado or distribuir:
        total = sum(c["comp"] for c in cubas_spec)
        folga = W_int - total
        if folga < DIST_MIN_CUBAS * (n + 1):
            erros.append(f"Sem espaço: folga {folga:.0f} mm < {DIST_MIN_CUBAS*(n+1):.0f} mm (mínimo entre/nas bordas).")
        gap = folga / (n + 1)
        x = -W_int / 2 + gap
        for c in cubas_spec:
            cubas.append((x + c["comp"] / 2, 0.0, c["comp"], c["larg"], c.get("raio", 0.0)))
            x += c["comp"] + gap
    else:
        eixos = eixos or []
        for i, c in enumerate(cubas_spec):
            ex = eixos[i] if i < len(eixos) else W_int / 2
            cubas.append((-W_int / 2 + ex, 0.0, c["comp"], c["larg"], c.get("raio", 0.0)))
    s = sorted(cubas, key=lambda k: k[0])
    for a, b in zip(s, s[1:]):
        gap = (b[0] - b[2] / 2) - (a[0] + a[2] / 2)
        if gap < DIST_MIN_CUBAS:
            erros.append(f"Recortes muito próximos: {gap:.0f} mm < {DIST_MIN_CUBAS:.0f} mm entre cubas.")
    for cx, cy, cw, chh, r in cubas:
        if cx - cw / 2 < -W_int / 2 - 1e-6 or cx + cw / 2 > W_int / 2 + 1e-6 or abs(cy) + chh / 2 > D_int / 2 + 1e-6:
            erros.append("Cuba ultrapassa os limites internos da bancada.")
            break
    return cubas, erros


def preview_prims(prims):
    """Prévia = exatamente o que é cortado (contorno + alívio + cuba). Sem linhas de dobra."""
    p = dict(prims)
    p["deco"] = list(prims.get("rasgos", [])) + list(prims.get("deco", []))
    p["dobras"] = []
    return p


def esquema_png(espelhos):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    espset = set(espelhos or ())
    fig, ax = plt.subplots(figsize=(3.4, 2.9)); ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(plt.Rectangle((-1, -0.7), 2, 1.4, fc="#f4f4f5", ec="#bbb", lw=1.2))
    ax.text(0, 0.05, "tampa", ha="center", va="center", color="#aaa", fontsize=9)
    ax.annotate("", xy=(0, -0.95), xytext=(0, -0.55), arrowprops=dict(arrowstyle="->", color="#bbb"))
    ax.text(0.06, -0.78, "operador", fontsize=6.5, color="#bbb", va="center")

    def bar(side, x, y):
        on = side in espset
        col = "#1565c0" if on else "#c2c2c2"; lw = 8 if on else 3.5
        ax.plot(x, y, color=col, lw=lw, solid_capstyle="butt")
    bar("fundo", [-1, 1], [0.7, 0.7]); bar("frente", [-1, 1], [-0.7, -0.7])
    bar("esq", [-1, -1], [-0.7, 0.7]); bar("dir", [1, 1], [-0.7, 0.7])

    def col(s):
        return "#1565c0" if s in espset else "#888"
    ax.text(0, 0.85, "Fundo (espelho frontal)", ha="center", fontsize=7.5, color=col("fundo"))
    ax.text(0, -0.86, "Frente", ha="center", va="top", fontsize=8, color=col("frente"))
    ax.text(-1.07, 0, "Esq.", ha="right", va="center", fontsize=8, rotation=90, color=col("esq"))
    ax.text(1.07, 0, "Dir.", ha="left", va="center", fontsize=8, rotation=90, color=col("dir"))
    ax.text(0, -1.16, "azul = espelho (dobra ↑)  ·  cinza = aba (dobra ↓)", ha="center", fontsize=7, color="#666")
    ax.set_xlim(-1.6, 1.6); ax.set_ylim(-1.4, 1.05)
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=120, bbox_inches="tight"); plt.close(fig)
    return b.getvalue()


def dxf_bytes(items):
    """DXF de CORTE apenas: contorno externo + rasgos de alívio (CORTE) e cubas (FUROS).
    NÃO inclui linhas de dobra — o laser corta somente o que está aqui."""
    doc = ezdxf.new(setup=True)
    doc.layers.add("CORTE", color=1); doc.layers.add("FUROS", color=5)
    msp = doc.modelspace()
    for prims, dx, dy in items:
        o = prims["outer"]
        msp.add_lwpolyline([(x + dx, y + dy) for x, y in o[1]], close=True, dxfattribs={"layer": "CORTE"})
        for r in prims.get("rasgos", []):
            msp.add_lwpolyline([(x + dx, y + dy) for x, y in r[1]], close=False, dxfattribs={"layer": "CORTE"})
        for h in prims["holes"]:
            msp.add_lwpolyline([(x + dx, y + dy) for x, y in h[1]], close=True, dxfattribs={"layer": "FUROS"})
    s = io.StringIO(); doc.write(s)
    return s.getvalue().encode("utf-8")


def imagem_3d(prims, elev=30, azim=-58):
    """Renderiza a peça DOBRADA em 3D (painel + espelhos pra cima + abas pra baixo
    + hem do espelho + retorno da aba + cubas). Retorna PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    info = prims["info"]
    W = float(info["comprimento_int"]); D = float(info["profundidade_int"])
    tipo = info["tipo"]; H = float(info["espelho_altura"]); A = float(info["aba"])
    dsign = 1 if info.get("dobra_fora", True) else -1
    faces = []; cols = []

    def face(pts, col):
        faces.append(pts); cols.append(col)

    face([(-W / 2, -D / 2, 0), (W / 2, -D / 2, 0), (W / 2, D / 2, 0), (-W / 2, D / 2, 0)], "#dedede")
    for side in EDGES:
        up = tipo[side] == "espelho"; ext = H if up else A; s = 1 if up else -1
        cwall = "#7ea9d4" if up else "#c6c6c6"; chem = "#628cbb" if up else "#b4b4b4"
        if side in ("fundo", "frente"):
            y = D / 2 if side == "fundo" else -D / 2
            ny = 1 if side == "fundo" else -1
            face([(-W / 2, y, 0), (W / 2, y, 0), (W / 2, y, s * ext), (-W / 2, y, s * ext)], cwall)
            if up:
                yin = y + dsign * ny * DOBRA_ESP
                face([(-W / 2, y, ext), (W / 2, y, ext), (W / 2, yin, ext), (-W / 2, yin, ext)], chem)
                face([(-W / 2, yin, ext), (W / 2, yin, ext), (W / 2, yin, ext - RETORNO_ESP), (-W / 2, yin, ext - RETORNO_ESP)], chem)
            else:
                yin = y - ny * RETORNO_ABA
                face([(-W / 2, y, -ext), (W / 2, y, -ext), (W / 2, yin, -ext), (-W / 2, yin, -ext)], chem)
        else:
            x = W / 2 if side == "dir" else -W / 2
            nx = 1 if side == "dir" else -1
            face([(x, -D / 2, 0), (x, D / 2, 0), (x, D / 2, s * ext), (x, -D / 2, s * ext)], cwall)
            if up:
                xin = x + dsign * nx * DOBRA_ESP
                face([(x, -D / 2, ext), (x, D / 2, ext), (xin, D / 2, ext), (xin, -D / 2, ext)], chem)
                face([(xin, -D / 2, ext), (xin, D / 2, ext), (xin, D / 2, ext - RETORNO_ESP), (xin, -D / 2, ext - RETORNO_ESP)], chem)
            else:
                xin = x - nx * RETORNO_ABA
                face([(x, -D / 2, -ext), (x, D / 2, -ext), (xin, D / 2, -ext), (xin, -D / 2, -ext)], chem)

    fig = plt.figure(figsize=(6.4, 5.2)); ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(Poly3DCollection(faces, facecolors=cols, edgecolors="#3f5f7f", linewidths=0.4, alpha=0.9))
    for h in prims.get("holes", []):
        loop = h[1]
        pts = [(x, y, 1.0) for x, y in loop]
        ax.add_collection3d(Poly3DCollection([pts], facecolors="#232323", edgecolors="#000", linewidths=1.1))
        xs = [p[0] for p in loop] + [loop[0][0]]; ys = [p[1] for p in loop] + [loop[0][1]]
        ax.plot(xs, ys, [1.2] * len(xs), color="#000", lw=1.3)
    R = max(W, D) / 2 * 1.1
    ax.set_xlim(-R, R); ax.set_ylim(-R, R); ax.set_zlim(-max(A, 20) - 8, H + 34)
    try:
        ax.set_box_aspect((max(W, D), max(D, W * 0.5), max(H + A, W * 0.28)))
    except Exception:
        pass
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    fc = info.get("final_comprimento", W); fp = info.get("final_profundidade", D)
    fig.text(0.5, 0.05, f"Montada (externa): {fc:.0f} × {fp:.0f} mm   ·   espelho {H:.0f} mm   ·   aba {A:.0f} mm",
             ha="center", fontsize=9.5, color="#333")
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=115, bbox_inches="tight"); plt.close(fig)
    return b.getvalue()


def gerar_de_params(params, name=None):
    """Recria a bancada a partir de um dict de parâmetros salvos na biblioteca."""
    p = dict(params or {})
    if name:
        p["name"] = name
    p.setdefault("espelhos", ("fundo",))
    p["espelhos"] = tuple(p.get("espelhos") or ())
    cubas = p.get("cubas") or []
    p["cubas"] = [tuple(c) for c in cubas]
    return gerar(p.get("comprimento", 1000), p.get("profundidade", 500),
                 esp=p.get("esp", 1.2), espelhos=p["espelhos"],
                 espelho_altura=p.get("espelho_altura", ESPELHO_ALTURA),
                 aba=p.get("aba", ABA_PADRAO), rasgo=p.get("rasgo", RASGO_PADRAO),
                 dobra_fora=p.get("dobra_fora", True), cubas=p["cubas"],
                 name=p.get("name", "Bancada"))


def _bbox_real(prims):
    xs = [pt[0] for pt in prims["outer"][1]]
    ys = [pt[1] for pt in prims["outer"][1]]
    return min(xs), min(ys), max(xs), max(ys)


def nest_dxf(pecas, gap=40.0, larg_max=3000.0):
    """pecas = lista de (prims, qtd). Dispõe TODAS as cópias num único DXF (prateleiras
    da esquerda p/ direita, quebrando linha ao passar de larg_max). Retorna bytes DXF."""
    itens = []
    x = 0.0; y = 0.0; row_h = 0.0
    for prims, qtd in pecas:
        x0, y0, x1, y1 = _bbox_real(prims)
        w = x1 - x0; h = y1 - y0
        for _ in range(max(int(qtd), 1)):
            if x > 0 and x + w > larg_max:
                x = 0.0; y += row_h + gap; row_h = 0.0
            itens.append((prims, x - x0, y - y0))
            x += w + gap; row_h = max(row_h, h)
    return dxf_bytes(itens)


def peso_kg(prims, densidade=INOX_DENS):
    return prims["area"] * prims["esp"] * densidade
