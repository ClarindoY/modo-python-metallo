"""Nesting LINEAR (1D) de tubos/barras: distribui peças em barras de estoque.

- Agrupa por perfil (só encaixa peças do mesmo perfil na mesma barra).
- Empacota por First-Fit Decreasing, descontando o 'kerf' (largura do corte) por peça.
- Marca MICRO-JUNTA: peça curta que cai na ponta da barra (a sobra após ela é menor
  que a 'zona de micro-junta'), para a máquina mover o tubo sem cortá-lo por completo.

Tudo é cálculo/numérico — verificável aqui (não depende de CadQuery).
"""
from __future__ import annotations
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def empacotar(itens, barra=6000.0, kerf=3.0, zona_mj=700.0, min_mj=700.0):
    """itens: [{'perfil', 'comprimento', 'qtd', 'id'?}].
    Retorna lista (por perfil): {perfil, barras:[...], n_barras, total_pecas, impossiveis}.
    Cada barra: {pecas:[{comprimento,id,ini,fim,micro_junta}], usado, sobra, aproveitamento}."""
    barra = float(barra); kerf = float(kerf)
    zona_mj = float(zona_mj); min_mj = float(min_mj)
    grupos = {}
    for it in itens:
        perf = (str(it.get("perfil", "")).strip() or "Perfil")
        c = float(it.get("comprimento", 0) or 0)
        q = int(it.get("qtd", 1) or 1)
        if c <= 0 or q <= 0:
            continue
        grupos.setdefault(perf, []).extend(
            [{"comprimento": c, "id": str(it.get("id", ""))} for _ in range(q)])

    plano = []
    for perf, unidades in grupos.items():
        impossiveis = [u for u in unidades if u["comprimento"] + kerf > barra]
        unidades = [u for u in unidades if u["comprimento"] + kerf <= barra]
        unidades.sort(key=lambda u: u["comprimento"], reverse=True)
        barras = []
        for u in unidades:
            need = u["comprimento"] + kerf
            alvo = next((b for b in barras if b["restante"] >= need - 1e-6), None)
            if alvo is None:
                alvo = {"restante": barra, "pos": 0.0, "pecas": []}
                barras.append(alvo)
            ini = alvo["pos"]; fim = ini + u["comprimento"]
            alvo["pecas"].append({"comprimento": u["comprimento"], "id": u["id"],
                                  "ini": ini, "fim": fim})
            alvo["pos"] = fim + kerf
            alvo["restante"] = barra - alvo["pos"]
        for b in barras:
            usado = b["pecas"][-1]["fim"] if b["pecas"] else 0.0
            b["usado"] = usado
            b["sobra"] = barra - usado
            b["aproveitamento"] = (usado / barra) if barra else 0.0
            for p in b["pecas"]:
                rem_apos = barra - p["fim"]
                p["micro_junta"] = (p["comprimento"] < min_mj) and (rem_apos < zona_mj)
        plano.append({"perfil": perf, "barras": barras, "n_barras": len(barras),
                      "total_pecas": sum(len(b["pecas"]) for b in barras),
                      "impossiveis": impossiveis})
    return plano


def resumo(plano, barra=6000.0):
    """Totais gerais do plano."""
    n_barras = sum(p["n_barras"] for p in plano)
    n_pecas = sum(p["total_pecas"] for p in plano)
    usado = sum(b["usado"] for p in plano for b in p["barras"])
    total = n_barras * float(barra)
    sobra = total - usado
    mj = sum(1 for p in plano for b in p["barras"] for pc in b["pecas"] if pc["micro_junta"])
    return {"barras": n_barras, "pecas": n_pecas, "aproveitamento": (usado / total) if total else 0.0,
            "sobra_total_mm": sobra, "sobra_total_m": sobra / 1000.0, "micro_juntas": mj}


def sequencia_corte(plano):
    """Lista plana na ordem de corte (perfil → barra → peça), p/ alimentar a Produção."""
    seq = []
    n = 0
    for p in plano:
        for bi, b in enumerate(p["barras"], 1):
            for pc in b["pecas"]:
                n += 1
                seq.append({"seq": n, "perfil": p["perfil"], "barra": bi,
                            "comprimento": pc["comprimento"], "id": pc["id"],
                            "micro_junta": pc["micro_junta"], "ini": pc["ini"], "fim": pc["fim"]})
    return seq


def plano_png(plano, barra=6000.0, zona_mj=700.0, max_barras=24):
    """Diagrama: cada barra como faixa horizontal com as peças; micro-juntas em destaque."""
    linhas = [(p["perfil"], bi, b) for p in plano for bi, b in enumerate(p["barras"], 1)]
    linhas = linhas[:max_barras]
    if not linhas:
        fig = plt.figure(figsize=(6, 1)); buf = io.BytesIO()
        fig.savefig(buf, format="png"); plt.close(fig); return buf.getvalue()
    h = max(1.2, 0.5 * len(linhas) + 0.6)
    fig = plt.figure(figsize=(9, h)); ax = fig.add_axes([0.16, 0.10, 0.80, 0.84])
    cores = ["#4C78A8", "#72B7B2", "#54A24B", "#EECA3B", "#E45756", "#B279A2", "#FF9DA6", "#9D755D"]
    for row, (perf, bi, b) in enumerate(linhas):
        y = len(linhas) - 1 - row
        ax.add_patch(plt.Rectangle((0, y + 0.12), barra, 0.76, fill=False, ec="0.6", lw=0.8))
        # zona de micro-junta (últimos zona_mj mm)
        ax.add_patch(plt.Rectangle((barra - zona_mj, y + 0.12), zona_mj, 0.76,
                                   color="#ffe0e0", alpha=0.6, lw=0))
        for k, pc in enumerate(b["pecas"]):
            cor = cores[k % len(cores)]
            ax.add_patch(plt.Rectangle((pc["ini"], y + 0.16), pc["comprimento"], 0.68,
                                       color=cor, ec="white", lw=0.6))
            if pc["comprimento"] >= barra * 0.045:
                ax.text(pc["ini"] + pc["comprimento"] / 2, y + 0.5, f"{pc['comprimento']:g}",
                        ha="center", va="center", fontsize=6.5, color="white")
            if pc["micro_junta"]:
                ax.plot([pc["fim"], pc["fim"]], [y + 0.10, y + 0.90], color="#c00", lw=2.0)
                ax.text(pc["fim"], y + 0.96, "MJ", ha="center", va="bottom", fontsize=6, color="#c00")
        if b["sobra"] > 1:
            ax.text(b["usado"] + b["sobra"] / 2, y + 0.5, f"sobra {b['sobra']:g}",
                    ha="center", va="center", fontsize=6, color="0.4")
        ax.text(-barra * 0.015, y + 0.5, f"{perf}  #{bi}", ha="right", va="center", fontsize=7)
    ax.set_xlim(-barra * 0.18, barra * 1.02); ax.set_ylim(0, len(linhas))
    ax.set_yticks([]); ax.set_xlabel("mm"); ax.spines[["top", "right", "left"]].set_visible(False)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120); plt.close(fig)
    return buf.getvalue()
