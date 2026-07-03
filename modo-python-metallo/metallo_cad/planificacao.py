"""Planificação de chapas (caldeiraria): desenvolve formas 3D em chapa plana para corte.

Implementa a geometria/matemática clássica de traçagem:
- Virola / cilindro  -> retângulo (π·D × altura)
- Cone completo      -> setor circular (raio = geratriz, arco = π·D)
- Tronco de cone     -> setor anelar entre dois raios (redução concêntrica)

Saída no mesmo formato 'prims' das demais peças (outer poly + bbox + área),
compatível com flanges.dxf_bytes / preview_png / preview_pdf.
Tudo é geometria padrão de domínio técnico — sem qualquer cópia de terceiros.
"""
from __future__ import annotations
import math


def _shoelace(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _centralizar(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    cx = (min(xs) + max(xs)) / 2; cy = (min(ys) + max(ys)) / 2
    return [(x - cx, y - cy) for x, y in pts]


def _bbox(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (max(xs) - min(xs), max(ys) - min(ys))


def _prims(pts, name, esp, info, deco=None):
    pts = _centralizar(pts)
    pr = {"outer": ("poly", pts), "holes": [], "bbox": _bbox(pts),
          "area": _shoelace(pts), "name": name, "esp": float(esp), "info": info}
    if deco:
        pr["deco"] = [("line", _centralizar_ref(seg, pts)) for seg in deco] if False else deco
    return pr


def _centralizar_ref(seg, ref):
    return seg


def cilindro(diam_ref, altura, esp=0.0, name="virola"):
    """Virola/cilindro: retângulo de largura π·D_ref e altura H.
    diam_ref = diâmetro na fibra neutra (geralmente D_interno + espessura)."""
    L = math.pi * float(diam_ref)
    H = float(altura)
    pts = [(0, 0), (L, 0), (L, H), (0, H)]
    info = {"tipo": "Virola / cilindro", "larg_chapa": L, "alt_chapa": H,
            "diam_ref": float(diam_ref), "perimetro": L}
    return _prims(pts, name, esp, info)


def cone(diam_base, altura, esp=0.0, seg=160, name="cone"):
    """Cone reto completo: setor circular de raio = geratriz e arco = π·D."""
    r = float(diam_base) / 2.0
    h = float(altura)
    g = math.hypot(r, h)                       # geratriz (slant)
    theta = (2 * math.pi * r) / g if g else 0  # ângulo do setor (rad)
    pts = [(0.0, 0.0)]
    for i in range(seg + 1):
        a = -theta / 2 + theta * i / seg
        pts.append((g * math.sin(a), -g * math.cos(a)))
    info = {"tipo": "Cone", "geratriz": g, "raio_setor": g,
            "angulo_setor_g": math.degrees(theta), "diam_base": float(diam_base), "altura": h}
    return _prims(pts, name, esp, info)


def tronco_cone(diam_maior, diam_menor, altura, esp=0.0, seg=160, name="tronco_cone"):
    """Tronco de cone (redução concêntrica): setor anelar entre R1 (base maior) e R2 (base menor)."""
    D = float(diam_maior); d = float(diam_menor); h = float(altura)
    if D < d:
        D, d = d, D
    if abs(D - d) < 1e-6:                       # vira cilindro
        Ls = h
        return cilindro(D, Ls, esp=esp, name=name)
    Ls = math.hypot((D - d) / 2.0, h)           # geratriz do tronco
    R1 = Ls * D / (D - d)                        # raio externo do setor (até base maior)
    R2 = R1 - Ls                                 # raio interno (até base menor)
    theta = (2 * math.pi * (D / 2.0)) / R1       # ângulo do setor (rad)
    outer = []
    for i in range(seg + 1):
        a = -theta / 2 + theta * i / seg
        outer.append((R1 * math.sin(a), -R1 * math.cos(a)))
    inner = []
    for i in range(seg + 1):
        a = theta / 2 - theta * i / seg
        inner.append((R2 * math.sin(a), -R2 * math.cos(a)))
    pts = outer + inner
    info = {"tipo": "Tronco de cone", "geratriz": Ls, "raio_maior_R1": R1, "raio_menor_R2": R2,
            "angulo_setor_g": math.degrees(theta), "diam_maior": D, "diam_menor": d, "altura": h}
    return _prims(pts, name, esp, info)


def peso_kg(prims, densidade=7.93e-6):
    """Peso aproximado (kg) pela área da planificação × espessura. Inox 304 por padrão."""
    esp = prims.get("esp", 0.0) or 0.0
    return prims.get("area", 0.0) * esp * densidade
