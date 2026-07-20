"""
iTubeCAM — preparação de peças para o software de nesting 3D da laser de tubo
(FLCNC / Fangling iTubeCAM).

Validado contra o manual oficial (Zhuo Chang SinoCAM 3D, mesma família do
iTubeCAM, ed. out/2024): o software importa IGS, STEP/STP, SAT/SAB, IFC,
DSTV NC1, DWG/DXF e GEN; extrai as linhas de corte do sólido importado;
detecta a direção do eixo automaticamente; a QUANTIDADE é propriedade da
peça informada no software; e o cadastro de "custom pipe" aceita apenas
seção FECHADA em DWG/DXF. Este módulo gera:

  - tubo_peca(...)  : UM tubo retangular OCO (parede real) com as esquadrias
                      já cortadas nas pontas -> Result exportável em IGS/STEP
                      pelo fluxo padrão do app.
  - lote_igs(...)   : várias peças de uma vez -> .zip com um IGS por peça
                      (importação em lote no iTubeCAM) + lista.csv de conferência.
  - secao_dxf(...)  : DXF de contorno fechado (externo + interno) da seção do
                      tubo, para cadastro de "tubo personalizado" no iTubeCAM.

Convenções:
  - Peça ao longo do eixo X; comprimento L medido na ARESTA EXTERNA (a mais
    longa), como nas demais listas de corte do kit.
  - Ângulo do corte em graus a partir do corte reto: 0 = reto 90°,
    45 = meia esquadria. Cortes das duas pontas convergem (peça trapezoidal,
    padrão de quadro soldado).
  - plano = "largura": a esquadria atravessa a largura w (vista em planta).
    plano = "altura" : a esquadria atravessa a altura h (vista de frente).
"""
import io
import math
import zipfile


# ---------------------------------------------------------------- peça de tubo
def tubo_peca(w, h, esp, L, corte_esq=45.0, corte_dir=45.0,
              plano="largura", nome=None):
    """
    Tubo retangular OCO w x h, parede esp, comprimento L (aresta externa),
    com esquadrias corte_esq / corte_dir (graus; 0 = corte reto).

    Retorna Result (kind='tubo_itc') pronto para IGS/STEP individuais.
    """
    import cadquery as cq
    from .parts import Result
    from .config import DENSIDADE

    w, h, esp, L = float(w), float(h), float(esp), float(L)
    ce, cd = float(corte_esq), float(corte_dir)
    if plano not in ("largura", "altura"):
        raise ValueError("plano deve ser 'largura' ou 'altura'.")
    if esp * 2 >= min(w, h):
        raise ValueError("Espessura maior que o meio da seção.")
    span = w if plano == "largura" else h
    rec = span * (math.tan(math.radians(ce)) + math.tan(math.radians(cd)))
    if L <= rec + 2:
        raise ValueError("Comprimento pequeno demais para os ângulos escolhidos.")
    for c in (ce, cd):
        if not (0 <= c <= 75):
            raise ValueError("Ângulo de corte deve estar entre 0 e 75 graus.")

    # tubo oco ao longo de X (seção centrada em YZ)
    o = cq.Workplane("YZ").rect(w, h).extrude(L)
    i = cq.Workplane("YZ").rect(w - 2 * esp, h - 2 * esp).extrude(L)
    tubo = o.cut(i)

    # cortes por prisma explícito no plano da esquadria
    M = 4 * (w + h + L)
    def prisma(pts_xu):
        if plano == "largura":
            wp = cq.Workplane("XY").polyline(pts_xu).close().extrude(2 * M)
            return wp.translate((0, 0, -M))
        # Workplane("XZ") extruda ao longo de -Y: centraliza transladando +M
        wp = cq.Workplane("XZ").polyline(pts_xu).close().extrude(2 * M)
        return wp.translate((0, M, 0))

    u_hi, u_lo = span / 2, -span / 2
    if ce > 0:
        d = span * math.tan(math.radians(ce))
        # plano de corte passa por (0, u_hi) e (d, u_lo); remove x menor
        tubo = tubo.cut(prisma([(0, u_hi + M), (d, u_lo - M),
                                (d - 3 * M, u_lo - M), (-3 * M, u_hi + M)]))
    else:
        pass  # ponta reta: já é a face x=0
    if cd > 0:
        d = span * math.tan(math.radians(cd))
        # plano por (L, u_hi) e (L-d, u_lo); remove x maior
        tubo = tubo.cut(prisma([(L, u_hi + M), (L - d, u_lo - M),
                                (L - d + 3 * M, u_lo - M), (L + 3 * M, u_hi + M)]))

    sec = w * h - (w - 2 * esp) * (h - 2 * esp)
    L_med = L - rec / 2.0
    massa = L_med * sec * DENSIDADE

    rot = []
    for c, lado in ((ce, "esq"), (cd, "dir")):
        rot.append(f"{lado} {'reto 90' if c == 0 else f'esquadria {c:g}'}")
    cut_list = [
        (f"Tubo {w:g}x{h:g} esp {esp:g}", 1, round(L),
         " + ".join(rot) + f" (na {plano})"),
    ]
    nome = nome or f"Tubo_{w:g}x{h:g}x{esp:g}_L{L:g}_{ce:g}-{cd:g}"
    nome = str(nome).replace(" ", "_")
    return Result(
        shape=tubo.val().wrapped, solid=tubo, name=nome, kind="tubo_itc",
        dims=(L, w, h), wall=esp, mass=massa, cut_list=cut_list,
        extra=dict(w=w, h=h, esp=esp, L=L, ce=ce, cd=cd, plano=plano,
                   L_curta=L - rec, L_med=L_med, sec=sec),
    )


# ---------------------------------------------------------------- lote p/ importação em massa
def lote_igs(pecas, incluir_step=False):
    """
    Gera um .zip com UM arquivo IGS por peça (o iTubeCAM importa em lote)
    + lista.csv de conferência. `pecas` = lista de dicts:
      {nome, w, h, esp, L, ce, cd, plano, qtd}
    A quantidade vai no nome do arquivo (o nesting usa a qtd na importação).
    Retorna (zip_bytes, avisos).
    """
    import tempfile
    from pathlib import Path
    from . import exporters

    avisos = []
    buf = io.BytesIO()
    linhas = ["item;nome;secao;espessura;comprimento;corte_esq;corte_dir;plano;qtd"]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for k, p in enumerate(pecas, start=1):
                try:
                    qtd = int(p.get("qtd", 1) or 1)
                    r = tubo_peca(p["w"], p["h"], p["esp"], p["L"],
                                  corte_esq=p.get("ce", 45), corte_dir=p.get("cd", 45),
                                  plano=p.get("plano", "largura"),
                                  nome=p.get("nome") or None)
                    base = f"{k:02d}_{r.name}_x{qtd}"
                    ig = d / f"{base}.igs"
                    exporters.to_iges(r, ig)
                    z.write(ig, f"iTubeCAM/{base}.igs")
                    if incluir_step:
                        stp = d / f"{base}.step"
                        exporters.to_step(r, stp)
                        z.write(stp, f"iTubeCAM/{base}.step")
                    e = r.extra
                    linhas.append(
                        f"{k};{r.name};{e['w']:g}x{e['h']:g};{e['esp']:g};"
                        f"{e['L']:g};{e['ce']:g};{e['cd']:g};{e['plano']};{qtd}")
                except Exception as exc:                     # não derruba o lote
                    avisos.append(f"Peça {k} ({p.get('nome', '?')}): {exc}")
        z.writestr("iTubeCAM/lista.csv", "\n".join(linhas))
    return buf.getvalue(), avisos


# ---------------------------------------------------------------- seção personalizada (DXF)
def secao_dxf(w, h, esp, raio=0.0):
    """
    DXF da seção do tubo em contorno FECHADO (externo + interno) — formato que
    o iTubeCAM aceita no cadastro de tubo personalizado. Cantos com raio
    opcional (arcos por bulge). Retorna bytes.
    """
    import ezdxf
    w, h, esp, raio = float(w), float(h), float(esp), float(raio)
    if esp * 2 >= min(w, h):
        raise ValueError("Espessura maior que o meio da seção.")
    raio = min(raio, min(w, h) / 2 - 0.1) if raio > 0 else 0.0
    ri = max(raio - esp, 0.0)

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.layers.add("SECAO", color=7)
    msp = doc.modelspace()
    B = math.tan(math.radians(90) / 4)      # bulge de arco 90°

    def anel(cx, cy, ww, hh, r):
        x0, y0 = cx - ww / 2, cy - hh / 2
        x1, y1 = cx + ww / 2, cy + hh / 2
        if r <= 0:
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "SECAO"})
            return
        pts = [
            (x0 + r, y0, 0), (x1 - r, y0, B), (x1, y0 + r, 0),
            (x1, y1 - r, B), (x1 - r, y1, 0), (x0 + r, y1, B),
            (x0, y1 - r, 0), (x0, y0 + r, B),
        ]
        msp.add_lwpolyline(pts, format="xyb", close=True,
                           dxfattribs={"layer": "SECAO"})

    anel(0, 0, w, h, raio)
    anel(0, 0, w - 2 * esp, h - 2 * esp, ri)

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")
