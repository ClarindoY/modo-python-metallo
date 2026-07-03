"""PDFs da bancada: (1) desenho cotado da planificacao e (2) plano de corte de dobra."""
from __future__ import annotations
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def _draw_outline(ax, prims):
    o = prims["outer"][1]
    xs = [p[0] for p in o] + [o[0][0]]
    ys = [p[1] for p in o] + [o[0][1]]
    ax.plot(xs, ys, "-", color="#c00", lw=1.3)
    for h in prims["holes"]:
        pts = h[1] + [h[1][0]]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "-", color="#06c", lw=1.0)
    for d in prims.get("dobras", []):
        seg = d[1]
        ax.plot([p[0] for p in seg], [p[1] for p in seg], "--", color="#090", lw=0.8)
    for r in prims.get("rasgos", []):
        seg = r[1]
        ax.plot([p[0] for p in seg], [p[1] for p in seg], "-", color="#c00", lw=1.6)


def desenho_pdf(prims):
    """Planificacao cotada (A3 paisagem): contorno, cubas, dobras e cotas gerais."""
    info = prims.get("info", {})
    w, h = prims["bbox"]
    buf = io.BytesIO()
    with PdfPages(buf) as pp:
        fig = plt.figure(figsize=(16.54, 11.69))
        ax = fig.add_axes([0.06, 0.16, 0.9, 0.78]); ax.set_aspect("equal")
        _draw_outline(ax, prims)
        mx = max(w, h) * 0.62
        ax.set_xlim(-w / 2 - mx * 0.12, w / 2 + mx * 0.12)
        ax.set_ylim(-h / 2 - mx * 0.14, h / 2 + mx * 0.12)
        yb = -h / 2 - mx * 0.06
        ax.annotate("", (-w / 2, yb), (w / 2, yb), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax.text(0, yb - mx * 0.03, f"{w:.0f} mm (chapa)", ha="center", va="top", fontsize=10)
        xb = -w / 2 - mx * 0.06
        ax.annotate("", (xb, -h / 2), (xb, h / 2), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax.text(xb - mx * 0.02, 0, f"{h:.0f} mm", ha="right", va="center", rotation=90, fontsize=10)
        ax.axis("off")
        peso = prims.get("area", 0) * (prims.get("esp", 0) or 0) * 7.93e-6
        esptxt = ", ".join(info.get("espelhos", [])) or "lisa (sem espelho)"
        txt = (f"{prims.get('name','bancada')}   |   Externa {info.get('comprimento_ext',0):.0f} x "
               f"{info.get('profundidade_ext',0):.0f} mm  (interna {info.get('comprimento_int',0):.0f} x "
               f"{info.get('profundidade_int',0):.0f})   |   espelho: {esptxt}   |   "
               f"cubas: {info.get('cubas',0)}   |   esp. {prims.get('esp',0):g} mm   |   ~{peso:.1f} kg (inox)")
        fig.text(0.06, 0.085, txt, fontsize=10)
        fig.text(0.06, 0.05, "METALLO / CONCETTO - Bancada inox - 1o processo (corte). "
                 "Vermelho=corte, azul=cuba, verde tracejado=dobra.", fontsize=8, color="0.3")
        pp.savefig(fig); plt.close(fig)
    return buf.getvalue()


def _fmt(v):
    return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def folha_projeto(prims, img3d_bytes=None, cliente="", data="", qtd=1,
                  escala="", desenhista="Metallo", material=None):
    """Folha de projeto A3 (paisagem) padrão NBR: moldura + legenda com logo,
    planificação cotada e vista 3D. Retorna bytes PDF."""
    import datetime
    import matplotlib.image as mpimg
    try:
        from metallo_cad.config import LOGO
    except Exception:
        LOGO = None
    info = prims.get("info", {})
    w, h = prims["bbox"]
    esp = prims.get("esp", 0) or 0
    peso = prims.get("area", 0) * esp * 7.93e-6
    data = data or datetime.date.today().strftime("%d/%m/%Y")
    material = material or f"Inox 304 {esp:g} mm"
    esptxt = ", ".join(info.get("espelhos", [])) or "lisa (sem espelho)"

    buf = io.BytesIO()
    with PdfPages(buf) as pp:
        fig = plt.figure(figsize=(16.54, 11.69))
        bg = fig.add_axes([0, 0, 1, 1]); bg.set_xlim(0, 420); bg.set_ylim(0, 297); bg.axis("off")
        # moldura NBR (dupla)
        bg.add_patch(plt.Rectangle((8, 8), 404, 281, fill=False, lw=1.6))
        bg.add_patch(plt.Rectangle((11, 11), 398, 275, fill=False, lw=0.6))

        # ---------- legenda (title block) canto inferior direito ----------
        TBw, TBh = 196, 50
        TBx, TBy = 409 - TBw, 11
        lbw = 54
        bg.add_patch(plt.Rectangle((TBx, TBy), TBw, TBh, fill=False, lw=1.2))
        bg.plot([TBx + lbw, TBx + lbw], [TBy, TBy + TBh], color="k", lw=0.7)
        bg.plot([TBx + lbw, TBx + TBw], [TBy + TBh - 13, TBy + TBh - 13], color="k", lw=0.7)
        bg.text((TBx + lbw + TBx + TBw) / 2, TBy + TBh - 6.5, prims.get("name", "Bancada"),
                fontsize=12.5, weight="bold", va="center", ha="center")
        # grade de campos 3 col x 3 lin
        fx0 = TBx + lbw; fw = TBw - lbw; fy1 = TBy + TBh - 13
        colw = fw / 3.0; rowh = (fy1 - TBy) / 3.0
        for i in range(1, 3):
            bg.plot([fx0 + i * colw, fx0 + i * colw], [TBy, fy1], color="k", lw=0.4)
        for j in range(1, 3):
            bg.plot([fx0, fx0 + fw], [TBy + j * rowh, TBy + j * rowh], color="k", lw=0.4)

        def campo(ci, rj, rot, val):
            cx = fx0 + ci * colw; cy = TBy + rj * rowh
            bg.text(cx + 1.6, cy + rowh - 1.6, rot, fontsize=5.6, color="0.35", va="top")
            bg.text(cx + colw / 2, cy + rowh * 0.36, val, fontsize=8.2, weight="bold",
                    ha="center", va="center")
        campo(0, 2, "MATERIAL", material)
        campo(1, 2, "ESPESSURA", f"{esp:g} mm")
        campo(2, 2, "PESO (un.)", f"{peso:.1f} kg")
        campo(0, 1, "EXTERNA (mm)", f"{_fmt(info.get('comprimento_ext',0))}x{_fmt(info.get('profundidade_ext',0))}")
        campo(1, 1, "INTERNA (mm)", f"{_fmt(info.get('comprimento_int',0))}x{_fmt(info.get('profundidade_int',0))}")
        campo(2, 1, "CHAPA (mm)", f"{_fmt(w)}x{_fmt(h)}")
        campo(0, 0, "QUANT.", str(int(qtd)))
        campo(1, 0, "DATA", data)
        campo(2, 0, "ESCALA", escala or "S/ esc.")
        # rodapé da legenda: cliente/desenhista + norma
        bg.text(TBx + lbw + 1.6, TBy - 3.2, f"Cliente: {cliente or '-'}   ·   Des.: {desenhista}   ·   NBR 8403/10068/16752",
                fontsize=5.4, color="0.4", va="top")
        # logo
        if LOGO is not None:
            try:
                im = mpimg.imread(str(LOGO))
                la = fig.add_axes([(TBx + 2) / 420, (TBy + 3) / 297, (lbw - 4) / 420, (TBh - 6) / 297])
                la.imshow(im); la.axis("off")
            except Exception:
                bg.text(TBx + lbw / 2, TBy + TBh / 2, "METALLO", fontsize=10, weight="bold",
                        ha="center", va="center", rotation=0)

        # ---------- planificação cotada ----------
        axd = fig.add_axes([0.045, 0.20, 0.55, 0.73]); axd.set_aspect("equal")
        _draw_outline(axd, prims)
        mx = max(w, h) * 0.6
        axd.set_xlim(-w / 2 - mx * 0.16, w / 2 + mx * 0.16)
        axd.set_ylim(-h / 2 - mx * 0.18, h / 2 + mx * 0.16)
        yb = -h / 2 - mx * 0.07
        axd.annotate("", (-w / 2, yb), (w / 2, yb), arrowprops=dict(arrowstyle="<->", lw=0.7))
        axd.text(0, yb - mx * 0.035, f"{_fmt(w)}", ha="center", va="top", fontsize=10)
        xb = -w / 2 - mx * 0.07
        axd.annotate("", (xb, -h / 2), (xb, h / 2), arrowprops=dict(arrowstyle="<->", lw=0.7))
        axd.text(xb - mx * 0.03, 0, f"{_fmt(h)}", ha="right", va="center", rotation=90, fontsize=10)
        axd.axis("off")
        fig.text(0.045, 0.945, "PLANIFICAÇÃO (corte a laser)", fontsize=11, weight="bold")
        fig.text(0.045, 0.17, "Vermelho = contorno + alívio (corte)  ·  azul = recorte de cuba  ·  "
                 "verde tracejado = linha de dobra (referência, NÃO cortar).", fontsize=7.5, color="0.35")

        # ---------- vista 3D ----------
        if img3d_bytes:
            try:
                a3 = fig.add_axes([0.62, 0.40, 0.35, 0.52])
                a3.imshow(mpimg.imread(io.BytesIO(img3d_bytes))); a3.axis("off")
                fig.text(0.795, 0.93, "VISTA 3D (peça montada)", fontsize=11, weight="bold", ha="center")
            except Exception:
                pass
        # ficha resumo (espelhos/alívios)
        resumo = (f"Espelhos: {esptxt}\n"
                  f"Altura espelho: {info.get('espelho_altura',0):g} mm  ·  aba: {info.get('aba',0):g} mm\n"
                  f"Alívios: {info.get('n_rasgos',0)}  ·  esquadrias: {info.get('n_esquadrias',0)}  ·  cubas: {info.get('cubas',0)}\n"
                  f"Dobra do espelho: {'para fora (+20 mm)' if info.get('dobra_fora', True) else 'para dentro'}")
        fig.text(0.62, 0.24, resumo, fontsize=8.5, va="top", family="monospace")
        pp.savefig(fig); plt.close(fig)
    return buf.getvalue()


def etiqueta_itens(prims, qtd=1):
    """Monta os itens p/ etiquetas.gerar_etiquetas_pdf a partir da bancada."""
    info = prims.get("info", {})
    esp = prims.get("esp", 0) or 0
    desc = (f"{prims.get('name','Bancada')}  "
            f"{_fmt(info.get('comprimento_ext',0))}x{_fmt(info.get('profundidade_ext',0))} mm")
    return [{"descricao": desc, "material": f"Inox 304 {esp:g}mm", "qtd": max(int(qtd), 1)}]


def dobra_pdf(prims):
    """Plano de corte de DOBRA (2o processo): linhas de dobra cotadas + sequencia."""
    info = prims.get("info", {})
    w, h = prims["bbox"]
    he = info.get("espelho_altura", 0); hs = info.get("aba", 0)
    buf = io.BytesIO()
    with PdfPages(buf) as pp:
        fig = plt.figure(figsize=(16.54, 11.69))
        ax = fig.add_axes([0.06, 0.30, 0.9, 0.64]); ax.set_aspect("equal")
        # painel (so contorno fraco) + dobras em destaque
        o = prims["outer"][1]
        ax.plot([p[0] for p in o] + [o[0][0]], [p[1] for p in o] + [o[0][1]], "-", color="0.6", lw=0.8)
        seq = []
        for k, d in enumerate(prims.get("dobras", []), 1):
            seg = d[1]
            ax.plot([p[0] for p in seg], [p[1] for p in seg], "-", color="#d00", lw=1.6)
            mx = (seg[0][0] + seg[1][0]) / 2; my = (seg[0][1] + seg[1][1]) / 2
            ax.text(mx, my, f"D{k}", color="#d00", fontsize=9, ha="center", va="center",
                    bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec="#d00", lw=0.8))
            horizontal = abs(seg[0][1] - seg[1][1]) < 1e-6
            seq.append((k, "horizontal" if horizontal else "vertical",
                        round(seg[0][1] if horizontal else seg[0][0], 1)))
        mx = max(w, h) * 0.62
        ax.set_xlim(-w / 2 - mx * 0.10, w / 2 + mx * 0.10)
        ax.set_ylim(-h / 2 - mx * 0.10, h / 2 + mx * 0.10)
        ax.axis("off")
        fig.text(0.06, 0.26, f"PLANO DE DOBRA - {prims.get('name','bancada')}", fontsize=13, weight="bold")
        linhas = ["Sequencia sugerida (todas a 90 graus):",
                  f"  - Espelho(s): dobrar {he:g} mm para cima (+ dobra superior 20 + retorno 10).",
                  f"  - Aba lateral: dobrar {hs:g} mm para baixo (+ retorno 10 com esquadria).",
                  "  - Encontro de espelhos: dobrar a esquadria 45 graus (topo continuo).",
                  "  - Conferir os ALIVIOS nos cantos espelho x aba antes de dobrar.",
                  "",
                  "Linhas de dobra (D = marcada no desenho):"]
        for (k, ori, pos) in seq:
            linhas.append(f"  D{k}: {ori:10} @ {pos:.0f} mm")
        fig.text(0.06, 0.04, "\n".join(linhas), fontsize=9, va="bottom", family="monospace")
        fig.text(0.62, 0.04, "METALLO / CONCETTO - 2o processo (dobra).\n"
                 "Vermelho = linha de dobra. Angulos 90 graus salvo indicacao.", fontsize=8,
                 color="0.3", va="bottom")
        pp.savefig(fig); plt.close(fig)
    return buf.getvalue()
