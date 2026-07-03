"""Exportadores IGES e STEP (via OpenCASCADE / OCP)."""
from OCP.IGESControl import IGESControl_Writer
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs


def _shape(obj):
    """Aceita um Result, um cq.Workplane ou um TopoDS_Shape."""
    if hasattr(obj, "shape"):          # Result
        return obj.shape
    if hasattr(obj, "val"):            # cq.Workplane
        return obj.val().wrapped
    return obj                          # TopoDS_Shape


def to_iges(obj, path):
    """Escreve IGES (sólido B-rep, unidades em mm)."""
    Interface_Static.SetCVal_s("write.iges.unit", "MM")
    Interface_Static.SetIVal_s("write.iges.brep.mode", 1)
    w = IGESControl_Writer("MM", 0)
    w.AddShape(_shape(obj))
    w.ComputeModel()
    ok = w.Write(str(path))
    return bool(ok)


def to_step(obj, path):
    """Escreve STEP (AP214)."""
    sw = STEPControl_Writer()
    sw.Transfer(_shape(obj), STEPControl_AsIs)
    sw.Write(str(path))
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
