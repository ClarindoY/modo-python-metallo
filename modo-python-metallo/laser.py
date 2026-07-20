"""
Motor de tempo de corte a laser (fibra 3000 W) para o gerador Metallo / Concetto.

Conteúdo:
  - TABELA_3000W : parâmetros de corte (material × espessura → velocidade, gás, bico, foco…)
  - parametros() : consulta a linha da tabela (espessura exata ou mais próxima)
  - comprimento_corte_result() : comprimento de corte + nº de perfurações a partir de um Result
  - comprimento_corte_dxf()    : idem, lendo um arquivo .dxf
  - estimar_tempo()            : tempo de corte (min) a partir de comprimento + perfurações
  - DENSIDADES                 : densidades por material p/ peso

A tabela é de corte de CHAPA PLANA (velocidades em m/min). Para chapas e DXF o tempo
é direto; para tubos é uma estimativa (somatório dos furos + cortes de ponta).
"""
from __future__ import annotations
import math

# --------------------------------------------------------------------- densidades (kg/mm^3)
DENSIDADES = {
    "Aço-carbono": 7.85e-6,
    "Aço inox": 7.93e-6,
    "Alumínio": 2.70e-6,
    "Latão": 8.50e-6,
}

# nome curto da tabela -> rótulo usado na interface
MATERIAIS = ["Aço-carbono", "Aço inox", "Alumínio", "Latão"]

# --------------------------------------------------------------------- tabela 3000 W
# Cada linha: (espessura_mm, vel_min, vel_max [m/min], potencia_W, gas,
#              pressao_bar, bico, foco_mm, altura_mm)
# Para aço-carbono 1–2 mm há dois regimes (N2/Ar rápido e O2). Mantidos os dois;
# a consulta usa, por padrão, o regime de maior velocidade disponível.
TABELA_3000W = {
    "Aço-carbono": [
        (1,  28.0, 35.0, 3000, "N2/Ar", 10.0, "1.5S",  0.0, 1.0),
        (2,  16.0, 20.0, 3000, "N2/Ar", 10.0, "2.0S",  0.0, 0.5),
        (2,  3.8,  4.2,  2100, "O2",     1.6, "1.0D",  3.0, 0.8),
        (3,  3.2,  3.6,  2100, "O2",     0.6, "1.0D",  4.0, 0.8),
        (4,  3.0,  3.2,  2400, "O2",     0.6, "1.0D",  4.0, 0.8),
        (5,  2.7,  3.0,  3000, "O2",     0.6, "1.2D",  4.0, 0.8),
        (6,  2.2,  2.5,  3000, "O2",     0.6, "1.2D",  4.0, 0.8),
        (8,  1.8,  2.2,  3000, "O2",     0.6, "1.2D",  4.0, 0.8),
        (10, 1.0,  1.3,  3000, "O2",     0.6, "1.2D",  4.0, 0.8),
        (12, 0.9,  1.0,  2400, "O2",     0.6, "3.0D",  4.0, 0.8),
        (14, 0.8,  0.9,  2400, "O2",     0.6, "3.0D",  4.0, 0.8),
        (16, 0.6,  0.7,  2400, "O2",     0.6, "3.5D",  4.0, 0.8),
        (18, 0.5,  0.6,  2400, "O2",     0.6, "4.0D",  4.0, 0.8),
        (20, 0.5,  0.55, 2400, "O2",     0.6, "4.0D",  4.0, 0.8),
        (22, 0.5,  0.5,  2400, "O2",     0.6, "4.0D",  4.0, 0.8),
    ],
    "Aço inox": [
        (1,  28.0, 35.0, 3000, "N2", 10.0, "1.5S",  0.0, 0.8),
        (2,  18.0, 24.0, 3000, "N2", 12.0, "2.0S",  0.0, 0.5),
        (3,  7.0,  10.0, 3000, "N2", 12.0, "2.5S", -0.5, 0.5),
        (4,  5.0,  6.5,  3000, "N2", 14.0, "2.5S", -1.5, 0.5),
        (5,  3.0,  3.6,  3000, "N2", 14.0, "3.0S", -2.5, 0.5),
        (6,  2.0,  2.7,  3000, "N2", 14.0, "3.0S", -3.0, 0.5),
        (8,  1.0,  1.2,  3000, "N2", 16.0, "3.5S", -4.5, 0.5),
        (10, 0.5,  0.6,  3000, "N2", 16.0, "4.0S", -6.0, 0.5),
    ],
    "Alumínio": [
        (1,  25.0, 30.0, 3000, "N2", 12.0, "1.5S",  0.0, 0.8),
        (2,  15.0, 18.0, 3000, "N2", 12.0, "2.0S",  0.0, 0.5),
        (3,  7.0,  8.0,  3000, "N2", 14.0, "2.0S", -1.0, 0.5),
        (4,  5.0,  6.0,  3000, "N2", 14.0, "2.5S", -2.0, 0.5),
        (5,  2.5,  3.0,  3000, "N2", 16.0, "3.0S", -3.0, 0.5),
        (6,  1.5,  2.0,  3000, "N2", 16.0, "3.0S", -3.5, 0.5),
        (8,  0.6,  0.7,  3000, "N2", 16.0, "3.5S", -4.0, 0.5),
    ],
    "Latão": [
        (1,  20.0, 28.0, 3000, "N2", 12.0, "1.5S",  0.0, 0.8),
        (2,  10.0, 15.0, 3000, "N2", 12.0, "2.0S",  0.0, 0.5),
        (3,  5.0,  6.0,  3000, "N2", 14.0, "2.5S", -1.0, 0.5),
        (4,  2.5,  3.0,  3000, "N2", 14.0, "3.0S", -2.0, 0.5),
        (5,  1.8,  2.2,  3000, "N2", 14.0, "3.0S", -2.5, 0.5),
        (6,  0.8,  1.0,  3000, "N2", 16.0, "3.0S", -3.0, 0.5),
    ],
}

_CAMPOS = ("espessura", "vel_min", "vel_max", "potencia", "gas",
           "pressao", "bico", "foco", "altura")


def _linha_dict(linha):
    return dict(zip(_CAMPOS, linha))


def espessuras_disponiveis(material):
    """Lista ordenada de espessuras (mm) com parâmetro tabelado para o material."""
    linhas = TABELA_3000W.get(material, [])
    return sorted({l[0] for l in linhas})


def parametros(material, espessura, preferir_gas=None):
    """
    Devolve os parâmetros de corte para (material, espessura).

    Se a espessura exata não existir na tabela, usa a linha de espessura mais
    próxima (e marca 'aproximada'=True). Quando há mais de um regime para a mesma
    espessura (ex.: aço-carbono N2/Ar vs O2), escolhe o de maior velocidade,
    salvo se 'preferir_gas' for informado.
    """
    linhas = TABELA_3000W.get(material)
    if not linhas:
        raise ValueError(f"Material sem tabela: {material}")
    esp = float(espessura)
    # espessura tabelada mais próxima
    alvo = min((l[0] for l in linhas), key=lambda e: abs(e - esp))
    candidatas = [l for l in linhas if l[0] == alvo]
    if preferir_gas:
        pg = [l for l in candidatas if preferir_gas.lower() in l[4].lower()]
        candidatas = pg or candidatas
    # maior velocidade média
    linha = max(candidatas, key=lambda l: (l[1] + l[2]) / 2.0)
    d = _linha_dict(linha)
    d["aproximada"] = (abs(alvo - esp) > 1e-6)
    d["espessura_tabela"] = alvo
    return d


# --------------------------------------------------------------------- comprimento de corte
def _perimetro_poligono(pts):
    n = len(pts)
    if n < 2:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i][0], pts[i][1]
        x2, y2 = pts[(i + 1) % n][0], pts[(i + 1) % n][1]
        s += math.hypot(x2 - x1, y2 - y1)
    return s


def _perimetro_furo(tipo, tam):
    """Perímetro de um furo: redondo (tam=Ø) ou sextavado (tam=chave/entre-faces)."""
    if str(tipo) in ("sextavado", "hex"):
        # hexágono regular: lado = chave/√3  ->  perímetro = 6·lado = 2·√3·chave
        return 2.0 * math.sqrt(3.0) * tam
    return math.pi * tam


def comprimento_corte_result(r, cortes_ponta=2):
    """
    Comprimento de corte (mm) e nº de perfurações (pierces) de um Result.

    chapa  : perímetro do contorno + perímetro de cada furo.
    tubo   : perímetro de cada furo + (cortes_ponta) × perímetro da seção.
             (a tabela é de chapa; para tubo é uma estimativa.)
    Devolve (comprimento_mm, n_pierces, detalhe_dict).
    """
    kind = getattr(r, "kind", "")
    comp = 0.0
    pierces = 0
    det = {}

    if kind == "chapa" or getattr(r, "outline", None):
        contorno = _perimetro_poligono(r.outline or [])
        comp += contorno
        pierces += 1 if contorno > 0 else 0
        furos = 0.0
        for f in (getattr(r, "furos2d", None) or []):
            furos += _perimetro_furo(f[2], f[3])
            pierces += 1
        comp += furos
        det = {"contorno": contorno, "furos": furos,
               "n_furos": len(getattr(r, "furos2d", None) or [])}
    else:
        # tubo / torre / angular
        dims = getattr(r, "dims", (0, 0, 0))
        W, T = (dims[0], dims[1]) if len(dims) >= 2 else (0, 0)
        if kind == "tubo_redondo":
            OD = (getattr(r, "extra", None) or {}).get("OD", W)
            sec = math.pi * OD                 # perímetro da seção circular
        else:
            sec = 2.0 * (W + T)
        n_ends = int(cortes_ponta)
        comp_ends = n_ends * sec
        furos = 0.0
        n_furos = 0
        for feat in (getattr(r, "feats", None) or []):
            tipo = "hex" if feat[0] in ("hex", "sextavado") else "redondo"
            furos += _perimetro_furo(tipo, feat[2])
            n_furos += 1
        comp = comp_ends + furos
        pierces = n_ends + n_furos
        det = {"cortes_ponta": comp_ends, "n_ends": n_ends,
               "furos": furos, "n_furos": n_furos, "secao": sec}

    return comp, pierces, det


def comprimento_corte_dxf(path, camadas_furo=None):
    """
    Lê um .dxf e devolve (comprimento_mm, n_pierces, detalhe_dict).

    Soma o comprimento de todas as entidades de corte do modelspace
    (LINE, ARC, CIRCLE, LWPOLYLINE, POLYLINE, ELLIPSE, SPLINE) usando ezdxf.path,
    que lida com bulges/arcos corretamente. Cada entidade conta como 1 perfuração.
    Também devolve a área aproximada (mm²) do maior contorno fechado, p/ peso.
    """
    import ezdxf
    from ezdxf import path as ezpath

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    total = 0.0
    pierces = 0
    n_ent = 0
    maior_area = 0.0
    for e in msp:
        try:
            p = ezpath.make_path(e)
        except Exception:
            continue
        verts = [(v.x, v.y) for v in p.flattening(0.05)]
        L = _comprimento_polilinha(verts)
        if L <= 1e-9:
            continue
        total += L
        pierces += 1
        n_ent += 1
        # área do contorno fechado (para estimar peso da chapa)
        try:
            if e.dxftype() == "CIRCLE":
                a = math.pi * (e.dxf.radius ** 2)
            elif getattr(p, "is_closed", False) or _quase_fechado(verts):
                a = _area_poligono(verts)
            else:
                a = 0.0
            maior_area = max(maior_area, a)
        except Exception:
            pass

    det = {"n_entidades": n_ent, "area_mm2": maior_area}
    return total, pierces, det


def _comprimento_polilinha(pts):
    """Soma das cordas de uma sequência de pontos (não fecha automaticamente)."""
    s = 0.0
    for i in range(len(pts) - 1):
        s += math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
    return s


def _quase_fechado(pts, tol=0.05):
    return len(pts) >= 3 and math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]) <= tol


def _area_poligono(pts):
    n = len(pts)
    if n < 3:
        return 0.0
    a = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


# --------------------------------------------------------------------- tempo de furação (pierce)
# tempo (s) por perfuração, por faixa de espessura (fibra 3 kW, valores médios)
_PIERCE_S = [
    (1.0, 0.2), (2.0, 0.3), (3.0, 0.4), (4.0, 0.5), (5.0, 0.6),
    (6.0, 0.8), (8.0, 1.2), (10.0, 1.8), (12.0, 2.5),
    (16.0, 4.0), (20.0, 7.0), (1e9, 10.0),
]


def tempo_pierce_s(espessura):
    for lim, s in _PIERCE_S:
        if espessura <= lim:
            return s
    return 10.0


# --------------------------------------------------------------------- estimativa de tempo
def estimar_tempo(material, espessura, comprimento_mm, n_pierces=0,
                  eficiencia=0.85, preferir_gas=None):
    """
    Estima o tempo de corte.

    material, espessura : chave da tabela 3000 W
    comprimento_mm      : comprimento total de corte
    n_pierces           : nº de perfurações (cada uma adiciona o tempo de furação)
    eficiencia          : 0–1; desconta posicionamento/aceleração da máquina
                          (0.85 = a máquina corta ~85% da velocidade de catálogo na média)

    Devolve um dict com tempos em minutos e os parâmetros usados.
    """
    p = parametros(material, espessura, preferir_gas=preferir_gas)
    vmin, vmax = p["vel_min"], p["vel_max"]
    vmed = (vmin + vmax) / 2.0
    comp_m = comprimento_mm / 1000.0

    def _t_corte(v):
        v_ef = max(v * eficiencia, 1e-6)
        return comp_m / v_ef  # min

    t_corte = _t_corte(vmed)
    t_corte_rapido = _t_corte(vmax)
    t_corte_lento = _t_corte(vmin)

    t_pierce = n_pierces * tempo_pierce_s(p["espessura_tabela"]) / 60.0  # min
    t_total = t_corte + t_pierce

    return {
        "material": material,
        "espessura": espessura,
        "params": p,
        "vel_med": vmed,
        "comprimento_mm": comprimento_mm,
        "n_pierces": n_pierces,
        "t_corte_min": t_corte,
        "t_pierce_min": t_pierce,
        "t_total_min": t_total,
        "t_total_min_rapido": t_corte_rapido + t_pierce,
        "t_total_min_lento": t_corte_lento + t_pierce,
        "eficiencia": eficiencia,
    }


def fmt_tempo(minutos):
    """Formata minutos -> 'm:ss' (ou 'h:mm:ss' se passar de 1 h)."""
    seg = max(0, round(minutos * 60))
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    if h:
        return f"{h}h {m:02d}min {s:02d}s"
    if m:
        return f"{m}min {s:02d}s"
    return f"{s}s"


def peso_chapa(area_mm2, espessura, material):
    """Peso (kg) de uma peça de chapa: área × espessura × densidade do material."""
    dens = DENSIDADES.get(material, DENSIDADES["Aço-carbono"])
    return area_mm2 * espessura * dens
