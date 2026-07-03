"""
Geração de desenho técnico em PDF (folha A3, carimbo Metallo).

draw(result, path) escolhe automaticamente o layout:
  - kind == 'tubo' -> draw_tube  (vista superior, frontal, seção, perspectiva)
  - kind == 'mesa' -> draw_table (frontal, superior, lateral c/ meia esquadria, lista de corte)
"""
import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, FancyArrowPatch, Polygon, Circle, Ellipse

from .config import LOGO, EMPRESA, LINHA, TOLERANCIA, PROJECAO

_logo = None
def _logo_img():
    global _logo
    if _logo is None and LOGO.exists():
        _logo = plt.imread(str(LOGO))
    return _logo

C30, S30 = np.cos(np.radians(30)), np.sin(np.radians(30))


# ------------------------------------------------------------------ carimbo
def _sheet(pp, title, desnum, material, draw_fn, folha="01/01", data="--/--/----"):
    fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 420); ax.set_ylim(0, 297)
    ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Rectangle((7, 7), 406, 283, fill=False, lw=1.6))
    ax.add_patch(Rectangle((12, 12), 396, 273, fill=False, lw=0.8))
    bx, by, bw, bh = 233, 12, 175, 52
    ax.add_patch(Rectangle((bx, by), bw, bh, fill=False, lw=1.0))
    ax.add_patch(Rectangle((bx, by + bh - 20), 46, 20, fill=True, fc="black", ec="k", lw=0.8))
    img = _logo_img()
    if img is not None:
        axl = fig.add_axes([(bx + 2) / 420, (by + bh - 19) / 297, 42 / 420, 18 / 297])
        axl.imshow(img); axl.axis("off")
    ax.text(bx + 50, by + bh - 7, EMPRESA, fontsize=6.5, va="center", weight="bold")
    ax.text(bx + 50, by + bh - 14, LINHA, fontsize=5, va="center", color="0.3")
    ax.plot([bx, bx + bw], [by + bh - 20, by + bh - 20], "k", lw=0.6)
    ax.text(bx + 2, by + bh - 26.5, "PRODUTO:", fontsize=4.6, color="0.45")
    ax.text(bx + 2, by + bh - 33, title, fontsize=6.2, weight="bold")
    ax.plot([bx, bx + bw], [by + 18, by + 18], "k", lw=0.6)
    ax.plot([bx, bx + bw], [by + 9, by + 9], "k", lw=0.6)
    cols = [bx, bx + 34, bx + 74, bx + 104, bx + 138, bx + bw]
    for cxx in cols[1:-1]:
        ax.plot([cxx, cxx], [by, by + 18], "k", lw=0.5)
    p0 = [("DES. Nº", desnum), ("MATERIAL", material), ("ACABAM.", "Pint. pó"),
          ("ESCALA", "INDICADA"), ("UNID.", "mm")]
    p1 = [("TOLER.", TOLERANCIA), ("PROJEÇÃO", PROJECAO), ("DATA", data),
          ("REV.", "00"), ("FOLHA", folha)]
    for i, (l, v) in enumerate(p0):
        ax.text(cols[i] + 1.5, by + 14.8, l, fontsize=4.2, color="0.45", va="center")
        ax.text(cols[i] + 1.5, by + 11.2, str(v), fontsize=5.0, va="center", weight="bold")
    for i, (l, v) in enumerate(p1):
        ax.text(cols[i] + 1.5, by + 5.8, l, fontsize=4.2, color="0.45", va="center")
        ax.text(cols[i] + 1.5, by + 2.2, str(v), fontsize=5.0, va="center", weight="bold")
    draw_fn(ax)
    pp.savefig(fig); plt.close(fig)


def _dimh(ax, xa, xb, y, t, tu=1.7, fs=5.6):
    ax.add_patch(FancyArrowPatch((xa, y), (xb, y), arrowstyle="<|-|>", mutation_scale=4,
                                 lw=0.5, color="k", shrinkA=0, shrinkB=0))
    ax.text((xa + xb) / 2, y + tu, t, fontsize=fs, ha="center", va="bottom")


def _dimv(ax, ya, yb, x, t, side=1, fs=5.6):
    ax.add_patch(FancyArrowPatch((x, ya), (x, yb), arrowstyle="<|-|>", mutation_scale=4,
                                 lw=0.5, color="k", shrinkA=0, shrinkB=0))
    ax.text(x + 1.7 * side, (ya + yb) / 2, t, fontsize=fs,
            ha=("left" if side > 0 else "right"), va="center", rotation=90)


def _hexpts(chave, offset=0.0):
    R = chave / (2 * C30)
    return [(R * np.cos(np.radians(a + offset)), R * np.sin(np.radians(a + offset)))
            for a in range(0, 360, 60)], R


def _rrect_pts(x0, y0, w, h, r, n=7):
    """Pontos de um retângulo de cantos arredondados (para a vista de seção)."""
    r = max(0.0, min(r, w / 2 - 0.001, h / 2 - 0.001))
    if r <= 0.05:
        return [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h), (x0, y0)]
    cs = [(x0 + w - r, y0 + r, -90, 0), (x0 + w - r, y0 + h - r, 0, 90),
          (x0 + r, y0 + h - r, 90, 180), (x0 + r, y0 + r, 180, 270)]
    pts = []
    for cx, cy, a0, a1 in cs:
        for a in np.linspace(np.radians(a0), np.radians(a1), n):
            pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    pts.append(pts[0])
    return pts


# ------------------------------------------------------------------ TUBO
def _emit(pp_out, path, title, desnum, material, page, data, folha="01/01"):
    """Emite a pagina: num PDF aberto (pp_out, multipagina) ou cria um PDF proprio."""
    if pp_out is not None:
        _sheet(pp_out, title, desnum, material, page, folha=folha, data=data)
    else:
        with PdfPages(str(path)) as pp:
            _sheet(pp, title, desnum, material, page, folha=folha, data=data)


class _PngCatcher:
    """Recebe o mesmo `savefig` que o PdfPages e captura a figura como PNG."""
    def __init__(self, dpi=110):
        self.buf = io.BytesIO(); self.dpi = dpi

    def savefig(self, fig):
        fig.savefig(self.buf, format="png", dpi=self.dpi)


def draw_png(r, dpi=110):
    """Renderiza o MESMO desenho técnico como PNG (para preview inline e zip)."""
    catcher = _PngCatcher(dpi)
    draw(r, path=None, pp_out=catcher)
    return catcher.buf.getvalue()


def draw_tube(r, path=None, data="--/--/----", pp_out=None, folha="01/01"):
    W, T, L = r.dims
    wall = r.wall
    def _face(f): return f[3] if len(f) > 3 else "largo"
    feats = sorted(r.feats, key=lambda f: f[1])
    feats_l = [f for f in feats if _face(f) == "largo"]      # faces largas (W) — eixo Z
    feats_e = [f for f in feats if _face(f) == "estreito"]   # faces estreitas (T) — eixo X
    faces = r.faces
    ex = getattr(r, "extra", None) or {}
    lat_pass = bool(ex.get("passante_lado"))
    top_face = faces in ("topo", "ambas")
    bot_face = faces in ("fundo", "ambas")
    raio = r.raio
    s = min(0.62, 230.0 / L)

    def page(ax):
        ax.text(210, 281, f"{r.name}", fontsize=8.4, ha="center", weight="bold")
        ox, oy = 26, 196
        # ---- VISTA SUPERIOR (face W, comprimento horizontal) ----
        ax.add_patch(Rectangle((ox, oy), L * s, W * s, fill=False, lw=1.0))
        ax.plot([ox, ox + L * s], [oy + W / 2 * s, oy + W / 2 * s], "k", lw=0.3, ls=(0, (7, 3)))
        # furos das faces LARGAS (vistos de cima como circulos/hex)
        for typ, y, size in [(f[0], f[1], f[2]) for f in feats_l]:
            cx, cy = ox + y * s, oy + W / 2 * s
            if typ == "circle":
                ax.add_patch(Circle((cx, cy), size / 2 * s, fill=False, lw=1.0))
            else:
                hp, _ = _hexpts(size, r.sext_orient)
                ax.add_patch(Polygon([(cx + px * s, cy + py * s) for px, py in hp],
                                     closed=True, fill=False, lw=1.0))
            ax.plot([cx, cx], [oy, oy + W * s], "k", lw=0.3, ls=(0, (7, 3)))
        # furos das faces ESTREITAS (laterais) — vistos de cima como rasgos nas bordas
        for typ, y, size in [(f[0], f[1], f[2]) for f in feats_e]:
            wgap = (size if typ == "circle" else size / C30) * s
            cx = ox + y * s
            ax.add_patch(Rectangle((cx - wgap / 2, oy - 0.2), wgap, wall * s + 0.4, fc="w", ec="k", lw=0.6))
            if lat_pass:
                ax.add_patch(Rectangle((cx - wgap / 2, oy + W * s - wall * s - 0.2),
                                       wgap, wall * s + 0.4, fc="w", ec="k", lw=0.6))
        base_feats = feats_l or feats_e
        pts = [0] + [f[1] for f in base_feats] + [L]
        for a, b in zip(pts[:-1], pts[1:]):
            _dimh(ax, ox + a * s, ox + b * s, oy - 7, f"{b - a:g}")
        _dimh(ax, ox, ox + L * s, oy - 14, f"{L:g}")
        _dimv(ax, oy, oy + W * s, ox - 7, f"{W:g}", side=-1)
        if feats_l or feats_e:
            nominal = r.tam_nominal or feats[-1][2]
            head = (f"Ø{nominal:g}" if feats[0][0] == "circle" else f"sext ch {nominal:g}")
            seg = []
            if feats_l:
                fc = {"ambas": "faces largas (sup+inf)", "fundo": "face larga inferior"}.get(faces, "face larga superior")
                seg.append(f"{len(feats_l)}× {fc}")
            if feats_e:
                seg.append(f"{len(feats_e)}× lateral" + (" passante" if lat_pass else ""))
            txt = head + " — " + "; ".join(seg)
            if r.comp:
                txt += f"  (comp {r.comp:g} -> corte {nominal + r.comp:g})"
            ax.annotate(txt, (ox + feats[-1][1] * s, oy + W * s), (ox + L * s + 8, oy + W * s - 3),
                        fontsize=5.4, arrowprops=dict(arrowstyle="->", lw=0.5))
        ax.text(ox + L * s / 2, oy - 21, "VISTA SUPERIOR (face furada)",
                fontsize=7.5, ha="center", weight="bold")
        # ---- VISTA FRONTAL (comprimento x altura) ----
        oy2 = 150
        ax.add_patch(Rectangle((ox, oy2), L * s, T * s, fill=False, lw=1.0))
        ax.plot([ox, ox + L * s], [oy2 + wall * s, oy2 + wall * s], "k", lw=0.35)
        ax.plot([ox, ox + L * s], [oy2 + T * s - wall * s, oy2 + T * s - wall * s], "k", lw=0.35)
        for typ, y, size in [(f[0], f[1], f[2]) for f in feats_l]:
            wgap = (size if typ == "circle" else size / C30) * s
            cx = ox + y * s
            if top_face:
                ax.add_patch(Rectangle((cx - wgap / 2, oy2 + T * s - wall * s - 0.2),
                                       wgap, wall * s + 0.4, fc="w", ec="k", lw=0.5))
            if bot_face:
                ax.add_patch(Rectangle((cx - wgap / 2, oy2 - 0.2),
                                       wgap, wall * s + 0.4, fc="w", ec="k", lw=0.5))
        for typ, y, size in [(f[0], f[1], f[2]) for f in feats_e]:
            ccx, ccy = ox + y * s, oy2 + T / 2 * s
            if typ == "circle":
                ax.add_patch(Circle((ccx, ccy), size / 2 * s, fill=False, lw=1.0))
            else:
                hp, _ = _hexpts(size, r.sext_orient)
                ax.add_patch(Polygon([(ccx + px * s, ccy + py * s) for px, py in hp],
                                     closed=True, fill=False, lw=1.0))
        _dimh(ax, ox, ox + L * s, oy2 - 6, f"{L:g}")
        _dimv(ax, oy2, oy2 + T * s, ox - 7, f"{T:g}", side=-1)
        ax.text(ox + L * s / 2, oy2 - 12, "VISTA FRONTAL", fontsize=7.5, ha="center", weight="bold")
        # ---- SEÇÃO ----
        ss = min(2.6, 70.0 / max(W, T)); cx, cy = 300, 150
        if raio and raio > 0.05:
            outer = _rrect_pts(cx, cy, W * ss, T * ss, raio * ss)
            inner = _rrect_pts(cx + wall * ss, cy + wall * ss,
                               (W - 2 * wall) * ss, (T - 2 * wall) * ss, max(raio - wall, 0.0) * ss)
            ax.plot([p[0] for p in outer], [p[1] for p in outer], "k", lw=1.2)
            ax.plot([p[0] for p in inner], [p[1] for p in inner], "k", lw=0.8)
        else:
            ax.add_patch(Rectangle((cx, cy), W * ss, T * ss, fill=False, lw=1.2))
            ax.add_patch(Rectangle((cx + wall * ss, cy + wall * ss),
                                   (W - 2 * wall) * ss, (T - 2 * wall) * ss, fill=False, lw=0.8))
        _dimh(ax, cx, cx + W * ss, cy - 6, f"{W:g}")
        _dimv(ax, cy, cy + T * ss, cx + W * ss + 7, f"{T:g}")
        ax.annotate(f"parede {wall:g}", (cx + wall * ss / 2, cy + T * ss * 0.55),
                    (cx - 20, cy + T * ss + 5), fontsize=5.4, arrowprops=dict(arrowstyle="-", lw=0.4))
        rtxt = f"  -  raio canto {raio:g}" if (raio and raio > 0.05) else ""
        ax.text(cx + W * ss / 2, cy + T * ss + 6, "SEÇÃO DO TUBO" + rtxt, fontsize=7.5, ha="center", weight="bold")
        # ---- PERSPECTIVA (wireframe) ----
        isc = min(0.05, 70.0 / L); iox, ioy = 352, 205
        def P(x, y, z): return (iox + (x - y) * C30 * isc, ioy + ((x + y) * S30 + z) * isc)
        v = [(0, 0, 0), (W, 0, 0), (W, L, 0), (0, L, 0), (0, 0, T), (W, 0, T), (W, L, T), (0, L, T)]
        E = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
        for a, b in E:
            pa, pb = P(*v[a]), P(*v[b]); ax.plot([pa[0], pb[0]], [pa[1], pb[1]], "k", lw=0.4)
        zc_face = T if top_face else 0.0
        for typ, y, size in [(f[0], f[1], f[2]) for f in feats_l]:
            if typ == "circle":
                cc = P(W / 2, y, zc_face); ax.add_patch(Circle(cc, size / 2 * isc, fc="0.2", ec="k", lw=0.3))
            else:
                hp, _ = _hexpts(size, r.sext_orient)
                ax.add_patch(Polygon([P(W / 2 + px, y + py, zc_face) for px, py in hp],
                                     closed=True, fc="0.2", ec="k", lw=0.3))
        for typ, y, size in [(f[0], f[1], f[2]) for f in feats_e]:
            if typ == "circle":
                ax.add_patch(Circle(P(0, y, T / 2), size / 2 * isc, fc="0.4", ec="k", lw=0.3))
            else:
                hp, _ = _hexpts(size, r.sext_orient)
                ax.add_patch(Polygon([P(0, y + px, T / 2 + py) for px, py in hp],
                                     closed=True, fc="0.4", ec="k", lw=0.3))
        ax.text(iox - 10, ioy - 6, "PERSPECTIVA", fontsize=7, ha="center", weight="bold")
        # ---- NOTAS ----
        ax.text(26, 74, "NOTAS:", fontsize=6, weight="bold")
        ax.text(26, 68, f"1. Tubo retangular {W:g}×{T:g} mm, parede {wall:g} mm; comprimento {L:g} mm.", fontsize=5.6)
        nl = []
        if feats_l:
            fr = {"ambas": "em ambas as faces largas (sup+inf)",
                  "fundo": "apenas na face larga inferior"}.get(faces, "apenas na face larga superior")
            tf = "hexagonais" if feats_l[0][0] == "hex" else "redondos"
            nl.append(f"Furos {tf} {fr}, linha de centro de {W:g} mm.")
        if feats_e:
            tf = "hexagonais" if feats_e[0][0] == "hex" else "redondos"
            modo = "passantes (atravessam as 2 laterais)" if lat_pass else "em 1 face lateral"
            nl.append(f"Furos {tf} {modo} (faces de {T:g} mm), linha de centro.")
        if nl:
            ax.text(26, 62, "2. " + "  ".join(nl), fontsize=5.4)
        rline = f"  Raio dos cantos do tubo: {raio:g} mm." if (raio and raio > 0.05) else ""
        ax.text(26, 56, f"3. Massa estimada ~ {r.mass:.3f} kg.  Corte/furos no laser de tubo (TubeKit).{rline}", fontsize=5.6)
        if r.comp:
            ax.text(26, 50, f"4. Compensacao de furo: {r.comp:g} mm (corte = nominal + compensacao).", fontsize=5.6)

    _emit(pp_out, path, r.name, "MET-AUTO", f"Tubo {W:g}x{T:g}x{wall:g}", page, data, folha=folha)


# ------------------------------------------------------------------ MESA
def draw_table(r, path=None, data="--/--/----", pp_out=None, folha="01/01"):
    L, Dp, H = r.dims
    ex = getattr(r, "extra", None) or {}
    TW = float(ex.get("perfil", 40.0))     # perfil real da estrutura (largura do metalon)
    Zt = H - TW
    # layout por regioes (sem sobreposicao): esquerda = frontal(cima)+superior(meio);
    # direita = lateral(cima)+perspectiva(baixo); lista de corte no rodape esquerdo.
    n = len(r.cut_list)
    rh = 7
    oy3 = 50 + rh * (n + 1)                       # base VISTA SUPERIOR (lista de corte fica abaixo)
    s = min(0.115, 190.0 / L, 175.0 / max(Dp, 1.0), (258.0 - oy3) / max(H + Dp, 1.0))
    s = max(s, 0.012)

    def page(ax):
        ox = 20
        oy = oy3 + Dp * s + 16                    # base VISTA FRONTAL e LATERAL
        ax.text(ox + L * s / 2, oy + H * s + 6, f"{r.name}  —  meia esquadria nas pontas",
                fontsize=7.5, ha="center", weight="bold")
        # ---- VISTA FRONTAL (sup. esquerda)
        def F(x, z): return (ox + x * s, oy + z * s)
        for (x0, x1) in [(0, TW), (L - TW, L)]:
            ax.add_patch(Rectangle(F(x0, 0), (x1 - x0) * s, H * s, fill=False, lw=1.0))
        ax.add_patch(Rectangle(F(TW, Zt), (L - 2 * TW) * s, TW * s, fill=False, lw=1.0))
        _dimh(ax, ox, ox + L * s, oy - 7, f"{L:g}"); _dimv(ax, oy, oy + H * s, ox - 7, f"{H:g}", side=-1)
        ax.text(ox + L * s / 2, oy - 13, "VISTA FRONTAL", fontsize=7.0, ha="center", weight="bold")
        # ---- VISTA SUPERIOR (meio esquerda)
        def U(x, y): return (ox + x * s, oy3 + y * s)
        for (x0, x1) in [(0, TW), (L - TW, L)]:
            ax.add_patch(Rectangle(U(x0, 0), (x1 - x0) * s, Dp * s, fill=False, lw=1.0))
        for (y0, y1) in [(0, TW), (Dp - TW, Dp)]:
            ax.add_patch(Rectangle(U(TW, y0), (L - 2 * TW) * s, (y1 - y0) * s, fill=False, lw=1.0))
        _dimh(ax, ox, ox + L * s, oy3 - 6, f"{L:g}"); _dimv(ax, oy3, oy3 + Dp * s, ox - 7, f"{Dp:g}", side=-1)
        ax.text(ox + L * s / 2, oy3 - 12, "VISTA SUPERIOR (perímetro)", fontsize=7.0, ha="center", weight="bold")
        # ---- VISTA LATERAL (sup. direita) — quadro de ponta
        ox2 = 232
        def Lt(y, z): return (ox2 + y * s, oy + z * s)
        for (y0, y1) in [(0, TW), (Dp - TW, Dp)]:
            ax.add_patch(Rectangle(Lt(y0, 0), (y1 - y0) * s, Zt * s, fill=False, lw=1.0))
        ax.add_patch(Rectangle(Lt(TW, Zt), (Dp - 2 * TW) * s, TW * s, fill=False, lw=1.0))
        ax.add_patch(Polygon([Lt(0, Zt), Lt(0, H), Lt(TW, H), Lt(TW, Zt)], closed=True, fill=False, lw=1.0))
        ax.add_patch(Polygon([Lt(Dp - TW, Zt), Lt(Dp - TW, H), Lt(Dp, H), Lt(Dp, Zt)], closed=True, fill=False, lw=1.0))
        ax.plot([Lt(0, H)[0], Lt(TW, Zt)[0]], [Lt(0, H)[1], Lt(TW, Zt)[1]], "k", lw=0.9)
        ax.plot([Lt(Dp, H)[0], Lt(Dp - TW, Zt)[0]], [Lt(Dp, H)[1], Lt(Dp - TW, Zt)[1]], "k", lw=0.9)
        ax.annotate("45°", Lt(TW * 0.55, H - TW * 0.45), (ox2 + TW * 1.7 * s, oy + H * s + 3),
                    fontsize=6, ha="center", arrowprops=dict(arrowstyle="->", lw=0.4))
        _dimh(ax, ox2, ox2 + Dp * s, oy - 7, f"{Dp:g}"); _dimv(ax, oy, oy + H * s, ox2 - 7, f"{H:g}", side=-1)
        ax.text(ox2 + Dp * s / 2, oy - 13, "VISTA LATERAL — quadro de ponta (∏)", fontsize=6.8, ha="center", weight="bold")
        # ---- PERSPECTIVA (direita, abaixo da lateral, acima do carimbo)
        wlim = 168.0 / max((L + Dp) * C30, 1.0)
        hlim = max(oy - 20 - 74, 24.0) / max((L + Dp) * S30 + H, 1.0)
        isc = min(0.04, wlim, hlim)
        cxp, ioy = 318.0, 74.0
        iox = cxp - (L - Dp) * C30 * isc / 2.0
        def P(x, y, z): return (iox + (x - y) * C30 * isc, ioy + ((x + y) * S30 + z) * isc)
        mem = [(0, TW, 0, TW, 0, H), (0, TW, Dp - TW, Dp, 0, H), (L - TW, L, 0, TW, 0, H),
               (L - TW, L, Dp - TW, Dp, 0, H), (0, TW, 0, Dp, Zt, H), (L - TW, L, 0, Dp, Zt, H),
               (TW, L - TW, 0, TW, Zt, H), (TW, L - TW, Dp - TW, Dp, Zt, H)]
        E = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
        for (x0, x1, y0, y1, z0, z1) in mem:
            v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                 (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
            for a, b in E:
                pa, pb = P(*v[a]), P(*v[b]); ax.plot([pa[0], pb[0]], [pa[1], pb[1]], "k", lw=0.4)
        ax.text(cxp, ioy - 6, "PERSPECTIVA", fontsize=7, ha="center", weight="bold")
        # ---- LISTA DE CORTE (rodape esquerdo, livre do carimbo)
        tx, tw = 20, 196
        ty = 22 + rh * (n + 1)
        ax.text(tx, ty + 7, "LISTA DE CORTE", fontsize=8, weight="bold")
        hdr = ["Item", "Descrição", "Qtd", "Comp.", "Pontas"]; cw = [14, 80, 14, 26, 62]
        cx = [tx]
        for w in cw: cx.append(cx[-1] + w)
        ax.add_patch(Rectangle((tx, ty - rh * (n + 1)), tw, rh * (n + 1), fill=False, lw=0.7))
        for k, hh in enumerate(hdr): ax.text(cx[k] + 1.5, ty - 5, hh, fontsize=5.2, weight="bold")
        ax.plot([tx, tx + tw], [ty - rh, ty - rh], "k", lw=0.6)
        for ri, (desc, qtd, comp, pontas) in enumerate(r.cut_list):
            yy = ty - rh * (ri + 1)
            if ri % 2 == 0: ax.add_patch(Rectangle((tx, yy - rh), tw, rh, fc="0.94", ec="none"))
            for k, val in enumerate([str(ri + 1), desc, str(qtd), f"{comp:g}", pontas]):
                ax.text(cx[k] + 1.5, yy - 5, val, fontsize=5.0)
        for k in cx[1:-1]: ax.plot([k, k], [ty - rh * (n + 1), ty], "k", lw=0.4)
        tb = ty - rh * (n + 1)
        ax.text(tx, tb - 4, f"Massa estimada ≈ {r.mass:.1f} kg (parede {r.wall:g}).  Comp. = aresta externa.", fontsize=5.0)
        if tb - 10 > 14:
            ax.text(tx, tb - 10, f"Metalon {TW:g}×{TW:g} · meia esquadria 45° nas pontas · "
                    f"travessas longas retas {L - 2 * TW:g} mm.", fontsize=5.2)

    _emit(pp_out, path, r.name, "MET-AUTO", f"Metalon {TW:g}x{TW:g}", page, data, folha=folha)


def draw_chapa(r, path=None, data="--/--/----", pp_out=None, folha="01/01"):
    pts = r.outline or []
    furos = r.furos2d or []
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, miny = min(xs), min(ys)
    W = max(xs) - minx; H = max(ys) - miny
    s = min(230.0 / W, 150.0 / H, 2.2)
    ox, oy = 46, 96

    def page(ax):
        ax.text(210, 281, f"{r.name}", fontsize=8.4, ha="center", weight="bold")
        poly = [(ox + (x - minx) * s, oy + (y - miny) * s) for x, y in pts]
        ax.add_patch(Polygon(poly, closed=True, fill=False, lw=1.4))
        for f in furos:
            cx, cy, tipo, tam = f[0], f[1], f[2], f[3]
            orient = f[4] if len(f) > 4 else 0.0
            X = ox + (cx - minx) * s; Y = oy + (cy - miny) * s
            if tipo in ("sextavado", "hex"):
                hp, _ = _hexpts(tam, orient)
                ax.add_patch(Polygon([(X + px * s, Y + py * s) for px, py in hp],
                                     closed=True, fill=False, lw=1.0, ec="r"))
            else:
                ax.add_patch(Circle((X, Y), tam / 2 * s, fill=False, lw=1.0, ec="r"))
            ax.plot([X, X], [Y - 3, Y + 3], "r", lw=0.4)
            ax.plot([X - 3, X + 3], [Y, Y], "r", lw=0.4)
        _dimh(ax, ox, ox + W * s, oy - 9, f"{W:g}")
        _dimv(ax, oy, oy + H * s, ox - 9, f"{H:g}", side=-1)
        if furos:
            xsh = sorted(f[0] for f in furos)
            f0 = furos[0]
            tipo = f0[2]; tam = f0[3]
            tam_n = r.tam_nominal or tam
            base = f"{len(furos)}x Ø{tam_n:g}" if tipo not in ("sextavado", "hex") else f"{len(furos)}x sextavado ch {tam_n:g}"
            if r.comp:
                base += f" (corte {tam_n + r.comp:g})"
            extra = f"  (eixo a {max(ys) - f0[1]:g} do topo; 1o a {xsh[0] - minx:g} da esq."
            if len(xsh) > 1:
                extra += f"; passo {xsh[1] - xsh[0]:g}"
            extra += ")"
            X0 = ox + (f0[0] - minx) * s; Y0 = oy + (f0[1] - miny) * s
            ax.annotate(base + extra, (X0, Y0), (ox, oy + H * s + 12),
                        fontsize=6.0, arrowprops=dict(arrowstyle="->", lw=0.5))
        ax.text(46, 72, "NOTAS:", fontsize=6, weight="bold")
        ax.text(46, 66, f"1. Chapa cortada a laser. Envelope {W:g} x {H:g} mm.", fontsize=5.8)
        ax.text(46, 60, f"2. Espessura {r.espessura:g} mm.  Massa estimada ~ {r.mass:.3f} kg.", fontsize=5.8)
        ax.text(46, 54, "3. Geometria de corte no arquivo DXF (camadas CORTE e FUROS).", fontsize=5.8)

    _emit(pp_out, path, r.name, "MET-AUTO", f"Chapa esp. {r.espessura:g}", page, data, folha=folha)


def draw_angular(r, path=None, data="--/--/----", pp_out=None, folha="01/01"):
    import math
    W, T, L = r.dims
    wall, raio = r.wall, r.raio
    ang, npc, plano, lado = r.angulo, r.pontas, r.plano, r.lado
    feats = sorted(r.feats, key=lambda f: f[1]) if r.feats else []
    both = (r.faces == "ambas")
    long_high = lado in ("topo", "direita", "A")
    run = 0.0 if ang >= 89.999 else (W if plano == "largura" else T) / math.tan(math.radians(ang))
    s = min(0.6, 250.0 / L)
    qlabel = "largura" if plano == "largura" else "altura"

    def sil(Qd):
        if run <= 0:
            return [(0, 0), (L, 0), (L, Qd), (0, Qd)]
        if npc >= 2:
            return ([(0, Qd), (L, Qd), (L - run, 0), (run, 0)] if long_high
                    else [(run, Qd), (L - run, Qd), (L, 0), (0, 0)])
        return ([(0, Qd), (L, Qd), (L - run, 0), (0, 0)] if long_high
                else [(0, Qd), (L - run, Qd), (L, 0), (0, 0)])

    def page(ax):
        ax.text(210, 281, f"{r.name}", fontsize=8.4, ha="center", weight="bold")

        # ---- VISTA SUPERIOR (face furada): comprimento x largura ----
        oxA, oyA = 30, 214
        cornersA = sil(W) if plano == "largura" else [(0, 0), (L, 0), (L, W), (0, W)]
        ax.add_patch(Polygon([(oxA + y * s, oyA + q * s) for (y, q) in cornersA], closed=True, fill=False, lw=1.3))
        ax.plot([oxA, oxA + L * s], [oyA + W / 2 * s, oyA + W / 2 * s], "k", lw=0.3, ls=(0, (7, 3)))
        for typ, y, size in [(f[0], f[1], f[2]) for f in feats]:
            cx, cy = oxA + y * s, oyA + W / 2 * s
            if typ == "circle":
                ax.add_patch(Circle((cx, cy), size / 2 * s, fill=False, lw=1.0))
            else:
                hp, _ = _hexpts(size, r.sext_orient)
                ax.add_patch(Polygon([(cx + px * s, cy + py * s) for px, py in hp], closed=True, fill=False, lw=1.0))
            ax.plot([cx, cx], [oyA, oyA + W * s], "k", lw=0.3, ls=(0, (7, 3)))
        if feats:
            pts = [0] + [f[1] for f in feats] + [L]
            for a, b in zip(pts[:-1], pts[1:]):
                _dimh(ax, oxA + a * s, oxA + b * s, oyA - 6, f"{b - a:g}")
            typ, y, size = feats[-1][0], feats[-1][1], feats[-1][2]
            nominal = r.tam_nominal or size
            txt = (f"{len(feats)}× Ø{nominal:g}" if typ == "circle" else f"sextavado ch {nominal:g}")
            txt += " (ambas)" if both else " (1 face)"
            if r.comp:
                txt += f"  corte {nominal + r.comp:g}"
            ax.annotate(txt, (oxA + y * s, oyA + W * s), (oxA + L * s + 6, oyA + W * s - 2),
                        fontsize=6, arrowprops=dict(arrowstyle="->", lw=0.5))
        _dimh(ax, oxA, oxA + L * s, oyA - 13, f"{L:g}")
        _dimv(ax, oyA, oyA + W * s, oxA - 7, f"{W:g}", side=-1)
        ax.text(oxA + L * s / 2, oyA - 21, "VISTA SUPERIOR (face furada)", fontsize=7.3, ha="center", weight="bold")

        # ---- VISTA LATERAL: comprimento x altura ----
        oxB, oyB = 30, 168
        cornersB = sil(T) if plano != "largura" else [(0, 0), (L, 0), (L, T), (0, T)]
        ax.add_patch(Polygon([(oxB + y * s, oyB + q * s) for (y, q) in cornersB], closed=True, fill=False, lw=1.3))
        if plano == "largura":  # lateral nao chanfrada -> mostra furos como rasgos nas paredes
            for typ, y, size in [(f[0], f[1], f[2]) for f in feats]:
                wgap = (size if typ == "circle" else size / C30) * s
                cx = oxB + y * s
                ax.add_patch(Rectangle((cx - wgap / 2, oyB + T * s - wall * s - 0.2), wgap, wall * s + 0.4, fc="w", ec="k", lw=0.5))
                if both:
                    ax.add_patch(Rectangle((cx - wgap / 2, oyB - 0.2), wgap, wall * s + 0.4, fc="w", ec="k", lw=0.5))
        if run > 0:
            ax.annotate(f"{ang:g}°", (oxB + (L - run / 2) * s, oyB + T / 2 * s),
                        (oxB + L * s + 6, oyB + T * s - 2), fontsize=8, weight="bold",
                        arrowprops=dict(arrowstyle="->", lw=0.5))
        _dimh(ax, oxB, oxB + L * s, oyB - 6, f"{L:g}")
        _dimv(ax, oyB, oyB + T * s, oxB - 7, f"{T:g}", side=-1)
        ax.text(oxB + L * s / 2, oyB - 13,
                f"VISTA LATERAL — {npc} ponta(s) em {ang:g}°" if run > 0 else "VISTA LATERAL — pontas retas 90°",
                fontsize=7.3, ha="center", weight="bold")

        # ---- SEÇÃO ----
        ss = min(2.4, 66.0 / max(W, T)); cx, cy = 40, 92
        if raio and raio > 0.05:
            outer = _rrect_pts(cx, cy, W * ss, T * ss, raio * ss)
            inner = _rrect_pts(cx + wall * ss, cy + wall * ss, (W - 2 * wall) * ss, (T - 2 * wall) * ss, max(raio - wall, 0) * ss)
            ax.plot([p[0] for p in outer], [p[1] for p in outer], "k", lw=1.2)
            ax.plot([p[0] for p in inner], [p[1] for p in inner], "k", lw=0.8)
        else:
            ax.add_patch(Rectangle((cx, cy), W * ss, T * ss, fill=False, lw=1.2))
            ax.add_patch(Rectangle((cx + wall * ss, cy + wall * ss), (W - 2 * wall) * ss, (T - 2 * wall) * ss, fill=False, lw=0.8))
        _dimh(ax, cx, cx + W * ss, cy - 6, f"{W:g}")
        _dimv(ax, cy, cy + T * ss, cx + W * ss + 7, f"{T:g}")
        ax.text(cx + W * ss / 2, cy + T * ss + 6, "SEÇÃO", fontsize=7.3, ha="center", weight="bold")

        # ---- LISTA DE CORTE ----
        tx, ty = 232, 150
        ax.text(tx, ty, "LISTA DE CORTE", fontsize=8, weight="bold")
        ax.add_patch(Rectangle((tx, ty - 36), 176, 32, fill=False, lw=0.7))
        ax.text(tx + 3, ty - 9, f"Qtd: {r.qtd}     Comprimento: {L:g} mm", fontsize=6)
        ang_txt = f"{npc}x corte {ang:g}° ({qlabel}, lado {lado})" if run > 0 else "2 pontas retas 90°"
        ax.text(tx + 3, ty - 17, f"Pontas: {ang_txt}", fontsize=6)
        if feats:
            nominal = r.tam_nominal or feats[0][2]
            fk = "Ø" if feats[0][0] == "circle" else "sext ch "
            ax.text(tx + 3, ty - 25, f"Furos: {len(feats)}x {fk}{nominal:g}" + (" (ambas faces)" if both else " (1 face)"), fontsize=6)
        ax.text(tx + 3, ty - 33, f"Secao {W:g}x{T:g} parede {wall:g}" + (f", raio {raio:g}" if raio else ""), fontsize=6)

        # ---- NOTAS ----
        ax.text(30, 70, "NOTAS:", fontsize=6, weight="bold")
        ax.text(30, 64, f"1. Tubo {W:g}×{T:g} mm, parede {wall:g} mm, comprimento {L:g} mm (lado mais longo).", fontsize=5.5)
        if run > 0:
            ax.text(30, 58, f"2. Corte angular {ang:g}° em {npc} ponta(s), plano da {qlabel}; lado longo: {lado}.", fontsize=5.5)
        else:
            ax.text(30, 58, "2. Cortes retos (90°) nas pontas.", fontsize=5.5)
        n3 = f"3. Massa ~ {r.mass:.3f} kg/peça."
        if feats:
            n3 += f"  Furos na linha de centro da face de {W:g} mm" + (f"; compensacao {r.comp:g} mm." if r.comp else ".")
        ax.text(30, 52, n3, fontsize=5.5)

    _emit(pp_out, path, r.name, "MET-AUTO", f"Tubo {W:g}x{T:g}x{wall:g}", page, data, folha=folha)


def draw_mesa_c(r, path=None, data="--/--/----", pp_out=None, folha="01/01"):
    W, Dp, H = r.dims
    e = r.extra
    foot, flag, Hq, diag, ang = e["foot"], e["flag"], e["Hq"], e["diag"], e["ang"]
    b, top_th, inset = e["perfil"], e["top_th"], e["inset"]
    outer, inner = e["outer"], e["inner"]

    def page(ax):
        ax.text(210, 289, f"{r.name}", fontsize=8.4, ha="center", weight="bold")

        # ---- VISTA LATERAL DO PÉ (elevacao do quadro) ----
        s = min(0.22, 185.0 / Hq)
        ox, oy = 42, 72
        ax.add_patch(Polygon([(ox + x * s, oy + z * s) for (x, z) in outer], closed=True, fill=False, lw=1.5))
        ax.add_patch(Polygon([(ox + x * s, oy + z * s) for (x, z) in inner], closed=True, fill=False, lw=1.0))
        _dimv(ax, oy, oy + Hq * s, ox - 9, f"{Hq:g}", side=-1)
        _dimh(ax, ox, ox + foot * s, oy - 8, f"{foot:g}")
        _dimh(ax, ox, ox + flag * s, oy + Hq * s + 7, f"{flag:g}")
        ax.annotate(f"diagonal {diag:.0f}  ({ang:.0f}°)",
                    (ox + (foot + flag) / 2 * s, oy + Hq / 2 * s),
                    (ox + foot * s + 8, oy + Hq * 0.62 * s), fontsize=6.2,
                    arrowprops=dict(arrowstyle="->", lw=0.5))
        ax.text(ox + 2, oy + Hq * s - 6, "poste\n(fundo)", fontsize=5.4, va="top")
        ax.text(ox + foot * s * 0.5, oy - 16, "VISTA LATERAL DO PÉ", fontsize=7.4, ha="center", weight="bold")
        ax.text(ox + foot * s * 0.5, oy - 22, f"tubo {b:g}×{b:g} mm", fontsize=5.6, ha="center")

        # ---- PLANTA (tampo + pés) ----
        s2 = min(0.13, 150.0 / W)
        px, py = 250, 175
        ax.add_patch(Rectangle((px, py), Dp * s2, W * s2, fill=False, lw=1.3))  # tampo
        for y0 in (inset, W - inset - b):
            ax.add_patch(Rectangle((px, py + y0 * s2), foot * s2, b * s2, fc="0.25", ec="k", lw=0.4))
        if e.get("com_rail"):
            ax.add_patch(Rectangle((px + (flag / 2 - b / 2) * s2, py + inset * s2),
                                   b * s2, (W - 2 * inset) * s2, fc="0.55", ec="k", lw=0.3))
        _dimh(ax, px, px + Dp * s2, py - 6, f"{Dp:g}")
        _dimv(ax, py, py + W * s2, px - 7, f"{W:g}", side=-1)
        ax.text(px + Dp * s2 / 2, py - 12, "PLANTA (tampo e pés)", fontsize=7.0, ha="center", weight="bold")
        ax.text(px + Dp * s2 + 3, py + (W - inset) * s2, "fundo →", fontsize=5.0)

        # ---- LISTA DE CORTE ----
        tx, ty = 240, 150
        ax.text(tx, ty, "LISTA DE CORTE", fontsize=8, weight="bold")
        nrows = len(r.cut_list)
        ax.add_patch(Rectangle((tx, ty - 6 - 8 * nrows), 168, 6 + 8 * nrows, fill=False, lw=0.7))
        ax.text(tx + 3, ty - 6, "Peça | Qtd | Comp.(mm) | Cortes", fontsize=5.6, weight="bold")
        for k, c in enumerate(r.cut_list):
            ax.text(tx + 3, ty - 14 - 8 * k, f"{c[0]} | {c[1]} | {c[2]:g} | {c[3]}", fontsize=5.3)

        # ---- NOTAS ----
        ax.text(42, 56, "NOTAS:", fontsize=6, weight="bold")
        ax.text(42, 50, f"1. Mesa {W:g}×{Dp:g} mm, altura {H:g} mm. Pés laterais em 'C' em tubo {b:g}×{b:g} mm.", fontsize=5.4)
        ax.text(42, 44, f"2. Aba superior {flag:g} mm, pé {foot:g} mm, diagonal {diag:.0f} mm (~{ang:.0f}° com o piso).", fontsize=5.4)
        ax.text(42, 38, f"3. Estrutura metálica ~ {r.mass:.2f} kg (sem tampo). Tampo {Dp:g}×{W:g}, esp. {top_th:g} mm.", fontsize=5.4)
        if e.get("espelhado"):
            ax.text(42, 32, "4. Pés ESPELHADOS.", fontsize=5.4)

    _emit(pp_out, path, r.name, "MET-AUTO", f"Mesa pés C {b:g}x{b:g}", page, data, folha=folha)


def draw(r, path=None, data="--/--/----", pp_out=None, folha="01/01"):
    """Despacha para o desenho correto conforme r.kind."""
    if r.kind == "mesa":
        draw_table(r, path, data=data, pp_out=pp_out, folha=folha)
    elif r.kind == "mesa_c":
        draw_mesa_c(r, path, data=data, pp_out=pp_out, folha=folha)
    elif r.kind == "chapa":
        draw_chapa(r, path, data=data, pp_out=pp_out, folha=folha)
    elif r.kind == "angular":
        draw_angular(r, path, data=data, pp_out=pp_out, folha=folha)
    elif r.kind == "tubo_redondo":
        draw_tube_round(r, path, data=data, pp_out=pp_out, folha=folha)
    else:
        draw_tube(r, path, data=data, pp_out=pp_out, folha=folha)


def draw_tube_round(r, path=None, data="--/--/----", pp_out=None, folha="01/01"):
    OD, _, L = r.dims
    wall = r.wall
    ex = getattr(r, "extra", None) or {}
    bitola = ex.get("bitola", "") or f"Ø{OD:g}"
    passante = bool(ex.get("passante", True))
    feats = sorted(r.feats, key=lambda f: f[1])
    s = min(0.62, 240.0 / L)

    def page(ax):
        ax.text(210, 282, f"{r.name}", fontsize=8.0, ha="center", weight="bold")
        # ---- VISTA LATERAL (retângulo L × OD)
        ox, oy = 22, 170
        ax.add_patch(Rectangle((ox, oy), L * s, OD * s, fill=False, lw=1.2))
        ax.plot([ox, ox + L * s], [oy + OD * s / 2, oy + OD * s / 2], "k", lw=0.4, ls=(0, (8, 4)))
        for typ, y, size in [(f[0], f[1], f[2]) for f in feats]:
            cx, cy = ox + y * s, oy + OD * s / 2
            ax.add_patch(Circle((cx, cy), size / 2 * s, fill=False, lw=1.0))
            ax.plot([cx, cx], [oy, oy + OD * s], "k", lw=0.3, ls=(0, (6, 3)))
        _dimv(ax, oy, oy + OD * s, ox - 7, f"{OD:g}", side=-1)
        pts = [0] + [f[1] for f in feats] + [L]
        for a, b in zip(pts[:-1], pts[1:]):
            _dimh(ax, ox + a * s, ox + b * s, oy - 7, f"{b - a:g}")
        ax.text(ox + L * s / 2, oy - 14, "VISTA LATERAL", fontsize=7.5, ha="center", weight="bold")
        if feats:
            modo = "passante (diametral)" if passante else "1 parede"
            ax.annotate(f"{len(feats)}× Ø{r.tam_nominal:g} {modo}",
                        (ox + feats[-1][1] * s, oy + OD * s), (ox + L * s + 6, oy + OD * s - 2),
                        fontsize=5.6, arrowprops=dict(arrowstyle="->", lw=0.5))

        # ---- SEÇÃO (dois círculos concêntricos)
        scx, scy = 250, 150
        ssec = min(1.6, 78.0 / OD)
        Rp = OD / 2 * ssec
        ax.add_patch(Circle((scx, scy), Rp, fill=False, lw=1.3))
        ax.add_patch(Circle((scx, scy), max(OD / 2 - wall, 0.1) * ssec, fill=False, lw=0.9))
        _dimh(ax, scx - Rp, scx + Rp, scy - Rp - 8, f"Ø{OD:g}")
        ax.annotate(f"parede {wall:g}", (scx + Rp - wall * ssec / 2, scy),
                    (scx + Rp + 6, scy + 10), fontsize=5.6, arrowprops=dict(arrowstyle="-", lw=0.4))
        ax.text(scx, scy + Rp + 7, f"SEÇÃO — {bitola}", fontsize=7.5, ha="center", weight="bold")

        # ---- PERSPECTIVA (cilindro)
        pcx, pcy = 330, 220
        pl = min(70.0, L * 0.10); pr = min(16.0, OD * 0.18)
        dx, dy = pl * 0.9, pl * 0.35
        ax.add_patch(Ellipse((pcx, pcy), pr * 0.7, pr * 1.6, fill=False, lw=1.0))
        ax.add_patch(Ellipse((pcx + dx, pcy + dy), pr * 0.7, pr * 1.6, fill=False, lw=1.0, ls=(0, (4, 3))))
        ax.plot([pcx, pcx + dx], [pcy + pr * 0.8, pcy + dy + pr * 0.8], "k", lw=1.0)
        ax.plot([pcx, pcx + dx], [pcy - pr * 0.8, pcy + dy - pr * 0.8], "k", lw=1.0)
        ax.text(pcx + dx / 2, pcy - pr * 1.6, "PERSPECTIVA", fontsize=7, ha="center", weight="bold")

        # ---- NOTAS
        ax.text(22, 70, "NOTAS:", fontsize=7, weight="bold")
        ax.text(26, 62, f"1. Tubo redondo {bitola} (Ø {OD:g} mm), parede {wall:g} mm, comprimento {L:g} mm.",
                fontsize=5.8)
        if feats:
            modo = "passantes (diametral)" if passante else "em 1 parede"
            ax.text(26, 56, f"2. {len(feats)} furo(s) Ø{r.tam_nominal:g} {modo} na linha de centro.", fontsize=5.8)
        ax.text(26, 50, f"{'3' if feats else '2'}. Massa estimada ~ {r.mass:.3f} kg. Corte/furos no laser de tubo.",
                fontsize=5.8)

    _emit(pp_out, path, r.name, "MET-AUTO", f"Tubo red. {bitola} e={wall:g}", page, data, folha=folha)


def draw_multi(results, path, data="--/--/----"):
    """Gera UM PDF multipagina, uma peca por pagina (com numeracao de folha)."""
    n = len(results)
    with PdfPages(str(path)) as pp:
        for i, r in enumerate(results, 1):
            draw(r, data=data, pp_out=pp, folha=f"{i:02d}/{n:02d}")
