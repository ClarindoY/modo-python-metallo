"""Biblioteca de cubas: o usuario sobe o DXF/PDF da cuba + a dimensao, e reutiliza.

Salva em disco (DATA_DIR/cubas ou ./dados/cubas):
  - <slug>.json  com {nome, larg, prof, canto, valor, valvula, arquivo_ref}
  - opcional <slug>.<ext> com o DXF/PDF de referencia enviado.
"""
from __future__ import annotations
import io
import os
import re
import json


def _base_dir():
    raiz = os.environ.get("DATA_DIR") or os.path.join(os.getcwd(), "dados")
    p = os.path.join(raiz, "cubas")
    os.makedirs(p, exist_ok=True)
    return p


def _slug(nome):
    s = re.sub(r"[^\w\- ]+", "", str(nome or ""), flags=re.UNICODE).strip().replace(" ", "_")
    return s or "cuba"


def salvar_cuba(nome, larg, prof, canto="chanfro", valor=0.0, valvula=0.0, ref_bytes=None, ref_ext=""):
    pasta = _base_dir()
    base = _slug(nome)
    meta = {"nome": str(nome), "larg": float(larg), "prof": float(prof),
            "canto": canto, "valor": float(valor), "valvula": float(valvula),
            "arquivo_ref": ""}
    if ref_bytes and ref_ext:
        ext = ref_ext.lower().lstrip(".")
        ref_name = f"{base}.{ext}"
        with open(os.path.join(pasta, ref_name), "wb") as f:
            f.write(ref_bytes)
        meta["arquivo_ref"] = ref_name
    with open(os.path.join(pasta, base + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return base + ".json"


def listar_cubas():
    pasta = _base_dir()
    out = []
    for fn in sorted(os.listdir(pasta)):
        if fn.lower().endswith(".json"):
            try:
                meta = json.load(open(os.path.join(pasta, fn), encoding="utf-8"))
                meta["_arquivo"] = fn
                ref = meta.get("arquivo_ref")
                meta["_ref_path"] = os.path.join(pasta, ref) if ref else ""
                out.append(meta)
            except Exception:
                continue
    return out


def remover_cuba(arquivo_json):
    pasta = _base_dir()
    try:
        meta = json.load(open(os.path.join(pasta, arquivo_json), encoding="utf-8"))
        ref = meta.get("arquivo_ref")
        if ref and os.path.exists(os.path.join(pasta, ref)):
            os.remove(os.path.join(pasta, ref))
    except Exception:
        pass
    p = os.path.join(pasta, arquivo_json)
    if os.path.exists(p):
        os.remove(p)
