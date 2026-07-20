"""
metallo_cad — gerador paramétrico de peças (Metallo / Concetto).

Famílias disponíveis:
  - tubo_retangular_furos : tubo retangular com furos redondos
  - torre_sextavada       : tubo retangular com furo hexagonal
  - mesa_metalon          : estrutura de mesa em metalon com meia esquadria

Cada construtor devolve um objeto Result com:
  .shape    -> sólido (TopoDS) pronto para exportar (IGES/STEP)
  .mass     -> massa estimada em kg
  .name     -> nome sugerido de arquivo
  .cut_list -> lista de corte [(descrição, qtd, comprimento_mm, pontas), ...]
  .parts    -> (mesa) dicionário de tubos mitrados individuais

Exportadores em metallo_cad.exporters ; desenhos em metallo_cad.drawing.
"""
from .parts import (
    Result,
    tubo_retangular_furos,
    tubo_redondo,
    POLEGADAS_OD,
    torre_sextavada,
    mesa_metalon,
    chapa_poligono,
    poligono_L,
    hexagono,
    tubo_corte_angular,
    mesa_pes_c,
    mesa_pe_quadro,
    mesa_base_x,
    mesa_cubo,
    mesa_pe_trapezio,
    mesa_estrutura_quadro,
    encaixe_mola,
)
from . import exporters, drawing, laser, etiquetas, config

__all__ = [
    "Result",
    "tubo_retangular_furos",
    "tubo_redondo",
    "POLEGADAS_OD",
    "torre_sextavada",
    "mesa_metalon",
    "chapa_poligono",
    "poligono_L",
    "hexagono",
    "tubo_corte_angular",
    "mesa_pes_c",
    "mesa_pe_quadro",
    "mesa_base_x",
    "mesa_cubo",
    "mesa_pe_trapezio",
    "mesa_estrutura_quadro",
    "encaixe_mola",
    "exporters",
    "drawing",
    "laser",
    "etiquetas",
]
