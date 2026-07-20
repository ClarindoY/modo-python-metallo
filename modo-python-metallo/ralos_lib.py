"""Biblioteca persistente de RALOS gerados (parâmetros + quantidade).

Guarda os PARÂMETROS (L, W, esp, nome) — as saídas (DXF sup/inf/conjunto)
são regeneradas a um clique. Mesmo padrão de bancadas_lib/cubas.
"""
import os
import re
import json


def _base_dir():
    raiz = os.environ.get("DATA_DIR") or os.path.join(os.getcwd(), "dados")
    p = os.path.join(raiz, "ralos")
    os.makedirs(p, exist_ok=True)
    return p


def _slug(nome):
    s = re.sub(r"[^\w\- ]+", "", str(nome or ""), flags=re.UNICODE).strip().replace(" ", "_")
    return s or "ralo"


def salvar_ralo(nome, params, qtd=1):
    pasta = _base_dir()
    base = _slug(nome)
    meta = {"nome": str(nome), "qtd": max(int(qtd), 1), "params": params}
    with open(os.path.join(pasta, base + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return base + ".json"


def listar_ralos():
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


def remover_ralo(arquivo_json):
    p = os.path.join(_base_dir(), arquivo_json)
    if os.path.exists(p):
        os.remove(p)
