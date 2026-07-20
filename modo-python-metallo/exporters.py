"""Exportadores IGES e STEP (via OpenCASCADE / OCP)."""
from OCP.IGESControl import IGESControl_Writer
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs


def _shape(obj):
    """Aceita um Result, um cq.Workplane ou um TopoDS_Shape.
    Para Workplane com VÁRIOS sólidos na pilha, monta um Compound com todos
    (antes só o primeiro era exportado — peças sumiam do IGS/STEP)."""
    if hasattr(obj, "shape"):          # Result
        solid = getattr(obj, "solid", None)
        if solid is not None and hasattr(solid, "vals"):
            vals = [v for v in solid.vals() if v is not None]
            if len(vals) > 1:          # shape foi criado com .val() e perderia peças
                import cadquery as cq
                return cq.Compound.makeCompound(vals).wrapped
        return obj.shape
    if hasattr(obj, "vals"):           # cq.Workplane
        vals = [v for v in obj.vals() if v is not None]
        if len(vals) > 1:
            import cadquery as cq
            comp = cq.Compound.makeCompound(vals)
            return comp.wrapped
        if vals:
            return vals[0].wrapped
    if hasattr(obj, "val"):
        return obj.val().wrapped
    return obj                          # TopoDS_Shape


def _confere(path, o_que):
    import os
    if not os.path.exists(str(path)) or os.path.getsize(str(path)) < 200:
        raise RuntimeError(f"Exportação {o_que} não gerou arquivo válido: {path}")


def to_iges(obj, path):
    """Escreve IGES (sólido B-rep, unidades em mm)."""
    Interface_Static.SetCVal_s("write.iges.unit", "MM")
    Interface_Static.SetIVal_s("write.iges.brep.mode", 1)
    w = IGESControl_Writer("MM", 0)
    ok_add = w.AddShape(_shape(obj))
    w.ComputeModel()
    ok = w.Write(str(path))
    if not (ok_add and ok):
        raise RuntimeError(f"IGES falhou (AddShape={ok_add}, Write={ok}): {path}")
    _confere(path, "IGES")
    return True


def to_step(obj, path):
    """Escreve STEP (AP214) conferindo o status de transferência e escrita."""
    sw = STEPControl_Writer()
    st_tr = sw.Transfer(_shape(obj), STEPControl_AsIs)
    st_wr = sw.Write(str(path))
    # IFSelect_RetDone == 1; qualquer outro status é falha
    if int(st_tr) != 1 or int(st_wr) != 1:
        raise RuntimeError(f"STEP falhou (Transfer={int(st_tr)}, Write={int(st_wr)}): {path}")
    _confere(path, "STEP")
    return True


def to_dxf(result, path):
    """Escreve DXF de corte (so para pecas de chapa, kind='chapa').
       Contorno na camada CORTE; furos na camada FUROS; unidades em mm."""
    import ezdxf
    import numpy as np
    if not getattr(result, "outline", None):
        raise ValueError("to_dxf: peca sem contorno 2D (use uma familia de chapa).")
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm
    msp = doc.modelspace()
    doc.layers.add("CORTE", color=7)
    doc.layers.add("FUROS", color=1)
    msp.add_lwpolyline(result.outline, close=True, dxfattribs={"layer": "CORTE"})
    for f in (result.furos2d or []):
        cx, cy, tipo, tam = f[0], f[1], f[2], f[3]
        orient = f[4] if len(f) > 4 else 0.0
        if tipo in ("sextavado", "hex"):
            R = tam / (2 * np.cos(np.radians(30)))
            pts = [(cx + R * np.cos(np.radians(a + orient)), cy + R * np.sin(np.radians(a + orient)))
                   for a in range(0, 360, 60)]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "FUROS"})
        else:
            msp.add_circle((cx, cy), tam / 2.0, dxfattribs={"layer": "FUROS"})
    doc.saveas(str(path))
    return True


def mola_dxf(r, path):
    """DXF do corte do encaixe-mola: contorno da face + rasgos (mola) em camadas separadas."""
    import ezdxf
    e = r.extra
    Lf, W = e["L_femea"], e["W"]
    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()
    doc.layers.add("CONTORNO", color=7)
    doc.layers.add("CORTE", color=1)
    # contorno da face do tubo (Lf x W), centrado em y=0
    msp.add_lwpolyline([(0, -W / 2), (Lf, -W / 2), (Lf, W / 2), (0, W / 2)],
                       close=True, dxfattribs={"layer": "CONTORNO"})
    # rasgos (cada um como retangulo fechado)
    for (cx, cy, w, h) in e["slots"]:
        x0, y0 = cx - w / 2.0, cy - h / 2.0
        msp.add_lwpolyline([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                           close=True, dxfattribs={"layer": "CORTE"})
    doc.saveas(str(path))
    return path
