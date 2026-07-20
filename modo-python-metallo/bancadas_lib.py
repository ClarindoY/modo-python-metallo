"""Biblioteca persistente de BANCADAS geradas (parâmetros + quantidade).

Guarda os PARÂMETROS da peça (não o DXF), então qualquer saída pode ser
regenerada a um clique: planificação, DXF, folha de projeto, etiqueta.
Salva em DATA_DIR/bancadas (ou ./dados/bancadas) como JSON — mesmo padrão de cubas.py.
"""
import os
import re
import json


def _base_dir():
    raiz = os.environ.get("DATA_DIR") or os.path.join(os.getcwd(), "dados")
    p = os.path.join(raiz, "bancadas")
    os.makedirs(p, exist_ok=True)
    return p


def _slug(nome):
    s = re.sub(r"[^\w\- ]+", "", str(nome or ""), flags=re.UNICODE).strip().replace(" ", "_")
    return s or "bancada"


def salvar_bancada(nome, params, qtd=1, arquivo=None):
    """params = dict com os argumentos de bancada.gerar (serializável em JSON)."""
    pasta = _base_dir()
    base = _slug(arquivo[:-5] if arquivo else nome)
    meta = {"nome": str(nome), "qtd": max(int(qtd), 1), "params": params}
    with open(os.path.join(pasta, base + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return base + ".json"


def listar_bancadas():
    pasta = _base_dir()
    out = []
    for fn in sorted(os.listdir(pasta)):
        if fn.lower().endswith(".json"):
            try:
                meta = json.load(open(os.path.join(pasta, fn), encoding="utf-8"))
                meta["_arquivo"] = fn
                out.append(meta)
            except Exception:
                continue
    return out


def atualizar_qtd(arquivo_json, qtd):
    p = os.path.join(_base_dir(), arquivo_json)
    if os.path.exists(p):
        meta = json.load(open(p, encoding="utf-8"))
        meta["qtd"] = max(int(qtd), 1)
        json.dump(meta, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def remover_bancada(arquivo_json):
    p = os.path.join(_base_dir(), arquivo_json)
    if os.path.exists(p):
        os.remove(p)


def limpar():
    for m in listar_bancadas():
        remover_bancada(m["_arquivo"])
