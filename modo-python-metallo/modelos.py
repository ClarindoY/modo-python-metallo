"""Biblioteca de MODELOS DXF do usuário.

Permite anexar arquivos .dxf próprios, dar um nome a cada modelo e reutilizá-los.
Os modelos ficam salvos em disco (em DATA_DIR/modelos_dxf ou ./dados/modelos_dxf),
então sobrevivem ao reinício do app — desde que a pasta seja persistente
(no Render, exige um disco persistente apontado por DATA_DIR).
"""
from __future__ import annotations
import io
import os
import re
import ezdxf


def _base_dir():
    raiz = os.environ.get("DATA_DIR") or os.path.join(os.getcwd(), "dados")
    p = os.path.join(raiz, "modelos_dxf")
    os.makedirs(p, exist_ok=True)
    return p


def _slug(nome):
    s = re.sub(r"[^\w\- ]+", "", str(nome or ""), flags=re.UNICODE).strip().replace(" ", "_")
    return s or "modelo"


def _info(dxf_bytes):
    """Conta entidades e calcula o bounding box do DXF (mm)."""
    doc = ezdxf.read(io.StringIO(dxf_bytes.decode("utf-8", "ignore")))
    msp = doc.modelspace()
    n = 0
    xs, ys = [], []
    for e in msp:
        n += 1
        t = e.dxftype()
        try:
            if t == "LINE":
                xs += [e.dxf.start.x, e.dxf.end.x]; ys += [e.dxf.start.y, e.dxf.end.y]
            elif t == "CIRCLE":
                xs += [e.dxf.center.x - e.dxf.radius, e.dxf.center.x + e.dxf.radius]
                ys += [e.dxf.center.y - e.dxf.radius, e.dxf.center.y + e.dxf.radius]
            elif t == "ARC":
                xs += [e.dxf.center.x - e.dxf.radius, e.dxf.center.x + e.dxf.radius]
                ys += [e.dxf.center.y - e.dxf.radius, e.dxf.center.y + e.dxf.radius]
            elif t == "LWPOLYLINE":
                for p in e.get_points("xy"):
                    xs.append(p[0]); ys.append(p[1])
            elif t == "POLYLINE":
                for v in e.vertices:
                    xs.append(v.dxf.location.x); ys.append(v.dxf.location.y)
        except Exception:
            pass
    w = (max(xs) - min(xs)) if xs else 0.0
    h = (max(ys) - min(ys)) if ys else 0.0
    return {"n_entidades": n, "bbox": (w, h)}


def validar(dxf_bytes):
    """Confirma que o DXF abre; devolve info. Lança exceção se inválido."""
    return _info(dxf_bytes)


def salvar_modelo(nome, dxf_bytes):
    """Salva o DXF com o nome dado (valida antes). Não sobrescreve: cria sufixo se já existir.
    Retorna o nome do arquivo salvo."""
    _info(dxf_bytes)                                  # valida (lança se inválido)
    pasta = _base_dir()
    base = _slug(nome)
    fname = base + ".dxf"
    path = os.path.join(pasta, fname)
    i = 2
    while os.path.exists(path):
        fname = f"{base}_{i}.dxf"; path = os.path.join(pasta, fname); i += 1
    with open(path, "wb") as f:
        f.write(dxf_bytes)
    return fname


def listar_modelos():
    """Lista os modelos salvos: [{nome, arquivo, dxf, n_entidades, bbox}]."""
    pasta = _base_dir()
    out = []
    for fn in sorted(os.listdir(pasta)):
        if not fn.lower().endswith(".dxf"):
            continue
        try:
            data = open(os.path.join(pasta, fn), "rb").read()
            info = _info(data)
            out.append({"nome": os.path.splitext(fn)[0].replace("_", " "),
                        "arquivo": fn, "dxf": data, **info})
        except Exception:
            continue
    return out


def carregar_modelo(arquivo):
    return open(os.path.join(_base_dir(), arquivo), "rb").read()


def renomear_modelo(arquivo, novo_nome):
    pasta = _base_dir()
    velho = os.path.join(pasta, arquivo)
    if not os.path.exists(velho):
        return arquivo
    base = _slug(novo_nome); novo = base + ".dxf"; path = os.path.join(pasta, novo); i = 2
    while os.path.exists(path) and os.path.basename(path) != arquivo:
        novo = f"{base}_{i}.dxf"; path = os.path.join(pasta, novo); i += 1
    os.rename(velho, path)
    return novo


def remover_modelo(arquivo):
    p = os.path.join(_base_dir(), arquivo)
    if os.path.exists(p):
        os.remove(p)
