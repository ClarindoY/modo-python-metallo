"""Constantes e identidade visual usadas pelo kit."""
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
LOGO = ASSETS / "logo.jpeg"

# Aço-carbono (kg/mm^3). Para inox use ~7.93e-6.
DENSIDADE = 7.85e-6

# Carimbo / título
EMPRESA = "METALLO IND. DE AÇOS DO NORDESTE LTDA"
LINHA = "Linha CONCETTO   |   Caucaia - CE"
TOLERANCIA = "ISO 2768-mK"
PROJECAO = "1º diedro"


# ------------------------------------------------------------------
# Overrides dinâmicos (aba Configurações do app): logo e identificação
# da empresa podem ser trocados sem mexer no código — os arquivos ficam
# em DATA_DIR (ou ./dados) e, se não existirem, vale o padrão METALLO.
import os as _os


def _data_dir():
    d = _os.environ.get("DATA_DIR") or _os.path.join(_os.getcwd(), "dados")
    try:
        _os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def logo_path():
    """Caminho do logo em uso (custom se existir; senão o padrão METALLO)."""
    for ext in ("png", "jpg", "jpeg"):
        p = _os.path.join(_data_dir(), f"logo_custom.{ext}")
        if _os.path.exists(p):
            return p
    return str(LOGO)


def _txt_override(arquivo, padrao):
    try:
        v = open(_os.path.join(_data_dir(), arquivo), encoding="utf-8").read().strip()
        return v if v else padrao
    except Exception:
        return padrao


def empresa():
    return _txt_override("empresa.txt", EMPRESA)


def linha():
    return _txt_override("linha.txt", LINHA)
