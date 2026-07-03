"""
Construtores paramétricos de peças.

Convenção de eixos:
  X = largura do tubo
  Y = comprimento da peça
  Z = altura do tubo
Tudo em milímetros.
"""
from dataclasses import dataclass, field
import numpy as np
import cadquery as cq

from .config import DENSIDADE


@dataclass
class Result:
    """Resultado de um construtor de peça."""
    shape: object                     # TopoDS_Shape (para exportar IGES/STEP)
    solid: object                     # cq.Workplane (para inspeção)
    name: str                         # nome sugerido do arquivo
    kind: str                         # 'tubo' ou 'mesa'
    dims: tuple                       # (W,T,L) p/ tubo  |  (L,Dp,H) p/ mesa
    wall: float = 1.5
    mass: float = 0.0                 # kg
    feats: list = field(default_factory=list)   # [('circle'|'hex', y, tamanho), ...]
    faces: str = "topo"               # 'topo' (so superior) ou 'ambas' (superior+inferior)
    raio: float = 0.0                 # raio externo dos cantos do tubo
    sext_orient: float = 0.0          # rotacao do sextavado em graus (0=face p/ cima, 30=vertice)
    comp: float = 0.0                 # compensacao do furo em mm (somada ao Ø/chave)
    tam_nominal: float = 0.0          # tamanho nominal do furo (Ø ou chave) antes da compensacao
    angulo: float = 0.0               # corte angular: angulo do corte (90 = reto)
    pontas: int = 0                   # corte angular: numero de pontas cortadas (1 ou 2)
    plano: str = ""                   # corte angular: "altura" ou "largura"
    lado: str = ""                    # corte angular: lado longo (topo/fundo ou esquerda/direita)
    qtd: int = 1                      # quantidade da peca (lote)
    extra: dict = field(default_factory=dict)      # dados extras p/ desenho (mesa_c etc.)
    cut_list: list = field(default_factory=list)  # [(desc, qtd, comp, pontas), ...]
    parts: dict = field(default_factory=dict)      # mesa: {nome: cq.Workplane}
    outline: list = None              # chapa: pontos (x,y) do contorno
    furos2d: list = None              # chapa: [(cx,cy,tipo,tamanho,orient_deg), ...]
    espessura: float = 0.0            # chapa: espessura da chapa


# ---------------------------------------------------------------- helpers
def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").transformed(offset=(x0, y0, z0)).box(
        x1 - x0, y1 - y0, z1 - z0, centered=False
    )


def _tubo_oco(W, T, wall, L, raio=0.0):
    """Tubo retangular oco ao longo de Y, pontas abertas, com cantos opcionalmente arredondados."""
    outer = cq.Workplane("XY").box(W, L, T, centered=False)  # (0,0,0)->(W,L,T)
    if raio and raio > 0.05:
        r = min(raio, min(W, T) / 2 - 0.01)
        try:
            outer = outer.edges("|Y").fillet(r)
        except Exception:
            pass
    inner = cq.Workplane("XY").transformed(offset=(wall, -1, wall)).box(
        W - 2 * wall, L + 2, T - 2 * wall, centered=False
    )
    ri = (raio - wall) if raio else 0.0
    if ri > 0.05:
        ri = min(ri, min(W - 2 * wall, T - 2 * wall) / 2 - 0.01)
        try:
            inner = inner.edges("|Y").fillet(ri)
        except Exception:
            pass
    return outer.cut(inner)


def _furo_prism(tipo, tamanho, cx, cy, z0, z1, orient=0.0):
    """Cilindro (redondo) ou prisma hexagonal (sextavado) para recortar o furo.
       orient = rotacao do sextavado em graus (0 = face p/ cima, 30 = vertice p/ cima)."""
    wp = cq.Workplane("XY").workplane(offset=z0)
    if tipo in ("sextavado", "hex"):
        R = tamanho / (2 * np.cos(np.radians(30)))   # tamanho = entre faces (chave)
        pts = [(cx + R * np.cos(np.radians(a + orient)), cy + R * np.sin(np.radians(a + orient)))
               for a in range(0, 360, 60)]
        return wp.polyline(pts).close().extrude(z1 - z0)
    return wp.moveTo(cx, cy).circle(tamanho / 2).extrude(z1 - z0)


def _furo_prism_x(tipo, tamanho, cy, cz, x0, x1, orient=0.0):
    """Cilindro/prisma hexagonal com eixo ao longo de X (para furar as faces
    LATERAIS do tubo, as de altura T). Plano YZ; cy,cz = centro no plano;
    x0->x1 = faixa em X a perfurar. Mesmo padrao usado em encaixe_mola."""
    wp = cq.Workplane("YZ").workplane(offset=x0)
    if tipo in ("sextavado", "hex"):
        R = tamanho / (2 * np.cos(np.radians(30)))
        pts = [(cy + R * np.cos(np.radians(a + orient)), cz + R * np.sin(np.radians(a + orient)))
               for a in range(0, 360, 60)]
        return wp.polyline(pts).close().extrude(x1 - x0)
    return wp.moveTo(cy, cz).circle(tamanho / 2).extrude(x1 - x0)


def _hollow_from_profile(outer_pts, inner_pts, espessura=40.0, wall=1.5, raio=0.0, axis="Y"):
    o = cq.Workplane("XY").polyline(outer_pts).close().extrude(espessura)
    if raio and raio > 0.05:
        try:
            o = o.edges("|" + axis).fillet(min(raio, espessura / 2 - 0.01))
        except Exception:
            pass
    i = (cq.Workplane("XY").workplane(offset=wall)
         .polyline(inner_pts).close().extrude(espessura - 2 * wall))
    return o.cut(i)


def _massa(solid):
    return solid.val().Volume() * DENSIDADE


# ---------------------------------------------------------------- 1) tubo com furos
def tubo_retangular_furos(W, T, wall, L, furos, tamanho,
                          tipo_furo="redondo", faces="topo", raio=0.0,
                          orient_sext="face", comp=0.0,
                          furos_lado=None, passante_lado=False):
    """
    Tubo retangular com furos. Dois conjuntos independentes:

    - faces LARGAS (largura W = topo/fundo): posicoes em 'furos', controladas por 'faces'
      ("topo", "fundo" ou "ambas"). "ambas" = passante nas duas paredes largas.
    - faces ESTREITAS (altura T = laterais): posicoes em 'furos_lado'. 'passante_lado'
      True = atravessa as duas paredes laterais; False = so uma.

    W, T        : secao do tubo (mm) — W = largura (face larga), T = altura (face estreita)
    wall        : espessura da parede (mm)
    L           : comprimento total (mm)
    furos       : lista de posicoes Y (mm) dos furos na(s) face(s) larga(s)
    tamanho     : Ø (redondo) ou chave (sextavado) NOMINAL, em mm
    tipo_furo   : "redondo" ou "sextavado"
    faces       : "topo" / "fundo" / "ambas" — paredes largas usadas
    furos_lado  : lista de posicoes Y (mm) dos furos nas faces estreitas (laterais)
    passante_lado: True = furo atravessa as duas laterais; False = uma so
    orient_sext : "face" ou "vertice"
    comp        : compensacao em mm somada ao furo (corte = nominal + comp)
    """
    tube = _tubo_oco(W, T, wall, L, raio)
    hx = W / 2.0
    if faces == "ambas":
        z0, z1 = (-1, T + 1)
    elif faces == "fundo":
        z0, z1 = (-1, wall + 0.1)
    else:  # topo
        z0, z1 = (T - wall - 0.1, T + 1)
    orient = 30.0 if (tipo_furo == "sextavado" and orient_sext == "vertice") else 0.0
    eff = max(float(tamanho) + float(comp), 0.1)
    feats = []
    ftype = "hex" if tipo_furo == "sextavado" else "circle"
    # --- furos nas faces largas (topo/fundo) — eixo Z
    for y in (furos or []):
        tube = tube.cut(_furo_prism(tipo_furo, eff, hx, y, z0, z1, orient))
        feats.append((ftype, float(y), eff, "largo"))
    # --- furos nas faces estreitas (laterais) — eixo X
    furos_lado = list(furos_lado or [])
    if furos_lado:
        cz = T / 2.0
        xL0, xL1 = (-1, W + 1) if passante_lado else (-1, wall + 0.1)
        for y in furos_lado:
            tube = tube.cut(_furo_prism_x(tipo_furo, eff, y, cz, xL0, xL1, orient))
            feats.append((ftype, float(y), eff, "estreito"))
    n = len(furos or []) + len(furos_lado)
    suf = "sext" if tipo_furo == "sextavado" else "D"
    nm_furo = "furos" if n != 1 else "furo"
    tag = faces
    if furos_lado:
        tag = (faces + "+lat") if (furos or []) else ("lat" + ("P" if passante_lado else ""))
    name = (f"Tubo_{W:g}x{T:g}x{wall:g}_{L:g}_{n}{nm_furo}"
            f"_{suf}{tamanho:g}_{tag}")
    if raio:
        name += f"_r{raio:g}"
    if comp:
        name += f"_comp{comp:g}"
    cl_obs = "retas 90 graus"
    if (furos or []) and furos_lado:
        cl_obs = "furos faces largas + laterais"
    elif furos_lado:
        cl_obs = ("furos laterais passantes" if passante_lado else "furos laterais")
    return Result(
        shape=tube.val().wrapped, solid=tube, name=name, kind="tubo",
        dims=(W, T, L), wall=wall, mass=_massa(tube), feats=feats,
        faces=faces, raio=raio, sext_orient=orient,
        comp=float(comp), tam_nominal=float(tamanho),
        extra=dict(passante_lado=bool(passante_lado), n_largo=len(furos or []),
                   n_estreito=len(furos_lado)),
        cut_list=[(f"Tubo {W:g}x{T:g}x{wall:g}", 1, L, cl_obs)],
    )


# ---------------------------------------------------------------- tubo redondo
# diâmetro externo (mm) por bitola nominal — tubo redondo mecânico (OD = pol × 25,4)
POLEGADAS_OD = {
    '1/2"': 12.7, '3/4"': 19.05, '1"': 25.4, '1.1/4"': 31.75, '1.1/2"': 38.1,
    '2"': 50.8, '2.1/2"': 63.5, '3"': 76.2, '4"': 101.6, '5"': 127.0,
    '6"': 152.4, '8"': 203.2, '10"': 254.0,
}


def _tubo_redondo_oco(OD, wall, L):
    """Tubo redondo oco ao longo de Y; seção centrada em (OD/2, *, OD/2),
    bounding box [0,OD] × [0,L] × [0,OD] (mesma origem do tubo retangular)."""
    R = OD / 2.0
    ri = max(R - wall, 0.1)
    outer = cq.Workplane("XZ").moveTo(R, R).circle(R).extrude(L)
    inner = cq.Workplane("XZ").moveTo(R, R).circle(ri).extrude(L)
    tubo = outer.cut(inner)
    # garante Y iniciando em 0, independente do sentido do extrude
    bb = tubo.val().BoundingBox()
    return tubo.translate((0, -bb.ymin, 0))


def tubo_redondo(OD, wall, L, furos=None, d_furo=0.0, passante=True,
                 comp=0.0, bitola=""):
    """
    Tubo redondo (seção circular) com furos radiais opcionais.

    OD       : diâmetro externo (mm)
    wall     : espessura da parede (mm)
    L        : comprimento (mm)
    furos    : lista de posições Y (mm da ponta) dos furos
    d_furo   : diâmetro do furo (mm)
    passante : True = furo atravessa o tubo (diametral); False = só a parede de cima
    comp     : compensação somada ao furo
    bitola   : rótulo da bitola (ex.: '2"') só para o nome
    """
    R = OD / 2.0
    tubo = _tubo_redondo_oco(OD, wall, L)
    feats = []
    furos = list(furos or [])
    if furos and d_furo > 0:
        eff = max(float(d_furo) + float(comp), 0.1)
        z0, z1 = (-1.0, OD + 1.0) if passante else (R - 0.01, OD + 1.0)
        for y in furos:
            tubo = tubo.cut(_furo_prism("redondo", eff, R, y, z0, z1, 0.0))
            feats.append(("circle", float(y), eff, "radial"))
    nb = (bitola or f"{OD:g}mm").replace('"', 'pol').replace("/", "-")
    nfuros = f"_{len(furos)}furos_D{d_furo:g}" if furos else ""
    name = f"TuboRedondo_{nb}_e{wall:g}_{L:g}{nfuros}"
    return Result(
        shape=tubo.val().wrapped, solid=tubo, name=name, kind="tubo_redondo",
        dims=(OD, OD, L), wall=wall, mass=_massa(tubo), feats=feats,
        faces="topo", raio=0.0, sext_orient=0.0,
        comp=float(comp), tam_nominal=float(d_furo),
        extra=dict(OD=float(OD), bitola=bitola, passante=bool(passante)),
        cut_list=[(f"Tubo redondo {bitola or f'Ø{OD:g}'} e={wall:g}", 1, L, "corte reto 90°")],
    )


def barra_redonda(OD, L, bitola=""):
    """Barra redonda MACIÇA ao longo de Y (seção circular cheia)."""
    R = OD / 2.0
    barra = cq.Workplane("XZ").moveTo(R, R).circle(R).extrude(L)
    bb = barra.val().BoundingBox()
    barra = barra.translate((0, -bb.ymin, 0))
    nb = (bitola or f"{OD:g}mm").replace('"', 'pol').replace("/", "-")
    name = f"BarraRedonda_{nb}_{L:g}"
    return Result(
        shape=barra.val().wrapped, solid=barra, name=name, kind="barra_redonda",
        dims=(OD, OD, L), wall=0.0, mass=_massa(barra),
        extra=dict(OD=float(OD), bitola=bitola),
        cut_list=[(f"Barra redonda Ø{OD:g}", 1, L, "corte reto 90°")],
    )


def cantoneira(aba, esp, L, aba2=None, bitola=""):
    """Cantoneira (perfil em L) ao longo de Y: duas abas perpendiculares de espessura 'esp'."""
    a1 = float(aba); a2 = float(aba2 or aba); t = float(esp)
    pts = [(0, 0), (a1, 0), (a1, t), (t, t), (t, a2), (0, a2)]
    perfil = cq.Workplane("XZ").polyline(pts).close().extrude(L)
    bb = perfil.val().BoundingBox()
    perfil = perfil.translate((0, -bb.ymin, 0))
    nb = (bitola or f"{a1:g}x{a2:g}").replace('"', 'pol').replace("/", "-")
    name = f"Cantoneira_{nb}_e{t:g}_{L:g}"
    return Result(
        shape=perfil.val().wrapped, solid=perfil, name=name, kind="cantoneira",
        dims=(a1, a2, L), wall=t, mass=_massa(perfil),
        extra=dict(aba=a1, aba2=a2, bitola=bitola),
        cut_list=[(f"Cantoneira {nb} e={t:g}", 1, L, "corte reto 90°")],
    )


# ---------------------------------------------------------------- 2) torre sextavada
def torre_sextavada(W, T, wall, L, chave, pos_centros, faces="topo", raio=0.0,
                    orient_sext="face", comp=0.0):
    """Tubo retangular com 1 ou mais furos hexagonais (chave) nas posições
    'pos_centros' (lista, em mm da borda)."""
    if isinstance(pos_centros, (int, float)):
        pos_centros = [pos_centros]
    pos_centros = [float(p) for p in pos_centros]
    r = tubo_retangular_furos(W, T, wall, L, pos_centros, chave,
                              tipo_furo="sextavado", faces=faces, raio=raio,
                              orient_sext=orient_sext, comp=comp)
    nf = len(pos_centros)
    r.name = (f"Torre_{W:g}x{T:g}x{wall:g}_{L:g}_sextavado_ch{chave:g}"
              f"_{nf}furo{'s' if nf != 1 else ''}_{faces}")
    if raio:
        r.name += f"_r{raio:g}"
    if comp:
        r.name += f"_comp{comp:g}"
    return r


# ---------------------------------------------------------------- 3) mesa em metalon
def mesa_metalon(L, Dp, H, perfil=40.0, wall=1.5, raio=0.0):
    """
    Estrutura de mesa em metalon quadrado, com meia esquadria 45 graus nos quadros de ponta.
    raio = raio externo dos cantos do metalon (0 = canto vivo).
    """
    TW = perfil
    Zt = H - TW
    off = wall * np.sqrt(2)

    # estrutura como solido limpo (uniao de barras) p/ visualizacao
    P = []
    for cx in (TW / 2, L - TW / 2):
        for cy in (TW / 2, Dp - TW / 2):
            P.append(_box(cx - TW / 2, cx + TW / 2, cy - TW / 2, cy + TW / 2, 0, H))
    for cx in (TW / 2, L - TW / 2):
        P.append(_box(cx - TW / 2, cx + TW / 2, 0, Dp, Zt, H))
    for cy in (TW / 2, Dp - TW / 2):
        P.append(_box(TW, L - TW, cy - TW / 2, cy + TW / 2, Zt, H))
    frame = P[0]
    for p in P[1:]:
        frame = frame.union(p)

    # tubos mitrados individuais (ocos) p/ producao
    h = TW / 2.0
    wi = h - wall
    legtop = (H - off)
    leg_o = [(-h, 0), (h, 0), (h, H - TW), (-h, H)]
    leg_i = [(-wi, -1), (wi, -1), (wi, legtop - wi), (-wi, legtop + wi)]
    perna = _hollow_from_profile(leg_o, leg_i, TW, wall, raio, axis="Y")

    cb_o = [(0, h), (Dp, h), (Dp - TW, -h), (TW, -h)]
    TLy = (TW + off) - wi
    TRy = (Dp - TW - off) + wi
    BRy = (Dp - TW - off) - wi
    BLy = (TW + off) + wi
    cb_i = [(TLy, wi), (TRy, wi), (BRy, -wi), (BLy, -wi)]
    trav_ponta = _hollow_from_profile(cb_o, cb_i, TW, wall, raio, axis="X")

    Lr = L - 2 * TW
    rl_o = [(-h, 0), (h, 0), (h, Lr), (-h, Lr)]
    rl_i = [(-wi, -1), (wi, -1), (wi, Lr + 1), (-wi, Lr + 1)]
    trav_longa = _hollow_from_profile(rl_o, rl_i, TW, wall, raio, axis="Y")

    massa = 4 * _massa(perna) + 2 * _massa(trav_ponta) + 2 * _massa(trav_longa)
    cut_list = [
        (f"Perna metalon {TW:g}x{TW:g}", 4, H, "1 meia esq. 45 + 1 reta"),
        (f"Travessa de ponta {TW:g}x{TW:g}", 2, Dp, "2 meia esquadria 45"),
        (f"Travessa longa {TW:g}x{TW:g}", 2, Lr, "2 retas 90"),
    ]
    name = f"Mesa_{L:g}x{Dp:g}x{H:g}_metalon{TW:g}" + (f"_r{raio:g}" if raio else "")
    return Result(
        shape=frame.val().wrapped, solid=frame, name=name, kind="mesa",
        dims=(L, Dp, H), wall=wall, mass=massa, raio=raio, cut_list=cut_list,
        extra=dict(perfil=float(TW), perfil_a=float(TW)),
        parts={
            "Perna_meiaesq45": perna,
            "Travessa_ponta_2meiaesq45": trav_ponta,
            "Travessa_longa_reta": trav_longa,
        },
    )


# ---------------------------------------------------------------- 4) chapas (corte 2D)
def _poly_area(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def chapa_poligono(pts, espessura, furos2d=None, nome="Chapa"):
    """
    Chapa plana definida por um contorno poligonal, com furos opcionais.

    pts      : lista de pontos (x,y) do contorno (mm)
    espessura: espessura da chapa (mm)
    furos2d  : lista (cx, cy, tipo, tamanho, orient_deg)
               tipo = "redondo"/"circle" (tamanho=Ø) ou "sextavado"/"hex" (tamanho=chave)
    """
    furos2d = list(furos2d or [])
    wp = cq.Workplane("XY").polyline(pts).close().extrude(espessura)
    for f in furos2d:
        cx, cy, tipo, tam = f[0], f[1], f[2], f[3]
        orient = f[4] if len(f) > 4 else 0.0
        wp = wp.cut(_furo_prism(tipo, tam, cx, cy, -1, espessura + 1, orient))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    W = max(xs) - min(xs); H = max(ys) - min(ys)
    mass = wp.val().Volume() * DENSIDADE
    return Result(
        shape=wp.val().wrapped, solid=wp, name=nome, kind="chapa",
        dims=(W, H, espessura), espessura=espessura, mass=mass,
        outline=list(pts), furos2d=furos2d,
    )


def poligono_L(W=60.0, H=110.0, bloco=35.0, rec_alt=40.0, espessura=2.0,
               furo=8.0, n_furos=2, d_topo=13.0, d_esq=10.0, passo=15.0,
               tipo_furo="redondo", orient_sext="face", comp=0.0):
    """
    Chapa em 'L' (degrau): retangulo W x H com recorte no canto superior direito.

    bloco   : largura do bloco esquerdo (onde ficam os furos)
    rec_alt : altura do recorte no canto superior direito
    furos   : n_furos, Ø/chave 'furo' NOMINAL, a 'd_topo' do topo, 1o a 'd_esq' da esquerda, 'passo' entre furos
    comp    : compensacao em mm somada ao furo (corte = nominal + comp)
    """
    pts = [(0, 0), (W, 0), (W, H - rec_alt), (bloco, H - rec_alt), (bloco, H), (0, H)]
    orient = 30.0 if (tipo_furo == "sextavado" and orient_sext == "vertice") else 0.0
    t = "hex" if tipo_furo == "sextavado" else "circle"
    eff = max(float(furo) + float(comp), 0.1)
    y = H - d_topo
    furos = [(d_esq + i * passo, y, t, eff, orient) for i in range(int(n_furos))]
    nome = f"Chapa_L_{W:g}x{H:g}_{int(n_furos)}furo{furo:g}"
    if comp:
        nome += f"_comp{comp:g}"
    r = chapa_poligono(pts, espessura, furos, nome)
    r.comp = float(comp)
    r.tam_nominal = float(furo)
    return r


def hexagono(base=200.0, topo=100.0, altura=60.0, chanfro_v=50.0, espessura=2.0):
    """
    Chapa hexagonal simetrica (escudo): base embaixo, topo em cima, chanfros 45 nos cantos sup.

    chanfro horizontal = (base - topo)/2 (automatico)
    chanfro_v          = queda vertical do chanfro
    altura             = altura total (lateral reta = altura - chanfro_v)
    """
    ch_h = (base - topo) / 2.0
    lado = max(altura - chanfro_v, 0.0)
    pts = [(0, 0), (base, 0), (base, lado), (base - ch_h, altura), (ch_h, altura), (0, lado)]
    nome = f"Chapa_hex_base{base:g}_topo{topo:g}_alt{altura:g}"
    return chapa_poligono(pts, espessura, [], nome)


# ---------------------------------------------------------------- 5) tubo com corte angular nas pontas
def _miter_cutter(W, T, L, ang, end, plano, lado):
    """Solido para recortar uma ponta do tubo em angulo (ang = graus em relacao ao eixo; 90 = reto)."""
    import math
    BIG = 6.0 * max(W, T, L)
    Q = W if plano == "largura" else T
    run = Q / math.tan(math.radians(ang))
    long_high = lado in ("topo", "direita", "A")

    if end == "end":
        if long_high:
            def yc(q): return (L - run) + run * q / Q
        else:
            def yc(q): return L - run * q / Q
        far = L + BIG
    else:  # start
        if long_high:
            def yc(q): return run - run * q / Q
        else:
            def yc(q): return run * q / Q
        far = -BIG

    poly = [(yc(-BIG), -BIG), (yc(BIG), BIG), (far, BIG), (far, -BIG)]
    if plano == "largura":
        pts = [(q, y) for (y, q) in poly]           # plano (X,Y), extrude em Z
        return cq.Workplane("XY").workplane(offset=-1).polyline(pts).close().extrude(T + 2)
    pts = [(y, q) for (y, q) in poly]               # plano (Y,Z), extrude em X
    return cq.Workplane("YZ").workplane(offset=-1).polyline(pts).close().extrude(W + 2)


def tubo_corte_angular(W, T, wall, L, angulo=90.0, pontas=2,
                       plano="altura", lado="topo", raio=0.0, qtd=1,
                       furos=None, tamanho=0.0, tipo_furo="redondo",
                       faces="topo", orient_sext="face", comp=0.0):
    """
    Tubo retangular com corte ANGULAR em 1 ou 2 pontas (e furos opcionais).

    angulo : angulo do corte em relacao ao eixo do tubo (90 = corte reto/esquadro; menor = chanfro)
    pontas : 1 ou 2 pontas com corte
    plano  : "altura" (chanfra no plano da altura T) ou "largura" (no plano da largura W)
    lado   : lado mais longo - "topo"/"fundo" (altura) ou "direita"/"esquerda" (largura)
    raio   : raio do canto do tubo (0 = canto vivo)
    qtd    : quantidade da peca
    furos  : lista de posicoes Y (mm) dos furos (opcional); na linha de centro da face de W
    tamanho: Ø (redondo) ou chave (sextavado) NOMINAL dos furos
    tipo_furo / faces / orient_sext / comp : iguais a tubo_retangular_furos
    """
    import math
    ang = float(angulo)
    if ang <= 0 or ang > 90:
        ang = 90.0
    npc = 2 if int(pontas) >= 2 else 1
    Q = W if plano == "largura" else T
    run = 0.0 if ang >= 89.999 else Q / math.tan(math.radians(ang))
    if run > 0 and run * npc >= L:
        raise ValueError(
            f"Angulo {ang:g} graus muito agressivo para L={L:g} mm "
            f"(corte total {run * npc:.0f} mm >= comprimento)."
        )
    def _montar(raio_):
        t = _tubo_oco(W, T, wall, L, raio_)
        if run > 0:
            ends = ["end", "start"] if npc == 2 else ["end"]
            for e in ends:
                t = t.cut(_miter_cutter(W, T, L, ang, e, plano, lado))
        return t

    raio_usado = float(raio)
    try:
        tube = _montar(raio)
    except Exception:
        # Em algumas seções o boolean (canto arredondado + corte angular) falha no
        # kernel. Refaz com canto vivo (mais robusto) para a geração não travar.
        raio_usado = 0.0
        tube = _montar(0.0)

    # furos opcionais
    furos = list(furos or [])
    feats = []
    if furos and tamanho:
        eff = max(float(tamanho) + float(comp), 0.1)
        orient = 30.0 if (tipo_furo == "sextavado" and orient_sext == "vertice") else 0.0
        z0, z1 = (-1, T + 1) if faces == "ambas" else (T - wall - 0.1, T + 1)
        hx = W / 2.0
        ftype = "hex" if tipo_furo == "sextavado" else "circle"
        for y in furos:
            tube = tube.cut(_furo_prism(tipo_furo, eff, hx, y, z0, z1, orient))
            feats.append((ftype, float(y), eff, "largo"))

    pl = "largura" if plano == "largura" else "altura"
    name = f"TuboAng_{W:g}x{T:g}x{wall:g}_{L:g}_{ang:g}g_{npc}p"
    if feats:
        name += f"_{len(feats)}furo{tamanho:g}"
    if raio_usado:
        name += f"_r{raio_usado:g}"
    if comp:
        name += f"_comp{comp:g}"
    if int(qtd) > 1:
        name += f"_x{int(qtd)}"
    pontas_txt = f"{npc}x corte {ang:g} graus" if run > 0 else "retas 90 graus"
    return Result(
        shape=tube.val().wrapped, solid=tube, name=name, kind="angular",
        dims=(W, T, L), wall=wall, mass=_massa(tube), raio=raio_usado,
        angulo=ang, pontas=npc, plano=pl, lado=lado, qtd=int(qtd),
        feats=feats, faces=faces,
        sext_orient=(30.0 if (tipo_furo == "sextavado" and orient_sext == "vertice") else 0.0),
        comp=float(comp), tam_nominal=float(tamanho),
        extra=dict(raio_reduzido=(raio_usado != float(raio))),
        cut_list=[(f"Tubo {W:g}x{T:g}x{wall:g}", int(qtd), L, pontas_txt)],
    )


# ---------------------------------------------------------------- 6) mesa com pes laterais em "C" (cantilever)
def _leg_c(foot, flag, Hq, b, t, y0, mirror=False, Dp=0.0):
    """Quadro lateral em 'C' (trapezio): poste vertical no fundo, frente em diagonal.
    Plano do quadro = X(profundidade) x Z(altura); espessura 't' ao longo de Y, iniciando em y0."""
    import math
    run = foot - flag
    diag = math.hypot(run, Hq)
    nx, nz = -Hq / diag, -run / diag
    Ax, Az = foot + b * nx, 0.0 + b * nz
    Bx, Bz = flag + b * nx, Hq + b * nz
    s1 = (b - Az) / (Bz - Az); xbr = Ax + s1 * (Bx - Ax)
    s2 = ((Hq - b) - Az) / (Bz - Az); xtr = Ax + s2 * (Bx - Ax)
    outer = [(0, 0), (foot, 0), (flag, Hq), (0, Hq)]
    inner = [(b, b), (xbr, b), (xtr, Hq - b), (b, Hq - b)]
    o = cq.Workplane("XY").polyline(outer).close().extrude(t)
    i = cq.Workplane("XY").polyline(inner).close().extrude(t)
    band = o.cut(i).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, y0 + t, 0))
    if mirror and Dp:
        band = band.mirror("YZ", (Dp / 2.0, 0, 0))
    return band, outer, inner, diag


def mesa_pes_c(W, Dp, H, perfil=30.0, wall=1.5, top_th=25.0,
               recuo_pe=None, aba=None, espelhado=False, com_rail=True, inset_lateral=90.0):
    """
    Mesa/escrivaninha com PES LATERAIS EM "C" (cantilever).

    W, Dp, H : largura x profundidade x altura (mm) - W ao longo de Y, prof. ao longo de X
    perfil   : lado do tubo quadrado dos pes (mm)
    top_th   : espessura do tampo (mm)
    recuo_pe : profundidade do pe no chao (default 0.72*Dp)
    aba      : comprimento da aba superior do pe (default 0.40*Dp)
    espelhado: True = pes espelhados; False = mesmo sentido
    com_rail : adiciona uma travessa superior ligando os dois pes
    """
    import math
    b = float(perfil); t = float(perfil)
    foot = float(recuo_pe) if recuo_pe else 0.72 * Dp
    flag = float(aba) if aba else 0.40 * Dp
    Hq = H - top_th
    foot = min(foot, Dp - 1.0); flag = min(flag, foot - 1.0)
    run = foot - flag; diag = math.hypot(run, Hq)
    ang_diag = math.degrees(math.atan2(Hq, run))   # angulo da diagonal com o chao

    leg1, outer, inner, _ = _leg_c(foot, flag, Hq, b, t, inset_lateral)
    y2 = W - inset_lateral - t
    leg2, _, _, _ = _leg_c(foot, flag, Hq, b, t, y2, mirror=espelhado, Dp=Dp)

    top = cq.Workplane("XY").transformed(offset=(0, 0, Hq)).box(Dp, W, top_th, centered=False)
    asm = leg1.union(leg2)
    L_rail = 0.0
    if com_rail:
        L_rail = W - 2 * inset_lateral
        rail = cq.Workplane("XY").transformed(
            offset=(flag / 2 - b / 2, inset_lateral, Hq - b)).box(b, L_rail, b, centered=False)
        asm = asm.union(rail)
    asm = asm.union(top)

    sec = b * t - (b - 2 * wall) * (t - 2 * wall)
    comp_perna = Hq + flag + foot + diag
    massa = (2 * comp_perna + L_rail) * sec * DENSIDADE

    cut_list = [
        (f"Poste fundo {b:g}x{t:g}", 2, round(Hq), "1 reta (base) + 1 esq. 45"),
        (f"Aba topo {b:g}x{t:g}", 2, round(flag), "esq. 45 + esq. diagonal"),
        (f"Diagonal frente {b:g}x{t:g}", 2, round(diag), f"2 esquadrias (~{ang_diag:.0f} graus)"),
        (f"Pe base {b:g}x{t:g}", 2, round(foot), "esq. 45 + esq. diagonal"),
    ]
    if com_rail:
        cut_list.append((f"Travessa superior {b:g}x{t:g}", 1, round(L_rail), "2 retas 90"))
    cut_list.append((f"Tampo {Dp:g}x{W:g} (esp. {top_th:g})", 1, round(W), "—"))

    name = f"Mesa_pesC_{W:g}x{Dp:g}x{H:g}_perfil{b:g}" + ("_esp" if espelhado else "")
    return Result(
        shape=asm.val().wrapped, solid=asm, name=name, kind="mesa_c",
        dims=(W, Dp, H), wall=wall, mass=massa, cut_list=cut_list,
        extra=dict(foot=foot, flag=flag, Hq=Hq, diag=diag, ang=ang_diag,
                   perfil=b, top_th=top_th, espelhado=espelhado, com_rail=com_rail,
                   inset=inset_lateral, outer=outer, inner=inner),
    )


# ---------------------------------------------------------------- 7) encaixe-mola (snap-fit serpentina em S)
def _mola_slots(Lf, W, mola_L, beam_off, sw, catch_w, catch_h, n_molas=1, esp=110.0):
    """Retorna lista de rasgos (cx, cy, w, h) na face do tubo (x ao longo do tubo, y na largura).
       Mola: 2 fendas longas intercaladas (apoio em S) + rasgo-trava central."""
    rects = []
    if n_molas == 1:
        centros = [Lf / 2.0]
    else:
        centros = [Lf / 2.0 + (i - (n_molas - 1) / 2.0) * esp for i in range(n_molas)]
    for cx0 in centros:
        xa = cx0 - mola_L / 2.0
        xL = xa + 0.18 * mola_L
        xR = xa + 0.82 * mola_L
        # fenda A (em cima), aberta na direita -> ancora a esquerda
        rects.append(((xa + xR) / 2.0, +beam_off, (xR - xa), sw))
        # fenda B (embaixo), aberta na esquerda -> ancora a direita (apoio em S)
        rects.append(((xL + (xa + mola_L)) / 2.0, -beam_off, (xa + mola_L - xL), sw))
        # respiros nas pontas da lingueta (libera o flexionamento)
        rects.append((xa + 0.5, 0.0, sw, 2 * beam_off))
        rects.append((xa + mola_L - 0.5, 0.0, sw, 2 * beam_off))
        # rasgo-trava (onde o ressalto do macho prende)
        rects.append((cx0, 0.0, catch_w, catch_h))
    return rects


def encaixe_mola(W=40.0, T=40.0, wall=1.2, L_femea=260.0, L_macho=160.0,
                 mola_L=120.0, beam_off=5.0, sw=1.5, catch_w=14.0, catch_h=3.0,
                 folga=0.15, n_molas=1):
    """
    Encaixe-mola (snap-fit) com lingueta serpentina em S na FEMEA + ressalto no MACHO.
    A mola eh cortada na face superior do tubo femea; o macho entra com um ressalto
    que a mola trava. mola_L = comprimento; beam_off = meia-largura da lingueta;
    sw = largura do corte (kerf da mola); catch = rasgo-trava.
    """
    W = float(W); T = float(T); wall = float(wall)
    slots = _mola_slots(L_femea, W, mola_L, beam_off, sw, catch_w + folga, catch_h + folga, n_molas)

    # FEMEA: tubo ao longo de X, secao centrada em (y=0,z=0); parede de cima em z=[T/2-wall, T/2]
    outer = cq.Workplane("YZ").rect(W, T).extrude(L_femea)
    inner = cq.Workplane("YZ").rect(W - 2 * wall, T - 2 * wall).extrude(L_femea)
    femea = outer.cut(inner)
    bb = femea.val().BoundingBox()
    if bb.xmin < -1:
        femea = femea.translate((L_femea, 0, 0))
    # corta os rasgos na parede de cima (z = T/2)
    cutter = None
    for (cx, cy, w, h) in slots:
        b = (cq.Workplane("XY").transformed(offset=(cx, cy, T / 2.0 - wall - 0.2))
             .box(w, h, wall + 0.6, centered=(True, True, False)))
        cutter = b if cutter is None else cutter.union(b)
    femea = femea.cut(cutter)

    # MACHO: tubo ao longo de X com um ressalto (saliencia) que a mola trava
    om = cq.Workplane("YZ").rect(W - 2 * folga, T - 2 * folga).extrude(L_macho)
    im = cq.Workplane("YZ").rect(W - 2 * folga - 2 * wall, T - 2 * folga - 2 * wall).extrude(L_macho)
    macho = om.cut(im)
    bbm = macho.val().BoundingBox()
    if bbm.xmin < -1:
        macho = macho.translate((L_macho, 0, 0))
    ress = (cq.Workplane("XY").transformed(offset=(L_macho * 0.5, 0, T / 2.0 - folga))
            .box(catch_w, catch_h, wall, centered=(True, True, False)))
    macho = macho.union(ress)

    sec = (W * T - (W - 2 * wall) * (T - 2 * wall))
    massa = (L_femea + L_macho) * sec * DENSIDADE

    cut_list = [
        (f"Femea tubo {W:g}x{T:g}x{wall:g}", 1, round(L_femea), f"corte da mola na face (kerf {sw:g})"),
        (f"Macho tubo {W:g}x{T:g}x{wall:g}", 1, round(L_macho), f"ressalto {catch_w:g}x{catch_h:g}"),
    ]
    return Result(
        shape=femea.union(macho).val().wrapped, solid=femea.union(macho),
        name=f"EncaixeMola_{W:g}x{T:g}x{wall:g}_L{mola_L:g}", kind="encaixe_mola",
        dims=(W, T, wall), wall=wall, mass=massa, cut_list=cut_list,
        parts={"femea": femea, "macho": macho},
        extra=dict(slots=slots, L_femea=L_femea, L_macho=L_macho, mola_L=mola_L,
                   beam_off=beam_off, sw=sw, catch_w=catch_w, catch_h=catch_h,
                   folga=folga, n_molas=n_molas, W=W, T=T, wall=wall),
    )
