"""Saiote metalico para bancadas - geracao parametrica (spec fechada).

Entradas: C (comprimento da bancada) e L (largura). Calcula:
  PL = C - 30  (2 pecas longitudinais A e B, SEM corte)
  PT = L - 30  (2 pecas transversais C e D, COM corte)

Secao identica p/ todas: 170 mm = 10 + 15 + 120 + 15 + 10
Coordenadas Y: 0, 10, 25, 145, 160, 170. Dobras em Y=10, 25, 145, 160.
Alma = retangulo Y 25..145, X 0..P - NUNCA alterada.
Aba superior (Y 145..170): sem corte X 0..P; com corte X 17..P-17.
Aba inferior (Y 0..25):    sem corte X 0..P; com corte X 62..P-62.
So segmentos ortogonais - sem arcos, chanfros, diagonais.

Opcional (conforme desenho de fabricacao): dobra central da alma em Y=85
(60+60), gerando perfil em L 60x60 com flanges 15 e retornos 10.
"""
import io

ALT = 170.0
Y0, Y1, Y2, Y3, Y4, Y5 = 0.0, 10.0, 25.0, 145.0, 160.0, 170.0
CORTE_SUP = 17.0
CORTE_INF = 62.0
INOX_DENS = 7.93e-6


def _contorno(P, corte):
    a = CORTE_SUP if corte else 0.0
    b = CORTE_INF if corte else 0.0
    if not corte:
        return [(0, Y0), (P, Y0), (P, Y5), (0, Y5)]
    return [(b, Y0), (P - b, Y0), (P - b, Y2), (P, Y2), (P, Y3), (P - a, Y3),
            (P - a, Y5), (a, Y5), (a, Y3), (0, Y3), (0, Y2), (b, Y2)]


def _peca(nome, tipo, P, corte, esp, dobra_central):
    a = CORTE_SUP if corte else 0.0
    b = CORTE_INF if corte else 0.0
    dobras = [("line", [(b, Y1), (P - b, Y1)]),
              ("line", [(b, Y2), (P - b, Y2)]),
              ("line", [(a, Y3), (P - a, Y3)]),
              ("line", [(a, Y4), (P - a, Y4)])]
    if dobra_central:
        dobras.append(("line", [(0.0, 85.0), (P, 85.0)]))
    area = P * (Y3 - Y2) + (P - 2 * a) * (Y5 - Y3) + (P - 2 * b) * (Y2 - Y0)
    return {"outer": ("poly", _contorno(P, corte)), "holes": [], "rasgos": [],
            "dobras": dobras, "deco": [], "bbox": (P, ALT), "area": area,
            "name": nome, "esp": float(esp),
            "info": {"tipo": tipo, "P": P, "corte": corte,
                     "aba_sup": (a, P - a), "aba_inf": (b, P - b),
                     "dobra_central": bool(dobra_central)}}


def gerar(C, L, esp=1.2, dobra_central=True):
    C = float(C); L = float(L)
    PL = C - 30.0
    PT = L - 30.0
    if PL <= 2 * CORTE_INF or PT <= 2 * CORTE_INF:
        raise ValueError("Dimensoes pequenas demais: P deve ser maior que 124 mm (2x62).")
    pecas = [_peca("Peca A", "Longitudinal", PL, False, esp, dobra_central),
             _peca("Peca B", "Longitudinal", PL, False, esp, dobra_central),
             _peca("Peca C", "Transversal", PT, True, esp, dobra_central),
             _peca("Peca D", "Transversal", PT, True, esp, dobra_central)]
    checks = validar(pecas)
    return {"pecas": pecas, "PL": PL, "PT": PT, "C": C, "L": L,
            "esp": float(esp), "dobra_central": bool(dobra_central), "checks": checks}


def validar(pecas):
    """Checklist obrigatorio da especificacao. Retorna lista (ok, texto)."""
    out = []
    out.append((len(pecas) == 4, "Existem exatamente 4 pecas."))
    nlong = sum(1 for p in pecas if p["info"]["tipo"] == "Longitudinal")
    ntrans = sum(1 for p in pecas if p["info"]["tipo"] == "Transversal")
    out.append((nlong == 2 and ntrans == 2, "2 longitudinais e 2 transversais."))
    ok3 = all(p["info"]["aba_sup"][0] == 0 and p["info"]["aba_inf"][0] == 0
              for p in pecas if p["info"]["tipo"] == "Longitudinal")
    out.append((ok3, "Longitudinais sem interrupcao das abas."))
    ok4 = all(p["info"]["corte"] for p in pecas if p["info"]["tipo"] == "Transversal")
    out.append((ok4, "Transversais com interrupcao das abas."))
    ok5 = True; ok8 = True; ok9 = True; ok10 = True
    for p in pecas:
        P = p["info"]["P"]
        pts = p["outer"][1]
        xs = [q[0] for q in pts]
        ok5 &= (min(xs) == 0 and max(xs) == P)
        if p["info"]["corte"]:
            ok8 &= p["info"]["aba_sup"] == (CORTE_SUP, P - CORTE_SUP)
            ok9 &= p["info"]["aba_inf"] == (CORTE_INF, P - CORTE_INF)
        for i in range(len(pts)):
            x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % len(pts)]
            ok10 &= (abs(x1 - x2) < 1e-9 or abs(y1 - y2) < 1e-9)
    out.append((ok5, "Alma percorre 100% do comprimento."))
    out.append((all(abs(p["bbox"][1] - 170.0) < 1e-9 for p in pecas), "Largura total da chapa = 170 mm."))
    dob_ok = True
    for p in pecas:
        ys = sorted({round(d[1][0][1], 3) for d in p["dobras"] if d[1][0][1] != 85.0})
        dob_ok &= ys == [10.0, 25.0, 145.0, 160.0]
    out.append((dob_ok, "Dobras em Y = 10, 25, 145 e 160 mm."))
    out.append((ok8, "Com corte: aba superior so entre X=17 e P-17."))
    out.append((ok9, "Com corte: aba inferior so entre X=62 e P-62."))
    out.append((ok10, "So entidades ortogonais (sem diagonais/arcos/chanfros)."))
    return out


def perfil_png(dobra_central=True):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(3.6, 3.4)); ax.set_aspect("equal")
    lw = 2.6; c = "#20486e"
    if dobra_central:
        ax.plot([0, 60], [0, 0], c, lw=lw)
        ax.plot([60, 60], [0, 15], c, lw=lw)
        ax.plot([60, 50], [15, 15], c, lw=lw)
        ax.plot([0, 0], [0, 60], c, lw=lw)
        ax.plot([0, 15], [60, 60], c, lw=lw)
        ax.plot([15, 15], [60, 50], c, lw=lw)
        for x, y, t in [(30, -7, "60"), (-8, 30, "60"), (66, 7.5, "15"), (52, 19, "10"),
                        (7, 64, "15"), (19, 52, "10")]:
            ax.text(x, y, t, fontsize=9, ha="center", va="center", color="#333")
        ax.set_title("Perfil dobrado (L 60x60)", fontsize=10)
        ax.set_xlim(-16, 80); ax.set_ylim(-14, 76)
    else:
        ax.plot([0, 0], [0, 120], c, lw=lw)
        ax.plot([0, 15], [120, 120], c, lw=lw)
        ax.plot([15, 15], [120, 110], c, lw=lw)
        ax.plot([0, 15], [0, 0], c, lw=lw)
        ax.plot([15, 15], [0, 10], c, lw=lw)
        for x, y, t in [(-8, 60, "120 (alma)"), (7, 125, "15"), (19, 113, "10"),
                        (7, -7, "15"), (19, 7, "10")]:
            ax.text(x, y, t, fontsize=9, ha="center", va="center", color="#333",
                    rotation=(90 if "alma" in t else 0))
        ax.set_title("Perfil dobrado (alma 120)", fontsize=10)
        ax.set_xlim(-20, 42); ax.set_ylim(-16, 136)
    ax.axis("off")
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return b.getvalue()


def folha_pdf(res, cliente="", data="", desenhista="Metallo"):
    """Folha de projeto A3 (NBR): moldura + legenda com logo, planificacoes das
    4 pecas com dobras e cotas, perfil dobrado e checklist."""
    import datetime
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    from matplotlib.backends.backend_pdf import PdfPages
    try:
        from metallo_cad.config import logo_path
        LOGO = logo_path()
    except Exception:
        LOGO = None
    data = data or datetime.date.today().strftime("%d/%m/%Y")
    pecas = res["pecas"]; esp = res["esp"]
    peso_tot = sum(p["area"] * esp * INOX_DENS for p in pecas)

    buf = io.BytesIO()
    with PdfPages(buf) as pp:
        fig = plt.figure(figsize=(16.54, 11.69))
        bg = fig.add_axes([0, 0, 1, 1]); bg.set_xlim(0, 420); bg.set_ylim(0, 297); bg.axis("off")
        bg.add_patch(plt.Rectangle((8, 8), 404, 281, fill=False, lw=1.6))
        bg.add_patch(plt.Rectangle((11, 11), 398, 275, fill=False, lw=0.6))
        TBw, TBh = 196, 50; TBx, TBy = 409 - TBw, 11; lbw = 54
        bg.add_patch(plt.Rectangle((TBx, TBy), TBw, TBh, fill=False, lw=1.2))
        bg.plot([TBx + lbw, TBx + lbw], [TBy, TBy + TBh], color="k", lw=0.7)
        bg.plot([TBx + lbw, TBx + TBw], [TBy + TBh - 13, TBy + TBh - 13], color="k", lw=0.7)
        bg.text((TBx + lbw + TBx + TBw) / 2, TBy + TBh - 6.5,
                "Saiote %.0fx%.0f" % (res["C"], res["L"]), fontsize=12.5, weight="bold",
                va="center", ha="center")
        fx0 = TBx + lbw; fw = TBw - lbw; fy1 = TBy + TBh - 13
        colw = fw / 3.0; rowh = (fy1 - TBy) / 3.0
        for i in range(1, 3):
            bg.plot([fx0 + i * colw, fx0 + i * colw], [TBy, fy1], color="k", lw=0.4)
        for j in range(1, 3):
            bg.plot([fx0, fx0 + fw], [TBy + j * rowh, TBy + j * rowh], color="k", lw=0.4)

        def campo(ci, rj, rot, val):
            cx = fx0 + ci * colw; cy = TBy + rj * rowh
            bg.text(cx + 1.6, cy + rowh - 1.6, rot, fontsize=5.6, color="0.35", va="top")
            bg.text(cx + colw / 2, cy + rowh * 0.36, val, fontsize=8.0, weight="bold",
                    ha="center", va="center")
        campo(0, 2, "MATERIAL", "Inox 304 %g mm" % esp)
        campo(1, 2, "PL (long.)", "%.0f mm x2" % res["PL"])
        campo(2, 2, "PT (transv.)", "%.0f mm x2" % res["PT"])
        campo(0, 1, "SECAO", "170 (10/15/120/15/10)")
        campo(1, 1, "PESO (4 pcs)", "%.1f kg" % peso_tot)
        campo(2, 1, "PERFIL", "L 60x60" if res["dobra_central"] else "alma 120")
        campo(0, 0, "QUANT.", "4 pecas")
        campo(1, 0, "DATA", data)
        campo(2, 0, "ESCALA", "S/ esc.")
        bg.text(TBx + lbw + 1.6, TBy - 3.2,
                "Cliente: %s   -   Des.: %s   -   NBR 8403/10068/16752" % (cliente or "-", desenhista),
                fontsize=5.4, color="0.4", va="top")
        if LOGO is not None:
            try:
                im = mpimg.imread(logo_path())
                la = fig.add_axes([(TBx + 2) / 420.0, (TBy + 3) / 297.0, (lbw - 4) / 420.0, (TBh - 6) / 297.0])
                la.imshow(im); la.axis("off")
            except Exception:
                pass

        fig.text(0.045, 0.945, "PLANIFICACOES (corte a laser - vermelho tracejado = dobra, NAO cortar)",
                 fontsize=11, weight="bold")
        y0 = 0.72
        for k, p in enumerate(pecas):
            axp = fig.add_axes([0.045, y0 - k * 0.175, 0.58, 0.155])
            P = p["info"]["P"]
            o = p["outer"][1]
            axp.plot([q[0] for q in o] + [o[0][0]], [q[1] for q in o] + [o[0][1]], "-", color="#c00", lw=1.1)
            for d in p["dobras"]:
                axp.plot([d[1][0][0], d[1][1][0]], [d[1][0][1], d[1][1][1]], "--", color="#c00", lw=0.7, alpha=0.8)
            axp.set_aspect("equal")
            axp.set_xlim(-P * 0.02, P * 1.24); axp.set_ylim(-45, ALT + 12)
            axp.axis("off")
            info = p["info"]
            axp.text(P * 1.03, ALT * 0.72,
                     "%s - %s\nP = %.0f mm - %s" % (p["name"], info["tipo"], P,
                                                     "COM corte" if info["corte"] else "SEM corte"),
                     fontsize=8.6, va="center")
            axp.annotate("", (0, -22), (P, -22), arrowprops=dict(arrowstyle="<->", lw=0.6))
            axp.text(P / 2, -40, "%.0f" % P, ha="center", fontsize=7.4)
            if info["corte"]:
                axp.text(CORTE_SUP / 2 + 6, Y5 + 5, "17", fontsize=6.4, ha="center")
                axp.text(CORTE_INF / 2, Y0 - 12, "62", fontsize=6.4, ha="center")

        try:
            a3 = fig.add_axes([0.66, 0.52, 0.30, 0.36])
            a3.imshow(mpimg.imread(io.BytesIO(perfil_png(res["dobra_central"])))); a3.axis("off")
        except Exception:
            pass
        fig.text(0.66, 0.47, "Secao (Y): 0 - 10 - 25 - 145 - 160 - 170  ->  10/15/120/15/10",
                 fontsize=8.6, family="monospace")
        chk = "\n".join(("[OK] " if ok else "[X ] ") + t for ok, t in res["checks"])
        fig.text(0.66, 0.435, "Checklist da especificacao:\n" + chk, fontsize=6.4,
                 va="top", family="monospace")
        pp.savefig(fig); plt.close(fig)
    return buf.getvalue()


def etiqueta_itens(res):
    esp = res["esp"]
    out = []
    for p in res["pecas"]:
        i = p["info"]
        out.append({"descricao": "Saiote %s - %s %.0fx170 mm%s" % (
                        p["name"][-1], i["tipo"], i["P"], " - c/ corte" if i["corte"] else ""),
                    "material": "Inox 304 %gmm" % esp, "qtd": 1})
    return out


def imagem_3d(res, elev=26, azim=-55):
    """Renderiza o QUADRO do saiote montado em 3D (4 pecas dobradas formando o
    retangulo PL x PT). Perfil L 60x60 (dobra central) ou alma 120 com flanges.
    Retorna PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    W = float(res["PL"]); D = float(res["PT"])
    dc = bool(res.get("dobra_central", True))
    faces = []; cols = []

    def face(pts, col):
        faces.append(pts); cols.append(col)

    cw = "#7ea9d4"; cf = "#9db9d6"; cl = "#628cbb"
    alt = 60.0 if dc else 120.0
    fl = 60.0 if dc else 15.0    # flange inferior p/ dentro
    lip = 15.0 if dc else 10.0   # aba na ponta do flange

    lados = [("frente", (-W / 2, -D / 2), (W / 2, -D / 2), (0, 1)),
             ("fundo", (-W / 2, D / 2), (W / 2, D / 2), (0, -1)),
             ("esq", (-W / 2, -D / 2), (-W / 2, D / 2), (1, 0)),
             ("dir", (W / 2, -D / 2), (W / 2, D / 2), (-1, 0))]
    for nome, p0, p1, (nx, ny) in lados:
        x0, y0 = p0; x1, y1 = p1
        # parede vertical (de z=0 descendo)
        face([(x0, y0, 0), (x1, y1, 0), (x1, y1, -alt), (x0, y0, -alt)], cw)
        # flange inferior p/ dentro
        fx0, fy0 = x0 + nx * fl, y0 + ny * fl
        fx1, fy1 = x1 + nx * fl, y1 + ny * fl
        face([(x0, y0, -alt), (x1, y1, -alt), (fx1, fy1, -alt), (fx0, fy0, -alt)], cf)
        # aba na ponta do flange (sobe)
        face([(fx0, fy0, -alt), (fx1, fy1, -alt), (fx1, fy1, -alt + lip), (fx0, fy0, -alt + lip)], cl)
        if not dc:
            # flange superior p/ dentro (perfil alma 120 tem 15 em cima tambem)
            face([(x0, y0, 0), (x1, y1, 0), (fx1 - nx * (fl - 15), fy1 - ny * (fl - 15), 0),
                  (fx0 - nx * (fl - 15), fy0 - ny * (fl - 15), 0)], cf)

    fig = plt.figure(figsize=(6.2, 4.8)); ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(Poly3DCollection(faces, facecolors=cols, edgecolors="#3f5f7f",
                                         linewidths=0.4, alpha=0.92))
    R = max(W, D) / 2 * 1.12
    ax.set_xlim(-R, R); ax.set_ylim(-R, R); ax.set_zlim(-alt - 26, 34)
    try:
        ax.set_box_aspect((max(W, D), max(D, W * 0.5), max(alt * 2.4, W * 0.26)))
    except Exception:
        pass
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    perfil = "L 60x60" if dc else "alma 120"
    fig.text(0.5, 0.05, "Saiote montado: %.0f x %.0f mm  -  perfil %s  -  4 pecas" % (W, D, perfil),
             ha="center", fontsize=9.5, color="#333")
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=115, bbox_inches="tight"); plt.close(fig)
    return b.getvalue()
