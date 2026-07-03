"""
Gerador de etiquetas / adesivos de peça (e ordem de produção) para o Metallo.

Cada etiqueta traz: descrição/medida, material, data, ordem de produção e,
opcionalmente, o nome do cliente. Gera 1 adesivo por página no tamanho físico
escolhido (60×40 mm, 150×50 mm ou personalizado) — pronto para impressora de
etiquetas ou para imposição em folha adesiva. Para uma ordem com várias peças,
gera todos os adesivos (qtd por peça) num único PDF.
"""
from __future__ import annotations
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle

# tamanhos pré-definidos (largura × altura em mm)
TAMANHOS = {
    "60 × 40 mm": (60.0, 40.0),
    "150 × 50 mm": (150.0, 50.0),
}


def _fs(h, frac, txt="", largura_util=None):
    """Tamanho de fonte (pt) proporcional à altura; encolhe se o texto for longo."""
    base = h * frac
    if largura_util and txt:
        # ~0.6*fs por caractere de largura média; limita p/ caber
        max_fs = largura_util * 1.8 / max(len(str(txt)), 1)
        base = min(base, max_fs)
    return max(base, 3.0)


def _desenha_etiqueta(ax, w, h, descricao, material, data, ordem, cliente, idx, total):
    m = max(1.2, h * 0.05)
    iw = w - 2 * m                      # largura util interna
    ax.add_patch(Rectangle((m, m), iw, h - 2 * m, fill=False, lw=1.1))
    # cabeçalho preto
    hb = h * 0.24
    ax.add_patch(Rectangle((m, h - m - hb), iw, hb, fill=True, fc="black", ec="black"))
    ax.text(m + iw * 0.03, h - m - hb / 2, "METALLO", color="white",
            fontsize=_fs(h, 0.20), va="center", weight="bold")
    if str(ordem).strip():
        ax.text(w - m - iw * 0.03, h - m - hb / 2, f"OP {ordem}", color="white",
                fontsize=_fs(h, 0.17), va="center", ha="right", weight="bold")
    yb = h - m - hb                     # topo da área de conteúdo
    area = yb - m
    # descrição / medida (destaque)
    ax.text(w / 2, yb - area * 0.30, str(descricao),
            fontsize=_fs(h, 0.27, descricao, iw), ha="center", va="center", weight="bold")
    # linha material | data
    ax.text(m + iw * 0.03, m + area * 0.42, f"Material: {material}",
            fontsize=_fs(h, 0.155, f'Material: {material}', iw * 0.62), va="center")
    ax.text(w - m - iw * 0.03, m + area * 0.42, str(data),
            fontsize=_fs(h, 0.155), va="center", ha="right")
    # cliente (opcional) + contador
    if cliente and str(cliente).strip():
        ax.text(m + iw * 0.03, m + area * 0.16, f"Cliente: {cliente}",
                fontsize=_fs(h, 0.145, f'Cliente: {cliente}', iw * 0.75), va="center")
    ax.text(w - m - iw * 0.03, m + area * 0.16, f"{idx}/{total}",
            fontsize=_fs(h, 0.13), va="center", ha="right", color="0.35")


def gerar_etiquetas_pdf(itens, tamanho=(60.0, 40.0), data="", ordem="", cliente=None):
    """
    itens   : lista de dicts {descricao, material, qtd}
    tamanho : (largura_mm, altura_mm)
    Gera 1 página por adesivo (qtd por item). Devolve bytes do PDF.
    """
    w, h = float(tamanho[0]), float(tamanho[1])
    # total para o contador i/total
    total = sum(max(int(it.get("qtd", 1) or 1), 1) for it in itens) or 1
    buf = io.BytesIO()
    idx = 0
    with PdfPages(buf) as pp:
        for it in itens:
            desc = it.get("descricao", "") or ""
            mat = it.get("material", "") or ""
            q = max(int(it.get("qtd", 1) or 1), 1)
            for _ in range(q):
                idx += 1
                fig = plt.figure(figsize=(w / 25.4, h / 25.4))
                ax = fig.add_axes([0, 0, 1, 1])
                ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off"); ax.set_aspect("equal")
                _desenha_etiqueta(ax, w, h, desc, mat, data, ordem, cliente, idx, total)
                pp.savefig(fig); plt.close(fig)
        if idx == 0:   # nenhum item válido -> 1 página em branco evita PDF inválido
            fig = plt.figure(figsize=(w / 25.4, h / 25.4)); plt.close(fig)
    return buf.getvalue()
