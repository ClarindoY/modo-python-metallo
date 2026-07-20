"""TORRE INOX METALLO — torre pinca de vidro (guarda-corpo).

Dois tubos 40x15 lado a lado com uma peca ao meio (40x10 ou 40x15, altura
40 mm na base), formando o canal do vidro (8 a 10 mm). Parametros: altura,
quantidade de furos, distancia da base ao 1o furo e passo entre furos.

Saidas: desenho tecnico cotado (PDF) + dois IGES com os MESMOS eixos:
  - TUBO PASSANTE: furo redondo passante (padrao Ø12) nas duas paredes largas;
  - TUBO PORCA: sextavado p/ porca M6 chave 10 com compensacao (padrao -0,33
    -> corte 9,67 mm), mesmos eixos.
"""
import io

from metallo_cad import parts


def gerar(altura, n_furos=2, base_furo1=100.0, entre_furos=200.0, wall=1.2,
          meio=10.0, d_furo=12.0, chave=10.0, comp=-0.33, base=40.0, raio=1.5):
    """base = altura da peca do meio (mm). base_furo1 = distancia do TOPO da
    base ate o EIXO do 1o furo. Posicao absoluta (da borda do tubo) =
    base + base_furo1. Ex.: torre 300, base 40, furo a 100 da base -> eixo 140."""
    altura = float(altura); base = float(base)
    n = max(int(n_furos), 1)
    pos = [base + float(base_furo1) + i * float(entre_furos) for i in range(n)]
    if pos[-1] + max(d_furo, chave) / 2 + 5 > altura:
        raise ValueError(
            f"Ultimo furo em {pos[-1]:.0f} mm (base {base:g} + {base_furo1:g}"
            f"{' + passos' if n > 1 else ''}) nao cabe na altura {altura:.0f} mm.")
    if float(base_furo1) < max(d_furo, chave) / 2:
        raise ValueError(
            f"1o furo colide com a base: eixo a {base_furo1:g} mm do topo da base "
            f"(minimo {max(d_furo, chave) / 2:g} mm).")
    rA = parts.tubo_retangular_furos(40.0, 15.0, wall, altura, pos, float(d_furo),
                                     tipo_furo="redondo", faces="ambas", raio=float(raio))
    rA.name = f"TorreInox_{altura:g}_TUBO_PASSANTE_D{d_furo:g}_{n}furo" + ("s" if n > 1 else "")
    # sextavado: corte APENAS numa face (a porca fica presa numa parede so)
    rB = parts.tubo_retangular_furos(40.0, 15.0, wall, altura, pos, float(chave),
                                     tipo_furo="sextavado", faces="topo", comp=float(comp),
                                     raio=float(raio))
    rB.name = (f"TorreInox_{altura:g}_TUBO_PORCA_M6_ch{chave:g}"
               f"_comp{comp:g}_{n}furo" + ("s" if n > 1 else ""))
    return {"A": rA, "B": rB, "pos": pos,
            "params": {"altura": altura, "n": n, "base_furo1": float(base_furo1),
                       "entre": float(entre_furos), "wall": float(wall),
                       "meio": float(meio), "d_furo": float(d_furo),
                       "chave": float(chave), "comp": float(comp), "base": base,
                       "raio": float(raio)}}


def desenho_pdf(res, nome="TORRE INOX METALLO", cliente="", data="", desenhista="Metallo"):
    """Folha A3 padrao ABNT/NBR: moldura dupla, legenda com logo, campos e
    rodape NBR 8403/10068/16752 — com as vistas frontal e lateral cotadas."""
    import datetime
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    import numpy as np
    from matplotlib.backends.backend_pdf import PdfPages
    try:
        from metallo_cad.config import logo_path
        LOGO = logo_path()
    except Exception:
        LOGO = None
    p = res["params"]; pos = res["pos"]
    H = p["altura"]; meio = p["meio"]; d = p["d_furo"]
    base = float(p.get("base", 40.0))
    data = data or datetime.date.today().strftime("%d/%m/%Y")

    buf = io.BytesIO()
    with PdfPages(buf) as pp:
        fig = plt.figure(figsize=(16.54, 11.69))       # A3 paisagem
        bg = fig.add_axes([0, 0, 1, 1]); bg.set_xlim(0, 420); bg.set_ylim(0, 297); bg.axis("off")
        bg.add_patch(plt.Rectangle((8, 8), 404, 281, fill=False, lw=1.6))
        bg.add_patch(plt.Rectangle((11, 11), 398, 275, fill=False, lw=0.6))

        # ---------------- legenda (title block) ----------------
        TBw, TBh = 196, 50; TBx, TBy = 409 - TBw, 11; lbw = 54
        bg.add_patch(plt.Rectangle((TBx, TBy), TBw, TBh, fill=False, lw=1.2))
        bg.plot([TBx + lbw, TBx + lbw], [TBy, TBy + TBh], color="k", lw=0.7)
        bg.plot([TBx + lbw, TBx + TBw], [TBy + TBh - 13, TBy + TBh - 13], color="k", lw=0.7)
        bg.text((TBx + lbw + TBx + TBw) / 2, TBy + TBh - 6.5, nome, fontsize=11.5,
                weight="bold", va="center", ha="center")
        fx0 = TBx + lbw; fw = TBw - lbw; fy1 = TBy + TBh - 13
        colw = fw / 3.0; rowh = (fy1 - TBy) / 3.0
        for i2 in range(1, 3):
            bg.plot([fx0 + i2 * colw, fx0 + i2 * colw], [TBy, fy1], color="k", lw=0.4)
        for j2 in range(1, 3):
            bg.plot([fx0, fx0 + fw], [TBy + j2 * rowh, TBy + j2 * rowh], color="k", lw=0.4)

        def campo(ci, rj, rot, val):
            cx = fx0 + ci * colw; cy = TBy + rj * rowh
            bg.text(cx + 1.6, cy + rowh - 1.6, rot, fontsize=5.6, color="0.35", va="top")
            bg.text(cx + colw / 2, cy + rowh * 0.36, val, fontsize=8.0, weight="bold",
                    ha="center", va="center")
        campo(0, 2, "MATERIAL", "Inox 304")
        campo(1, 2, "TUBOS", f"2x 40x15 #{p['wall']:g} r{p.get('raio', 1.5):g}")
        campo(2, 2, "PECA DO MEIO", f"40x{meio:g} h={base:g}")
        campo(0, 1, "ALTURA", f"{H:g} mm")
        campo(1, 1, "FUROS", f"{p['n']}x  topo base+{p['base_furo1']:g} / passo {p['entre']:g}")
        campo(2, 1, "FURO A / B", f"Ø{d:g} / sext {p['chave'] + p['comp']:.2f}")
        campo(0, 0, "QUANT.", "1 conjunto")
        campo(1, 0, "DATA", data)
        campo(2, 0, "ESCALA", "S/ esc.")
        bg.text(TBx + lbw + 1.6, TBy - 3.2,
                f"Cliente: {cliente or '-'}   ·   Des.: {desenhista}   ·   NBR 8403/10068/16752",
                fontsize=5.4, color="0.4", va="top")
        if LOGO is not None:
            try:
                im = mpimg.imread(logo_path())
                la = fig.add_axes([(TBx + 2) / 420, (TBy + 3) / 297, (lbw - 4) / 420, (TBh - 6) / 297])
                la.imshow(im); la.axis("off")
            except Exception:
                bg.text(TBx + lbw / 2, TBy + TBh / 2, "METALLO", fontsize=10, weight="bold",
                        ha="center", va="center")

        fig.text(0.05, 0.945, f"{nome} — MEDIDAS EM MM", fontsize=12, weight="bold")

        # ---------------- vista frontal ----------------
        ax = fig.add_axes([0.07, 0.16, 0.30, 0.74]); ax.set_aspect("equal")
        ax.plot([0, 40, 40, 0, 0], [0, 0, H, H, 0], "-k", lw=1.4)
        ax.plot([0, 40], [base, base], "-k", lw=0.8)
        for k in range(1, 30):
            d0 = k * 5.5
            xa, ya = max(d0 - 40.0, 0.0), min(d0, base)
            xb, yb = min(d0, 40.0), max(d0 - 40.0, 0.0)
            if ya <= base and yb <= base and d0 < 40.0 + base:
                ax.plot([xa, xb], [ya, yb], "-", color="0.6", lw=0.5)
        th = np.linspace(0, 2 * np.pi, 40)
        for y in pos:
            ax.plot(20 + d / 2 * np.cos(th), y + d / 2 * np.sin(th), "-k", lw=1.0)
            ax.plot([15, 25], [y, y], "-", color="0.4", lw=0.5)
            ax.plot([20, 20], [y - 5, y + 5], "-", color="0.4", lw=0.5)
        xd = 54

        def cota_v(y0, y1, x, txt):
            ax.annotate("", (x, y0), (x, y1), arrowprops=dict(arrowstyle="<->", lw=0.7))
            ax.text(x + 3.5, (y0 + y1) / 2, txt, fontsize=8.5, va="center", rotation=90)
        cota_v(0, base, xd, f"{base:g}")
        cota_v(base, pos[0], xd, f"{p['base_furo1']:g}")
        for i2 in range(1, len(pos)):
            cota_v(pos[i2 - 1], pos[i2], xd, f"{p['entre']:g}")
        cota_v(0, H, xd + 18, f"{H:g}")
        ax.annotate("", (0, -16), (40, -16), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax.text(20, -26, "40", fontsize=8.5, ha="center")
        ax.text(20 + d / 2 + 4, pos[-1] + 10, f"Ø{d:g}", fontsize=8.5)
        ax.set_xlim(-18, 96); ax.set_ylim(-40, H + 26); ax.axis("off")
        ax.set_title("VISTA FRONTAL", fontsize=10)

        # ---------------- vista lateral (secao) ----------------
        ax2 = fig.add_axes([0.42, 0.16, 0.30, 0.74]); ax2.set_aspect("equal")
        x0 = 0
        for wct, alt in [(15.0, H), (meio, base), (15.0, H)]:
            ax2.plot([x0, x0 + wct, x0 + wct, x0, x0], [0, 0, alt, alt, 0], "-k", lw=1.2)
            x0 += wct
        tot = 30.0 + meio
        ax2.annotate("", (0, -16), (tot, -16), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax2.text(tot / 2, -26, f"{tot:g}", fontsize=8.5, ha="center")
        for xx, ww in [(0, 15.0), (15.0, meio), (15.0 + meio, 15.0)]:
            ax2.annotate("", (xx, H + 12), (xx + ww, H + 12), arrowprops=dict(arrowstyle="<->", lw=0.6))
            ax2.text(xx + ww / 2, H + 20, f"{ww:g}", fontsize=8, ha="center")
        ax2.annotate("", (tot + 9, 0), (tot + 9, base), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax2.text(tot + 14, base / 2, f"{base:g}", fontsize=8, va="center", rotation=90)
        ax2.set_xlim(-12, tot + 40); ax2.set_ylim(-40, H + 34); ax2.axis("off")
        ax2.set_title("VISTA LATERAL (seção)", fontsize=10)

        nota = (f"TUBO A — furo redondo PASSANTE Ø{d:g} mm (2 paredes largas)\n"
                f"TUBO B — sextavado p/ porca M6, chave {p['chave']:g} mm, "
                f"compensação {p['comp']:g} (corte {p['chave'] + p['comp']:.2f} mm), "
                f"em UMA FACE apenas — MESMOS EIXOS\n"
                f"Base (peça do meio) h={base:g} mm — 1º furo medido do TOPO DA BASE ao eixo "
                f"({p['base_furo1']:g} mm; da borda do tubo = {base + p['base_furo1']:g} mm) · Vidros 8 a 10 mm")
        fig.text(0.07, 0.075, nota, fontsize=8.5, family="monospace")
        pp.savefig(fig); plt.close(fig)
    return buf.getvalue()
