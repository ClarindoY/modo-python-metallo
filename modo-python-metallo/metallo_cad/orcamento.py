"""Geração de orçamento (cotação) em PDF para enviar ao cliente."""
from __future__ import annotations
import io
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

try:
    from .config import EMPRESA, LINHA
except Exception:
    EMPRESA = "METALLO IND. DE AÇOS DO NORDESTE LTDA"
    LINHA = "Linha CONCETTO"


def _moeda(v):
    return ("R$ %0.2f" % float(v)).replace(",", "X").replace(".", ",").replace("X", ".")


def orcamento_pdf(itens, cliente="", contato="", numero="", validade_dias=10,
                  desconto=0.0, observacoes="", rate_info="", empresa=EMPRESA, linha=LINHA):
    """itens: lista de dicts {descricao, material, esp, qtd, unit, subtotal, peso, tempo}.
    Retorna bytes de um PDF A4 retrato com cabeçalho, tabela e totais."""
    hoje = datetime.date.today()
    validade = hoje + datetime.timedelta(days=int(validade_dias or 0))
    subtotal = sum(float(i.get("subtotal", 0) or 0) for i in itens)
    total = max(subtotal - float(desconto or 0), 0.0)
    peso_tot = sum(float(i.get("peso", 0) or 0) * float(i.get("qtd", 1) or 1) for i in itens)

    buf = io.BytesIO()
    with PdfPages(buf) as pp:
        fig = plt.figure(figsize=(8.27, 11.69))                 # A4 retrato
        ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
        ax.set_xlim(0, 100); ax.set_ylim(0, 100)

        # cabeçalho
        ax.add_patch(plt.Rectangle((6, 90), 88, 6.5, color="#111"))
        ax.text(7.5, 93.2, empresa, color="white", fontsize=12, weight="bold", va="center")
        ax.text(94, 93.2, "ORÇAMENTO", color="white", fontsize=12, weight="bold", va="center", ha="right")
        ax.text(7.5, 88, linha, fontsize=8, color="0.3")
        ax.text(94, 88, f"Nº {numero or hoje.strftime('%Y%m%d')}", fontsize=8, color="0.3", ha="right")

        # bloco cliente / datas
        ax.text(7.5, 83.5, "CLIENTE", fontsize=8, weight="bold", color="0.4")
        ax.text(7.5, 80.8, cliente or "—", fontsize=11, weight="bold")
        if contato:
            ax.text(7.5, 78.4, contato, fontsize=9, color="0.3")
        ax.text(94, 83.5, f"Data: {hoje.strftime('%d/%m/%Y')}", fontsize=9, ha="right")
        ax.text(94, 81.2, f"Validade: {validade.strftime('%d/%m/%Y')} ({validade_dias} dias)",
                fontsize=9, ha="right", color="0.3")

        # cabeçalho da tabela
        y = 74.5
        ax.add_patch(plt.Rectangle((6, y - 1.2), 88, 3.0, color="#e9eef5"))
        cols = [("#", 8.0, "left"), ("Descrição", 11.0, "left"), ("Material", 47.0, "left"),
                ("Qtd", 66.0, "right"), ("Vlr unit.", 80.0, "right"), ("Subtotal", 93.5, "right")]
        for label, x, ha in cols:
            ax.text(x, y, label, fontsize=8.2, weight="bold", ha=ha, va="center")

        # linhas
        y -= 4.0
        rh = 4.6
        for k, it in enumerate(itens, 1):
            if y < 24:                                          # nova página simples se estourar
                ax.text(50, 22, "(continua…)", fontsize=8, ha="center", color="0.5")
                break
            if k % 2 == 0:
                ax.add_patch(plt.Rectangle((6, y - rh + 1.2), 88, rh, color="#f6f8fb"))
            ax.text(8.0, y, str(k), fontsize=8.5, va="center")
            ax.text(11.0, y, str(it.get("descricao", ""))[:34], fontsize=8.5, va="center")
            mat = str(it.get("material", ""))
            if it.get("esp"):
                mat += f" {it['esp']:g}mm"
            ax.text(47.0, y, mat[:22], fontsize=8.0, va="center", color="0.3")
            ax.text(66.0, y, f"{int(it.get('qtd', 1))}", fontsize=8.5, va="center", ha="right")
            ax.text(80.0, y, _moeda(it.get("unit", 0)), fontsize=8.5, va="center", ha="right")
            ax.text(93.5, y, _moeda(it.get("subtotal", 0)), fontsize=8.5, va="center", ha="right")
            y -= rh

        # totais
        ax.plot([6, 94], [y + 1.0, y + 1.0], color="0.6", lw=0.8)
        y -= 1.0
        ax.text(80.0, y, "Subtotal", fontsize=9, ha="right"); ax.text(93.5, y, _moeda(subtotal), fontsize=9, ha="right"); y -= 4.0
        if desconto and desconto > 0:
            ax.text(80.0, y, "Desconto", fontsize=9, ha="right")
            ax.text(93.5, y, "- " + _moeda(desconto), fontsize=9, ha="right", color="#a00"); y -= 4.0
        ax.add_patch(plt.Rectangle((58, y - 1.4), 36, 5.2, color="#111"))
        ax.text(63, y + 1.2, "TOTAL", fontsize=10.5, weight="bold", color="white", va="center")
        ax.text(93.5, y + 1.2, _moeda(total), fontsize=11.5, weight="bold", color="white", va="center", ha="right")
        y -= 8.0

        if peso_tot > 0:
            ax.text(7.5, y, f"Peso total estimado: ~ {peso_tot:.2f} kg" + (f"   ·   {rate_info}" if rate_info else ""),
                    fontsize=8, color="0.4"); y -= 4.0

        # observações + rodapé
        if observacoes:
            ax.text(7.5, y, "Observações:", fontsize=8.5, weight="bold"); y -= 3.2
            for ln in str(observacoes).split("\n")[:6]:
                ax.text(7.5, y, ln[:95], fontsize=8, color="0.3"); y -= 3.0
        ax.text(50, 6, "Orçamento gerado pelo sistema Metallo / Concetto · valores sujeitos a confirmação.",
                fontsize=7, color="0.55", ha="center")
        pp.savefig(fig); plt.close(fig)
    return buf.getvalue()
