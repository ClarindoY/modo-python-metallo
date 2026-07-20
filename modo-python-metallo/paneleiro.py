"""Paneleiro + Reforco do Paneleiro + Reforco de bancada — planificados.

Specs fechadas do cliente. O desenho contem SOMENTE: contorno, linhas de
dobra e identificacao. Sem cotas, vistas, perspectivas ou perfis.
DXF de corte: apenas contorno (regra da casa: laser nunca ve linha de dobra).

PANELEIRO (a partir de C x L da bancada):
  alma = (C-100) x (L-140); perfil nas 4 laterais: aba 40 + retorno 10;
  esquadria (chanfro 45) SOMENTE no retorno de 10 (cantos); aba 40 continua;
  8 linhas de dobra. Planificado = alma + 50 por lado.

REFORCO DO PANELEIRO:
  comprimento = L - 143; alma 150; abas superior/inferior 35 + retorno 10;
  laterais retas, sem esquadria; retorno percorre todo o comprimento;
  4 linhas de dobra (2 por borda). Planificado: (L-143) x 240.

REFORCO DE BANCADA (avulso):
  CR = LB - 152 (obs.: o texto da spec tambem cita LB-150; adotado -152);
  alma 150; bordas longitudinais: dobra 15 + dobra 10 (ambas as bordas);
  abas de 15 nas DUAS extremidades SEM linha de dobra (so compoem a
  geometria). Planificado: (CR + 30) x 200; 4 linhas de dobra longitudinais.
"""
import io

INOX_DENS = 7.93e-6


def _rect(w, h):
    return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]


def paneleiro_prims(C, L, esp=1.2, aba=40.0, ret=10.0):
    C = float(C); L = float(L)
    aw = C - 100.0; ah = L - 140.0
    if aw <= 0 or ah <= 0:
        raise ValueError("Bancada pequena demais para o paneleiro (alma <= 0).")
    W = aw + 100.0; H = ah + 100.0
    Wx = W / 2.0; Hy = H / 2.0
    ins = aba + ret                 # recuo da alma (50 = 40 + 10)
    # contorno com RECORTE em L em cada canto (igual ao DXF de referencia):
    # aba para na borda da alma; retorno de 10 chanfrado 45 na pontinha. Ordem CCW.
    o = []
    o += [(-Wx, -Hy + (ins + ret)), (-Wx + ret, -Hy + ins), (-Wx + ins, -Hy + ins),
          (-Wx + ins, -Hy + ret), (-Wx + ins + ret, -Hy)]                 # BL
    o += [(Wx - ins - ret, -Hy), (Wx - ins, -Hy + ret), (Wx - ins, -Hy + ins),
          (Wx - ret, -Hy + ins), (Wx, -Hy + ins + ret)]                   # BR
    o += [(Wx, Hy - ins - ret), (Wx - ret, Hy - ins), (Wx - ins, Hy - ins),
          (Wx - ins, Hy - ret), (Wx - ins - ret, Hy)]                     # TR
    o += [(-Wx + ins + ret, Hy), (-Wx + ins, Hy - ret), (-Wx + ins, Hy - ins),
          (-Wx + ret, Hy - ins), (-Wx, Hy - ins - ret)]                   # TL
    ax = Wx - ins; ay = Hy - ins    # cantos da alma
    xr = Wx - ret; yr = Hy - ret    # dobras do retorno
    dob = [("line", [(ax, -ay), (ax, ay)]),
           ("line", [(xr, -ay), (xr, ay)]),
           ("line", [(-ax, -ay), (-ax, ay)]),
           ("line", [(-xr, -ay), (-xr, ay)]),
           ("line", [(-ax, ay), (ax, ay)]),
           ("line", [(-ax, yr), (ax, yr)]),
           ("line", [(-ax, -ay), (ax, -ay)]),
           ("line", [(-ax, -yr), (ax, -yr)])]
    area = W * H - 4 * (ins * ins - ret * ret / 2.0)
    return {"outer": ("poly", o), "holes": [], "rasgos": [], "dobras": dob, "deco": [],
            "bbox": (W, H), "area": area, "name": "Paneleiro", "esp": float(esp),
            "info": {"alma": (aw, ah), "plano": (W, H), "n_dobras": 8}}


def reforco_paneleiro_prims(L, esp=1.2):
    L = float(L)
    Wx = L - 143.0
    if Wx <= 0:
        raise ValueError("Bancada pequena demais para o reforco do paneleiro.")
    H = 10.0 + 35.0 + 150.0 + 35.0 + 10.0  # 240
    dob = [("line", [(-Wx / 2, -H / 2 + 10), (Wx / 2, -H / 2 + 10)]),
           ("line", [(-Wx / 2, -H / 2 + 45), (Wx / 2, -H / 2 + 45)]),
           ("line", [(-Wx / 2, H / 2 - 45), (Wx / 2, H / 2 - 45)]),
           ("line", [(-Wx / 2, H / 2 - 10), (Wx / 2, H / 2 - 10)])]
    return {"outer": ("poly", _rect(Wx, H)), "holes": [], "rasgos": [], "dobras": dob,
            "deco": [], "bbox": (Wx, H), "area": Wx * H, "name": "Reforco do Paneleiro",
            "esp": float(esp), "info": {"alma": 150.0, "comprimento": Wx, "n_dobras": 4}}


def reforco_bancada_prims(LB, esp=1.2):
    LB = float(LB)
    CR = LB - 152.0
    if CR <= 0:
        raise ValueError("Largura da bancada pequena demais para o reforco.")
    H = 10.0 + 15.0 + 150.0 + 15.0 + 10.0  # 200
    Hy = H / 2.0; cx = CR / 2.0
    alma = 75.0                 # meia-altura da alma (150 mm)
    tab = 15.0                  # aba das extremidades (so na altura da alma)
    # contorno em CRUZ: corpo CR x 200 + abas 15 nas laterais, apenas na alma. CCW.
    o = [(-cx, -Hy), (cx, -Hy), (cx, -alma), (cx + tab, -alma), (cx + tab, alma),
         (cx, alma), (cx, Hy), (-cx, Hy), (-cx, alma), (-cx - tab, alma),
         (-cx - tab, -alma), (-cx, -alma)]
    dob = [("line", [(-cx, -Hy + 10), (cx, -Hy + 10)]),
           ("line", [(-cx, -Hy + 25), (cx, -Hy + 25)]),
           ("line", [(-cx, Hy - 25), (cx, Hy - 25)]),
           ("line", [(-cx, Hy - 10), (cx, Hy - 10)])]
    return {"outer": ("poly", o), "holes": [], "rasgos": [], "dobras": dob,
            "deco": [], "bbox": (CR + 2 * tab, H), "area": CR * H + 2 * tab * 2 * alma,
            "name": "Reforco", "esp": float(esp),
            "info": {"CR": CR, "alma": 150.0, "plano": (CR + 2 * tab, H),
                     "n_dobras": 4, "abas_extremidade": tab}}


def desenho_pdf(pecas, titulo=""):
    """Folha simples: SOMENTE contorno + dobras tracejadas + nome de cada peca.
    Sem cotas, sem vistas, sem perspectiva (exigencia da especificacao)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    buf = io.BytesIO()
    with PdfPages(buf) as pp:
        fig = plt.figure(figsize=(16.54, 11.69))
        n = len(pecas)
        y0 = 0.93
        alt = 0.86 / n
        if titulo:
            fig.text(0.05, 0.965, titulo, fontsize=11, weight="bold")
        for k, p in enumerate(pecas):
            ax = fig.add_axes([0.05, y0 - (k + 1) * alt + 0.015, 0.9, alt - 0.05])
            o = p["outer"][1]
            ax.plot([q[0] for q in o] + [o[0][0]], [q[1] for q in o] + [o[0][1]],
                    "-", color="black", lw=1.3)
            for d in p.get("dobras", []):
                ax.plot([d[1][0][0], d[1][1][0]], [d[1][0][1], d[1][1][1]],
                        "--", color="#c00", lw=0.9)
            W, H = p["bbox"]
            ax.text(W / 2 + W * 0.02, 0, p["name"], fontsize=11, va="center", weight="bold")
            ax.set_aspect("equal"); ax.axis("off")
            ax.set_xlim(-W / 2 - W * 0.03, W / 2 + W * 0.22)
            ax.set_ylim(-H / 2 - H * 0.10, H / 2 + H * 0.10)
        pp.savefig(fig); plt.close(fig)
    return buf.getvalue()
