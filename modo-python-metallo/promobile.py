"""Importação de listas do ProMobile (CSV/Excel) e geração dos arquivos da peça.

O CSV do ProMobile vem separado por ';', sem cabeçalho, com (entre outras) as colunas:
  0 descrição | 1 comprimento | 2 larg/diâm | 3 qtd | 5 perfil+espessura |
  7 módulo/ambiente | 8 ID peça | 12 obra/cliente | 13 cód item

Aqui interpretamos cada linha como um perfil reto (metalon / barra redonda / cantoneira)
cortado no comprimento, e geramos:
- o sólido 3D (para exportar IGES/STEP via exporters) — requer CadQuery na máquina do usuário;
- o adesivo de identificação por obra (PDF), totalmente verificável.
"""
from __future__ import annotations
import io
import csv as _csv
import re
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

COL = {"descricao": 0, "comprimento": 1, "larg": 2, "qtd": 3, "codigo": 4,
       "perfil": 5, "modulo": 7, "id": 8, "obra": 12, "cod_item": 13}


def _num(s):
    s = str(s or "").strip().replace(",", ".")
    m = re.search(r"-?\d+\.?\d*", s)
    return float(m.group()) if m else 0.0


def parse_csv(data, encoding="latin-1"):
    """Lê o CSV do ProMobile (bytes ou str). Retorna lista de dicts já classificados."""
    if isinstance(data, bytes):
        try:
            txt = data.decode(encoding)
        except Exception:
            txt = data.decode("utf-8", "ignore")
    else:
        txt = data
    linhas = list(_csv.reader(io.StringIO(txt), delimiter=";"))
    pecas = []
    for i, r in enumerate(linhas, 1):
        if len(r) < 9 or not (r[COL["descricao"]].strip() or r[COL["perfil"]].strip()):
            continue
        def g(k):
            j = COL[k]
            return r[j].strip() if len(r) > j else ""
        perfil_txt = g("perfil") or g("descricao")
        info = classificar(perfil_txt, g("descricao"), _num(g("larg")))
        pecas.append({
            "linha": i,
            "id": g("id") or str(i),
            "descricao": g("descricao"),
            "perfil_txt": perfil_txt,
            "comprimento": _num(g("comprimento")),
            "larg_csv": _num(g("larg")),
            "qtd": max(int(_num(g("qtd")) or 1), 1),
            "modulo": g("modulo"),
            "obra": g("obra"),
            "cod_item": g("cod_item"),
            **info,
        })
    return pecas


def classificar(perfil_txt, descricao="", larg_csv=0.0):
    """Detecta tipo (metalon/redonda/cantoneira), dimensões da seção, espessura e material."""
    t = (perfil_txt + " " + (descricao or "")).upper()
    material = "Inox 304" if "INOX" in t else ("Aço-carbono" if ("CARBONO" in t or "FERRO" in t) else "Aço")
    # espessura típica (1.2 / 1.20 / 1.5 / 2 ...) — primeiro decimal <= 6 que não seja dimensão da seção
    esp = 0.0
    for m in re.findall(r"(\d+[.,]\d{1,2})", t.replace(",", ".")):
        v = float(m)
        if 0.3 <= v <= 6.0:
            esp = v; break

    if "BARRA REDONDA" in t or "REDOND" in t or "VERGALH" in t:
        # diâmetro: decimal típico de bitola (ex.: 7.9) senão a col larg
        d = 0.0
        for m in re.findall(r"(\d+[.,]\d{1,2})", t.replace(",", ".")):
            v = float(m)
            if 3.0 <= v <= 60.0:
                d = v; break
        if d <= 0:
            d = larg_csv or 8.0
        return {"tipo": "barra_redonda", "secao": (d,), "esp": 0.0,
                "material": material, "rotulo": f"Barra redonda Ø{d:g}"}

    if "CANTONEIRA" in t:
        # aba (1/2-=12.7) — número antes de MM, senão col larg
        aba = larg_csv or 0.0
        mm = re.search(r"(\d+[.,]?\d*)\s*MM", t)
        if mm:
            aba = float(mm.group(1).replace(",", "."))
        if aba <= 0:
            aba = larg_csv or 25.4
        return {"tipo": "cantoneira", "secao": (aba, aba), "esp": esp or 0.0,
                "material": material, "rotulo": f"Cantoneira {aba:g}mm"}

    # METALON / tubo retangular: WxH
    mwh = re.search(r"(\d+)\s*[xX]\s*(\d+)", t)
    if mwh:
        W = float(mwh.group(1)); H = float(mwh.group(2))
    else:
        W = larg_csv or 30.0; H = larg_csv or 30.0
    return {"tipo": "metalon", "secao": (W, H), "esp": esp or 1.2,
            "material": material, "rotulo": f"Metalon {W:g}x{H:g}"}


def solido(peca, raio_metalon=0.0, esp_cantoneira=2.0):
    """Monta o Result 3D da peça (para exportar IGES/STEP). Requer CadQuery instalado."""
    from . import parts
    L = float(peca["comprimento"]) or 1.0
    tipo = peca["tipo"]
    if tipo == "barra_redonda":
        OD = float(peca["secao"][0])
        r = parts.barra_redonda(OD, L, bitola=peca.get("rotulo", ""))
    elif tipo == "cantoneira":
        aba = float(peca["secao"][0]); esp = float(peca.get("esp") or 0) or float(esp_cantoneira)
        r = parts.cantoneira(aba, esp, L, bitola=f"{aba:g}mm")
    else:  # metalon
        W, H = peca["secao"]; wall = float(peca.get("esp") or 1.2)
        r = parts.tubo_retangular_furos(float(W), float(H), wall, L, [], 0.0, raio=float(raio_metalon))
    # nome do arquivo: ID + perfil + comprimento
    base = f"{peca['id']}_{_slug(peca.get('rotulo','peca'))}_{L:g}mm"
    r.name = base
    return r


def _slug(s):
    return re.sub(r"[^\w\-]+", "_", str(s or "").strip())[:40] or "peca"


def _barcode128_bars(texto):
    """Code128-B simples -> lista de larguras de barras (alterna preto/branco). Sem dependências."""
    B = _C128B
    vals = []
    start = 104
    vals.append(start)
    soma = start
    for k, ch in enumerate(str(texto), 1):
        code = ord(ch) - 32
        if code < 0 or code > 94:
            code = 0
        vals.append(code); soma += code * k
    vals.append(soma % 103)            # checksum
    vals.append(106)                   # stop
    larguras = []
    for v in vals:
        larguras.extend(B[v])
    return larguras


def etiqueta_generica_pdf(itens, tamanho=(80.0, 40.0), barras=True):
    """Adesivo genérico (campos livres). Cada item:
       {titulo?, destaque, linhas:[...], codigo?, qtd?}. 1 página por unidade."""
    w, h = float(tamanho[0]), float(tamanho[1])
    buf = io.BytesIO()
    n = 0
    with PdfPages(buf) as pp:
        for it in itens:
            for _ in range(max(int(it.get("qtd", 1) or 1), 1)):
                n += 1
                fig = plt.figure(figsize=(w / 25.4, h / 25.4))
                ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, w); ax.set_ylim(0, h)
                ax.axis("off"); ax.set_aspect("equal")
                ax.add_patch(plt.Rectangle((0.6, 0.6), w - 1.2, h - 1.2, fill=False, lw=0.8))
                y = h - 3.0
                if it.get("titulo"):
                    ax.text(w / 2, y, str(it["titulo"])[:34], ha="center", va="top",
                            fontsize=6.5, weight="bold"); y -= 3.0
                if it.get("destaque"):
                    ax.text(2.0, y, str(it["destaque"])[:30], fontsize=10, weight="bold", va="top"); y -= 4.4
                for ln in (it.get("linhas") or [])[:5]:
                    ax.text(2.0, y, str(ln)[:46], fontsize=7, va="top", color="0.2"); y -= 3.0
                cod = it.get("codigo") or ""
                if barras and cod:
                    try:
                        larg = _barcode128_bars(cod)
                        total = sum(larg); x = 2.0; unit = (w - 4.0) / total; bh = 5.0; preto = True
                        for lw_ in larg:
                            if preto:
                                ax.add_patch(plt.Rectangle((x, 1.2), lw_ * unit, bh, color="black"))
                            x += lw_ * unit; preto = not preto
                        ax.text(w / 2, 1.0 + bh + 0.3, str(cod), ha="center", va="bottom", fontsize=5.5)
                    except Exception:
                        ax.text(w / 2, 2.0, str(cod), ha="center", fontsize=7)
                pp.savefig(fig); plt.close(fig)
        if n == 0:
            fig = plt.figure(figsize=(w / 25.4, h / 25.4)); pp.savefig(fig); plt.close(fig)
    return buf.getvalue()


def etiqueta_pdf(pecas, tamanho=(80.0, 40.0), barras=True, titulo_obra=True):
    """Adesivos do ProMobile — mapeia as peças para o formato genérico."""
    itens = []
    for p in pecas:
        linhas = [p.get("rotulo", ""),
                  f"Comp.: {p.get('comprimento', 0):g} mm   ·   Qtd: {p.get('qtd', 1)}"]
        if p.get("modulo"):
            linhas.append(f"Módulo: {p['modulo']}")
        if p.get("material"):
            linhas.append(p["material"])
        itens.append({"titulo": p.get("obra") if titulo_obra else "",
                      "destaque": f"PEÇA {p.get('id', '')}",
                      "linhas": linhas, "codigo": p.get("cod_item") or p.get("id") or "",
                      "qtd": p.get("qtd", 1)})
    return etiqueta_generica_pdf(itens, tamanho=tamanho, barras=barras)


# tabela Code128 (conjunto B) — padrões de barras (6 módulos por símbolo)
_C128B = [
    [2,1,2,2,2,2],[2,2,2,1,2,2],[2,2,2,2,2,1],[1,2,1,2,2,3],[1,2,1,3,2,2],[1,3,1,2,2,2],[1,2,2,2,1,3],
    [1,2,2,3,1,2],[1,3,2,2,1,2],[2,2,1,2,1,3],[2,2,1,3,1,2],[2,3,1,2,1,2],[1,1,2,2,3,2],[1,2,2,1,3,2],
    [1,2,2,2,3,1],[1,1,3,2,2,2],[1,2,3,1,2,2],[1,2,3,2,2,1],[2,2,3,2,1,1],[2,2,1,1,3,2],[2,2,1,2,3,1],
    [2,1,3,2,1,2],[2,2,3,1,1,2],[3,1,2,1,3,1],[3,1,1,2,2,2],[3,2,1,1,2,2],[3,2,1,2,2,1],[3,1,2,2,1,2],
    [3,2,2,1,1,2],[3,2,2,2,1,1],[2,1,2,1,2,3],[2,1,2,3,2,1],[2,3,2,1,2,1],[1,1,1,3,2,3],[1,3,1,1,2,3],
    [1,3,1,3,2,1],[1,1,2,3,1,3],[1,3,2,1,1,3],[1,3,2,3,1,1],[2,1,1,3,1,3],[2,3,1,1,1,3],[2,3,1,3,1,1],
    [1,1,2,1,3,3],[1,1,2,3,3,1],[1,3,2,1,3,1],[1,1,3,1,2,3],[1,1,3,3,2,1],[1,3,3,1,2,1],[3,1,3,1,2,1],
    [2,1,1,3,3,1],[2,3,1,1,3,1],[2,1,3,1,1,3],[2,1,3,3,1,1],[2,1,3,1,3,1],[3,1,1,1,2,3],[3,1,1,3,2,1],
    [3,3,1,1,2,1],[3,1,2,1,1,3],[3,1,2,3,1,1],[3,3,2,1,1,1],[3,1,4,1,1,1],[2,2,1,4,1,1],[4,3,1,1,1,1],
    [1,1,1,2,2,4],[1,1,1,4,2,2],[1,2,1,1,2,4],[1,2,1,4,2,1],[1,4,1,1,2,2],[1,4,1,2,2,1],[1,1,2,2,1,4],
    [1,1,2,4,1,2],[1,2,2,1,1,4],[1,2,2,4,1,1],[1,4,2,1,1,2],[1,4,2,2,1,1],[2,4,1,2,1,1],[2,2,1,1,1,4],
    [4,1,3,1,1,1],[2,4,1,1,1,2],[1,3,4,1,1,1],[1,1,1,2,4,2],[1,2,1,1,4,2],[1,2,1,2,4,1],[1,1,4,2,1,2],
    [1,2,4,1,1,2],[1,2,4,2,1,1],[4,1,1,2,1,2],[4,2,1,1,1,2],[4,2,1,2,1,1],[2,1,2,1,4,1],[2,1,4,1,2,1],
    [4,1,2,1,2,1],[1,1,1,1,4,3],[1,1,1,3,4,1],[1,3,1,1,4,1],[1,1,4,1,1,3],[1,1,4,3,1,1],[4,1,1,1,1,3],
    [4,1,1,3,1,1],[1,1,3,1,4,1],[1,1,4,1,3,1],[3,1,1,1,4,1],[4,1,1,1,3,1],[2,1,1,4,1,2],[2,1,1,2,1,4],
    [2,1,1,2,3,2],[2,3,3,1,1,1,2],
]
