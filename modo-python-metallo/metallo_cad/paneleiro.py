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


def paneleiro_prims(C, L, esp=1.2):
    C = float(C); L = float(L)
    aw = C - 100.0; ah = L - 140.0
    if aw <= 0 or ah <= 0:
        raise ValueError("Bancada pequena demais para o paneleiro (alma <= 0).")
    W = aw + 100.0; H = ah + 100.0
    ch = 10.0  # esquadria apenas no retorno de 10
    o = [(-W / 2 + ch, -H / 2), (W / 2 - ch, -H / 2), (W / 2, -H / 2 + ch),
         (W / 2, H / 2 - ch), (W / 2 - ch, H / 2), (-W / 2 + ch, H / 2),
         (-W / 2, H / 2 - ch), (-W / 2, -H / 2 + ch)]
    dob = []
    # retorno de 10 (entre os chanfros) e aba de 40, nas 4 laterais = 8 linhas
    dob.append(("line", [(-W / 2 + ch, -H / 2 + 10), (W / 2 - ch, -H / 2 + 10)]))
    dob.append(("line", [(-W / 2 + ch, H / 2 - 10), (W / 2 - ch, H / 2 - 10)]))
    dob.append(("line", [(-W / 2 + 10, -H / 2 + ch), (-W / 2 + 10, H / 2 - ch)]))
    dob.append(("line", [(W / 2 - 10, -H / 2 + ch), (W / 2 - 10, H / 2 - ch)]))
    dob.append(("line", [(-W / 2 + 50, -H / 2 + 50), (W / 2 - 50, -H / 2 + 50)]))
    dob.append(("line", [(-W / 2 + 50, H / 2 - 50), (W / 2 - 50, H / 2 - 50)]))
    dob.append(("line", [(-W / 2 + 50, -H / 2 + 50), (-W / 2 + 50, H / 2 - 50)]))
    dob.append(("line", [(W / 2 - 50, -H / 2 + 50), (W / 2 - 50, H / 2 - 50)]))
    area = W * H - 2 * ch * ch
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
    Wx = CR + 30.0            # abas de 15 nas duas extremidades (sem linha de dobra)
    H = 10.0 + 15.0 + 150.0 + 15.0 + 10.0  # 200
    dob = [("line", [(-Wx / 2, -H / 2 + 10), (Wx / 2, -H / 2 + 10)]),
           ("line", [(-Wx / 2, -H / 2 + 25), (Wx / 2, -H / 2 + 25)]),
           ("line", [(-Wx / 2, H / 2 - 25), (Wx / 2, H / 2 - 25)]),
           ("line", [(-Wx / 2, H / 2 - 10), (Wx / 2, H / 2 - 10)])]
    return {"outer": ("poly", _rect(Wx, H)), "holes": [], "rasgos": [], "dobras": dob,
            "deco": [], "bbox": (Wx, H), "area": Wx * H, "name": "Reforco",
            "esp": float(esp), "info": {"CR": CR, "alma": 150.0, "plano": (Wx, H),
                                        "n_dobras": 4, "abas_extremidade": 15.0}}


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
