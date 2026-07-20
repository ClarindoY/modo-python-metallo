"""
Puxadores em tubo inox — dois modelos:

  puxador_tradicional : tubo RETO (redondo ou quadrado). Os dois furos de
      fixação são simétricos ao CENTRO do tubo, afastados "entre furos" um
      do outro, com diâmetro informado. Furos atravessam só a parede
      traseira (face voltada à porta).

  puxador_u : tubo RETANGULAR (40x20 ou 40x15) em forma de U/C — uma PEGA
      frontal com meia esquadria 45° nas duas pontas + duas PERNAS com
      esquadria 45° em cima e corte reto no pé. Furo pequeno opcional no
      LADO MENOR de cada perna (face voltada à porta), a uma distância
      configurável do pé. As três peças também saem individuais em
      r.parts (IGS/STEP separados, prontos para o iTubeCAM).
"""
import math

from .parts import Result
from .config import DENSIDADE


# ---------------------------------------------------------------- tradicional
def puxador_tradicional(secao, medida, esp, L, entre_furos, d_furo=5.0,
                        medida_h=None, raio=0.0):
    """
    secao       : "redondo", "quadrado" ou "retangular"
    medida      : diâmetro (redondo), lado (quadrado) ou LARGURA (retangular), mm
    medida_h    : profundidade do tubo retangular (obrigatório p/ retangular), mm
    esp         : espessura da parede, mm
    L           : comprimento total do tubo, mm
    entre_furos : distância entre os eixos dos 2 furos, CENTRADA no tubo, mm
    d_furo      : diâmetro dos furos, mm
    raio        : raio do canto (quadrado/retangular), mm — 0 = canto vivo
    """
    import cadquery as cq
    from .parts import _sec_tubo

    secao = str(secao).lower()
    medida, esp, L = float(medida), float(esp), float(L)
    EF, d, raio = float(entre_furos), float(d_furo), max(float(raio or 0.0), 0.0)
    if secao not in ("redondo", "quadrado", "retangular"):
        raise ValueError("Seção deve ser 'redondo', 'quadrado' ou 'retangular'.")
    w = medida
    h = medida if secao != "retangular" else float(medida_h or 0.0)
    if secao == "retangular" and h <= 0:
        raise ValueError("Informe a profundidade do tubo retangular.")
    if esp * 2 >= min(w, h):
        raise ValueError("Espessura maior que o meio da seção.")
    if EF + d >= L:
        raise ValueError("Entre furos + furo não cabem no comprimento.")
    if EF <= 0 or d <= 0:
        raise ValueError("Entre furos e diâmetro do furo devem ser positivos.")
    if secao == "redondo":
        raio = 0.0
    if raio > 0 and raio >= min(w, h) / 2 - 0.1:
        raise ValueError("Raio do canto grande demais para a seção.")

    # tubo ao longo de X, seção centrada em YZ; face traseira em z = -h/2
    if secao == "redondo":
        o = cq.Workplane("YZ").circle(w / 2).extrude(L)
        i = cq.Workplane("YZ").circle(w / 2 - esp).extrude(L)
        sec_area = math.pi / 4 * (w ** 2 - (w - 2 * esp) ** 2)
    else:
        o = cq.Workplane("YZ").rect(w, h).extrude(L)
        if raio > 0:
            o = o.edges("|X").fillet(raio)
        i = cq.Workplane("YZ").rect(w - 2 * esp, h - 2 * esp).extrude(L)
        ri = raio - esp
        if ri > 0.05:
            i = i.edges("|X").fillet(ri)
        sec_area = _sec_tubo(w, h, esp, raio)
    tubo = o.cut(i)

    # furos: eixos a EF/2 do centro, atravessando SÓ a parede traseira
    x1 = L / 2 - EF / 2
    x2 = L / 2 + EF / 2
    for xf in (x1, x2):
        broca = (cq.Workplane("XY")
                 .transformed(offset=(xf, 0, -h / 2 - 1))
                 .circle(d / 2).extrude(esp + 2))
        tubo = tubo.cut(broca)

    massa = L * sec_area * DENSIDADE
    borda = (L - EF) / 2
    if secao == "redondo":
        desc = f"Tubo Ø{w:g}"
    elif secao == "quadrado":
        desc = f"Tubo {w:g}x{w:g}"
    else:
        desc = f"Tubo {w:g}x{h:g}"
    if raio > 0:
        desc += f" r{raio:g}"
    cut_list = [
        (f"{desc} esp {esp:g}", 1, round(L), "2 retas 90"),
        (f"Furo Ø{d:g} (parede traseira)", 2, round(EF),
         f"eixos a {borda:g} mm das pontas"),
    ]
    tag = {"redondo": "R", "quadrado": "Q", "retangular": "RT"}[secao]
    nome = f"Puxador_trad_{tag}{w:g}" + (f"x{h:g}" if secao == "retangular" else "") \
           + f"_L{L:g}_EF{EF:g}" + (f"_r{raio:g}" if raio > 0 else "")
    return Result(
        shape=tubo.val().wrapped, solid=tubo, name=nome, kind="puxador_trad",
        dims=(L, w, h), wall=esp, raio=raio, mass=massa, cut_list=cut_list,
        extra=dict(secao=secao, medida=w, medida_h=h, esp=esp, L=L, EF=EF, d=d,
                   borda=borda, raio_canto=raio),
    )


# ---------------------------------------------------------------- modelo U
def puxador_u(tubo_w, tubo_h, esp, comp_pega, comp_perna,
              furo=True, d_furo=5.0, pos_furo=15.0):
    """
    tubo_w, tubo_h : seção retangular (lado maior x lado menor), ex. 40x20 ou 40x15
    comp_pega      : comprimento da PEGA (aresta externa), mm
    comp_perna     : comprimento de cada PERNA (aresta externa), mm
    furo           : True adiciona 1 furo pequeno no LADO MENOR de cada perna
    d_furo         : diâmetro do furo pequeno, mm
    pos_furo       : distância do eixo do furo até o PÉ (corte reto) da perna, mm
    """
    import cadquery as cq
    from .itubecam import tubo_peca

    w, h, esp = float(tubo_w), float(tubo_h), float(esp)
    Cp, Cl = float(comp_pega), float(comp_perna)
    d, pos = float(d_furo), float(pos_furo)
    if w <= h:
        raise ValueError("Informe a seção como lado maior x lado menor (ex.: 40x20).")
    if Cp <= 2 * w + 2:
        raise ValueError("Pega curta demais para as duas esquadrias.")
    if Cl <= w + 2:
        raise ValueError("Perna curta demais para a esquadria.")
    if furo and not (0 < pos < Cl - w):
        raise ValueError("Posição do furo fora do trecho reto da perna.")

    # ---- peças individuais (tubos ocos mitrados — prontos p/ iTubeCAM)
    pega = tubo_peca(w, h, esp, Cp, corte_esq=45, corte_dir=45,
                     plano="largura", nome=f"Pega_{w:g}x{h:g}_L{Cp:g}")
    perna = tubo_peca(w, h, esp, Cl, corte_esq=45, corte_dir=0,
                      plano="largura", nome=f"Perna_{w:g}x{h:g}_L{Cl:g}")
    perna_solid = perna.solid
    if furo:
        # tubo da perna ao longo de X (pé reto em x = Cl); lado menor = faces z
        broca = (cq.Workplane("XY")
                 .transformed(offset=(Cl - pos, 0, -h / 2 - 1))
                 .circle(d / 2).extrude(esp + 2))
        perna_solid = perna_solid.cut(broca)

    # ---- conjunto montado (perfil ∩ extrudado, p/ visual e IGS do conjunto)
    outer = [(0, 0), (0, Cl), (Cp, Cl), (Cp, 0),
             (Cp - w, 0), (Cp - w, Cl - w), (w, Cl - w), (w, 0)]
    prof = cq.Workplane("XY").polyline(outer).close().extrude(h)
    conj = prof.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, h, 0))

    sec_area = w * h - (w - 2 * esp) * (h - 2 * esp)
    Cp_med = Cp - w * math.tan(math.radians(45))            # média das 2 esq.
    Cl_med = Cl - w * math.tan(math.radians(45)) / 2.0
    massa = (Cp_med + 2 * Cl_med) * sec_area * DENSIDADE

    cut_list = [
        (f"Pega {w:g}x{h:g} esp {esp:g}", 1, round(Cp),
         "2 meia esquadria 45 (na largura)"),
        (f"Perna {w:g}x{h:g} esp {esp:g}", 2, round(Cl),
         "1 meia esquadria 45 + 1 reta 90"),
    ]
    if furo:
        cut_list.append((f"Furo Ø{d:g} no lado menor (face da porta)", 2,
                         round(pos), f"eixo a {pos:g} mm do pé"))

    nome = f"Puxador_U_{w:g}x{h:g}_pega{Cp:g}_perna{Cl:g}"
    r = Result(
        shape=conj.val().wrapped, solid=conj, name=nome, kind="puxador_u",
        dims=(Cp, h, Cl), wall=esp, mass=massa, cut_list=cut_list,
        extra=dict(w=w, h=h, esp=esp, Cp=Cp, Cl=Cl, furo=bool(furo),
                   d=d, pos=pos, Cp_curta=pega.extra["L_curta"],
                   Cl_curta=perna.extra["L_curta"]),
    )
    r.parts = {pega.name: pega.solid,
               f"{perna.name}_x2{'_furo' if furo else ''}": perna_solid}
    return r
