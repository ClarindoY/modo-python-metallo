"""
Interface web (Streamlit) do gerador de pecas Metallo / Concetto.

Rodar:
    streamlit run app.py
"""
import os
import io
import re
import base64
import zipfile
import tempfile
import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

import metallo_cad as mc
from metallo_cad import exporters, drawing, laser, etiquetas, flanges, orcamento, modelos, planificacao, promobile, nesting_linear, nest_report, itubecam, puxador
from metallo_cad import bancada, bancada_pdf, cubas as cubas_lib, bancadas_lib, saiote, paneleiro as paneleiro_mod
from metallo_cad import ralo as ralo_lib, ralos_lib
from metallo_cad import torre_inox
from metallo_cad import peca_plana
from metallo_cad.config import LOGO

APP_VERSAO = "v6.1 · 14/07/2026"
st.set_page_config(page_title="METALLO IA - Gerador de Pecas", page_icon="⚡",
                   layout="centered", initial_sidebar_state="collapsed")

# --------------------------------------------------------------------- estilo (escuro metalizado)
# ------------------------------------------------------------------ temas de interface
TEMAS_UI = {
    "Ciano Tech":    {"a1": "#00e5ff", "a2": "#7c4dff", "btn": "#021018"},
    "Ambar Forja":   {"a1": "#ffb300", "a2": "#ff6d3d", "btn": "#1a1204"},
    "Aco Prata":     {"a1": "#d6e0ec", "a2": "#8aa7c9", "btn": "#10151c"},
    "Verde Solda":   {"a1": "#39ff88", "a2": "#00c853", "btn": "#04170c"},
    "Rubi Plasma":   {"a1": "#ff3d5a", "a2": "#ff8a3d", "btn": "#1a060a"},
    "Azul Aço":      {"a1": "#4da3ff", "a2": "#2bd9d9", "btn": "#061223"},
    "Roxo Neon":     {"a1": "#b26bff", "a2": "#ff4dd2", "btn": "#120621"},
    "Dourado Laser": {"a1": "#ffd54d", "a2": "#ff9e3d", "btn": "#1c1404"},
    "Corten":        {"a1": "#ff7a3d", "a2": "#d9a05b", "btn": "#190c04"},
}


def _rgba(hexcolor, alpha):
    h = hexcolor.lstrip("#")
    return "rgba(%d,%d,%d,%s)" % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _tema_arquivo():
    raiz = os.environ.get("DATA_DIR") or os.path.join(os.getcwd(), "dados")
    try:
        os.makedirs(raiz, exist_ok=True)
    except Exception:
        pass
    return os.path.join(raiz, "ui_tema.txt")


def _tema_salvo():
    try:
        v = open(_tema_arquivo(), encoding="utf-8").read().strip()
        return v if v in TEMAS_UI else None
    except Exception:
        return None


def _salva_tema():
    try:
        open(_tema_arquivo(), "w", encoding="utf-8").write(st.session_state.get("ui_tema", ""))
    except Exception:
        pass


APP_BUILD = "v2026.07.14 · PDFs revisados + aba Configurações (logo/empresa + aparência)"

APARENCIA_PADRAO = {"modo": "Escuro", "largura": "Normal", "densidade": "Confortável",
                    "grade": True, "animacoes": True}


def _aparencia_arquivo():
    raiz = os.environ.get("DATA_DIR") or os.path.join(os.getcwd(), "dados")
    try:
        os.makedirs(raiz, exist_ok=True)
    except Exception:
        pass
    return os.path.join(raiz, "ui_aparencia.json")


def _aparencia_carrega():
    import json
    try:
        v = json.load(open(_aparencia_arquivo(), encoding="utf-8"))
        return {**APARENCIA_PADRAO, **v}
    except Exception:
        return dict(APARENCIA_PADRAO)


def _aparencia_salva(v):
    import json
    try:
        json.dump(v, open(_aparencia_arquivo(), "w", encoding="utf-8"))
    except Exception:
        pass


if "ui_aparencia" not in st.session_state:
    st.session_state["ui_aparencia"] = _aparencia_carrega()
_AP = st.session_state["ui_aparencia"]

if "ui_tema" not in st.session_state:
    st.session_state["ui_tema"] = _tema_salvo() or "Ciano Tech"
_tsel1, _tsel2 = st.columns([4.1, 1.7])
with _tsel2:
    _tema_nome = st.selectbox("🎨 Tema", list(TEMAS_UI.keys()), key="ui_tema",
                              on_change=_salva_tema)
    st.caption(APP_BUILD)
_T = TEMAS_UI.get(_tema_nome, TEMAS_UI["Ciano Tech"])

_CSS = """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');
      :root{ --neon:@A1@; --neon2:@A2@; --line:@A1_16@;
             --ink:#e8f1f8; --muted:#8fa3b8; }
      .stApp{
        background:
          radial-gradient(900px 480px at 15% -10%, @A1_10@, transparent 55%),
          radial-gradient(900px 520px at 90% 0%, @A2_10@, transparent 55%),
          linear-gradient(@A1_035@ 1px, transparent 1px),
          linear-gradient(90deg, @A1_035@ 1px, transparent 1px),
          linear-gradient(180deg,#070b12 0%, #04060b 100%);
        background-size:auto,auto,44px 44px,44px 44px,auto;
        color:var(--ink); font-family:'Rajdhani',sans-serif; }
      [data-testid="stHeader"]{ background:transparent; }
      #MainMenu, footer{ visibility:hidden; }
      .block-container{ max-width:940px; padding-top:1.0rem; padding-bottom:3rem; }

      .hero{ position:relative; display:flex; align-items:center; gap:20px; border-radius:18px;
        padding:22px 26px; margin:4px 0 18px; overflow:hidden;
        background:linear-gradient(135deg, rgba(10,18,32,.92), rgba(6,10,18,.88));
        border:1px solid var(--line); backdrop-filter:blur(10px);
        box-shadow:0 0 0 1px @A1_06@, 0 18px 48px rgba(0,0,0,.6), 0 0 34px @A1_10@ inset; }
      .hero::before{ content:""; position:absolute; inset:0; pointer-events:none;
        background:linear-gradient(100deg, transparent 30%, @A1_10@ 48%, transparent 62%);
        animation:sweep 6s linear infinite; }
      @keyframes sweep{ 0%{transform:translateX(-70%);} 100%{transform:translateX(70%);} }
      .hero img{ height:58px; border-radius:10px;
        box-shadow:0 0 18px @A1_35@, 0 2px 12px rgba(0,0,0,.6); }
      .hero .t{ font-family:'Orbitron',sans-serif; font-size:1.7rem; font-weight:900;
        letter-spacing:.14em; line-height:1.05; margin:0;
        background:linear-gradient(90deg,#eaffff 10%, var(--neon) 55%, var(--neon2) 100%);
        -webkit-background-clip:text; background-clip:text; color:transparent;
        filter:drop-shadow(0 0 12px @A1_35@); }
      .hero .badge{ display:inline-block; font-family:'Orbitron',sans-serif; font-size:.62rem;
        font-weight:700; letter-spacing:.28em; color:var(--neon);
        border:1px solid @A1_45@; border-radius:999px; padding:3px 12px;
        margin-top:7px; box-shadow:0 0 14px @A1_22@ inset, 0 0 10px @A1_18@;
        text-transform:uppercase; }
      .hero .s{ color:var(--muted); font-size:.86rem; letter-spacing:.06em; margin:7px 0 0; }

      div[data-testid="stVerticalBlockBorderWrapper"]{
        background:linear-gradient(150deg, rgba(13,21,36,.72), rgba(7,11,19,.66));
        border:1px solid var(--line) !important; border-radius:16px;
        backdrop-filter:blur(8px);
        box-shadow:0 12px 34px rgba(0,0,0,.55), 0 0 22px @A1_05@ inset; }

      div[data-baseweb="select"] > div{ border-radius:10px !important;
        background:rgba(6,11,19,.9) !important; border:1px solid @A1_22@ !important; }
      .stTextInput input, .stNumberInput input{ border-radius:10px !important;
        background:rgba(6,11,19,.9) !important; color:var(--ink) !important;
        border-color:@A1_22@ !important; }
      .stTextInput input:focus, .stNumberInput input:focus{
        box-shadow:0 0 0 1px var(--neon), 0 0 14px @A1_25@ !important; }

      .stButton > button{
        position:relative; border-radius:14px; font-weight:600; font-size:1.02rem; color:#dcebf5;
        font-family:'Rajdhani',sans-serif; letter-spacing:.03em;
        border:1px solid @A1_14@; padding:15px 46px 15px 22px;
        justify-content:flex-start; text-align:left;
        background:linear-gradient(180deg, rgba(16,26,42,.85), rgba(9,14,24,.85));
        box-shadow:0 4px 16px rgba(0,0,0,.45), inset 3px 0 0 @A1_55@;
        transition:all .18s ease; }
      .stButton > button:hover{
        border-color:@A1_50@; color:#fff; transform:translateX(3px);
        box-shadow:0 6px 22px rgba(0,0,0,.5), 0 0 20px @A1_20@, inset 3px 0 0 var(--neon); }
      .stButton > button::after{ content:"\203A"; position:absolute; right:18px; top:50%;
        transform:translateY(-50%); color:var(--neon); font-size:1.5rem; font-weight:700;
        line-height:0; text-shadow:0 0 10px @A1_60@; }
      .stButton > button[kind="primary"], [data-testid="baseButton-primary"], .stDownloadButton > button{
        border-radius:12px; font-weight:800; letter-spacing:.06em; color:@BTN@;
        font-family:'Rajdhani',sans-serif; text-transform:uppercase;
        border:1px solid @A1_60@; padding:.68rem 1.1rem;
        justify-content:center; text-align:center;
        background:linear-gradient(135deg, @A1@ 0%, @A1@ 45%, @A2@ 100%);
        box-shadow:0 0 18px @A1_35@, 0 6px 18px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.45);
        transition:all .16s ease; }
      .stButton > button[kind="primary"]:hover, [data-testid="baseButton-primary"]:hover, .stDownloadButton > button:hover{
        filter:brightness(1.12); transform:translateY(-1px); color:@BTN@;
        box-shadow:0 0 28px @A1_55@, 0 8px 22px rgba(0,0,0,.55); }
      .stButton > button[kind="primary"]::after, [data-testid="baseButton-primary"]::after{ content:""; }
      .ph-icon{ display:flex; justify-content:center; margin:6px 0 14px; }
      .ph-icon img{ height:98px; width:98px; object-fit:cover; border-radius:24px;
        border:1px solid @A1_35@; box-shadow:0 0 26px @A1_30@, 0 10px 30px rgba(0,0,0,.55); }

      [data-testid="stMetric"]{
        background:linear-gradient(150deg, rgba(13,22,38,.8), rgba(7,11,19,.75));
        border:1px solid var(--line); border-radius:14px; padding:14px 16px;
        box-shadow:0 4px 16px rgba(0,0,0,.45), 0 0 16px @A1_06@ inset; }
      [data-testid="stMetricValue"]{ font-size:1.22rem; font-weight:700; color:var(--neon);
        font-family:'Orbitron',sans-serif; text-shadow:0 0 12px @A1_35@; }
      [data-testid="stMetricLabel"]{ color:var(--muted); letter-spacing:.05em; }

      .stTabs [data-baseweb="tab-list"]{ gap:6px; border-bottom:1px solid @A1_15@; }
      .stTabs [data-baseweb="tab"]{ border-radius:10px 10px 0 0; padding:8px 16px;
        font-family:'Rajdhani',sans-serif; font-weight:600; letter-spacing:.03em; }
      .stTabs [aria-selected="true"]{ color:var(--neon) !important; text-shadow:0 0 10px @A1_45@; }

      [data-testid="stExpander"] summary{ font-weight:600; letter-spacing:.02em; }
      hr{ border-color:@A1_14@; }
      h2, h3, h4, h5{ letter-spacing:.03em; color:#eafaff;
        font-family:'Rajdhani',sans-serif; font-weight:700; }
    </style>
"""
for _tok, _alpha in [("@A1_05@", ".05"), ("@A1_06@", ".06"), ("@A1_10@", ".10"), ("@A1_14@", ".14"),
                     ("@A1_15@", ".15"), ("@A1_16@", ".16"), ("@A1_18@", ".18"), ("@A1_20@", ".20"),
                     ("@A1_22@", ".22"), ("@A1_25@", ".25"), ("@A1_30@", ".30"), ("@A1_35@", ".35"),
                     ("@A1_45@", ".45"), ("@A1_50@", ".50"), ("@A1_55@", ".55"), ("@A1_60@", ".60"),
                     ("@A1_035@", ".035")]:
    _CSS = _CSS.replace(_tok, _rgba(_T["a1"], _alpha))
_CSS = _CSS.replace("@A2_10@", _rgba(_T["a2"], ".10"))
_CSS = _CSS.replace("@A1@", _T["a1"]).replace("@A2@", _T["a2"]).replace("@BTN@", _T["btn"])
# ---- aparência (além das cores): modo, largura, densidade, grade, animações
_LARG = {"Normal": "940px", "Larga": "1200px", "Total": "98%"}[_AP.get("largura", "Normal")]
_CSS = _CSS.replace("max-width:940px", f"max-width:{_LARG}")
if _AP.get("densidade") == "Compacto":
    _CSS = _CSS.replace("padding-top:1.0rem; padding-bottom:3rem;",
                        "padding-top:0.4rem; padding-bottom:1.2rem;")
    _CSS += "<style>div[data-testid='stVerticalBlock']{gap:0.55rem;}</style>"
if not _AP.get("grade", True):
    _CSS = _CSS.replace("linear-gradient(@A1_035@ 1px, transparent 1px),", "")
    _CSS = _CSS.replace("linear-gradient(90deg, @A1_035@ 1px, transparent 1px),", "")
    _CSS = _CSS.replace("background-size:auto,auto,44px 44px,44px 44px,auto;",
                        "background-size:auto,auto,auto;")
if not _AP.get("animacoes", True):
    _CSS += "<style>.hero::before{animation:none !important; display:none;}</style>"
if _AP.get("modo") == "Claro":
    _CSS += """<style>
      .stApp{ background:
          radial-gradient(900px 480px at 15% -10%, rgba(0,0,0,.04), transparent 55%),
          linear-gradient(180deg,#f2f5f9 0%, #e8edf4 100%) !important;
          color:#16222f !important; }
      :root{ --ink:#16222f; --muted:#51677e; }
      .hero{ background:linear-gradient(135deg,#ffffffee,#eef2f7ee) !important; }
      [data-testid="stMarkdownContainer"], label, p, span{ color:#16222f; }
    </style>"""
st.markdown(_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------- helpers
def _logo_b64():
    try:
        return base64.b64encode(LOGO.read_bytes()).decode()
    except Exception:
        return ""


def gerar_zip(r, formatos=("igs", "step")) -> bytes:
    """Gera os arquivos de UMA peca e devolve um .zip em memoria.
    formatos: quais formatos 3D incluir — ('igs',), ('step',) ou ambos."""
    formatos = tuple(formatos)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        arquivos = []
        pdf = d / f"{r.name}.pdf"; drawing.draw(r, pdf); arquivos.append(pdf)
        if getattr(r, "shape", None) is not None:
            if "igs" in formatos:
                ig = d / f"{r.name}.igs"; exporters.to_iges(r, ig); arquivos.append(ig)
            if "step" in formatos:
                st_ = d / f"{r.name}.step"; exporters.to_step(r, st_); arquivos.append(st_)
        if getattr(r, "outline", None):
            dxf = d / f"{r.name}.dxf"; exporters.to_dxf(r, dxf); arquivos.append(dxf)
        for nome, solido in r.parts.items():
            if "igs" in formatos:
                a = d / f"{nome}.igs"; exporters.to_iges(solido, a); arquivos.append(a)
            if "step" in formatos:
                b = d / f"{nome}.step"; exporters.to_step(solido, b); arquivos.append(b)
        try:
            png = d / f"{r.name}.png"; png.write_bytes(drawing.draw_png(r)); arquivos.append(png)
        except Exception:
            pass
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for a in arquivos:
                z.write(a, f"{r.name}/{a.name}")     # tudo dentro de uma pasta
        return buf.getvalue()


def zip_flange(nome, dxf_data, png_data, pdf_data=None):
    """Empacota DXF + preview PNG (+ PDF) de uma peça plana dentro de uma pasta."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{nome}/{nome}.dxf", dxf_data)
        z.writestr(f"{nome}/{nome}.png", png_data)
        if pdf_data is not None:
            z.writestr(f"{nome}/{nome}.pdf", pdf_data)
    return buf.getvalue()


def _norm_promobile(pl):
    out = []
    for p in pl:
        out.append({"perfil": p["rotulo"], "rotulo": p["rotulo"], "id": p["id"],
                    "comprimento": p["comprimento"], "qtd": p["qtd"],
                    "obra": p.get("obra", ""), "modulo": p.get("modulo", ""),
                    "material": p.get("material", ""), "cod_item": p.get("cod_item") or p["id"],
                    "tipo": p.get("tipo"), "secao": p.get("secao"), "esp": p.get("esp")})
    return out


def ler_lista_arquivo(up):
    """Lê CSV (ProMobile) ou XLSX (relatório de nesting da máquina).
    Retorna (fonte, pecas, rep): fonte = 'maquina' | 'promobile'."""
    nome = up.name.lower()
    data = up.getvalue()
    if nome.endswith((".xlsx", ".xls")):
        try:
            rep = nest_report.ler_relatorio(data)
            if rep.get("barras") or rep.get("pecas"):
                pecas = []
                for p in nest_report.pecas_simples(rep):
                    info = promobile.classificar(p["perfil"])
                    pecas.append({"perfil": p["perfil"], "rotulo": info.get("rotulo", p["perfil"]),
                                  "id": p["id"], "comprimento": p["comprimento"], "qtd": p["qtd"],
                                  "obra": "", "modulo": "", "material": info.get("material", ""),
                                  "cod_item": p["id"], "tipo": info.get("tipo"),
                                  "secao": info.get("secao"), "esp": info.get("esp")})
                return ("maquina", pecas, rep)
        except Exception:
            pass
        dfx = pd.read_excel(io.BytesIO(data), header=None, dtype=str).fillna("")
        txt = "\n".join(";".join(str(c) for c in row) for row in dfx.values.tolist())
        return ("promobile", _norm_promobile(promobile.parse_csv(txt)), None)
    return ("promobile", _norm_promobile(promobile.parse_csv(data)), None)


def _multi_furos_calc(borda, passo, total):
    """Gera posições de furos: 1º a 'borda' da ponta, espaçados de 'passo', dentro de 'total'.
    Os furos ficam simétricos (recuo igual nas duas pontas)."""
    borda = float(borda); passo = float(passo); total = float(total)
    if passo <= 0 or total <= 0:
        return []
    util = total - 2 * borda
    if util < 0:
        return [round(total / 2.0, 2)]
    n = int(round(util / passo)) + 1
    sobra = total - (n - 1) * passo
    ini = sobra / 2.0
    return [round(ini + k * passo, 2) for k in range(n)]


def _aplica_multifuros(destinos, borda, passo, total):
    pos = _multi_furos_calc(borda, passo, total)
    s = ", ".join(f"{p:g}" for p in pos)
    for dk in destinos:
        st.session_state[dk] = s


def _ui_biblioteca_dxf(kp="lib"):
    """Biblioteca de modelos DXF (upload + lista), reutilizável em várias seções."""
    st.caption("Anexe **seus** arquivos .dxf, dê um **nome** a cada modelo e eles ficam salvos "
               "para reusar (idênticos). Use seus próprios desenhos ou arquivos que você tenha "
               "direito de usar.")
    up = st.file_uploader("Arquivo DXF do modelo", type=["dxf"], key=f"{kp}_up")
    nome_mod = st.text_input("Nome do modelo", "", key=f"{kp}_modnome",
                             placeholder="ex.: Geométrico 01, Floral, Vazado losango")
    if up is not None:
        data = up.read()
        try:
            info = modelos.validar(data)
            st.image(flanges.render_dxf_png(data),
                     caption=f"{up.name} — {info['n_entidades']} entidades · "
                             f"{info['bbox'][0]:.0f}×{info['bbox'][1]:.0f} mm", use_container_width=True)
            if st.button("💾 Salvar modelo", type="primary", use_container_width=True, key=f"{kp}_save"):
                if not nome_mod.strip():
                    st.warning("Dê um nome ao modelo antes de salvar.")
                else:
                    fn = modelos.salvar_modelo(nome_mod, data)
                    st.success(f"Modelo '{nome_mod}' salvo como {fn}."); st.rerun()
        except Exception as e:
            st.error("DXF inválido ou não suportado: " + str(e))
    salvos = modelos.listar_modelos()
    st.markdown(f"**Modelos salvos ({len(salvos)})**")
    if not salvos:
        st.info("Nenhum modelo salvo ainda. Anexe um .dxf acima, dê um nome e clique em Salvar.")
    for i, m in enumerate(salvos):
        with st.container(border=True):
            cc1, cc2 = st.columns([1, 1.4])
            with cc1:
                try:
                    st.image(flanges.render_dxf_png(m["dxf"]), use_container_width=True)
                except Exception:
                    st.caption("(sem prévia)")
            with cc2:
                st.markdown(f"**{m['nome']}**")
                st.caption(f"{m['n_entidades']} entidades · {m['bbox'][0]:.0f}×{m['bbox'][1]:.0f} mm  ·  {m['arquivo']}")
                novo_nome = st.text_input("Renomear", m["nome"], key=f"{kp}_rn_{i}")
                b1, b2, b3 = st.columns(3)
                b1.download_button("Baixar", data=m["dxf"], file_name=m["arquivo"],
                                   mime="image/vnd.dxf", key=f"{kp}_dl_{i}", use_container_width=True)
                if b2.button("Renomear", key=f"{kp}_rnb_{i}", use_container_width=True):
                    modelos.renomear_modelo(m["arquivo"], novo_nome); st.rerun()
                if b3.button("Remover", key=f"{kp}_rm_{i}", use_container_width=True):
                    modelos.remover_modelo(m["arquivo"]); st.rerun()
    st.caption("Os modelos ficam salvos em disco. No Render, mantenha um **disco persistente** "
               "com DATA_DIR apontado para ele, senão eles somem ao reiniciar.")


def zip_lote(pecas, extras=None):
    """Empacota um lote: cada peça num subfolder próprio. pecas: [{nome, dxf, png?, pdf?}].
    extras: dict opcional {caminho_no_zip: bytes} (ex.: etiquetas.pdf)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in pecas:
            z.writestr(f"{p['nome']}/{p['nome']}.dxf", p["dxf"])
            if p.get("png"):
                z.writestr(f"{p['nome']}/{p['nome']}.png", p["png"])
            if p.get("pdf"):
                z.writestr(f"{p['nome']}/{p['nome']}.pdf", p["pdf"])
        for caminho, dados in (extras or {}).items():
            z.writestr(caminho, dados)
    return buf.getvalue()


def gerar_zip_mola(r) -> bytes:
    """Encaixe-mola: DXF do corte (femea) + STEP/IGES da femea e do macho + lista."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        arquivos = []
        dxf = d / "femea_mola.dxf"; exporters.mola_dxf(r, dxf); arquivos.append(dxf)
        for nome, solido in r.parts.items():
            a = d / f"{nome}.igs"; exporters.to_iges(solido, a); arquivos.append(a)
            b = d / f"{nome}.step"; exporters.to_step(solido, b); arquivos.append(b)
        linhas = ["ENCAIXE-MOLA (snap-fit) - Metallo / Concetto", ""]
        for c in r.cut_list:
            linhas.append(f"{c[0]} | qtd {c[1]} | {c[2]} mm | {c[3]}")
        (d / "lista.txt").write_text("\n".join(linhas), encoding="utf-8")
        arquivos.append(d / "lista.txt")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for a in arquivos:
                z.write(a, a.name)
        return buf.getvalue()


def gerar_zip_lote(results) -> bytes:
    """Gera 1 PDF multipagina (todas as pecas) + IGES/STEP por peca + lista de corte, num .zip."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        arquivos = []
        linhas = ["LISTA DE CORTE - CORTE ANGULAR (Metallo / Concetto)", ""]
        # PDF unico, uma peca por pagina
        pdf = d / "Lote_corte_angular.pdf"
        drawing.draw_multi(results, pdf)
        arquivos.append(pdf)
        for i, r in enumerate(results, 1):
            base = f"{i:02d}_{r.name}"
            ig = d / f"{base}.igs"; exporters.to_iges(r, ig); arquivos.append(ig)
            stp = d / f"{base}.step"; exporters.to_step(r, stp); arquivos.append(stp)
            W, T, L = r.dims
            linhas.append(
                f"{i:02d}) Qtd {r.qtd:>3}  |  {W:g}x{T:g}x{r.wall:g}  |  L={L:g} mm  |  "
                f"{r.angulo:g} graus  |  {r.pontas} ponta(s)  |  {r.plano}/{r.lado}"
            )
        (d / "lista_corte.txt").write_text("\n".join(linhas), encoding="utf-8")
        arquivos.append(d / "lista_corte.txt")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for a in arquivos:
                z.write(a, a.name)
        return buf.getvalue()


def mostra_resultado(r):
    st.success("Peça gerada com sucesso.")
    c1, c2, c3 = st.columns(3)
    if r.kind in ("tubo", "angular"):
        W, T, L = r.dims
        c1.metric("Seção", f"{W:g} × {T:g} mm")
        c2.metric("Comprimento", f"{L:g} mm")
    elif r.kind == "tubo_redondo":
        OD, _, L = r.dims
        ex = getattr(r, "extra", None) or {}
        c1.metric("Ø externo", f"{OD:g} mm" + (f" ({ex.get('bitola')})" if ex.get("bitola") else ""))
        c2.metric("Comprimento", f"{L:g} mm")
    elif r.kind == "chapa":
        W, H, esp = r.dims
        c1.metric("Envelope", f"{W:g} × {H:g} mm")
        c2.metric("Espessura", f"{esp:g} mm")
    else:
        L, Dp, H = r.dims
        c1.metric("Tampo", f"{L:g} × {Dp:g} mm")
        c2.metric("Altura", f"{H:g} mm")
    c3.metric("Massa estimada", f"{r.mass:.2f} kg")
    if r.cut_list:
        st.markdown("**Lista de corte**")
        st.table(
            {"Descrição": [c[0] for c in r.cut_list],
             "Qtd": [c[1] for c in r.cut_list],
             "Comp. (mm)": [f"{c[2]:g}" for c in r.cut_list],
             "Pontas": [c[3] for c in r.cut_list]}
        )
    try:
        st.image(drawing.draw_png(r), caption="Preview do desenho técnico", use_container_width=True)
    except Exception:
        pass
    tem_3d = getattr(r, "shape", None) is not None or r.parts
    if tem_3d:
        st.download_button(
            "⬇  Baixar tudo (.zip — IGS + STEP)", data=gerar_zip(r),
            file_name=f"{r.name}.zip", mime="application/zip", use_container_width=True,
        )
        cf1, cf2 = st.columns(2)
        cf1.download_button(
            "⬇  Apenas STEP (.zip)", data=gerar_zip(r, formatos=("step",)),
            file_name=f"{r.name}_STEP.zip", mime="application/zip", use_container_width=True,
        )
        cf2.download_button(
            "⬇  Apenas IGS (.zip)", data=gerar_zip(r, formatos=("igs",)),
            file_name=f"{r.name}_IGS.zip", mime="application/zip", use_container_width=True,
        )
    else:
        st.download_button(
            "⬇  Baixar arquivos (.zip)", data=gerar_zip(r),
            file_name=f"{r.name}.zip", mime="application/zip", use_container_width=True,
        )
    with st.expander("🏷️  Etiqueta de identificação (opcional)"):
        sfx = r.kind
        e1, e2, e3 = st.columns(3)
        ger = e1.checkbox("Gerar etiqueta (PDF)", False, key=f"et_on_{sfx}")
        obra = e2.text_input("Obra / cliente", "", key=f"et_obra_{sfx}")
        qtd = e3.number_input("Quantidade", 1, 999, 1, 1, key=f"et_qtd_{sfx}")
        e4, e5, e6 = st.columns(3)
        cod = e4.text_input("Código (barras)", r.name[:24], key=f"et_cod_{sfx}")
        etw = e5.number_input("Largura (mm)", 30.0, 150.0, 80.0, 5.0, key=f"et_w_{sfx}")
        eth = e6.number_input("Altura (mm)", 20.0, 100.0, 40.0, 5.0, key=f"et_h_{sfx}")
        barras = st.checkbox("Código de barras", True, key=f"et_bar_{sfx}")
        if ger:
            rotulo = r.cut_list[0][0] if getattr(r, "cut_list", None) else r.name
            try:
                L = r.dims[2]
            except Exception:
                L = 0
            linhas = [rotulo[:40], f"Comp.: {L:g} mm   ·   Massa: {r.mass:.2f} kg"]
            if getattr(r, "feats", None):
                linhas.append(f"Furos: {len(r.feats)}")
            item = {"titulo": obra, "destaque": (r.name[:24]), "linhas": linhas,
                    "codigo": cod, "qtd": int(qtd)}
            pdf_et = promobile.etiqueta_generica_pdf([item], tamanho=(etw, eth), barras=barras)
            st.download_button("⬇  Baixar etiqueta (PDF)", data=pdf_et,
                               file_name=f"etiqueta_{r.name}.pdf", mime="application/pdf",
                               use_container_width=True)

    if r.kind in ("tubo", "tubo_redondo", "angular"):
        with st.expander("🪈  Enviar para o nesting de tubos"):
            rot = r.cut_list[0][0] if getattr(r, "cut_list", None) else r.name
            try:
                Lp = r.dims[2]
            except Exception:
                Lp = 0
            qn = st.number_input("Quantidade", 1, 999, 1, 1, key=f"nt_q_{r.kind}")
            if st.button("➕ Enviar para o nesting", key=f"nt_send_{r.kind}", use_container_width=True):
                lst = st.session_state.setdefault("nest_tubo_lista", [])
                lst.append({"perfil": rot, "comprimento": float(Lp), "qtd": int(qn)})
                st.success(f"Enviado: {int(qn)}× {rot} ({Lp:g} mm). Abra a aba **Nesting de tubos**.")


def _pdf_pagina_3d(imagens):
    """Uma pagina A3 com as vistas 3D (bytes PNG) lado a lado. Retorna bytes PDF."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    from matplotlib.backends.backend_pdf import PdfPages
    b = io.BytesIO()
    with PdfPages(b) as pp:
        fig = plt.figure(figsize=(16.54, 11.69))
        fig.text(0.05, 0.95, "VISTAS 3D DO CONJUNTO", fontsize=13, weight="bold")
        n = max(len(imagens), 1)
        for k, (titulo, png) in enumerate(imagens):
            ax = fig.add_axes([0.04 + k * (0.92 / n), 0.12, 0.92 / n - 0.03, 0.75])
            try:
                ax.imshow(mpimg.imread(io.BytesIO(png)))
            except Exception:
                pass
            ax.axis("off"); ax.set_title(titulo, fontsize=11)
        pp.savefig(fig); plt.close(fig)
    return b.getvalue()


def _merge_pdfs(pdfs):
    """Junta varios PDFs (bytes) num so. Usa pypdf; se faltar, retorna None."""
    try:
        from pypdf import PdfWriter, PdfReader
        w = PdfWriter()
        for pb in pdfs:
            if not pb:
                continue
            try:
                r = PdfReader(io.BytesIO(pb))
                for pg in r.pages:
                    w.add_page(pg)
            except Exception:
                continue
        out = io.BytesIO(); w.write(out)
        return out.getvalue()
    except Exception:
        return None


def nome_auto(key, sugestao):
    """Mantém o nome do arquivo sincronizado com a peça: enquanto o usuário não
    digitar um nome próprio, o campo acompanha a sugestão (que muda com as
    modificações da peça). Se o usuário editar, o nome dele é respeitado."""
    ks = key + "__sug"
    atual = st.session_state.get(key)
    anterior = st.session_state.get(ks)
    if atual is None or atual == anterior:
        st.session_state[key] = sugestao
    st.session_state[ks] = sugestao


def chave_sextavado(col, key):
    opt = col.selectbox("Chave do sextavado (mm)", [8, 10, 12, 15, "Outro"], key=f"{key}_opt")
    if opt == "Outro":
        return col.number_input("Chave personalizada (mm)", 2.0, 200.0, 10.0, 0.5, key=f"{key}_cust")
    return float(opt)


def comp_input(col, key, chave=None):
    # padrão por chave: sextavado de 10 mm -> -0.33 (ajuste de sangria do laser)
    padrao = -0.33 if (chave is not None and abs(float(chave) - 10.0) < 1e-6) else 0.0
    if key not in st.session_state:
        st.session_state[key] = padrao
    if chave is not None:
        lk = f"{key}__lastchave"
        if st.session_state.get(lk) != chave:
            st.session_state[lk] = chave
            st.session_state[key] = padrao
    return col.number_input(
        "Compensação do furo (mm)", -5.0, 5.0, step=0.05, key=key,
        help="Somado ao Ø/chave para compensar a sangria do laser. + alarga, - reduz. "
             "Sextavado chave 10 já vem com -0,33.",
    )


# --------------------------------------------------------------------- cabecalho
st.markdown(
    f"""
    <div class="hero">
      <img src="data:image/jpeg;base64,{_logo_b64()}" alt="Metallo"/>
      <div>
        <p class="t">METALLO&nbsp;IA</p>
        <span class="badge">Gerador inteligente de pecas</span>
        <p class="s">IGES · STEP · DXF · Desenho tecnico · Etiquetas · Nesting</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ===================================================================== navegacao (menu estilo app)
st.session_state.setdefault("secao", "home")
secao = st.session_state["secao"]

MENU = [
    ("tubo", "🔧   Tubo com furos"),
    ("redondo", "⭕   Tubo redondo (1/2\" a 10\")"),
    ("torre", "⬡   Torre sextavada"),
    ("chapas", "▭   Chapas (L / hexágono)"),
    ("pecaplana", "▱   Peça plana (formatos + furos)"),
    ("flange", "⬛   Flanges (DXF inox)"),
    ("descricao", "✍️   Peça por descrição (DXF)"),
    ("placa", "🔢   Placa numérica (número + furos)"),
    ("ralo", "🚿   Ralo / grelha (tampa + apoio)"),
    ("planificacao", "📐   Planificação (caldeiraria)"),
    ("lote", "📦   Gerar em lote (DXF)"),
    ("promobile", "🪵   ProMobile (importar lista → IGS + adesivo)"),
    ("producao", "🏭   Produção (fila de corte + etiquetas)"),
    ("nesttubo", "🪈   Nesting de tubos (barras)"),
    ("nesting", "🧩   Nesting (chapa única)"),
    ("angular", "📐   Corte angular (em lote)"),
    ("mesas", "🪑   Mesas"),
    ("itubecam", "📏   iTubeCAM (peças p/ laser de tubo)"),
    ("puxador", "🚪   Puxadores"),
    ("config", "⚙️   Configurações"),
    ("bancada", "🍽️   Bancada de inox (cubas + dobra)"),
    ("corte", "⏱   Tempo de corte (laser 3000 W)"),
    ("etiqueta", "🏷️   Gerar etiqueta"),
    ("ajuda", "ℹ️   Como usar"),
]
TITULOS = {
    "tubo": "Tubo com furos", "redondo": "Tubo redondo", "torre": "Torre sextavada", "chapas": "Chapas",
    "pecaplana": "Peça plana (formatos + furos)",
    "angular": "Corte angular (em lote)", "mesas": "Mesas", "bancada": "Bancada de inox",
    "itubecam": "iTubeCAM — peças para a laser de tubo",
    "puxador": "Puxadores",
    "config": "Configurações",
    "flange": "Flanges (DXF inox)", "nesting": "Nesting (chapa única)",
    "descricao": "Peça por descrição (DXF)",
    "placa": "Placa numérica",
    "ralo": "Ralo / grelha (tampa + apoio)",
    "planificacao": "Planificação de chapas",
    "lote": "Gerar em lote",
    "promobile": "ProMobile → IGS + adesivos",
    "producao": "Produção — fila de corte",
    "nesttubo": "Nesting de tubos (barras)",
    "corte": "Tempo de corte (laser 3000 W)",
    "etiqueta": "Gerar etiqueta",
    "ajuda": "Como usar",
}


def ir(s):
    st.session_state["secao"] = s


if secao == "home":
    st.markdown(
        f'<div class="ph-icon"><img src="data:image/jpeg;base64,{_logo_b64()}" alt="Metallo"/></div>',
        unsafe_allow_html=True,
    )
    for _key, _label in MENU:
        st.button(_label, use_container_width=True, key="nav_" + _key, on_click=ir, args=(_key,))
    st.caption(f"METALLO IA {APP_VERSAO} · Metallo Ind. de Aços do Nordeste — gerador inteligente de peças.")

else:
    st.button("‹  Início", type="primary", key="back", on_click=ir, args=("home",))
    st.markdown("#### " + TITULOS.get(secao, ""))

    # ------------------------------------------------- Tubo com furos
    if secao == "tubo":
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            W = c1.number_input("Largura (mm)", 5.0, 400.0, 40.0, 1.0)
            T = c2.number_input("Altura (mm)", 5.0, 400.0, 20.0, 1.0)
            wall = c3.number_input("Parede (mm)", 0.5, 6.0, 1.0, 0.1)
            L = c4.number_input("Comprimento (mm)", 20.0, 6000.0, 295.0, 1.0)
            c5, c6 = st.columns(2)
            tipo = c5.radio("Tipo de furo", ["Redondo", "Sextavado"], horizontal=True)
            if tipo == "Redondo":
                tamanho = c6.number_input("Ø furo (mm)", 1.0, 100.0, 5.0, 0.5)
                orient_lbl = "Face para cima"
            else:
                tamanho = chave_sextavado(c6, "tubo_chave")
                orient_lbl = st.radio("Orientação do sextavado",
                                      ["Face para cima", "Vértice para cima"], horizontal=True)
            lado = st.radio(
                "Furos na(s) face(s)",
                [f"Topo/Fundo (faces de {W:g})", f"Laterais (faces de {T:g})", "Ambas"],
                horizontal=True,
                help="Topo/Fundo = as duas faces de largura W. Laterais = as faces de altura T. "
                     "Em 'Ambas' você define posições e passante para cada par separadamente.")
            usa_lf = lado.startswith("Topo") or lado == "Ambas"   # faces largas (W)
            usa_lt = lado.startswith("Laterais") or lado == "Ambas"  # faces estreitas (T)
            with st.expander("↦  Multi-furos automático (preenche as posições)"):
                st.caption("Informe o recuo da ponta até o 1º furo, o passo entre furos e o comprimento "
                           "total. As posições saem simétricas (recuo igual nas duas pontas).")
                mf1, mf2, mf3 = st.columns(3)
                mf_borda = mf1.number_input("Borda → 1º furo (mm)", 0.0, 6000.0, 47.5, 0.5, key="mf_borda")
                mf_passo = mf2.number_input("Passo entre furos (mm)", 1.0, 6000.0, 200.0, 0.5, key="mf_passo")
                mf_total = mf3.number_input("Comprimento total (mm)", 1.0, 6000.0, float(L), 1.0, key="mf_total")
                _prev = _multi_furos_calc(mf_borda, mf_passo, mf_total)
                st.caption(f"→ {len(_prev)} furos: {', '.join(f'{p:g}' for p in _prev) if _prev else '—'}")
                if lado == "Ambas":
                    mf_alvo = st.radio("Aplicar em", [f"Faces de {W:g} (W)", f"Faces de {T:g} (T)", "Ambas"],
                                       horizontal=True, key="mf_alvo")
                else:
                    mf_alvo = f"Faces de {W:g} (W)" if usa_lf else f"Faces de {T:g} (T)"
                _dest = []
                if usa_lf and (mf_alvo.endswith("(W)") or mf_alvo == "Ambas"):
                    _dest.append("tubo_posW")
                if usa_lt and (mf_alvo.endswith("(T)") or mf_alvo == "Ambas"):
                    _dest.append("tubo_posE")
                st.button("Preencher posições", key="mf_apply", use_container_width=True,
                          on_click=_aplica_multifuros, args=(_dest, mf_borda, mf_passo, mf_total),
                          disabled=not _dest)
            pos_w, pass_w, pos_e, pass_e = "", False, "", False
            st.session_state.setdefault("tubo_posW", "47.5, 247.5")
            st.session_state.setdefault("tubo_posE", "147.5")
            if usa_lf:
                cw1, cw2 = st.columns([3, 2])
                pos_w = cw1.text_input(f"Posições nas faces de {W:g} mm (mm da ponta, vírgula)",
                                       key="tubo_posW")
                pass_w = cw2.checkbox("Passante (topo+fundo)", value=False, key="tubo_passW",
                                      help="Atravessa as duas faces largas. Desmarcado = só a face superior.")
            if usa_lt:
                ce1, ce2 = st.columns([3, 2])
                pos_e = ce1.text_input(f"Posições nas faces de {T:g} mm — laterais (mm da ponta, vírgula)",
                                       key="tubo_posE")
                pass_e = ce2.checkbox("Passante (2 laterais)", value=True, key="tubo_passE",
                                      help="Atravessa as duas faces estreitas. Desmarcado = só uma lateral.")
            c8, c9 = st.columns(2)
            raio = c8.number_input("Raio do canto do tubo (mm)", 0.0, 20.0, 0.0, 0.5,
                                   help="0 = canto vivo. Metalon costuma ter raio ~1,5 a 2x a espessura da parede.")
            comp = comp_input(c9, "tubo_comp", chave=(tamanho if tipo == "Sextavado" else None))
            if st.button("GERAR", type="primary", use_container_width=True):
                try:
                    def _parse(t):
                        return [float(x.strip().replace(",", ".")) for x in t.split(",") if x.strip()]
                    furos_w = _parse(pos_w) if usa_lf else []
                    furos_e = _parse(pos_e) if usa_lt else []
                    if not furos_w and not furos_e:
                        st.warning("Informe ao menos uma posição de furo.")
                    else:
                        r = mc.tubo_retangular_furos(
                            W, T, wall, L, furos_w, tamanho,
                            tipo_furo=("sextavado" if tipo == "Sextavado" else "redondo"),
                            faces=("ambas" if (usa_lf and pass_w) else "topo"),
                            raio=raio,
                            orient_sext=("vertice" if orient_lbl == "Vértice para cima" else "face"),
                            comp=comp,
                            furos_lado=furos_e,
                            passante_lado=(usa_lt and pass_e),
                        )
                        mostra_resultado(r)
                except Exception as e:
                    st.error("Erro ao gerar: " + str(e))

    # ------------------------------------------------- Tubo redondo
    elif secao == "redondo":
        with st.container(border=True):
            st.caption("Tubo redondo (seção circular) por bitola de 1/2\" a 10\". "
                       "O diâmetro externo segue tubo redondo mecânico (OD = polegada × 25,4 mm) e "
                       "pode ser ajustado.")
            bitolas = list(mc.POLEGADAS_OD.keys())
            c1, c2, c3 = st.columns(3)
            bit = c1.selectbox("Bitola", bitolas, index=bitolas.index('2"'))
            od_pad = mc.POLEGADAS_OD[bit]
            OD = c2.number_input("Ø externo (mm)", 5.0, 400.0, float(od_pad), 0.1,
                                 help="Pré-preenchido pela bitola; ajuste se o seu tubo for diferente.")
            wall = c3.number_input("Parede (mm)", 0.5, 12.0, 1.5, 0.1)
            c4, c5 = st.columns(2)
            L = c4.number_input("Comprimento (mm)", 20.0, 6000.0, 300.0, 1.0)
            d_furo = c5.number_input("Ø do furo (mm)", 0.0, 100.0, 0.0, 0.5,
                                     help="0 = sem furos.")
            pos = st.text_input("Posições dos furos (mm da ponta, separadas por vírgula)", "",
                                placeholder="ex.: 50, 150, 250")
            passante = st.checkbox("Furo passante (atravessa o tubo)", value=True,
                                   help="Desmarcado = fura só a parede de cima.")
            comp = comp_input(st.columns(2)[0], "red_comp")
            if st.button("GERAR", type="primary", use_container_width=True):
                try:
                    furos = [float(x.strip().replace(",", ".")) for x in pos.split(",") if x.strip()]
                    if furos and d_furo <= 0:
                        st.warning("Defina o Ø do furo (maior que zero) para furar.")
                    else:
                        r = mc.tubo_redondo(OD, wall, L, furos=furos, d_furo=d_furo,
                                            passante=passante, comp=comp, bitola=bit)
                        mostra_resultado(r)
                except Exception as e:
                    st.error("Erro ao gerar: " + str(e))

    # ------------------------------------------------- Torre sextavada
    elif secao == "torre":
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            W = c1.number_input("Largura (mm)", 5.0, 400.0, 40.0, 1.0)
            T = c2.number_input("Altura (mm)", 5.0, 400.0, 15.0, 1.0)
            wall = c3.number_input("Parede (mm)", 0.5, 6.0, 1.0, 0.1)
            L = c4.number_input("Comprimento (mm)", 20.0, 6000.0, 200.0, 1.0)
            c5, c6 = st.columns(2)
            chave = chave_sextavado(c5, "torre_chave")
            pos_txt = c6.text_input("Centros dos sextavados (mm da ponta, separados por vírgula)", "140",
                                    key="torre_pos", placeholder="ex.: 60, 140")
            c7, c8 = st.columns(2)
            faces_lbl = c7.radio("Furos em", ["Apenas face superior", "Ambas as faces"], horizontal=True)
            orient_lbl = c8.radio("Orientação", ["Face para cima", "Vértice para cima"], horizontal=True)
            c9, c10 = st.columns(2)
            raio = c9.number_input("Raio do canto (mm)", 0.0, 20.0, 0.0, 0.5, help="0 = canto vivo.")
            comp = comp_input(c10, "torre_comp", chave=chave)
            if st.button("GERAR", type="primary", use_container_width=True):
                try:
                    positions = [float(x.strip().replace(",", ".")) for x in pos_txt.split(",") if x.strip()]
                    if not positions:
                        st.warning("Informe ao menos um centro de furo.")
                    else:
                        r = mc.torre_sextavada(
                            W, T, wall, L, chave, positions,
                            faces=("ambas" if faces_lbl == "Ambas as faces" else "topo"),
                            raio=raio,
                            orient_sext=("vertice" if orient_lbl == "Vértice para cima" else "face"),
                            comp=comp,
                        )
                        mostra_resultado(r)
                except Exception as e:
                    st.error("Erro ao gerar: " + str(e))

        with st.container(border=True):
            st.markdown("#### 🏛️ TORRE INOX METALLO — pinça de vidro")
            st.caption("2 tubos 40×15 + peça ao meio (altura 40 mm na base). Gera o desenho técnico cotado e "
                       "**2 IGES com os mesmos eixos**: tubo com furo passante Ø12 e tubo com sextavado p/ "
                       "porca M6 chave 10 (compensação −0,33).")
            ti1, ti2, ti0, ti3, ti4 = st.columns(5)
            ti_h = ti1.number_input("Altura da torre (mm)", 100.0, 2000.0, 400.0, 10.0, key="ti_h")
            ti_n = int(ti2.number_input("Qtd. de furos", 1, 6, 2, 1, key="ti_n"))
            ti_base = ti0.number_input("Altura da base (mm)", 10.0, 300.0, 40.0, 5.0, key="ti_base",
                                       help="Altura da peça do meio, medida da borda inferior do tubo.")
            ti_b1 = ti3.number_input("Topo da base → eixo do 1º furo (mm)", 5.0, 1900.0, 100.0, 5.0, key="ti_b1",
                                     help="Ex.: torre 300, base 40, valor 100 → eixo a 140 mm da borda do tubo.")
            ti_e = ti4.number_input("Entre furos (mm)", 10.0, 1900.0, 200.0, 5.0, key="ti_e")
            ti5, ti6, ti7, ti8, ti9 = st.columns(5)
            ti_w = ti5.number_input("Parede do tubo (mm)", 0.8, 3.0, 1.2, 0.1, key="ti_w")
            ti_r = ti9.number_input("Raio do canto do tubo (mm)", 0.0, 6.0, 1.5, 0.5, key="ti_r")
            ti_meio = 10.0 if ti6.radio("Peça do meio", ["40×10", "40×15"], horizontal=True, key="ti_meio") == "40×10" else 15.0
            ti_d = ti7.number_input("Ø furo passante (mm)", 4.0, 30.0, 12.0, 0.5, key="ti_d")
            ti_comp = ti8.number_input("Compensação sextavado (mm)", -2.0, 2.0, -0.33, 0.01, key="ti_comp",
                                       help="Somada à chave 10: corte = 10 + comp (padrão −0,33 → 9,67).")
            if st.button("GERAR TORRE INOX", type="primary", use_container_width=True, key="ti_gerar"):
                try:
                    res = torre_inox.gerar(ti_h, ti_n, ti_b1, ti_e, wall=ti_w, meio=ti_meio,
                                           d_furo=ti_d, chave=10.0, comp=ti_comp, base=ti_base, raio=ti_r)
                    pdf_ti = torre_inox.desenho_pdf(res, nome=f"TORRE INOX METALLO {ti_h:g} mm")
                    st.success(f"Torre gerada: {ti_n} furo(s) — eixos a {', '.join(f'{p:g}' for p in res['pos'])} mm "
                               f"da borda do tubo (base {ti_base:g} + {ti_b1:g}"
                               f"{' + passos' if ti_n > 1 else ''}).")
                    try:
                        cA, cB = st.columns(2)
                        cA.image(drawing.draw_png(res["A"]), caption="TUBO A — passante Ø" + f"{ti_d:g}", use_container_width=True)
                        cB.image(drawing.draw_png(res["B"]), caption="TUBO B — porca M6 ch10", use_container_width=True)
                    except Exception:
                        pass
                    import tempfile, os as _os
                    bufT = io.BytesIO()
                    with zipfile.ZipFile(bufT, "w", zipfile.ZIP_DEFLATED) as zt:
                        for tag, rr in (("TUBO_PASSANTE", res["A"]), ("TUBO_PORCA", res["B"])):
                            with tempfile.TemporaryDirectory() as td:
                                pth = _os.path.join(td, rr.name + ".igs")
                                exporters.to_iges(rr, pth)
                                zt.writestr(f"{rr.name}.igs", open(pth, "rb").read())
                                pst = _os.path.join(td, rr.name + ".step")
                                exporters.to_step(rr, pst)
                                zt.writestr(f"{rr.name}.step", open(pst, "rb").read())
                        zt.writestr(f"TorreInox_{ti_h:g}_DESENHO.pdf", pdf_ti)
                    st.download_button("\u2b07  Baixar TORRE (.zip: IGES + STEP + desenho)", data=bufT.getvalue(),
                                       file_name=f"TorreInox_{int(ti_h)}_{ti_n}furos.zip",
                                       mime="application/zip", use_container_width=True)
                    d1, d2, d3 = st.columns(3)
                    d1.download_button("📄 Desenho técnico", data=pdf_ti,
                                       file_name=f"TorreInox_{int(ti_h)}_desenho.pdf",
                                       mime="application/pdf", use_container_width=True)
                    d2.download_button("Completo TUBO A (.zip)", data=gerar_zip(res["A"]),
                                       file_name=f"{res['A'].name}.zip", mime="application/zip",
                                       use_container_width=True)
                    d3.download_button("Completo TUBO B (.zip)", data=gerar_zip(res["B"]),
                                       file_name=f"{res['B'].name}.zip", mime="application/zip",
                                       use_container_width=True)
                except ValueError as ve:
                    st.warning(str(ve))
                except Exception as e:
                    st.error("Erro ao gerar a torre: " + str(e))

    # ------------------------------------------------- Peca plana (formatos + furos)
    elif secao == "pecaplana":
        with st.container(border=True):
            st.caption("Peça planificada a partir de **formatos padrões** ou **contorno livre por coordenadas**, "
                       "com furos unitários ou em padrão (linha, grade, círculo de furação). "
                       "DXF com camadas CORTE e FUROS.")
            cf1, cf2, cf3 = st.columns([1.4, 1, 1])
            fmt = cf1.selectbox("Formato", peca_plana.FORMATOS, key="pp_fmt")
            espp = cf2.number_input("Espessura (mm)", 0.4, 12.0, 1.2, 0.1, key="pp_esp")
            params = {}
            if fmt == "Retângulo":
                c1, c2, c3 = st.columns(3)
                params = {"C": c1.number_input("Comprimento (mm)", 5.0, 6000.0, 300.0, 5.0, key="pp_C"),
                          "L": c2.number_input("Largura (mm)", 5.0, 3000.0, 200.0, 5.0, key="pp_L"),
                          "raio": c3.number_input("Raio do canto (mm)", 0.0, 200.0, 0.0, 1.0, key="pp_r")}
            elif fmt == "Retângulo chanfrado":
                c1, c2, c3 = st.columns(3)
                params = {"C": c1.number_input("Comprimento (mm)", 5.0, 6000.0, 300.0, 5.0, key="pp_C"),
                          "L": c2.number_input("Largura (mm)", 5.0, 3000.0, 200.0, 5.0, key="pp_L"),
                          "chanfro": c3.number_input("Chanfro (mm)", 0.0, 200.0, 15.0, 1.0, key="pp_ch")}
            elif fmt == "Disco":
                params = {"D": st.number_input("Diâmetro (mm)", 5.0, 3000.0, 250.0, 5.0, key="pp_D")}
            elif fmt == "Anel":
                c1, c2 = st.columns(2)
                params = {"D": c1.number_input("Ø externo (mm)", 5.0, 3000.0, 250.0, 5.0, key="pp_D"),
                          "d_int": c2.number_input("Ø interno (mm)", 2.0, 2990.0, 120.0, 5.0, key="pp_di")}
            elif fmt == "Oblongo":
                c1, c2 = st.columns(2)
                params = {"C": c1.number_input("Comprimento (mm)", 5.0, 6000.0, 300.0, 5.0, key="pp_C"),
                          "L": c2.number_input("Largura (mm)", 5.0, 3000.0, 80.0, 5.0, key="pp_L")}
            elif fmt == "L":
                c1, c2, c3, c4 = st.columns(4)
                params = {"C": c1.number_input("Comprimento (mm)", 5.0, 6000.0, 300.0, 5.0, key="pp_C"),
                          "L": c2.number_input("Altura (mm)", 5.0, 3000.0, 200.0, 5.0, key="pp_L"),
                          "perna_v": c3.number_input("Perna vertical (mm)", 2.0, 3000.0, 80.0, 5.0, key="pp_pv"),
                          "perna_h": c4.number_input("Perna horizontal (mm)", 2.0, 3000.0, 60.0, 5.0, key="pp_ph")}
            elif fmt == "U":
                c1, c2, c3, c4 = st.columns(4)
                params = {"C": c1.number_input("Comprimento (mm)", 5.0, 6000.0, 300.0, 5.0, key="pp_C"),
                          "L": c2.number_input("Altura (mm)", 5.0, 3000.0, 200.0, 5.0, key="pp_L"),
                          "ab_larg": c3.number_input("Abertura — largura (mm)", 2.0, 3000.0, 120.0, 5.0, key="pp_aw"),
                          "ab_prof": c4.number_input("Abertura — profundidade (mm)", 2.0, 3000.0, 100.0, 5.0, key="pp_ah")}
            elif fmt == "Trapézio":
                c1, c2, c3 = st.columns(3)
                params = {"B": c1.number_input("Base maior (mm)", 5.0, 6000.0, 300.0, 5.0, key="pp_B"),
                          "b": c2.number_input("Base menor (mm)", 2.0, 6000.0, 180.0, 5.0, key="pp_b"),
                          "h": c3.number_input("Altura (mm)", 2.0, 3000.0, 150.0, 5.0, key="pp_h")}
            elif fmt == "Triângulo":
                c1, c2 = st.columns(2)
                params = {"base": c1.number_input("Base (mm)", 5.0, 6000.0, 300.0, 5.0, key="pp_bs"),
                          "h": c2.number_input("Altura (mm)", 2.0, 3000.0, 200.0, 5.0, key="pp_h")}
            elif fmt == "Polígono regular":
                c1, c2 = st.columns(2)
                params = {"n": int(c1.number_input("Nº de lados", 3, 24, 6, 1, key="pp_n")),
                          "D": c2.number_input("Ø circunscrito (mm)", 5.0, 3000.0, 220.0, 5.0, key="pp_D")}
            else:
                params = {"coords": st.text_area("Coordenadas do contorno (mm) — 'x,y; x,y; ...' ou uma por linha",
                                                 "0,0; 200,0; 250,80; 120,160; 0,120", key="pp_coords", height=90)}
            st.markdown("---")
            st.markdown("**Furos** (origem no centro da peça):")
            ft1, ft2 = st.columns([1, 3])
            tipo_f = ft1.selectbox("Tipo", ["redondo", "oblongo", "retangular", "linha",
                                            "grade", "circulo_furos"], key="pp_ftipo")
            novo_f = {"tipo": tipo_f}
            with ft2:
                g = st.columns(6)
                novo_f["x"] = g[0].number_input("X", -3000.0, 3000.0, 0.0, 5.0, key="pp_fx")
                novo_f["y"] = g[1].number_input("Y", -3000.0, 3000.0, 0.0, 5.0, key="pp_fy")
                if tipo_f == "redondo":
                    novo_f["d"] = g[2].number_input("Ø", 0.5, 500.0, 10.0, 0.5, key="pp_fd")
                elif tipo_f == "oblongo":
                    novo_f["comp"] = g[2].number_input("Comp.", 2.0, 1000.0, 40.0, 1.0, key="pp_fc")
                    novo_f["larg"] = g[3].number_input("Larg.", 1.0, 500.0, 10.0, 0.5, key="pp_fl")
                    novo_f["ang"] = g[4].number_input("Âng.", -180.0, 180.0, 0.0, 5.0, key="pp_fa")
                elif tipo_f == "retangular":
                    novo_f["c"] = g[2].number_input("Comp.", 2.0, 1000.0, 40.0, 1.0, key="pp_fc")
                    novo_f["l"] = g[3].number_input("Larg.", 1.0, 500.0, 20.0, 0.5, key="pp_fl")
                    novo_f["ang"] = g[4].number_input("Âng.", -180.0, 180.0, 0.0, 5.0, key="pp_fa")
                elif tipo_f == "linha":
                    novo_f["n"] = int(g[2].number_input("Qtd", 1, 200, 4, 1, key="pp_fn"))
                    novo_f["passo"] = g[3].number_input("Passo", 1.0, 1000.0, 40.0, 1.0, key="pp_fp")
                    novo_f["ang"] = g[4].number_input("Âng.", -180.0, 180.0, 0.0, 5.0, key="pp_fa")
                    novo_f["d"] = g[5].number_input("Ø", 0.5, 500.0, 8.0, 0.5, key="pp_fd")
                elif tipo_f == "grade":
                    novo_f["nx"] = int(g[2].number_input("Nx", 1, 100, 3, 1, key="pp_fnx"))
                    novo_f["ny"] = int(g[3].number_input("Ny", 1, 100, 2, 1, key="pp_fny"))
                    novo_f["px"] = g[4].number_input("Passo X", 1.0, 1000.0, 40.0, 1.0, key="pp_fpx")
                    novo_f["py"] = g[5].number_input("Passo Y", 1.0, 1000.0, 40.0, 1.0, key="pp_fpy")
                    novo_f["d"] = st.number_input("Ø do furo", 0.5, 500.0, 8.0, 0.5, key="pp_fd")
                else:
                    novo_f["n"] = int(g[2].number_input("Qtd", 1, 100, 6, 1, key="pp_fn"))
                    novo_f["Dc"] = g[3].number_input("Ø círculo", 2.0, 3000.0, 150.0, 5.0, key="pp_fDc")
                    novo_f["d"] = g[4].number_input("Ø furo", 0.5, 500.0, 9.0, 0.5, key="pp_fd")
                    novo_f["ang0"] = g[5].number_input("Âng. inicial", -180.0, 180.0, 0.0, 5.0, key="pp_fa0")
            ab1, ab2 = st.columns([1, 1])
            st.session_state.setdefault("pp_furos", [])
            if ab1.button("➕ Adicionar furo", key="pp_add", use_container_width=True):
                st.session_state["pp_furos"].append(dict(novo_f))
            if ab2.button("🗑 Limpar todos", key="pp_clr", use_container_width=True):
                st.session_state["pp_furos"] = []
            for k, f in enumerate(list(st.session_state["pp_furos"])):
                lc1, lc2 = st.columns([5, 1])
                lc1.markdown(f"• {peca_plana.descreve_furo(f)}")
                if lc2.button("remover", key=f"pp_rm{k}"):
                    st.session_state["pp_furos"].pop(k)
                    st.rerun()
            st.markdown("---")
            nome_auto("pp_nome", f"Peca_{fmt.split(' ')[0]}")
            nomep = st.text_input("Nome da peça", key="pp_nome")
            try:
                prims = peca_plana.montar(fmt, params, st.session_state["pp_furos"], esp=espp, nome=nomep)
                inf = prims["info"]
                for av in inf["avisos"]:
                    st.warning("Atenção: " + av)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Dimensões", f"{prims['bbox'][0]:.0f} × {prims['bbox'][1]:.0f} mm")
                m2.metric("Furos", inf["n_furos"])
                m3.metric("Área líquida", f"{inf['area_liq'] / 1e4:.2f} dm²")
                m4.metric("Peso (inox)", f"{inf['peso']:.2f} kg")
                cV, cD = st.columns([1.2, 1])
                cV.image(flanges.preview_png(prims), use_container_width=True)
                with cD:
                    dxfp = flanges.dxf_bytes([(prims, 0, 0)])
                    st.download_button("⬇ DXF (CORTE + FUROS)", data=dxfp, file_name=f"{nomep}.dxf",
                                       mime="image/vnd.dxf", use_container_width=True, key="pp_dxf")
                    st.download_button("📄 Folha PDF", data=flanges.preview_pdf(prims, esp=espp,
                                       obs=f"{nomep} · {fmt} · {inf['n_furos']} furo(s)"),
                                       file_name=f"{nomep}_folha.pdf", mime="application/pdf",
                                       use_container_width=True, key="pp_pdf")
                    st.download_button("🏷 Etiqueta", data=etiquetas.gerar_etiquetas_pdf(
                                       [{"descricao": f"{nomep} {prims['bbox'][0]:.0f}x{prims['bbox'][1]:.0f}",
                                         "material": f"Inox 304 {espp:g}mm", "qtd": 1}], tamanho=(150.0, 50.0)),
                                       file_name=f"{nomep}_etiqueta.pdf", mime="application/pdf",
                                       use_container_width=True, key="pp_etq")
            except ValueError as ve:
                st.warning(str(ve))
            except Exception as e:
                st.error("Erro ao gerar a peça: " + str(e))

    # ------------------------------------------------- Chapas (L / hexagono)
    elif secao == "chapas":
        with st.container(border=True):
            tipo_chapa = st.selectbox("Tipo de chapa", ["Polígono em L", "Hexágono"])
            st.divider()
            if tipo_chapa == "Polígono em L":
                c1, c2, c3, c4 = st.columns(4)
                W = c1.number_input("Largura total (mm)", 10.0, 2000.0, 60.0, 1.0)
                H = c2.number_input("Altura total (mm)", 10.0, 2000.0, 110.0, 1.0)
                bloco = c3.number_input("Bloco esquerdo (mm)", 5.0, 2000.0, 35.0, 1.0,
                                        help="Largura da parte alta (onde ficam os furos).")
                rec_alt = c4.number_input("Altura do recorte (mm)", 0.0, 2000.0, 40.0, 1.0,
                                          help="Recorte no canto superior direito.")
                esp = st.number_input("Espessura da chapa (mm)", 0.4, 25.0, 2.0, 0.1)
                st.markdown("**Furos**")
                c5, c6, c7 = st.columns(3)
                n_furos = c5.number_input("Quantidade", 0, 20, 2, 1)
                tipo_f = c6.radio("Tipo", ["Redondo", "Sextavado"], horizontal=True)
                if tipo_f == "Redondo":
                    furo = c7.number_input("Ø furo (mm)", 1.0, 200.0, 8.0, 0.5)
                    orient_f = "Face para cima"
                else:
                    furo = chave_sextavado(c7, "chapaL_chave")
                    orient_f = st.radio("Orientação do sextavado",
                                        ["Face para cima", "Vértice para cima"], horizontal=True)
                c8, c9, c10 = st.columns(3)
                d_topo = c8.number_input("Eixo do furo ao topo (mm)", 0.0, 2000.0, 13.0, 0.5)
                d_esq = c9.number_input("1º furo à esquerda (mm)", 0.0, 2000.0, 10.0, 0.5)
                passo = c10.number_input("Passo entre furos (mm)", 0.0, 2000.0, 15.0, 0.5)
                comp = comp_input(st, "chapaL_comp", chave=(furo if tipo_f == "Sextavado" else None))
                if st.button("GERAR", type="primary", use_container_width=True):
                    try:
                        r = mc.poligono_L(
                            W=W, H=H, bloco=bloco, rec_alt=rec_alt, espessura=esp,
                            furo=furo, n_furos=int(n_furos), d_topo=d_topo, d_esq=d_esq, passo=passo,
                            tipo_furo=("sextavado" if tipo_f == "Sextavado" else "redondo"),
                            orient_sext=("vertice" if orient_f == "Vértice para cima" else "face"),
                            comp=comp,
                        )
                        mostra_resultado(r)
                        st.info("O .zip inclui o DXF de corte (camadas CORTE/FUROS) + STEP/IGES e o desenho PDF.")
                    except Exception as e:
                        st.error("Erro ao gerar: " + str(e))
            else:
                c1, c2, c3 = st.columns(3)
                base = c1.number_input("Base (mm)", 10.0, 3000.0, 200.0, 1.0)
                topo = c2.number_input("Topo (mm)", 0.0, 3000.0, 100.0, 1.0)
                altura = c3.number_input("Altura total (mm)", 5.0, 3000.0, 60.0, 1.0)
                c4, c5 = st.columns(2)
                chanfro_v = c4.number_input("Queda vertical do chanfro (mm)", 0.0, 3000.0, 50.0, 1.0,
                                            help="Chanfro horizontal = (base - topo)/2 é automático. "
                                                 "Lateral reta = altura - esta queda.")
                esp = c5.number_input("Espessura da chapa (mm)", 0.4, 25.0, 2.0, 0.1)
                if topo > base:
                    st.warning("O topo não pode ser maior que a base.")
                if st.button("GERAR", type="primary", use_container_width=True):
                    try:
                        r = mc.hexagono(base=base, topo=topo, altura=altura, chanfro_v=chanfro_v, espessura=esp)
                        mostra_resultado(r)
                        ch_h = (base - topo) / 2.0
                        lado = max(altura - chanfro_v, 0.0)
                        st.caption(f"Chanfro horizontal automático = {ch_h:g} mm · lateral reta = {lado:g} mm.")
                        st.info("O .zip inclui o DXF de corte + STEP/IGES e o desenho PDF.")
                    except Exception as e:
                        st.error("Erro ao gerar: " + str(e))

    # ------------------------------------------------- Corte angular (lote)
    elif secao == "angular":
        st.caption("Adicione os tubos à lista e gere todos de uma vez. "
                   "Ângulo 90° = corte reto (esquadro); menor = chanfro.")
        if "lote" not in st.session_state:
            st.session_state["lote"] = []
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            aL = c1.number_input("Comprimento (mm)", 20.0, 8000.0, 500.0, 10.0, key="aL")
            aW = c2.number_input("Largura (mm)", 5.0, 400.0, 40.0, 1.0, key="aW")
            aT = c3.number_input("Altura (mm)", 5.0, 400.0, 40.0, 1.0, key="aT")
            aWall = c4.number_input("Parede (mm)", 0.5, 6.0, 1.0, 0.1, key="aWall")
            c5, c6, c7, c8 = st.columns(4)
            aRaio = c5.number_input("Raio do canto (mm)", 0.0, 20.0, 2.0, 0.5, key="aRaio")
            aAng = c6.number_input("Ângulo do corte (graus)", 5.0, 90.0, 45.0, 1.0, key="aAng",
                                   help="90 = corte reto (esquadro). Menor = chanfro. "
                                        "Esta seção é para cortes em ângulo — use 90 só se quiser reto.")
            aPontas = c7.radio("Pontas com corte", [1, 2], index=1, horizontal=True, key="aPontas")
            aQtd = c8.number_input("Quantidade", 1, 999, 1, 1, key="aQtd")
            c9, c10 = st.columns(2)
            aPlano = c9.radio("Plano do corte", ["Altura", "Largura"], horizontal=True, key="aPlano",
                              help="Em qual dimensão da seção o chanfro acontece.")
            if aPlano == "Altura":
                aLado = c10.radio("Lado mais longo", ["Topo", "Fundo"], horizontal=True, key="aLadoA")
            else:
                aLado = c10.radio("Lado mais longo", ["Direita", "Esquerda"], horizontal=True, key="aLadoB")
            # prévia do corte (feedback imediato)
            import math as _m
            _Q = aW if aPlano == "Largura" else aT
            if aAng >= 89.999:
                st.caption("↗ Ângulo 90° = **corte reto** (sem chanfro). Diminua o ângulo para chanfrar.")
            else:
                _run = _Q / _m.tan(_m.radians(aAng))
                _tot = _run * (2 if aPontas == 2 else 1)
                if _tot >= aL:
                    st.warning(f"Ângulo {aAng:g}° agressivo demais: o corte ({_tot:.0f} mm) "
                               f"é maior que o comprimento ({aL:g} mm). Aumente o ângulo ou o comprimento.")
                else:
                    st.caption(f"✂️ Chanfro de ~**{_run:.0f} mm** em cada ponta ({aPontas}× corte a {aAng:g}°).")
            st.markdown("**Furos (opcional)**")
            aFuros = st.checkbox("Incluir furos na peça", key="aFuros")
            if aFuros:
                cf1, cf2 = st.columns(2)
                aPos = cf1.text_input("Posições dos furos (mm, da ponta)", "100, 400", key="aPos")
                aTipoF = cf2.radio("Tipo de furo", ["Redondo", "Sextavado"], horizontal=True, key="aTipoF")
                cf3, cf4 = st.columns(2)
                if aTipoF == "Redondo":
                    aTam = cf3.number_input("Ø furo (mm)", 1.0, 100.0, 8.0, 0.5, key="aTam")
                    aOriF = "Face para cima"
                else:
                    aTam = chave_sextavado(cf3, "ang_chave")
                    aOriF = cf3.radio("Orientação do sextavado",
                                      ["Face para cima", "Vértice para cima"], horizontal=True, key="aOriF")
                aFacesF = cf4.radio("Furos em", ["Apenas face superior", "Ambas as faces"], horizontal=True, key="aFacesF")
                aCompF = comp_input(cf4, "ang_comp", chave=(aTam if aTipoF == "Sextavado" else None))
            else:
                aPos, aTipoF, aTam = "", "Redondo", 0.0
                aOriF, aFacesF, aCompF = "Face para cima", "Apenas face superior", 0.0
            ca, cb = st.columns(2)
            if ca.button("➕  Adicionar à lista", type="primary", use_container_width=True, key="add"):
                furos = ([float(x.strip().replace(",", ".")) for x in aPos.split(",") if x.strip()]
                         if aFuros else [])
                st.session_state["lote"].append(dict(
                    L=aL, W=aW, T=aT, wall=aWall, raio=aRaio, angulo=aAng,
                    pontas=int(aPontas), plano=("largura" if aPlano == "Largura" else "altura"),
                    lado=aLado.lower(), qtd=int(aQtd),
                    furos=furos, tamanho=(float(aTam) if aFuros else 0.0),
                    tipo_furo=("sextavado" if aTipoF == "Sextavado" else "redondo"),
                    faces=("ambas" if aFacesF == "Ambas as faces" else "topo"),
                    orient_sext=("vertice" if aOriF == "Vértice para cima" else "face"),
                    comp=(float(aCompF) if aFuros else 0.0)))
                st.session_state.pop("lote_zip", None)
            if cb.button("🗑  Limpar lista", type="primary", use_container_width=True, key="clr"):
                st.session_state["lote"] = []
                st.session_state.pop("lote_zip", None)
        lote = st.session_state["lote"]
        if lote:
            st.markdown("**Peças na lista**")
            st.table({
                "Qtd": [p["qtd"] for p in lote],
                "Comp (mm)": [f'{p["L"]:g}' for p in lote],
                "Seção": [f'{p["W"]:g}×{p["T"]:g}' for p in lote],
                "Parede": [f'{p["wall"]:g}' for p in lote],
                "Raio": [f'{p["raio"]:g}' for p in lote],
                "Ângulo": [f'{p["angulo"]:g}°' for p in lote],
                "Pontas": [p["pontas"] for p in lote],
                "Furos": [f'{len(p.get("furos") or [])}× {p.get("tamanho", 0):g}' if p.get("furos") else "—" for p in lote],
                "Plano/lado": [f'{p["plano"]}/{p["lado"]}' for p in lote],
            })
            if st.button("GERAR TODAS", type="primary", use_container_width=True, key="genlote"):
                try:
                    results = [mc.tubo_corte_angular(
                        p["W"], p["T"], p["wall"], p["L"], angulo=p["angulo"], pontas=p["pontas"],
                        plano=p["plano"], lado=p["lado"], raio=p["raio"], qtd=p["qtd"],
                        furos=p.get("furos") or [], tamanho=p.get("tamanho", 0.0),
                        tipo_furo=p.get("tipo_furo", "redondo"), faces=p.get("faces", "topo"),
                        orient_sext=p.get("orient_sext", "face"), comp=p.get("comp", 0.0)) for p in lote]
                    total = sum(r.mass * r.qtd for r in results)
                    st.session_state["lote_zip"] = gerar_zip_lote(results)
                    n_red = sum(1 for r in results if (getattr(r, "extra", None) or {}).get("raio_reduzido"))
                    aviso = (f" ⚠️ {n_red} peça(s) tiveram o canto arredondado convertido em canto vivo "
                             "para o corte fechar (o kernel falhou com o raio nessa seção)." if n_red else "")
                    st.session_state["lote_msg"] = (f"{len(results)} peça(s) · massa total ~ {total:.2f} kg. "
                                                    f"O .zip traz 1 PDF único ({len(results)} páginas) + IGES/STEP por peça + lista de corte."
                                                    + aviso)
                except Exception as e:
                    st.session_state.pop("lote_zip", None)
                    st.error("Erro ao gerar: " + str(e))
            if st.session_state.get("lote_zip"):
                st.success(st.session_state.get("lote_msg", ""))
                st.download_button("⬇  Baixar todas (.zip)", data=st.session_state["lote_zip"],
                                   file_name="corte_angular_lote.zip", mime="application/zip",
                                   use_container_width=True, key="dllote")
        else:
            st.info("Nenhuma peça na lista ainda. Preencha acima e clique em **Adicionar à lista**.")

    # ------------------------------------------------- Bancada de inox
    elif secao == "bancada":
        st.caption("Gera a **planificação** da bancada de inox (corte) e o **plano de dobra** (2º "
                   "processo), com espelho, saia/rebaixo, **alívios** nos cantos e cubas.")
        tabB, tabBib, tabC, tabPan = st.tabs(["Gerar bancada", "📚 Minhas bancadas", "Biblioteca de cubas", "Paneleiro"])
        with tabPan:
            st.caption("Conjunto do paneleiro a partir da bancada: **Paneleiro** (alma = C−100 × L−140, "
                       "abas 40+10 nas 4 laterais, esquadria só no retorno) + **Reforço do paneleiro** "
                       "(L−143 × alma 150, abas 35+10 em cima/baixo). Desenho: só planificado + dobras + identificação.")
            pc1, pc2, pc3 = st.columns(3)
            pC = pc1.number_input("C — comprimento da bancada (mm)", 200.0, 6000.0, 1000.0, 10.0, key="pn_C")
            pL = pc2.number_input("L — largura da bancada (mm)", 200.0, 3000.0, 500.0, 10.0, key="pn_L")
            pEsp = pc3.number_input("Espessura (mm)", 0.6, 3.0, 1.2, 0.1, key="pn_esp")
            inc_ref = st.checkbox("Incluir também o REFORÇO de bancada avulso (CR = L − 152, dobras 15+10, "
                                  "abas 15 nas pontas sem linha de dobra)", False, key="pn_ref")
            nome_auto("pn_nome", f"Paneleiro_{int(pC)}x{int(pL)}")
            nomeP = st.text_input("Nome", key="pn_nome")
            try:
                pecas = [paneleiro_mod.paneleiro_prims(pC, pL, esp=pEsp),
                         paneleiro_mod.reforco_paneleiro_prims(pL, esp=pEsp)]
                if inc_ref:
                    pecas.append(paneleiro_mod.reforco_bancada_prims(pL, esp=pEsp))
                mm1, mm2, mm3 = st.columns(3)
                mm1.metric("Paneleiro (plano)", f"{pecas[0]['bbox'][0]:.0f} × {pecas[0]['bbox'][1]:.0f} mm")
                mm2.metric("Reforço paneleiro", f"{pecas[1]['bbox'][0]:.0f} × 240 mm")
                if inc_ref:
                    mm3.metric("Reforço bancada", f"{pecas[2]['bbox'][0]:.0f} × 200 mm")
                for p in pecas:
                    st.image(flanges.preview_png(bancada.preview_prims(p)), use_container_width=True,
                             caption=f"{p['name']} · {p['bbox'][0]:.0f} × {p['bbox'][1]:.0f} mm · "
                                     f"{len(p['dobras'])} linha(s) de dobra")
                dxf_conj = bancada.nest_dxf([(p, 1) for p in pecas], gap=30)
                pdfP = paneleiro_mod.desenho_pdf(pecas, titulo=nomeP)
                bufP = io.BytesIO()
                with zipfile.ZipFile(bufP, "w", zipfile.ZIP_DEFLATED) as z:
                    z.writestr(f"{nomeP}/{nomeP}_conjunto.dxf", dxf_conj)
                    for p in pecas:
                        pn = p["name"].replace(" ", "_")
                        z.writestr(f"{nomeP}/pecas/{pn}.dxf", bancada.dxf_bytes([(p, 0, 0)]))
                    z.writestr(f"{nomeP}/{nomeP}_desenho.pdf", pdfP)
                st.download_button("⬇  Baixar TUDO (.zip: DXFs + desenho)", data=bufP.getvalue(),
                                   file_name=f"{nomeP}.zip", mime="application/zip", use_container_width=True)
                pd1, pd2 = st.columns(2)
                pd1.download_button("DXF conjunto", data=dxf_conj, file_name=f"{nomeP}.dxf",
                                    mime="image/vnd.dxf", use_container_width=True)
                pd2.download_button("📄 Desenho (planificado + dobras)", data=pdfP,
                                    file_name=f"{nomeP}_desenho.pdf", mime="application/pdf",
                                    use_container_width=True)
                st.caption("DXF: só contorno de corte (sem linha de dobra). As dobras aparecem no desenho PDF, "
                           "tracejadas — inclusive as abas de 15 das pontas do reforço avulso ficam SEM linha, "
                           "conforme a especificação. Obs.: a spec do reforço avulso cita CR = L−152 e também "
                           "\"L−150\"; adotei **L−152** — me avise se for o outro.")
            except ValueError as ve:
                st.warning(str(ve))
            except Exception as e:
                st.error("Erro ao gerar o paneleiro: " + str(e))
        with tabB:
            c1, c2, c3 = st.columns(3)
            comp = c1.number_input("Comprimento externo (mm)", 200.0, 6000.0, 1000.0, 10.0, key="bc_comp")
            prof = c2.number_input("Profundidade externa (mm)", 200.0, 1500.0, 500.0, 10.0, key="bc_prof")
            esp = c3.number_input("Espessura (mm)", 0.6, 3.0, 1.2, 0.1, key="bc_esp")
            st.caption("Medidas **externas** (acabadas). As internas saem do cálculo automático "
                       "(ex.: profundidade interna = externa − 20 mm da dobra do espelho do fundo).")

            st.markdown("**Espelhos** — selecione a configuração (o gráfico mostra a seleção):")
            gcol, scol = st.columns([1, 1.15])
            with scol:
                opc = st.selectbox("Tipo de espelho", list(bancada.OPCOES_ESPELHO.keys()), key="bc_opc")
                espelhos = bancada.OPCOES_ESPELHO[opc]
                with st.expander("Alturas e abas (padrão de fábrica)"):
                    espalt = st.number_input("Altura do espelho (mm)", 0.0, 400.0, bancada.ESPELHO_ALTURA, 5.0, key="bc_espalt")
                    abav = st.number_input("Aba lateral (mm, mín. 10)", bancada.ABA_MIN, 300.0, bancada.ABA_PADRAO, 5.0, key="bc_aba")
                    dobra_fora = st.checkbox("Dobra superior do espelho vira PARA FORA (avança 20 mm)", True, key="bc_dfora")
                    st.caption(f"Espelho = altura + dobra {bancada.DOBRA_ESP:g} + retorno {bancada.RETORNO_ESP:g}. "
                               f"Aba = largura + retorno {bancada.RETORNO_ABA:g} (com esquadria). "
                               f"Encontro de espelhos: esquadria 45° (topo contínuo). "
                               f"{'Pra FORA: tampa = externa − 20; a dobra devolve os 20 → montada = externa.' if dobra_fora else 'Pra DENTRO: tampa = externa; a dobra fica sobre a tampa → montada = externa.'}")
            with gcol:
                st.image(bancada.esquema_png(espelhos), use_container_width=True)
                if not espelhos:
                    st.caption("Bancada lisa: abas nos 4 lados, recorte de canto, **sem rasgo de alívio**.")

            st.markdown("**Cubas** — posicionadas pelo eixo. Recorte = furo na chapa.")
            n_cubas = int(st.number_input("Quantidade de cubas (0 = sem cuba)", 0, 8, 1, 1, key="bc_ncub"))
            cubas_spec = []; centralizado = True; distribuir = True; eixos = []
            if n_cubas >= 1:
                salvas = cubas_lib.listar_cubas()
                for i in range(n_cubas):
                    st.markdown(f"*Cuba {i + 1}*")
                    q1, q2, q3, q4 = st.columns(4)
                    usemod = None
                    if salvas:
                        opcs = ["(digitar)"] + [m["nome"] for m in salvas]
                        sel = q1.selectbox("Modelo", opcs, key=f"bc_c{i}_mod")
                        if sel != "(digitar)":
                            usemod = next(m for m in salvas if m["nome"] == sel)
                    if usemod:
                        cw = float(usemod["larg"]); chh = float(usemod["prof"]); raio = float(usemod.get("valor", 0.0) or 0.0)
                        q2.metric("Recorte C", f"{cw:g}"); q3.metric("Recorte L", f"{chh:g}"); q4.metric("Raio", f"{raio:g}")
                    else:
                        cw = q2.number_input("Comp. recorte (mm)", 50.0, 2000.0, 500.0, 5.0, key=f"bc_c{i}_w")
                        chh = q3.number_input("Larg. recorte (mm)", 50.0, 1200.0, 400.0, 5.0, key=f"bc_c{i}_h")
                        raio = q4.number_input("Raio cantos (mm)", 0.0, 300.0, 0.0, 1.0, key=f"bc_c{i}_r")
                    cubas_spec.append({"comp": cw, "larg": chh, "raio": raio})
                if n_cubas == 1:
                    centralizado = st.checkbox("Cuba centralizada", True, key="bc_centr")
                    if not centralizado:
                        distribuir = False
                        eixos = [st.number_input("Extremidade esq. → eixo da cuba (mm)", 0.0, 6000.0, 500.0, 10.0, key="bc_eixo0")]
                else:
                    distribuir = st.checkbox("Distribuição automática", True, key="bc_distr")
                    if not distribuir:
                        centralizado = False
                        st.caption("Eixo de cada cuba (extremidade esq. → centro):")
                        cols = st.columns(min(n_cubas, 4))
                        for i in range(n_cubas):
                            eixos.append(cols[i % len(cols)].number_input(f"Eixo {i + 1} (mm)", 0.0, 6000.0, 300.0 * (i + 1), 10.0, key=f"bc_eixo{i}"))

            st.markdown("**Acessórios (gerados junto, na mesma peça):**")
            _ac1, _ac2, _ac3, _ac4 = st.columns(4)
            inc_saiote = _ac1.radio("Saiote", ["Não", "Sim"], horizontal=False, key="bc_saiote") == "Sim"
            q_ref_sup = int(_ac2.number_input("Reforço superior", 0, 10, 0, 1, key="bc_qrefsup",
                                              help="Reforço da bandeja superior: CR = L − 152, alma 150, "
                                                   "dobras 15+10 nas bordas, abas 15 nas pontas (sem linha de dobra)."))
            q_paneleiro = int(_ac3.number_input("Paneleiro", 1, 3, 1, 1, key="bc_qpan",
                                                help="Paneleiro: alma C−100 × L−140, abas 40+10 nas 4 laterais."))
            q_ref_pan = int(_ac4.number_input("Reforço paneleiro", 0, 5, 0, 1, key="bc_qrefpan",
                                              help="Reforço do paneleiro: L−143 × alma 150, abas 35+10 em cima/baixo."))
            _cod_esp = {"Espelho Frontal (fundo)": "F", "Frontal + Lateral Esquerda": "FE",
                        "Frontal + Lateral Direita": "FD", "Frontal + Laterais Esq. e Dir.": "U",
                        "Sem espelho (lisa)": "LISA"}.get(opc, "F")
            _sug = f"Bancada_{int(comp)}x{int(prof)}_{_cod_esp}"
            if n_cubas >= 1:
                _sug += f"_{n_cubas}cuba" + ("s" if n_cubas > 1 else "")
            if inc_saiote:
                _sug += "_saiote"
            nome_auto("bc_nome", _sug)
            nome = st.text_input("Nome do arquivo", key="bc_nome")
            try:
                Wint, Dint = bancada._interna(comp, prof, set(espelhos), dobra_fora)
                if n_cubas >= 1:
                    cubas, erros = bancada.posicionar_cubas(Wint, Dint, cubas_spec, centralizado, distribuir, eixos)
                else:
                    cubas, erros = [], []
                if erros:
                    for e in erros:
                        st.error("⚠ " + e)
                    st.warning("O desenho **não foi gerado** — corrija os itens acima (regra de fabricação).")
                else:
                    prims = bancada.gerar(comp, prof, esp, espelhos=espelhos, espelho_altura=espalt,
                                          aba=abav, dobra_fora=dobra_fora, cubas=cubas, name=nome)
                    dxf = bancada.dxf_bytes([(prims, 0, 0)])
                    png = flanges.preview_png(bancada.preview_prims(prims))
                    img3d = bancada.imagem_3d(prims)
                    pdf_corte = bancada_pdf.desenho_pdf(prims)
                    pdf_dobra = bancada_pdf.dobra_pdf(prims)
                    etiqueta = etiquetas.gerar_etiquetas_pdf(bancada_pdf.etiqueta_itens(prims, 1),
                                                             tamanho=(150.0, 50.0))
                    folha = bancada_pdf.folha_projeto(prims, img3d_bytes=img3d, qtd=1)
                    rs_sai = None; img3d_sai = None; dxf_sai = None; folha_sai = None; etiq_sai = None
                    if inc_saiote:
                        try:
                            rs_sai = saiote.gerar(comp, prof, esp=esp)
                            img3d_sai = saiote.imagem_3d(rs_sai)
                            dxf_sai = bancada.nest_dxf([(p, 1) for p in rs_sai["pecas"]], gap=30)
                            folha_sai = saiote.folha_pdf(rs_sai)
                            etiq_sai = etiquetas.gerar_etiquetas_pdf(saiote.etiqueta_itens(rs_sai), tamanho=(150.0, 50.0))
                        except ValueError as _ve:
                            st.warning("Saiote não gerado: " + str(_ve))
                    # acessórios com quantidade (mesma página) — subpasta, prims, qtd
                    acess = []
                    try:
                        if q_ref_sup > 0:
                            acess.append(("reforco_superior",
                                          paneleiro_mod.reforco_bancada_prims(prof, esp=esp), q_ref_sup))
                        acess.append(("paneleiro",
                                      paneleiro_mod.paneleiro_prims(comp, prof, esp=esp), q_paneleiro))
                        if q_ref_pan > 0:
                            acess.append(("reforco_paneleiro",
                                          paneleiro_mod.reforco_paneleiro_prims(prof, esp=esp), q_ref_pan))
                    except ValueError as _ve2:
                        st.warning("Acessório não gerado (bancada pequena demais): " + str(_ve2))
                    cP, cI = st.columns([1.5, 1])
                    with cP:
                        _abas = ["\U0001F4D0 Planificação (corte)", "\U0001F9CA 3D (dobrado)"]
                        if rs_sai is not None:
                            _abas.append("\U0001F532 Saiote 3D")
                        _tabs = st.tabs(_abas)
                        with _tabs[0]:
                            st.image(png, use_container_width=True)
                            st.caption("É o que o laser corta: contorno externo + alívio + cuba. **Sem linhas de dobra.**")
                        with _tabs[1]:
                            st.image(img3d, use_container_width=True)
                            st.caption("Peça depois de dobrada (espelho ↑, abas ↓).")
                        if rs_sai is not None:
                            with _tabs[2]:
                                st.image(img3d_sai, use_container_width=True)
                                st.caption(f"Quadro do saiote montado: {rs_sai['PL']:.0f} × {rs_sai['PT']:.0f} mm — "
                                           f"instalado por dentro das dobras da bancada.")
                    with cI:
                        inf = prims["info"]
                        st.metric("Montada (externa)", f"{inf['final_comprimento']:.0f} × {inf['final_profundidade']:.0f} mm")
                        st.metric("Interna (tampa)", f"{inf['comprimento_int']:.0f} × {inf['profundidade_int']:.0f} mm")
                        st.metric("Chapa plana (corte)", f"{inf['Wd']:.0f} × {inf['Hd']:.0f} mm")
                        st.metric("Peso (inox 304)", f"{bancada.peso_kg(prims):.1f} kg")
                        st.caption(f"Espelhos: {', '.join(inf['espelhos']) or 'nenhum (lisa)'} · "
                                   f"{inf['n_rasgos']} rasgo(s) de alívio · {inf['n_esquadrias']} esquadria(s). "
                                   f"Interna = externa − 20 mm por lado com espelho; a dobra superior vira pra fora e "
                                   f"devolve os 20 mm, então a **montada bate na medida externa**. Camadas DXF: CORTE / FUROS.")
                        if rs_sai is not None:
                            st.caption(f"**Saiote incluído:** PL {rs_sai['PL']:.0f} mm ×2 · PT {rs_sai['PT']:.0f} mm ×2 · "
                                       f"seção 170 mm — quadro ~2,5 cm menor, por dentro das dobras. "
                                       f"Arquivos na pasta **saiote/** do zip.")
                        if acess:
                            _res = " · ".join(f"{sub.replace('_', ' ')} ×{q}" for sub, _pr, q in acess)
                            st.caption(f"**Acessórios:** {_res}. Cada um na sua pasta no zip (DXF em lote + desenho).")
                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                            z.writestr(f"{nome}/{nome}.dxf", dxf)
                            z.writestr(f"{nome}/{nome}_FOLHA_PROJETO.pdf", folha)
                            z.writestr(f"{nome}/{nome}_etiqueta.pdf", etiqueta)
                            z.writestr(f"{nome}/{nome}.png", png)
                            z.writestr(f"{nome}/{nome}_3D.png", img3d)
                            z.writestr(f"{nome}/{nome}_corte.pdf", pdf_corte)
                            z.writestr(f"{nome}/{nome}_dobra.pdf", pdf_dobra)
                            for sub, pr, q in acess:
                                z.writestr(f"{nome}/{sub}/{sub}_x{q}.dxf", bancada.nest_dxf([(pr, q)], gap=30))
                                z.writestr(f"{nome}/{sub}/{sub}_unidade.dxf", bancada.dxf_bytes([(pr, 0, 0)]))
                                z.writestr(f"{nome}/{sub}/{sub}_desenho.pdf",
                                           paneleiro_mod.desenho_pdf([pr], titulo=f"{pr['name']} (x{q})"))
                            if rs_sai is not None:
                                z.writestr(f"{nome}/saiote/{nome}_saiote_conjunto.dxf", dxf_sai)
                                for p in rs_sai["pecas"]:
                                    pn = p["name"].replace(" ", "_")
                                    z.writestr(f"{nome}/saiote/pecas/{pn}.dxf", bancada.dxf_bytes([(p, 0, 0)]))
                                z.writestr(f"{nome}/saiote/{nome}_saiote_FOLHA.pdf", folha_sai)
                                z.writestr(f"{nome}/saiote/{nome}_saiote_etiquetas.pdf", etiq_sai)
                                z.writestr(f"{nome}/saiote/{nome}_saiote_3D.png", img3d_sai)
                            # ---------- RESUMO ----------
                            resumo_dxfs = [(f"bancada_{nome}.dxf", dxf)]
                            if rs_sai is not None:
                                resumo_dxfs.append(("saiote_conjunto.dxf", dxf_sai))
                            for sub, pr, q in acess:
                                resumo_dxfs.append((f"{sub}_x{q}.dxf", bancada.nest_dxf([(pr, q)], gap=30)))
                            itens_ger = bancada_pdf.etiqueta_itens(prims, 1)
                            if rs_sai is not None:
                                itens_ger += saiote.etiqueta_itens(rs_sai)
                            for sub, pr, q in acess:
                                itens_ger.append({"descricao": f"{pr['name']} {pr['bbox'][0]:.0f}x{pr['bbox'][1]:.0f} mm",
                                                  "material": f"Inox 304 {esp:g}mm", "qtd": q})
                            etiq_gerais = etiquetas.gerar_etiquetas_pdf(itens_ger, tamanho=(150.0, 50.0))
                            imgs3d = [("Bancada", img3d)]
                            if img3d_sai:
                                imgs3d.append(("Saiote", img3d_sai))
                            pdfs_proj = [_pdf_pagina_3d(imgs3d), folha, pdf_dobra]
                            if rs_sai is not None:
                                pdfs_proj.append(folha_sai)
                            for sub, pr, q in acess:
                                pdfs_proj.append(paneleiro_mod.desenho_pdf([pr], titulo=f"{pr['name']} (x{q})"))
                            resumo_proj = _merge_pdfs(pdfs_proj)
                            for fn, db in resumo_dxfs:
                                z.writestr(f"{nome}/RESUMO_DXF/{fn}", db)
                            z.writestr(f"{nome}/RESUMO_DXF/ETIQUETAS_GERAIS.pdf", etiq_gerais)
                            if resumo_proj:
                                z.writestr(f"{nome}/RESUMO_PROJETO.pdf", resumo_proj)
                            else:
                                for kk, pb in enumerate(pdfs_proj):
                                    if pb:
                                        z.writestr(f"{nome}/RESUMO_PROJETO/parte_{kk+1}.pdf", pb)
                        st.download_button("\u2b07  Baixar (.zip: DXF + folha + etiqueta + PDFs + PNG)", data=buf.getvalue(),
                                           file_name=f"{nome}.zip", mime="application/zip", use_container_width=True)
                        buf_res = io.BytesIO()
                        with zipfile.ZipFile(buf_res, "w", zipfile.ZIP_DEFLATED) as zr:
                            for fn, db in resumo_dxfs:
                                zr.writestr(f"RESUMO_DXF/{fn}", db)
                            zr.writestr("RESUMO_DXF/ETIQUETAS_GERAIS.pdf", etiq_gerais)
                            if resumo_proj:
                                zr.writestr("RESUMO_PROJETO.pdf", resumo_proj)
                        st.download_button("\U0001F4C1  RESUMO: todos os DXF numa pasta + etiquetas gerais + projeto",
                                           data=buf_res.getvalue(), file_name=f"{nome}_RESUMO.zip",
                                           mime="application/zip", use_container_width=True)
                        if rs_sai is not None:
                            buf_sai = io.BytesIO()
                            with zipfile.ZipFile(buf_sai, "w", zipfile.ZIP_DEFLATED) as zs:
                                zs.writestr(f"{nome}_saiote/{nome}_saiote_conjunto.dxf", dxf_sai)
                                for p in rs_sai["pecas"]:
                                    pn = p["name"].replace(" ", "_")
                                    zs.writestr(f"{nome}_saiote/pecas/{pn}.dxf", bancada.dxf_bytes([(p, 0, 0)]))
                                zs.writestr(f"{nome}_saiote/{nome}_saiote_FOLHA.pdf", folha_sai)
                                zs.writestr(f"{nome}_saiote/{nome}_saiote_etiquetas.pdf", etiq_sai)
                                zs.writestr(f"{nome}_saiote/{nome}_saiote_3D.png", img3d_sai)
                            st.download_button("\U0001F532  Baixar só o SAIOTE (.zip: DXFs + folha + etiquetas + 3D)",
                                               data=buf_sai.getvalue(), file_name=f"{nome}_saiote.zip",
                                               mime="application/zip", use_container_width=True)
                        f1, f2 = st.columns(2)
                        f1.download_button("📄 Folha de projeto", data=folha, file_name=f"{nome}_FOLHA.pdf",
                                           mime="application/pdf", use_container_width=True)
                        f2.download_button("🏷️ Etiqueta", data=etiqueta, file_name=f"{nome}_etiqueta.pdf",
                                           mime="application/pdf", use_container_width=True)
                        arquivos = [("DXF", f"{nome}.dxf", dxf, "image/vnd.dxf"),
                                    ("Folha projeto", f"{nome}_FOLHA.pdf", folha, "application/pdf"),
                                    ("Etiqueta", f"{nome}_etiqueta.pdf", etiqueta, "application/pdf"),
                                    ("PDF corte", f"{nome}_corte.pdf", pdf_corte, "application/pdf"),
                                    ("PDF dobra", f"{nome}_dobra.pdf", pdf_dobra, "application/pdf"),
                                    ("PNG plano", f"{nome}.png", png, "image/png"),
                                    ("PNG 3D", f"{nome}_3D.png", img3d, "image/png")]
                        with st.expander("Baixar arquivos separados (sem zip)"):
                            dcols = st.columns(3)
                            for idx, (lbl, fn, data, mime) in enumerate(arquivos):
                                dcols[idx % 3].download_button(lbl, data=data, file_name=fn, mime=mime,
                                                               key=f"bc_dl_{idx}", use_container_width=True)
                        with st.expander("Salvar direto numa pasta (uso local)"):
                            pasta = st.text_input("Caminho da pasta no seu PC", key="bc_pasta",
                                                  placeholder="ex.: C:\\Users\\voce\\Bancadas")
                            if st.button("Salvar na pasta", key="bc_salvar"):
                                if not pasta.strip():
                                    st.warning("Informe o caminho da pasta.")
                                else:
                                    try:
                                        import os
                                        dest = os.path.join(pasta.strip(), nome)
                                        os.makedirs(dest, exist_ok=True)
                                        for _lbl, fn, data, _m in arquivos:
                                            with open(os.path.join(dest, fn), "wb") as fh:
                                                fh.write(data)
                                        st.success(f"Salvo em: {dest}")
                                    except Exception as ex:
                                        st.error(f"Não deu pra salvar: {ex}")
                            st.caption("Funciona ao rodar o app no seu PC (streamlit run). Na versão web (Render) "
                                       "o servidor não acessa suas pastas — aí use o .zip ou os arquivos separados.")
                        st.markdown("---")
                        st.markdown("**Enviar para a biblioteca** — fica salva pra acesso a 1 clique e lote.")
                        eb1, eb2 = st.columns([1, 1.3])
                        qtd_lib = int(eb1.number_input("Quantidade", 1, 999, 1, 1, key="bc_qtdlib"))
                        if eb2.button("📥 Salvar na biblioteca", key="bc_envlib", use_container_width=True):
                            params = {"comprimento": comp, "profundidade": prof, "esp": esp,
                                      "espelhos": list(espelhos), "espelho_altura": espalt, "aba": abav,
                                      "dobra_fora": dobra_fora, "cubas": [list(c) for c in cubas],
                                      "saiote": bool(inc_saiote), "ref_sup": int(q_ref_sup),
                                      "paneleiro": int(q_paneleiro), "ref_pan": int(q_ref_pan)}
                            bancadas_lib.salvar_bancada(nome, params, qtd_lib)
                            st.success(f"'{nome}' (×{qtd_lib}) salva. Veja na aba 📚 Minhas bancadas.")
            except Exception as e:
                st.error("Erro ao gerar a bancada: " + str(e))

        with tabBib:
            libs = bancadas_lib.listar_bancadas()
            if not libs:
                st.info("Nenhuma bancada salva. Gere uma peça na aba **Gerar bancada** e clique em "
                        "**Salvar na biblioteca** — ela aparece aqui pra acesso a 1 clique e para lote.")
            else:
                pecas = []
                for m in libs:
                    try:
                        pecas.append((m, bancada.gerar_de_params(m["params"], name=m["nome"])))
                    except Exception:
                        pecas.append((m, None))
                validas = [(m, pr) for m, pr in pecas if pr is not None]
                total_pcs = sum(int(m.get("qtd", 1)) for m, _ in validas)
                st.caption(f"{len(validas)} modelo(s) · {total_pcs} peça(s) no total (com as quantidades).")

                st.markdown("**Lote** — todas as peças de uma vez, respeitando a quantidade:")
                lc1, lc2, lc3 = st.columns(3)
                if validas:
                    lote_dxf = bancada.nest_dxf([(pr, int(m.get("qtd", 1))) for m, pr in validas])
                    lc1.download_button("⬇ DXF em lote (1 arquivo)", data=lote_dxf,
                                        file_name="bancadas_lote.dxf", mime="image/vnd.dxf", use_container_width=True)
                    # RESUMO DXF de TODAS: cada DXF (bancada + conjunto) numa pasta só + etiquetas gerais
                    buf_rall = io.BytesIO()
                    itens_ger_lib = []
                    with zipfile.ZipFile(buf_rall, "w", zipfile.ZIP_DEFLATED) as zr:
                        for m, pr in validas:
                            qb = int(m.get("qtd", 1)); pz = m.get("params", {}) or {}
                            nm = m["nome"]
                            zr.writestr(f"RESUMO_DXF/bancada_{nm}_x{qb}.dxf", bancada.nest_dxf([(pr, qb)], gap=40))
                            itens_ger_lib += bancada_pdf.etiqueta_itens(pr, qb)
                            zr.writestr(f"ADESIVOS/etiquetas_{nm}_x{qb}.pdf",
                                        etiquetas.gerar_etiquetas_pdf(
                                            bancada_pdf.etiqueta_itens(pr, qb),
                                            tamanho=(150.0, 50.0)))
                            try:
                                if pz.get("saiote"):
                                    rs = saiote.gerar(pz.get("comprimento", 1000), pz.get("profundidade", 500),
                                                      esp=pz.get("esp", 1.2))
                                    pcs = [(p, qb) for p in rs["pecas"]]
                                    zr.writestr(f"RESUMO_DXF/saiote_{nm}_x{qb}.dxf", bancada.nest_dxf(pcs, gap=30))
                                    for _it in saiote.etiqueta_itens(rs):
                                        _it = dict(_it); _it["qtd"] = qb
                                        itens_ger_lib.append(_it)
                                _ac = [("reforco_superior", pz.get("ref_sup", 0),
                                        lambda: paneleiro_mod.reforco_bancada_prims(pz.get("profundidade", 500), esp=pz.get("esp", 1.2))),
                                       ("paneleiro", pz.get("paneleiro", 0),
                                        lambda: paneleiro_mod.paneleiro_prims(pz.get("comprimento", 1000), pz.get("profundidade", 500), esp=pz.get("esp", 1.2))),
                                       ("reforco_paneleiro", pz.get("ref_pan", 0),
                                        lambda: paneleiro_mod.reforco_paneleiro_prims(pz.get("profundidade", 500), esp=pz.get("esp", 1.2)))]
                                for _sub, _q, _fn in _ac:
                                    _qt = int(_q or 0) * qb
                                    if _qt > 0:
                                        _pr2 = _fn()
                                        zr.writestr(f"RESUMO_DXF/{_sub}_{nm}_x{_qt}.dxf",
                                                    bancada.nest_dxf([(_pr2, _qt)], gap=30))
                                        itens_ger_lib.append({"descricao": f"{_pr2['name']} {_pr2['bbox'][0]:.0f}x{_pr2['bbox'][1]:.0f} mm ({nm})",
                                                              "material": f"Inox 304 {pz.get('esp', 1.2):g}mm", "qtd": _qt})
                            except Exception:
                                pass
                        if itens_ger_lib:
                            zr.writestr("RESUMO_DXF/ETIQUETAS_GERAIS.pdf",
                                        etiquetas.gerar_etiquetas_pdf(itens_ger_lib, tamanho=(150.0, 50.0)))
                    lc1.download_button("\U0001F4C1 RESUMO DXF de todas (pasta única + etiquetas)",
                                        data=buf_rall.getvalue(), file_name="bancadas_RESUMO_DXF.zip",
                                        mime="application/zip", use_container_width=True, key="bc_resall")
                    itens = []
                    for m, pr in validas:
                        itens += bancada_pdf.etiqueta_itens(pr, int(m.get("qtd", 1)))
                    et_lote = etiquetas.gerar_etiquetas_pdf(itens, tamanho=(150.0, 50.0))
                    lc2.download_button("🏷️ Etiquetas em lote", data=et_lote,
                                        file_name="bancadas_etiquetas.pdf", mime="application/pdf", use_container_width=True)
                    if lc3.button("📦 Preparar pacote completo (folhas + 3D)", key="bc_prep_all", use_container_width=True):
                        tb = io.BytesIO()
                        with zipfile.ZipFile(tb, "w", zipfile.ZIP_DEFLATED) as z:
                            z.writestr("LOTE/bancadas_lote.dxf", lote_dxf)
                            z.writestr("LOTE/bancadas_etiquetas.pdf", et_lote)
                            for m, pr in validas:
                                nm = m["nome"]; q = int(m.get("qtd", 1))
                                i3 = bancada.imagem_3d(pr)
                                z.writestr(f"{nm}/{nm}.dxf", bancada.dxf_bytes([(pr, 0, 0)]))
                                z.writestr(f"{nm}/{nm}_FOLHA_PROJETO.pdf", bancada_pdf.folha_projeto(pr, img3d_bytes=i3, qtd=q))
                                z.writestr(f"{nm}/{nm}_etiqueta.pdf", etiquetas.gerar_etiquetas_pdf(bancada_pdf.etiqueta_itens(pr, q), tamanho=(150.0, 50.0)))
                                z.writestr(f"{nm}/{nm}_3D.png", i3)
                        st.session_state["bc_pack_all"] = tb.getvalue()
                    if st.session_state.get("bc_pack_all"):
                        st.download_button("⬇ Baixar pacote completo (.zip)", data=st.session_state["bc_pack_all"],
                                           file_name="bancadas_TUDO.zip", mime="application/zip", use_container_width=True)
                    if st.button("🖨️ Preparar PDF ÚNICO p/ impressão (todos os projetos)",
                                 key="bc_print_all", use_container_width=True):
                        pdfs_all = []
                        for m, pr in validas:
                            q = int(m.get("qtd", 1))
                            try:
                                i3 = bancada.imagem_3d(pr)
                            except Exception:
                                i3 = None
                            try:
                                pdfs_all.append(bancada_pdf.folha_projeto(pr, img3d_bytes=i3, qtd=q))
                                pdfs_all.append(bancada_pdf.dobra_pdf(pr))
                            except Exception as _ex:
                                st.warning(f"{m['nome']}: {_ex}")
                        unico = _merge_pdfs([p for p in pdfs_all if p])
                        if unico:
                            st.session_state["bc_print_pdf"] = unico
                        else:
                            st.error("Não foi possível montar o PDF único.")
                    if st.session_state.get("bc_print_pdf"):
                        st.download_button("⬇ Baixar PDF único de impressão", data=st.session_state["bc_print_pdf"],
                                           file_name="bancadas_PROJETOS_IMPRESSAO.pdf",
                                           mime="application/pdf", use_container_width=True)

                st.markdown("---")
                for m, pr in pecas:
                    with st.container(border=True):
                        cc = st.columns([3.2, 1, 1, 1])
                        inf = pr["info"] if pr else {}
                        cc[0].markdown(f"**{m['nome']}** · {inf.get('comprimento_ext',0):.0f}×{inf.get('profundidade_ext',0):.0f} mm"
                                       f" · espelhos: {', '.join(inf.get('espelhos',[])) or 'lisa'}"
                                       f" · {inf.get('cubas',0)} cuba(s)")
                        nq = int(cc[1].number_input("Qtd", 1, 999, int(m.get("qtd", 1)), 1, key=f"bc_q_{m['_arquivo']}"))
                        if nq != int(m.get("qtd", 1)):
                            bancadas_lib.atualizar_qtd(m["_arquivo"], nq)
                        if cc[2].button("Ver", key=f"bc_v_{m['_arquivo']}", use_container_width=True):
                            st.session_state["bc_lib_sel"] = m["_arquivo"]
                        if cc[3].button("Remover", key=f"bc_rm_{m['_arquivo']}", use_container_width=True):
                            bancadas_lib.remover_bancada(m["_arquivo"])
                            st.rerun()
                        if pr is not None and st.session_state.get("bc_lib_sel") == m["_arquivo"]:
                            i3 = bancada.imagem_3d(pr)
                            v1, v2 = st.columns(2)
                            v1.image(flanges.preview_png(bancada.preview_prims(pr)), use_container_width=True)
                            v2.image(i3, use_container_width=True)
                            dd = st.columns(3)
                            dd[0].download_button("DXF", data=bancada.dxf_bytes([(pr, 0, 0)]),
                                                  file_name=f"{m['nome']}.dxf", mime="image/vnd.dxf",
                                                  key=f"bc_ld_{m['_arquivo']}", use_container_width=True)
                            dd[1].download_button("Folha", data=bancada_pdf.folha_projeto(pr, img3d_bytes=i3, qtd=nq),
                                                  file_name=f"{m['nome']}_FOLHA.pdf", mime="application/pdf",
                                                  key=f"bc_lf_{m['_arquivo']}", use_container_width=True)
                            dd[2].download_button("Etiqueta", data=etiquetas.gerar_etiquetas_pdf(bancada_pdf.etiqueta_itens(pr, nq), tamanho=(150.0, 50.0)),
                                                  file_name=f"{m['nome']}_etiqueta.pdf", mime="application/pdf",
                                                  key=f"bc_le_{m['_arquivo']}", use_container_width=True)

        with tabC:
            st.caption("Cadastre suas cubas: informe a dimensão e (opcional) suba o **DXF/PDF** de referência.")
            cn = st.text_input("Nome da cuba", "", key="cb_nome", placeholder="ex.: Tencocuba 40×34")
            q1, q2, q3 = st.columns(3)
            cl = q1.number_input("Largura (mm)", 50.0, 1500.0, 400.0, 5.0, key="cb_l")
            cp = q2.number_input("Profundidade (mm)", 50.0, 1200.0, 340.0, 5.0, key="cb_p")
            canto2 = q3.selectbox("Canto", ["Chanfro 45°", "Raio"], key="cb_canto")
            q4, q5 = st.columns(2)
            cval = q4.number_input("Valor do canto (mm)", 0.0, 400.0, 60.0, 1.0, key="cb_val")
            cvalv = q5.number_input("Furo de válvula Ø (mm, 0=sem)", 0.0, 200.0, 0.0, 1.0, key="cb_valv")
            ref = st.file_uploader("DXF/PDF de referência (opcional)", type=["dxf", "pdf"], key="cb_ref")
            if st.button("💾 Salvar cuba", type="primary", use_container_width=True):
                if not cn.strip():
                    st.warning("Dê um nome à cuba.")
                else:
                    rb = ref.getvalue() if ref is not None else None
                    rext = (ref.name.rsplit(".", 1)[-1] if ref is not None else "")
                    cubas_lib.salvar_cuba(cn, cl, cp, "raio" if canto2.startswith("Raio") else "chanfro",
                                          cval, cvalv, ref_bytes=rb, ref_ext=rext)
                    st.success(f"Cuba '{cn}' salva."); st.rerun()
            salvas = cubas_lib.listar_cubas()
            st.markdown(f"**Cubas salvas ({len(salvas)})**")
            for i, m in enumerate(salvas):
                cA, cB, cC = st.columns([3, 1, 1])
                cA.write(f"**{m['nome']}** — {m['larg']:g}×{m['prof']:g} mm · {m['canto']} {m['valor']:g}"
                         + (f" · válvula Ø{m['valvula']:g}" if m.get("valvula") else ""))
                if m.get("_ref_path"):
                    try:
                        cB.download_button("Ref.", data=open(m["_ref_path"], "rb").read(),
                                           file_name=m["arquivo_ref"], key=f"cbref_{i}", use_container_width=True)
                    except Exception:
                        cB.write("—")
                if cC.button("Remover", key=f"cbrm_{i}", use_container_width=True):
                    cubas_lib.remover_cuba(m["_arquivo"]); st.rerun()

    # ------------------------------------------------- Mesas
    elif secao == "mesas":
        st.caption("Escolha o modelo de base pela foto de referência, um modelo pronto ou ajuste as medidas.")
        MODELOS_MESA = {
            "Estrutura metalon (4 pernas)": (
                "metalon", "Quadro completo em metalon: 4 pernas + travessas em meia esquadria 45°."),
            "Estrutura completa (moldura + pés U)": (
                "estrutura", "Moldura superior perimetral + pés em quadro fechado + travessa central. "
                             "Base p/ tampo de vidro, madeira ou pedra."),
            "Pés laterais em C (cantilever)": (
                "pes_c", "Par de pés em 'C' com diagonal frontal. Visual leve, tampo à parte."),
            "Pé de quadro (par ou avulso)": (
                "quadro", "Molduras retangulares fechadas (estilo trestle), com travessa, "
                          "niveladores e opção de quadro avulso."),
            "Pé trapézio (par)": (
                "trapezio", "Quadro trapezoidal simétrico: topo na largura do tampo, base menor."),
            "Base em X (cruzeta)": (
                "base_x", "Dois quadros cruzados a 90° com meia-madeira central. Ideal p/ tampo redondo."),
            "Pé cubo (diagonais)": (
                "cubo", "Quadros cruzados nas diagonais do tampo quadrado, com moldura superior."),
        }
        cSel, cImg = st.columns([3, 2])
        base = cSel.radio("Modelo de base", list(MODELOS_MESA.keys()), key="mesa_base")
        _slug, _desc = MODELOS_MESA[base]
        _img = mc.config.ASSETS / "mesas" / f"{_slug}.png"
        if _img.exists():
            cImg.image(str(_img), caption=base, use_container_width=True)
        cSel.caption(_desc)
        if base.startswith("Estrutura metalon"):
            PRESETS = {
                "Mesa de jantar — 1600×800×750": (1600.0, 800.0, 750.0, 40),
                "Mesa de centro — 1000×500×450": (1000.0, 500.0, 450.0, 30),
                "Aparador — 1200×400×900": (1200.0, 400.0, 900.0, 30),
                "Bancada — 2000×600×900": (2000.0, 600.0, 900.0, 50),
                "Banqueta — 400×400×750": (400.0, 400.0, 750.0, 30),
                "Personalizado": None,
            }
            for _k, _v in {"mL": 1600.0, "mDp": 800.0, "mH": 750.0, "mPerfil": 40, "mWall": 1.5, "mRaio": 0.0}.items():
                st.session_state.setdefault(_k, _v)
            with st.container(border=True):
                modelo = st.selectbox("Modelo de mesa", list(PRESETS.keys()), key="mesa_modelo")
                pre = PRESETS[modelo]
                if pre and st.session_state.get("_mesa_last") != modelo:
                    (st.session_state["mL"], st.session_state["mDp"],
                     st.session_state["mH"], st.session_state["mPerfil"]) = (
                        float(pre[0]), float(pre[1]), float(pre[2]), pre[3])
                st.session_state["_mesa_last"] = modelo
                st.divider()
                c1, c2, c3 = st.columns(3)
                L = c1.number_input("Comprimento (mm)", 300.0, 4000.0, step=10.0, key="mL")
                Dp = c2.number_input("Profundidade (mm)", 200.0, 1500.0, step=10.0, key="mDp")
                H = c3.number_input("Altura (mm)", 300.0, 1200.0, step=10.0, key="mH")
                c4, c5, c6 = st.columns(3)
                perfil = c4.selectbox("Perfil metalon (mm)", [20, 30, 40, 50], key="mPerfil")
                wall = c5.number_input("Espessura do tubo (mm)", 0.8, 3.0, step=0.1, key="mWall", help="Parede do metalon — entra no cálculo de massa e no sólido 3D.")
                raio = c6.number_input("Raio do canto (mm)", 0.0, 15.0, step=0.5, key="mRaio",
                                       help="0 = canto vivo. Aplica nos tubos individuais do metalon.")
                if st.button("GERAR MESA", type="primary", use_container_width=True, key="mGen"):
                    try:
                        r = mc.mesa_metalon(L, Dp, H, perfil=float(perfil), wall=wall, raio=raio)
                        mostra_resultado(r)
                        st.info("O .zip inclui a estrutura montada + os tubos mitrados individuais "
                                "(perna, travessa de ponta, travessa longa) para o laser de tubo.")
                    except Exception as e:
                        st.error("Erro ao gerar: " + str(e))
        elif base.startswith("Pés laterais"):
            PRESETS_C = {
                "Escrivaninha — 1200×750×780": (1200.0, 750.0, 780.0, 30),
                "Escrivaninha compacta — 1000×600×750": (1000.0, 600.0, 750.0, 30),
                "Mesa de centro — 1000×500×450": (1000.0, 500.0, 450.0, 40),
                "Aparador — 1200×400×850": (1200.0, 400.0, 850.0, 30),
                "Personalizado": None,
            }
            for _k, _v in {"cW": 1200.0, "cDp": 750.0, "cH": 780.0, "cPerfil": 30, "cWall": 1.5, "cTop": 25.0}.items():
                st.session_state.setdefault(_k, _v)
            with st.container(border=True):
                modelo = st.selectbox("Modelo de mesa", list(PRESETS_C.keys()), key="mesa_modelo_c")
                pre = PRESETS_C[modelo]
                if pre and st.session_state.get("_mesa_last_c") != modelo:
                    (st.session_state["cW"], st.session_state["cDp"],
                     st.session_state["cH"], st.session_state["cPerfil"]) = (
                        float(pre[0]), float(pre[1]), float(pre[2]), pre[3])
                st.session_state["_mesa_last_c"] = modelo
                st.divider()
                c1, c2, c3 = st.columns(3)
                W = c1.number_input("Largura (mm)", 400.0, 4000.0, step=10.0, key="cW")
                Dp = c2.number_input("Profundidade (mm)", 250.0, 1200.0, step=10.0, key="cDp")
                H = c3.number_input("Altura (mm)", 350.0, 1100.0, step=10.0, key="cH")
                c4, c5, c6 = st.columns(3)
                perfil = c4.selectbox("Perfil do tubo (mm)", [20, 25, 30, 40, 50], key="cPerfil")
                wall = c5.number_input("Espessura do tubo (mm)", 0.8, 3.0, step=0.1, key="cWall", help="Parede do metalon — entra no cálculo de massa e no sólido 3D.")
                top_th = c6.number_input("Espessura do tampo (mm)", 6.0, 60.0, step=1.0, key="cTop")
                c7, c8 = st.columns(2)
                espelhado = c7.checkbox("Pés espelhados", value=False, key="cEsp",
                                        help="Marque para os dois pés inclinarem em sentidos opostos.")
                com_rail = c8.checkbox("Travessa superior", value=True, key="cRail",
                                       help="Barra ligando os dois pés por baixo do tampo.")
                raio = st.number_input("Raio do canto (mm)", 0.0, 15.0, 0.0, 0.5, key="cRaio",
                                       help="0 = canto vivo. Entra na massa e fica registrado no nome/desenho.")
                if st.button("GERAR MESA", type="primary", use_container_width=True, key="cGen"):
                    try:
                        r = mc.mesa_pes_c(W, Dp, H, perfil=float(perfil), wall=wall, top_th=top_th, raio=raio,
                                          espelhado=espelhado, com_rail=com_rail)
                        mostra_resultado(r)
                        e = r.extra
                        st.caption(f"Pé: aba {e['flag']:g} mm · base {e['foot']:g} mm · "
                                   f"diagonal {e['diag']:.0f} mm (~{e['ang']:.0f}° com o piso).")
                        st.info("O .zip inclui o conjunto (IGES/STEP) + o desenho com a vista do pé, "
                                "planta e lista de corte. O tampo entra como peça à parte (madeira/MDF ou chapa).")
                    except Exception as e:
                        st.error("Erro ao gerar: " + str(e))

        elif base.startswith("Pé de quadro"):
            PRESETS_Q = {
                "Escrivaninha — 1200×600×750": (1200.0, 600.0, 750.0, 30),
                "Mesa de jantar — 1600×800×750": (1600.0, 800.0, 750.0, 40),
                "Aparador — 1200×400×900": (1200.0, 400.0, 900.0, 30),
                "Bancada alta — 1400×600×1050": (1400.0, 600.0, 1050.0, 40),
                "Personalizado": None,
            }
            for _k, _v in {"qW": 1200.0, "qDp": 600.0, "qH": 750.0, "qPerfil": 30,
                           "qWall": 1.5, "qTop": 25.0}.items():
                st.session_state.setdefault(_k, _v)
            with st.container(border=True):
                modelo = st.selectbox("Modelo de mesa", list(PRESETS_Q.keys()), key="mesa_modelo_q")
                pre = PRESETS_Q[modelo]
                if pre and st.session_state.get("_mesa_last_q") != modelo:
                    (st.session_state["qW"], st.session_state["qDp"],
                     st.session_state["qH"], st.session_state["qPerfil"]) = (
                        float(pre[0]), float(pre[1]), float(pre[2]), pre[3])
                st.session_state["_mesa_last_q"] = modelo
                st.divider()
                c1, c2, c3 = st.columns(3)
                W = c1.number_input("Largura (mm)", 400.0, 4000.0, step=10.0, key="qW")
                Dp = c2.number_input("Profundidade (mm)", 250.0, 1200.0, step=10.0, key="qDp")
                H = c3.number_input("Altura (mm)", 350.0, 1200.0, step=10.0, key="qH")
                c4, c5, c6 = st.columns(3)
                perfil = c4.selectbox("Perfil do tubo (mm)", [20, 25, 30, 40, 50], key="qPerfil")
                wall = c5.number_input("Espessura do tubo (mm)", 0.8, 3.0, step=0.1, key="qWall", help="Parede do metalon — entra no cálculo de massa e no sólido 3D.")
                top_th = c6.number_input("Espessura do tampo (mm)", 6.0, 60.0, step=1.0, key="qTop")
                c7, c8, c9 = st.columns(3)
                com_rail = c7.checkbox("Travessa superior", value=True, key="qRail",
                                       help="Barra ligando os dois quadros por baixo do tampo.")
                recuo = c8.number_input("Recuo frente/fundo (mm)", 0.0, 200.0, 0.0, 5.0, key="qRec",
                                        help="0 = quadro alinhado com o tampo. Valores maiores "
                                             "recuam o pé em relação à borda.")
                niv = c9.checkbox("Niveladores", value=False, key="qNiv",
                                  help="Pés reguláveis sob o quadro, como na referência.")
                avulso = st.checkbox("Gerar quadro AVULSO (1 unidade, sem tampo)", value=False,
                                     key="qAvulso",
                                     help="Gera um único quadro para venda/uso avulso. "
                                          "Largura e travessa são ignoradas.")
                raio = st.number_input("Raio do canto (mm)", 0.0, 15.0, 0.0, 0.5, key="qRaio",
                                       help="0 = canto vivo. Entra na massa e fica registrado no nome/desenho.")
                if st.button("GERAR MESA", type="primary", use_container_width=True, key="qGen"):
                    try:
                        r = mc.mesa_pe_quadro(W, Dp, H, perfil=float(perfil), wall=wall, raio=raio,
                                              top_th=top_th, com_rail=com_rail, recuo_frente=recuo,
                                              niveladores=niv, par=not avulso)
                        mostra_resultado(r)
                        e = r.extra
                        st.caption(f"Quadro: {e['F']:g} × {e['Hq']:g} mm, soldado em meia "
                                   f"esquadria 45° nos 4 cantos."
                                   + (f" Niveladores h {e['niv_h']:g} mm." if niv else ""))
                        st.info("O .zip inclui o conjunto (IGES/STEP) + o desenho com a vista do "
                                "quadro, planta e lista de corte. Tampo à parte.")
                    except Exception as e:
                        st.error("Erro ao gerar: " + str(e))

        elif base.startswith("Estrutura completa"):
            PRESETS_E = {
                "Mesa de jantar — 1500×800×740": (1500.0, 800.0, 740.0, 40),
                "Mesa de centro — 1000×600×420": (1000.0, 600.0, 420.0, 30),
                "Escrivaninha — 1200×600×740": (1200.0, 600.0, 740.0, 30),
                "Aparador — 1300×400×850": (1300.0, 400.0, 850.0, 30),
                "Personalizado": None,
            }
            for _k, _v in {"eL": 1500.0, "eDp": 800.0, "eH": 740.0, "ePerfil": 40,
                           "eWall": 1.5}.items():
                st.session_state.setdefault(_k, _v)
            with st.container(border=True):
                modelo = st.selectbox("Modelo de estrutura", list(PRESETS_E.keys()), key="mesa_modelo_e")
                pre = PRESETS_E[modelo]
                if pre and st.session_state.get("_mesa_last_e") != modelo:
                    (st.session_state["eL"], st.session_state["eDp"],
                     st.session_state["eH"], st.session_state["ePerfil"]) = (
                        float(pre[0]), float(pre[1]), float(pre[2]), pre[3])
                st.session_state["_mesa_last_e"] = modelo
                st.divider()
                c1, c2, c3 = st.columns(3)
                L = c1.number_input("Comprimento (mm)", 400.0, 4000.0, step=10.0, key="eL")
                Dp = c2.number_input("Profundidade (mm)", 250.0, 1500.0, step=10.0, key="eDp")
                H = c3.number_input("Altura da estrutura (mm)", 200.0, 1200.0, step=10.0, key="eH",
                                    help="O tampo apoia por cima; altura final = estrutura + tampo.")
                c4, c5, c6 = st.columns(3)
                perfil = c4.selectbox("Perfil do tubo (mm)", [20, 25, 30, 40, 50], key="ePerfil")
                wall = c5.number_input("Espessura do tubo (mm)", 0.8, 3.0, step=0.1, key="eWall", help="Parede do metalon — entra no cálculo de massa e no sólido 3D.")
                trav = c6.checkbox("Travessa central", value=True, key="eTrav",
                                   help="Barra longitudinal no meio da moldura, como na referência.")
                raio = st.number_input("Raio do canto (mm)", 0.0, 15.0, 0.0, 0.5, key="eRaio",
                                       help="0 = canto vivo. Entra na massa e fica registrado no nome/desenho.")
                if st.button("GERAR ESTRUTURA", type="primary", use_container_width=True, key="eGen"):
                    try:
                        r = mc.mesa_estrutura_quadro(L, Dp, H, perfil=float(perfil), wall=wall, raio=raio,
                                                     travessa_central=trav)
                        mostra_resultado(r)
                        st.caption("Moldura em meia esquadria 45°; montantes e travessas "
                                   "inferiores em corte reto 90°.")
                        st.info("O .zip inclui a estrutura (IGES/STEP) + desenho com vistas "
                                "frontal, lateral, planta e lista de corte. Tampo apoiado, à parte.")
                    except Exception as e:
                        st.error("Erro ao gerar: " + str(e))

        elif base.startswith("Pé trapézio"):
            PRESETS_T = {
                "Mesa de jantar — 1600×800×750": (1600.0, 800.0, 750.0, 40),
                "Escrivaninha — 1200×700×750": (1200.0, 700.0, 750.0, 30),
                "Bancada alta — 1400×600×1050": (1400.0, 600.0, 1050.0, 40),
                "Personalizado": None,
            }
            for _k, _v in {"tW": 1600.0, "tDp": 800.0, "tH": 750.0, "tPerfil": 40,
                           "tWall": 1.5, "tTop": 25.0, "tBase": 0.0}.items():
                st.session_state.setdefault(_k, _v)
            with st.container(border=True):
                modelo = st.selectbox("Modelo de mesa", list(PRESETS_T.keys()), key="mesa_modelo_t")
                pre = PRESETS_T[modelo]
                if pre and st.session_state.get("_mesa_last_t") != modelo:
                    (st.session_state["tW"], st.session_state["tDp"],
                     st.session_state["tH"], st.session_state["tPerfil"]) = (
                        float(pre[0]), float(pre[1]), float(pre[2]), pre[3])
                st.session_state["_mesa_last_t"] = modelo
                st.divider()
                c1, c2, c3 = st.columns(3)
                W = c1.number_input("Largura (mm)", 400.0, 4000.0, step=10.0, key="tW")
                Dp = c2.number_input("Profundidade (mm)", 250.0, 1200.0, step=10.0, key="tDp")
                H = c3.number_input("Altura (mm)", 350.0, 1200.0, step=10.0, key="tH")
                c4, c5, c6 = st.columns(3)
                perfil = c4.selectbox("Perfil do tubo (mm)", [20, 25, 30, 40, 50], key="tPerfil")
                wall = c5.number_input("Espessura do tubo (mm)", 0.8, 3.0, step=0.1, key="tWall", help="Parede do metalon — entra no cálculo de massa e no sólido 3D.")
                top_th = c6.number_input("Espessura do tampo (mm)", 6.0, 60.0, step=1.0, key="tTop")
                c7, c8 = st.columns(2)
                base_pe = c7.number_input("Base no chão (mm)", 0.0, 1100.0, step=10.0, key="tBase",
                                          help="0 = automático (62% da profundidade).")
                com_rail = c8.checkbox("Travessa superior", value=False, key="tRail")
                raio = st.number_input("Raio do canto (mm)", 0.0, 15.0, 0.0, 0.5, key="tRaio",
                                       help="0 = canto vivo. Entra na massa e fica registrado no nome/desenho.")
                if st.button("GERAR MESA", type="primary", use_container_width=True, key="tGen"):
                    try:
                        r = mc.mesa_pe_trapezio(W, Dp, H, base=(base_pe or None), raio=raio,
                                                perfil=float(perfil), wall=wall,
                                                top_th=top_th, com_rail=com_rail)
                        mostra_resultado(r)
                        e = r.extra
                        st.caption(f"Pé: topo {Dp:g} mm · base {e['Db']:g} mm · montante "
                                   f"{e['diag']:.0f} mm (~{e['ang']:.0f}° com o piso).")
                        st.info("O .zip inclui o conjunto (IGES/STEP) + desenho com a vista do "
                                "pé, planta e lista de corte. Tampo à parte.")
                    except Exception as e:
                        st.error("Erro ao gerar: " + str(e))

        elif base.startswith("Base em X"):
            PRESETS_X = {
                "Mesa de jantar redonda — Ø1100 (base 750×720)": (750.0, 720.0, 40, 1100.0),
                "Mesa bistrô — Ø800 (base 560×720)": (560.0, 720.0, 30, 800.0),
                "Mesa lateral — Ø500 (base 380×500)": (380.0, 500.0, 25, 500.0),
                "Personalizado": None,
            }
            for _k, _v in {"xWf": 750.0, "xH": 720.0, "xPerfil": 40, "xWall": 1.5,
                           "xTampo": 1100.0}.items():
                st.session_state.setdefault(_k, _v)
            with st.container(border=True):
                modelo = st.selectbox("Modelo de base", list(PRESETS_X.keys()), key="mesa_modelo_x")
                pre = PRESETS_X[modelo]
                if pre and st.session_state.get("_mesa_last_x") != modelo:
                    (st.session_state["xWf"], st.session_state["xH"],
                     st.session_state["xPerfil"], st.session_state["xTampo"]) = (
                        float(pre[0]), float(pre[1]), pre[2], float(pre[3]))
                st.session_state["_mesa_last_x"] = modelo
                st.divider()
                c1, c2, c3 = st.columns(3)
                Wf = c1.number_input("Envergadura da base (mm)", 250.0, 1500.0, step=10.0, key="xWf",
                                     help="Largura de cada quadro = pegada da base no chão.")
                H = c2.number_input("Altura da base (mm)", 300.0, 1200.0, step=10.0, key="xH",
                                    help="O tampo assenta por cima; altura final = base + tampo.")
                tampo = c3.number_input("Tampo Ø ou lado (mm)", 0.0, 2000.0, step=10.0, key="xTampo",
                                        help="Somente informativo (entra na lista de corte).")
                c4, c5 = st.columns(2)
                perfil = c4.selectbox("Perfil do tubo (mm)", [25, 30, 40, 50], key="xPerfil")
                wall = c5.number_input("Espessura do tubo (mm)", 0.8, 3.0, step=0.1, key="xWall", help="Parede do metalon — entra no cálculo de massa e no sólido 3D.")
                raio = st.number_input("Raio do canto (mm)", 0.0, 15.0, 0.0, 0.5, key="xRaio",
                                       help="0 = canto vivo. Entra na massa e fica registrado no nome/desenho.")
                if st.button("GERAR BASE", type="primary", use_container_width=True, key="xGen"):
                    try:
                        r = mc.mesa_base_x(Wf, H, perfil=float(perfil), wall=wall, tampo_D=tampo, raio=raio)
                        mostra_resultado(r)
                        st.caption("Os dois quadros são idênticos: cruzam a 90° com encaixe "
                                   "meia-madeira no centro das travessas superior e inferior.")
                        st.info("O .zip inclui a base (IGES/STEP) + desenho com elevação do "
                                "quadro, planta em X e lista de corte. Tampo à parte.")
                    except Exception as e:
                        st.error("Erro ao gerar: " + str(e))

        else:  # Pé cubo
            PRESETS_CB = {
                "Mesa lateral — 400×400×450": (400.0, 450.0, 25),
                "Mesa de centro — 600×600×400": (600.0, 400.0, 30),
                "Banqueta — 350×350×450": (350.0, 450.0, 25),
                "Personalizado": None,
            }
            for _k, _v in {"cbA": 400.0, "cbH": 450.0, "cbPerfil": 25, "cbWall": 1.5,
                           "cbTop": 20.0}.items():
                st.session_state.setdefault(_k, _v)
            with st.container(border=True):
                modelo = st.selectbox("Modelo de mesa", list(PRESETS_CB.keys()), key="mesa_modelo_cb")
                pre = PRESETS_CB[modelo]
                if pre and st.session_state.get("_mesa_last_cb") != modelo:
                    (st.session_state["cbA"], st.session_state["cbH"],
                     st.session_state["cbPerfil"]) = (float(pre[0]), float(pre[1]), pre[2])
                st.session_state["_mesa_last_cb"] = modelo
                st.divider()
                c1, c2, c3 = st.columns(3)
                A = c1.number_input("Lado do tampo (mm)", 250.0, 1200.0, step=10.0, key="cbA")
                H = c2.number_input("Altura montada (mm)", 300.0, 1100.0, step=10.0, key="cbH")
                top_th = c3.number_input("Espessura do tampo (mm)", 6.0, 60.0, step=1.0, key="cbTop")
                c4, c5, c6 = st.columns(3)
                perfil = c4.selectbox("Perfil do tubo (mm)", [20, 25, 30, 40], key="cbPerfil")
                wall = c5.number_input("Espessura do tubo (mm)", 0.8, 3.0, step=0.1, key="cbWall", help="Parede do metalon — entra no cálculo de massa e no sólido 3D.")
                moldura = c6.checkbox("Moldura superior", value=True, key="cbMold",
                                      help="Quadro-borda contornando o tampo, como na referência.")
                raio = st.number_input("Raio do canto (mm)", 0.0, 15.0, 0.0, 0.5, key="cbRaio",
                                       help="0 = canto vivo. Entra na massa e fica registrado no nome/desenho.")
                if st.button("GERAR MESA", type="primary", use_container_width=True, key="cbGen"):
                    try:
                        r = mc.mesa_cubo(A, H, perfil=float(perfil), wall=wall, raio=raio,
                                         top_th=top_th, moldura=moldura)
                        mostra_resultado(r)
                        e = r.extra
                        st.caption(f"Quadros diagonais: {e['diag']:.0f} × {e['Hf']:g} mm, "
                                   f"meia-madeira no cruzamento central.")
                        st.info("O .zip inclui o conjunto (IGES/STEP) + desenho com elevação do "
                                "quadro diagonal, planta e lista de corte. Tampo à parte.")
                    except Exception as e:
                        st.error("Erro ao gerar: " + str(e))

    # ------------------------------------------------- iTubeCAM
    elif secao == "itubecam":
        st.caption("Prepara peças para o **iTubeCAM / SinoCAM 3D** (nesting da laser de tubo): "
                   "sólidos ocos com as esquadrias já cortadas. Conforme o manual, o software "
                   "importa IGS, STEP, SAT, DXF/DWG e NC1, extrai as linhas de corte do próprio "
                   "sólido e detecta a direção do eixo automaticamente.")
        tab1, tab2, tab3 = st.tabs(["Peça individual", "Lote de peças (.zip de IGS)",
                                    "Seção personalizada (DXF)"])

        with tab1:
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                tw = c1.number_input("Tubo — largura (mm)", 10.0, 300.0, 40.0, 1.0, key="itW")
                th = c2.number_input("Tubo — altura (mm)", 10.0, 300.0, 40.0, 1.0, key="itH")
                esp = c3.number_input("Espessura do tubo (mm)", 0.5, 8.0, 1.5, 0.1, key="itEsp")
                c4, c5, c6 = st.columns(3)
                L = c4.number_input("Comprimento (mm) — aresta externa", 30.0, 12000.0,
                                    800.0, 5.0, key="itL")
                ce = c5.number_input("Corte esquerdo (graus)", 0.0, 75.0, 45.0, 1.0, key="itCe",
                                     help="0 = corte reto 90°; 45 = meia esquadria.")
                cd = c6.number_input("Corte direito (graus)", 0.0, 75.0, 45.0, 1.0, key="itCd")
                plano = st.radio("Esquadria atravessa a...", ["largura", "altura"],
                                 horizontal=True, key="itPlano",
                                 help="Largura = esquadria vista em planta; altura = vista de frente.")
                nome = st.text_input("Nome da peça (opcional)", key="itNome",
                                     placeholder="ex.: Montante quadro escrivaninha")
            if st.button("GERAR PEÇA", type="primary", use_container_width=True, key="itGen"):
                try:
                    r = itubecam.tubo_peca(tw, th, esp, L, corte_esq=ce, corte_dir=cd,
                                           plano=plano, nome=nome or None)
                    mostra_resultado(r)
                    e = r.extra
                    st.caption(f"Aresta curta {e['L_curta']:g} mm · massa {r.mass:.3f} kg. "
                               "Use o botão 'Apenas IGS' para baixar só o arquivo que o "
                               "iTubeCAM importa.")
                except Exception as e:
                    st.error("Erro ao gerar: " + str(e))

        with tab2:
            st.caption("Uma linha por peça — selecione todos os IGS de uma vez na importação "
                       "(CTRL+clique). A quantidade é informada DENTRO do software, nas "
                       "propriedades da peça; o nome do arquivo e a lista.csv servem de conferência.")
            import pandas as _pd
            _df0 = _pd.DataFrame([
                {"Nome": "Montante", "Largura": 40.0, "Altura": 40.0, "Esp": 1.5,
                 "Comp": 700.0, "Corte esq °": 45.0, "Corte dir °": 45.0,
                 "Plano": "largura", "Qtd": 4},
                {"Nome": "Travessa", "Largura": 40.0, "Altura": 40.0, "Esp": 1.5,
                 "Comp": 520.0, "Corte esq °": 45.0, "Corte dir °": 45.0,
                 "Plano": "largura", "Qtd": 4},
            ])
            df = st.data_editor(
                _df0, num_rows="dynamic", use_container_width=True, key="itLote",
                column_config={
                    "Plano": st.column_config.SelectboxColumn(options=["largura", "altura"]),
                    "Qtd": st.column_config.NumberColumn(min_value=1, step=1),
                })
            inc_step = st.checkbox("Incluir também STEP de cada peça", value=False, key="itLoteStep")
            if st.button("GERAR LOTE", type="primary", use_container_width=True, key="itLoteGen"):
                try:
                    pecas = [dict(nome=str(row["Nome"]), w=float(row["Largura"]),
                                  h=float(row["Altura"]), esp=float(row["Esp"]),
                                  L=float(row["Comp"]), ce=float(row["Corte esq °"]),
                                  cd=float(row["Corte dir °"]), plano=str(row["Plano"]),
                                  qtd=int(row["Qtd"]))
                             for _, row in df.iterrows() if str(row.get("Nome", "")).strip()]
                    if not pecas:
                        st.warning("Nenhuma peça válida na tabela.")
                    else:
                        data_zip, avisos = itubecam.lote_igs(pecas, incluir_step=inc_step)
                        for a in avisos:
                            st.warning(a)
                        st.success(f"Lote gerado: {len(pecas) - len(avisos)} peça(s).")
                        st.download_button("⬇  Baixar lote iTubeCAM (.zip)", data=data_zip,
                                           file_name="lote_iTubeCAM.zip", mime="application/zip",
                                           use_container_width=True)
                except Exception as e:
                    st.error("Erro ao gerar lote: " + str(e))

        with tab3:
            st.caption("Contorno fechado (externo + interno) da seção — o manual confirma: "
                       "'custom pipe' aceita apenas seção fechada, em DWG ou DXF.")
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                sw = c1.number_input("Largura (mm)", 10.0, 300.0, 40.0, 1.0, key="itSw")
                sh = c2.number_input("Altura (mm)", 10.0, 300.0, 40.0, 1.0, key="itSh")
                se = c3.number_input("Espessura (mm)", 0.5, 8.0, 1.5, 0.1, key="itSe")
                sr = c4.number_input("Raio do canto (mm)", 0.0, 20.0, 0.0, 0.5, key="itSr")
            try:
                dxf = itubecam.secao_dxf(sw, sh, se, raio=sr)
                st.download_button("⬇  Baixar seção (.dxf)", data=dxf,
                                   file_name=f"secao_{sw:g}x{sh:g}x{se:g}.dxf",
                                   mime="application/dxf", use_container_width=True)
            except Exception as e:
                st.error(str(e))


    # ------------------------------------------------- Puxadores
    elif secao == "puxador":
        st.caption("Puxador tradicional em tubo inox: seção redonda, quadrada ou "
                   "retangular (com raio de canto), dois furos de fixação sempre "
                   "centrados no tubo.")
        with st.container(border=True):
            sec_px = st.radio("Seção do tubo", ["Redondo", "Quadrado", "Retangular"],
                              horizontal=True, key="pxSec")
            c1, c2, c3 = st.columns(3)
            if sec_px == "Redondo":
                med = c1.number_input("Ø do tubo (mm)", 9.0, 76.0, 25.4, 0.1, key="pxMed",
                                      help="Ex.: Ø25,4 (1\"), Ø31,75 (1.1/4\").")
                medH = med
                c2.empty(); c3.empty()
            elif sec_px == "Quadrado":
                med = c1.number_input("Lado do tubo (mm)", 10.0, 60.0, 20.0, 1.0, key="pxMedQ")
                medH = med
                rc = c2.number_input("Raio do canto (mm)", 0.0, 8.0, 0.0, 0.5, key="pxRaioQ",
                                     help="0 = canto vivo. Entra na massa e no sólido 3D.")
            else:
                med = c1.number_input("Largura (mm)", 15.0, 80.0, 40.0, 1.0, key="pxMedW",
                                      help="Face voltada à porta (onde vão os furos).")
                medH = c2.number_input("Profundidade (mm)", 8.0, 50.0, 20.0, 1.0, key="pxMedH")
                rc = c3.number_input("Raio do canto (mm)", 0.0, 8.0, 0.0, 0.5, key="pxRaioR",
                                     help="0 = canto vivo. Entra na massa e no sólido 3D.")
            if sec_px == "Redondo":
                rc = 0.0
            c4, c5, c6 = st.columns(3)
            esp = c4.number_input("Espessura do tubo (mm)", 0.6, 3.0, 1.2, 0.1, key="pxEsp")
            L = c5.number_input("Comprimento do tubo (mm)", 60.0, 2500.0, 300.0, 5.0, key="pxL")
            EF = c6.number_input("Entre furos (mm)", 20.0, 2400.0, 192.0, 1.0, key="pxEF",
                                 help="Distância entre os eixos dos 2 furos, sempre "
                                      "CENTRADA no tubo. Padrões: 96, 128, 160, 192, "
                                      "224, 288, 320…")
            dF = st.number_input("Ø dos furos (mm)", 2.0, 12.0, 5.0, 0.5, key="pxD")
        if st.button("GERAR PUXADOR", type="primary", use_container_width=True, key="pxGen"):
            try:
                r = puxador.puxador_tradicional(sec_px.lower(), med, esp, L, EF,
                                                d_furo=dF, medida_h=medH, raio=rc)
                mostra_resultado(r)
                st.caption(f"Furos a {r.extra['borda']:g} mm de cada ponta "
                           f"(entre furos {EF:g} mm centrado).")
            except Exception as e:
                st.error("Erro ao gerar: " + str(e))


    # ------------------------------------------------- Configurações
    elif secao == "config":
        st.caption("Identidade dos PDFs (logo e empresa) e aparência do sistema — "
                   "tudo fica salvo e vale para todas as seções.")

        with st.container(border=True):
            st.markdown("**🏷️ Identidade nos PDFs (carimbo, folhas e etiquetas)**")
            from metallo_cad import config as mcfg
            c1, c2 = st.columns([1, 2])
            with c1:
                try:
                    st.image(mcfg.logo_path(), caption="Logo em uso", width=180)
                except Exception:
                    st.info("Sem logo carregado.")
            with c2:
                up = st.file_uploader("Trocar logo (PNG/JPG — fundo escuro fica melhor no carimbo)",
                                      type=["png", "jpg", "jpeg"], key="cfgLogo")
                emp = st.text_input("Nome da empresa", value=mcfg.empresa(), key="cfgEmp")
                lin = st.text_input("Linha / subtítulo (endereço, slogan…)",
                                    value=mcfg.linha(), key="cfgLin")
            b1, b2 = st.columns(2)
            if b1.button("💾 Salvar identidade", type="primary",
                         use_container_width=True, key="cfgSave"):
                try:
                    d = mcfg._data_dir()
                    if up is not None:
                        from PIL import Image
                        import io as _io
                        img = Image.open(_io.BytesIO(up.getvalue())).convert("RGB")
                        for _ext in ("png", "jpg", "jpeg"):
                            _p = os.path.join(d, f"logo_custom.{_ext}")
                            if os.path.exists(_p):
                                os.remove(_p)
                        img.save(os.path.join(d, "logo_custom.png"))
                    open(os.path.join(d, "empresa.txt"), "w", encoding="utf-8").write(emp.strip())
                    open(os.path.join(d, "linha.txt"), "w", encoding="utf-8").write(lin.strip())
                    st.success("Identidade salva — os próximos PDFs já saem com ela.")
                    st.rerun()
                except Exception as e:
                    st.error("Erro ao salvar: " + str(e))
            if b2.button("↩️ Restaurar padrão METALLO", use_container_width=True, key="cfgReset"):
                try:
                    d = mcfg._data_dir()
                    for f in ("logo_custom.png", "logo_custom.jpg", "logo_custom.jpeg",
                              "empresa.txt", "linha.txt"):
                        p = os.path.join(d, f)
                        if os.path.exists(p):
                            os.remove(p)
                    st.success("Padrão METALLO restaurado.")
                    st.rerun()
                except Exception as e:
                    st.error("Erro: " + str(e))

        with st.container(border=True):
            st.markdown("**🖥️ Aparência do sistema** (além do tema de cores no topo)")
            ap = dict(st.session_state["ui_aparencia"])
            c1, c2, c3 = st.columns(3)
            ap["modo"] = c1.selectbox("Modo", ["Escuro", "Claro"],
                                      index=["Escuro", "Claro"].index(ap.get("modo", "Escuro")),
                                      key="cfgModo")
            ap["largura"] = c2.selectbox("Largura do conteúdo", ["Normal", "Larga", "Total"],
                                         index=["Normal", "Larga", "Total"].index(ap.get("largura", "Normal")),
                                         key="cfgLarg")
            ap["densidade"] = c3.selectbox("Densidade", ["Confortável", "Compacto"],
                                           index=["Confortável", "Compacto"].index(ap.get("densidade", "Confortável")),
                                           key="cfgDens")
            c4, c5 = st.columns(2)
            ap["grade"] = c4.checkbox("Grade de fundo", value=bool(ap.get("grade", True)), key="cfgGrade")
            ap["animacoes"] = c5.checkbox("Animações", value=bool(ap.get("animacoes", True)), key="cfgAnim")
            if ap != st.session_state["ui_aparencia"]:
                st.session_state["ui_aparencia"] = ap
                _aparencia_salva(ap)
                st.rerun()
            st.caption("As opções valem na hora e ficam salvas para as próximas sessões.")

    # ------------------------------------------------- Tempo de corte (laser)
    elif secao == "corte":
        st.caption("Estimativa de tempo de corte a laser de fibra **3000 W**, a partir da "
                   "tabela de parâmetros. Importe um DXF, ou calcule manualmente, ou consulte a tabela.")
        tab_dxf, tab_manual, tab_tabela, tab_orc = st.tabs(
            ["📥 Importar DXF", "✍️ Cálculo manual", "📋 Tabela 3000 W", "💰 Orçamento (lote)"])

        # ---- helpers comuns
        def _custo_inputs(prefixo):
            cc1, cc2 = st.columns(2)
            ef = cc1.slider("Eficiência da máquina (%)", 50, 100, 85, 1, key=f"{prefixo}_ef",
                            help="Desconta posicionamento/aceleração. 85% = corta ~85% da "
                                 "velocidade de catálogo na média.") / 100.0
            rate = cc2.number_input("Custo de máquina (R$/min)", 0.0, 100.0, 0.0, 0.5,
                                    key=f"{prefixo}_rate",
                                    help="Opcional: para estimar o custo do corte. 0 = não calcular.")
            return ef, rate

        def _mostra_estimativa(material, esp, comp, pierces, ef, rate, area_mm2=None, qtd=1):
            est = laser.estimar_tempo(material, esp, comp, pierces, eficiencia=ef)
            p = est["params"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Comprimento de corte", f"{comp/1000:.2f} m")
            c2.metric("Perfurações", f"{pierces}")
            c3.metric("Tempo / peça", laser.fmt_tempo(est["t_total_min"]))
            c4, c5, c6 = st.columns(3)
            c4.metric("Mín–máx (faixa)",
                      f"{laser.fmt_tempo(est['t_total_min_rapido'])}–{laser.fmt_tempo(est['t_total_min_lento'])}")
            c5.metric("Velocidade usada", f"{est['vel_med']:g} m/min")
            if area_mm2:
                peso = laser.peso_chapa(area_mm2, esp, material)
                c6.metric("Peso / peça", f"{peso:.3f} kg")
            if qtd > 1:
                st.success(f"Lote de **{qtd}** peças → tempo total ~ "
                           f"**{laser.fmt_tempo(est['t_total_min'] * qtd)}**"
                           + (f"  ·  peso ~ {laser.peso_chapa(area_mm2, esp, material)*qtd:.2f} kg"
                              if area_mm2 else ""))
            if rate and rate > 0:
                custo = est["t_total_min"] * rate * qtd
                st.info(f"Custo de corte estimado: **R$ {custo:,.2f}** "
                        f"({laser.fmt_tempo(est['t_total_min']*qtd)} × R$ {rate:g}/min)"
                        .replace(",", "X").replace(".", ",").replace("X", "."))
            ap = " · ⚠️ espessura aproximada (tabela: %g mm)" % p["espessura_tabela"] if p.get("aproximada") else ""
            st.caption(f"Parâmetros: gás **{p['gas']}** · pressão {p['pressao']:g} bar · "
                       f"bico {p['bico']} · foco {p['foco']:+g} mm · altura {p['altura']:g} mm{ap}")

        # ===== aba importar DXF
        with tab_dxf:
            up = st.file_uploader("Arraste o DXF da peça (corte 2D plano)", type=["dxf"], key="dxf_up")
            cm1, cm2 = st.columns(2)
            material = cm1.selectbox("Material", laser.MATERIAIS, key="dxf_mat")
            esp = cm2.selectbox("Espessura (mm)", laser.espessuras_disponiveis(material),
                                key="dxf_esp")
            cq1, _ = st.columns(2)
            qtd = cq1.number_input("Quantidade", 1, 9999, 1, 1, key="dxf_qtd")
            ef, rate = _custo_inputs("dxf")
            if up is not None:
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tf:
                        tf.write(up.getvalue()); tmp = tf.name
                    comp, pierces, det = laser.comprimento_corte_dxf(tmp)
                    if comp <= 0:
                        st.warning("Não encontrei entidades de corte no DXF. "
                                   "Verifique se as linhas estão no modelspace.")
                    else:
                        st.success(f"DXF lido: {det['n_entidades']} entidade(s) de corte.")
                        _mostra_estimativa(material, float(esp), comp, pierces, ef, rate,
                                           area_mm2=det.get("area_mm2") or None, qtd=int(qtd))
                except Exception as e:
                    st.error("Erro ao ler o DXF: " + str(e))
            else:
                st.info("Envie um arquivo .dxf para calcular o tempo de corte e o peso.")

        # ===== aba cálculo manual
        with tab_manual:
            cm1, cm2 = st.columns(2)
            material = cm1.selectbox("Material", laser.MATERIAIS, key="man_mat")
            esp = cm2.selectbox("Espessura (mm)", laser.espessuras_disponiveis(material), key="man_esp")
            cc1, cc2, cc3 = st.columns(3)
            comp_m = cc1.number_input("Comprimento de corte (m)", 0.0, 10000.0, 1.0, 0.1, key="man_comp")
            pierces = cc2.number_input("Nº de perfurações", 0, 100000, 1, 1, key="man_pier")
            qtd = cc3.number_input("Quantidade", 1, 99999, 1, 1, key="man_qtd")
            ef, rate = _custo_inputs("man")
            if comp_m > 0:
                _mostra_estimativa(material, float(esp), comp_m * 1000.0, int(pierces),
                                   ef, rate, qtd=int(qtd))
            else:
                st.info("Informe o comprimento de corte para estimar o tempo.")

        # ===== aba tabela
        with tab_tabela:
            material = st.selectbox("Material", laser.MATERIAIS, key="tab_mat")
            linhas = laser.TABELA_3000W[material]
            st.table({
                "Esp. (mm)": [f'{l[0]:g}' for l in linhas],
                "Veloc. (m/min)": [f'{l[1]:g}–{l[2]:g}' if l[1] != l[2] else f'{l[1]:g}' for l in linhas],
                "Potência (W)": [l[3] for l in linhas],
                "Gás": [l[4] for l in linhas],
                "Pressão (bar)": [f'{l[5]:g}' for l in linhas],
                "Bico": [l[6] for l in linhas],
                "Foco (mm)": [f'{l[7]:+g}' for l in linhas],
                "Altura (mm)": [f'{l[8]:g}' for l in linhas],
            })
            st.caption("Parâmetros de referência para laser de fibra 3000 W. "
                       "Aço-carbono fino (1–2 mm) tem dois regimes: N2/Ar (rápido) e O2.")

        # ===== aba orçamento (lote de DXF)
        with tab_orc:
            st.caption("Suba **vários DXF** (sem limite), ajuste os preços e gere um **orçamento em "
                       "PDF** para o cliente. O preço pode ser sugerido pelo tempo de corte + material.")
            ups = st.file_uploader("DXFs das peças (pode selecionar vários)", type=["dxf"],
                                   accept_multiple_files=True, key="orc_ups")
            og1, og2, og3 = st.columns(3)
            mat_def = og1.selectbox("Material padrão", laser.MATERIAIS, key="orc_mat")
            esp_def = og2.selectbox("Espessura padrão (mm)", laser.espessuras_disponiveis(mat_def), key="orc_esp")
            rate = og3.number_input("Custo máquina (R$/min)", 0.0, 100.0, 0.0, 0.5, key="orc_rate")
            op1, op2 = st.columns(2)
            rkg = op1.number_input("Preço do material (R$/kg)", 0.0, 1000.0, 0.0, 0.5, key="orc_rkg")
            margem = op2.number_input("Margem / lucro (%)", 0.0, 500.0, 0.0, 5.0, key="orc_marg")
            if ups:
                rows = []
                for up in ups:
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tf:
                            tf.write(up.getvalue()); tmp = tf.name
                        comp, pierces, det = laser.comprimento_corte_dxf(tmp)
                        est = laser.estimar_tempo(mat_def, float(esp_def), comp, pierces, eficiencia=0.85)
                        tmin = est["t_total_min"]
                        peso = (laser.peso_chapa(det.get("area_mm2") or 0, float(esp_def), mat_def)
                                if det.get("area_mm2") else 0.0)
                        custo = tmin * rate + peso * rkg
                        unit = round(custo * (1 + margem / 100.0), 2)
                        rows.append({"Descrição": up.name.rsplit(".", 1)[0], "Material": mat_def,
                                     "Esp": float(esp_def), "Qtd": 1, "Vlr unit": unit,
                                     "_peso": peso, "_tmin": tmin})
                    except Exception as e:
                        st.warning(f"{up.name}: {e}")
                if rows:
                    st.caption(f"{len(rows)} arquivo(s) lido(s). Ajuste descrição, quantidade e preço:")
                    base = pd.DataFrame([{k: r[k] for k in ["Descrição", "Material", "Esp", "Qtd", "Vlr unit"]}
                                         for r in rows])
                    ed = st.data_editor(
                        base, num_rows="dynamic", use_container_width=True, key="orc_editor",
                        column_config={
                            "Esp": st.column_config.NumberColumn("Esp (mm)", format="%.1f", min_value=0.0, step=0.1),
                            "Qtd": st.column_config.NumberColumn(min_value=1, step=1),
                            "Vlr unit": st.column_config.NumberColumn("Vlr unit (R$)", format="%.2f", min_value=0.0),
                        })
                    itens = []
                    for idx, r in ed.iterrows():
                        q = int(r["Qtd"] or 1); u = float(r["Vlr unit"] or 0)
                        peso = rows[idx]["_peso"] if idx < len(rows) else 0.0
                        itens.append({"descricao": r["Descrição"], "material": r["Material"],
                                      "esp": float(r["Esp"] or 0), "qtd": q, "unit": u,
                                      "subtotal": q * u, "peso": peso})
                    total = sum(i["subtotal"] for i in itens)
                    st.metric("Total do orçamento", orcamento._moeda(total))

                    st.markdown("**Dados do cliente**")
                    k1, k2, k3 = st.columns(3)
                    cli = k1.text_input("Cliente", key="orc_cli")
                    cont = k2.text_input("Contato (tel / e-mail)", key="orc_cont")
                    num = k3.text_input("Nº do orçamento", key="orc_num")
                    k4, k5 = st.columns(2)
                    val = k4.number_input("Validade (dias)", 1, 180, 10, 1, key="orc_val")
                    desc = k5.number_input("Desconto (R$)", 0.0, 1_000_000.0, 0.0, 10.0, key="orc_desc")
                    obs = st.text_area("Observações (entrega, frete, pagamento…)", key="orc_obs")
                    if st.button("📄 Gerar orçamento (PDF)", type="primary", use_container_width=True):
                        pdf = orcamento.orcamento_pdf(
                            itens, cliente=cli, contato=cont, numero=num, validade_dias=int(val),
                            desconto=desc, observacoes=obs,
                            rate_info=(f"corte {rate:g} R$/min" if rate else ""))
                        st.session_state["orc_pdf"] = (f"orcamento_{num or 'metallo'}.pdf", pdf)
                    if st.session_state.get("orc_pdf"):
                        fn, pdf = st.session_state["orc_pdf"]
                        st.download_button("⬇  Baixar orçamento (PDF)", data=pdf, file_name=fn,
                                           mime="application/pdf", use_container_width=True)
            else:
                st.info("Suba um ou mais arquivos .dxf para montar o orçamento.")

    # ------------------------------------------------- Flanges (DXF inox)
    elif secao == "flange":
        st.caption("Gera **flanges planos em DXF** (corte a laser) — quadrado, redondo ou retangular, "
                   "com furo central opcional e furos de parafuso. Adicione até 10 modelos à biblioteca "
                   "e use a aba **Nesting** para encaixar tudo numa chapa só.")
        tab_bib, tab_ger = st.tabs(["📚 Biblioteca (DXF)", "Gerar flange"])
        with tab_bib:
            _ui_biblioteca_dxf("fllib")
        with tab_ger:
            with st.container(border=True):
                nome = st.text_input("Nome da peça", "Flange", key="fl_nome")
                forma = st.radio("Formato externo", ["Quadrado", "Redondo", "Retangular"],
                                 horizontal=True, key="fl_forma")
                peca = {"name": nome, "comp": 0.0}
                if forma == "Redondo":
                    D = st.number_input("Ø externo (mm)", 10.0, 2000.0, 80.0, 1.0, key="fl_D")
                    peca.update(shape="redondo", D=D)
                elif forma == "Quadrado":
                    S = st.number_input("Lado externo (mm)", 10.0, 2000.0, 100.0, 1.0, key="fl_S")
                    peca.update(shape="quadrado", S=S)
                else:
                    cW, cH = st.columns(2)
                    W = cW.number_input("Largura externa (mm)", 10.0, 2000.0, 120.0, 1.0, key="fl_W")
                    H = cH.number_input("Altura externa (mm)", 10.0, 2000.0, 80.0, 1.0, key="fl_H")
                    peca.update(shape="retangular", W=W, H=H)

                st.markdown("**Furo central** (concêntrico)")
                tem_centro = st.checkbox("Incluir furo central", value=True, key="fl_temc")
                if tem_centro:
                    modo_c = st.radio("Definir furo central por", ["Medida do furo", "Largura da aba"],
                                      horizontal=True, key="fl_modoc",
                                      help="A 'aba' é a borda entre o furo central e a borda externa da peça.")
                    if modo_c == "Largura da aba":
                        aba = st.number_input("Largura da aba (mm)", 0.5, 1000.0, 20.0, 0.5, key="fl_aba")
                        if forma == "Redondo":
                            cd = max(peca["D"] - 2 * aba, 1.0)
                            peca["centro"] = {"shape": "redondo", "d": cd}
                            st.caption(f"→ Furo central Ø **{cd:g} mm** (aba de {aba:g} mm).")
                        elif forma == "Quadrado":
                            cs = max(peca["S"] - 2 * aba, 1.0)
                            peca["centro"] = {"shape": "quadrado", "s": cs}
                            st.caption(f"→ Furo central **{cs:g}×{cs:g} mm** (aba de {aba:g} mm).")
                        else:
                            cw = max(peca["W"] - 2 * aba, 1.0); ch = max(peca["H"] - 2 * aba, 1.0)
                            peca["centro"] = {"shape": "retangular", "w": cw, "h": ch}
                            st.caption(f"→ Furo central **{cw:g}×{ch:g} mm** (aba de {aba:g} mm).")
                    else:
                        cforma = st.radio("Formato do furo central", ["Redondo", "Quadrado", "Retangular"],
                                          horizontal=True, key="fl_cforma")
                        if cforma == "Redondo":
                            cd = st.number_input("Ø do furo central (mm)", 1.0, 1900.0, 38.1, 0.1, key="fl_cd")
                            peca["centro"] = {"shape": "redondo", "d": cd}
                        elif cforma == "Quadrado":
                            cs = st.number_input("Lado do furo central (mm)", 1.0, 1900.0, 40.0, 0.5, key="fl_cs")
                            peca["centro"] = {"shape": "quadrado", "s": cs}
                        else:
                            k1, k2 = st.columns(2)
                            cw = k1.number_input("Largura furo central (mm)", 1.0, 1900.0, 40.0, 0.5, key="fl_cw")
                            ch = k2.number_input("Altura furo central (mm)", 1.0, 1900.0, 20.0, 0.5, key="fl_ch")
                            peca["centro"] = {"shape": "retangular", "w": cw, "h": ch}

                st.markdown("**Furos de parafuso**")
                g1, g2, g3 = st.columns(3)
                n = g1.number_input("Quantidade", 0, 24, 4 if forma != "Redondo" else 3, 1, key="fl_n")
                fforma = g2.selectbox("Formato do furo", ["Redondo", "Oblongo", "Quadrado"], key="fl_fforma")
                dist = g3.number_input("Distância da borda (mm)", 1.0, 500.0, 12.0, 0.5, key="fl_dist",
                                       help="Da borda externa até o centro do furo.")
                if fforma == "Oblongo":
                    o1, o2 = st.columns(2)
                    flen = o1.number_input("Comprimento do furo (mm)", 2.0, 200.0, 20.0, 0.5, key="fl_flen")
                    fwid = o2.number_input("Largura do furo (mm)", 1.0, 200.0, 9.0, 0.5, key="fl_fwid")
                    radial = st.checkbox("Orientar radialmente (apontando ao centro)", value=True, key="fl_rad")
                    girar = []
                    if int(n) > 0:
                        st.caption("Girar 90° cada furo (individual):")
                        ncol = min(int(n), 6)
                        gcols = st.columns(ncol)
                        for k in range(int(n)):
                            girar.append(gcols[k % ncol].checkbox(f"Furo {k+1}", key=f"fl_gir_{k}"))
                    peca["furo"] = {"n": int(n), "shape": "oblongo", "len": flen, "wid": fwid,
                                    "dist": dist, "radial": radial, "girar": girar}
                else:
                    fd = st.number_input("Ø do furo (mm)" if fforma == "Redondo" else "Lado do furo (mm)",
                                         1.0, 200.0, 8.0, 0.5, key="fl_fd")
                    peca["furo"] = {"n": int(n), "shape": fforma.lower(), "d": fd, "dist": dist}
                if forma != "Redondo" and n not in (0, 4, 8):
                    st.caption("ℹ️ Em flanges quadrados/retangulares os furos vão nos cantos (4) ou cantos + meios (8).")

                e1, e2 = st.columns(2)
                esp = e1.number_input("Espessura da chapa (mm)", 0.4, 25.0, 3.0, 0.1, key="fl_esp")
                peca["comp"] = comp_input(e2, "fl_comp")
                peca["esp"] = esp

                try:
                    prims = flanges.flange_prims(peca)
                    cP, cI = st.columns([1, 1])
                    with cP:
                        st.image(flanges.preview_png(prims), use_container_width=True)
                    with cI:
                        bw, bh = prims["bbox"]
                        st.metric("Tamanho", f"{bw:g} × {bh:g} mm")
                        st.metric("Peso (inox 304)", f"{flanges.peso_kg(prims):.3f} kg")
                        st.metric("Furos", f"{int(n)} de parafuso" + (" + central" if tem_centro else ""))
                        st.download_button("⬇  Baixar arquivos (.zip)",
                                           data=zip_flange(nome or "flange", flanges.dxf_bytes([(prims, 0, 0)]),
                                                           flanges.preview_png(prims)),
                                           file_name=f"{nome or 'flange'}.zip", mime="application/zip",
                                           use_container_width=True)
                    qlib = st.number_input("Quantidade desta peça (p/ nesting)", 1, 999, 1, 1, key="fl_qlib")
                    if st.button("➕ Adicionar à biblioteca", type="primary", use_container_width=True):
                        lib = st.session_state.setdefault("flange_lib", [])
                        if len(lib) >= 10:
                            st.warning("A biblioteca já tem 10 peças. Remova alguma na aba Nesting.")
                        else:
                            import copy
                            lib.append({"prims": copy.deepcopy(prims), "qtd": int(qlib), "name": nome})
                            st.success(f"'{nome}' adicionado à biblioteca ({len(lib)}/10).")
                except Exception as e:
                    st.error("Erro ao gerar o flange: " + str(e))

        # ------------------------------------------------- Peça por descrição (DXF)
    elif secao == "descricao":
        st.caption("Descreva a peça (retângulo, disco, anel/arruela, polígono) e gere o DXF na hora. "
                   "Ex.: *“disco de 100 mm com 6 furos de 8,5 mm em círculo de 80 mm”* ou "
                   "*“chapa 240 × 20 com 3 furos Ø6,2 equidistantes”*. Depois de **Interpretar**, ajuste.")
        FORMAS = {"Retângulo / Chapa": "retangulo", "Disco (redondo)": "disco",
                  "Anel / Arruela": "anel", "Polígono (hex/oct/…)": "poligono"}
        PADROES = {"Sem furos extras": "nenhum", "Em linha (equidistante)": "linha",
                   "Em círculo (PCD)": "circulo", "Em grade": "grade", "Nos cantos": "cantos"}
        INV_F = {v: k for k, v in FORMAS.items()}
        INV_P = {v: k for k, v in PADROES.items()}
        with st.container(border=True):
            txt = st.text_area("Descrição da peça", key="desc_txt",
                               placeholder="disco de 100 mm com 6 furos de 8.5 mm em círculo de 80 mm")
            if st.button("🔎 Interpretar descrição", use_container_width=True):
                pr = flanges.parse_descricao(txt)
                if pr.get("forma") in INV_F:
                    st.session_state["desc_forma_lbl"] = INV_F[pr["forma"]]
                for ks, kk, cast in [("comprimento", "desc_C", float), ("largura", "desc_W", float),
                                     ("diametro", "desc_diam", float), ("diametro_int", "desc_dint", float),
                                     ("lados", "desc_lados", int), ("medida", "desc_medida", float),
                                     ("furo_central", "desc_fc", float)]:
                    if ks in pr:
                        st.session_state[kk] = cast(pr[ks])
                fr = pr.get("furos")
                if fr:
                    st.session_state["desc_padrao_lbl"] = INV_P.get(fr.get("padrao", "linha"))
                    st.session_state["desc_n"] = int(fr.get("n", 0))
                    st.session_state["desc_d"] = float(fr.get("d", 6.0))
                    if fr.get("pcd"):
                        st.session_state["desc_pcd"] = float(fr["pcd"])
                else:
                    st.session_state["desc_padrao_lbl"] = "Sem furos extras"
                rec = pr.get("recorte")
                if rec:
                    st.session_state["desc_perf"] = True
                    st.session_state["desc_rcw"] = float(rec["w"])
                    st.session_state["desc_rch"] = float(rec["h"])
                    st.session_state["desc_rgap"] = float(rec.get("gap", 10.0))
                if pr.get("unidade") == "metros":
                    st.session_state["desc_unit"] = "metros"
                st.success("Interpretado: " + ", ".join(f"{k}={v}" for k, v in pr.items() if k != "equi"))
                st.rerun()

            forma = FORMAS[st.selectbox("Forma", list(FORMAS), key="desc_forma_lbl")]
            spec = {"forma": forma}
            if forma == "retangulo":
                unidade = st.radio("Unidade das medidas da chapa", ["mm", "metros"],
                                   horizontal=True, key="desc_unit")
                fator = 1000.0 if unidade == "metros" else 1.0
                a, b = st.columns(2)
                if unidade == "metros":
                    cv = a.number_input("Comprimento (m)", 0.02, 6.0,
                                        float(st.session_state.get("desc_C", 240.0)) / 1000.0, 0.05, key="desc_Cm")
                    wv = b.number_input("Largura (m)", 0.02, 3.0,
                                        float(st.session_state.get("desc_W", 20.0)) / 1000.0, 0.05, key="desc_Wm")
                    spec["comprimento"] = cv * 1000.0; spec["largura"] = wv * 1000.0
                    st.session_state["desc_C"] = spec["comprimento"]; st.session_state["desc_W"] = spec["largura"]
                else:
                    spec["comprimento"] = a.number_input("Comprimento (mm)", 5.0, 6000.0,
                                                         float(st.session_state.get("desc_C", 240.0)), 1.0, key="desc_C")
                    spec["largura"] = b.number_input("Largura (mm)", 5.0, 6000.0,
                                                     float(st.session_state.get("desc_W", 20.0)), 1.0, key="desc_W")
            elif forma == "disco":
                spec["diametro"] = st.number_input("Ø externo (mm)", 5.0, 3000.0,
                                                   float(st.session_state.get("desc_diam", 100.0)), 1.0, key="desc_diam")
            elif forma == "anel":
                a, b = st.columns(2)
                spec["diametro"] = a.number_input("Ø externo (mm)", 5.0, 3000.0,
                                                  float(st.session_state.get("desc_diam", 60.0)), 1.0, key="desc_diam")
                spec["diametro_int"] = b.number_input("Ø interno / furo (mm)", 1.0, 2990.0,
                                                      float(st.session_state.get("desc_dint", 30.0)), 1.0, key="desc_dint")
            else:                                   # poligono
                a, b = st.columns(2)
                spec["lados"] = int(a.number_input("Nº de lados", 3, 16,
                                                   int(st.session_state.get("desc_lados", 6)), 1, key="desc_lados"))
                spec["medida"] = b.number_input("Medida entre faces (mm)", 5.0, 3000.0,
                                                float(st.session_state.get("desc_medida", 50.0)), 1.0, key="desc_medida")
                spec["medida_tipo"] = "entre_faces"

            if forma != "anel":
                fc = st.number_input("Furo central Ø (mm) — 0 = nenhum", 0.0, 2990.0,
                                     float(st.session_state.get("desc_fc", 0.0)), 0.5, key="desc_fc")
                if fc > 0:
                    spec["furo_central"] = fc

            padrao = PADROES[st.selectbox("Furos adicionais", list(PADROES), key="desc_padrao_lbl")]
            if padrao != "nenhum":
                g = st.columns(3)
                nn = g[0].number_input("Nº de furos", 1, 200, int(st.session_state.get("desc_n", 6)), 1, key="desc_n")
                dd = g[1].number_input("Ø do furo (mm)", 0.5, 500.0,
                                       float(st.session_state.get("desc_d", 8.0)), 0.1, key="desc_d")
                fr = {"padrao": padrao, "n": int(nn), "d": dd}
                if padrao == "circulo":
                    fr["pcd"] = g[2].number_input("PCD — Ø do círculo de furação (mm)", 1.0, 3000.0,
                                                  float(st.session_state.get("desc_pcd", 80.0)), 1.0, key="desc_pcd")
                elif padrao == "grade":
                    fr["cols"] = int(g[2].number_input("Colunas", 1, 50, 3, 1, key="desc_cols"))
                    fr["rows"] = int(st.number_input("Linhas", 1, 50, 2, 1, key="desc_rows"))
                    fr["dist"] = st.number_input("Margem da borda (mm)", 1.0, 500.0, 15.0, 1.0, key="desc_gmarg")
                elif padrao == "cantos":
                    fr["dist"] = g[2].number_input("Distância da borda (mm)", 1.0, 500.0, 15.0, 1.0, key="desc_cdist")
                spec["furos"] = fr

            if forma == "retangulo":
                perf = st.checkbox("Recortes retangulares (chapa perfurada) — preenche a chapa",
                                   value=False, key="desc_perf")
                if perf:
                    r1, r2, r3 = st.columns(3)
                    rcw = r1.number_input("Recorte: medida no comprimento (mm)", 2.0, 2000.0,
                                          float(st.session_state.get("desc_rcw", 100.0)), 1.0, key="desc_rcw")
                    rch = r2.number_input("Recorte: medida na largura (mm)", 2.0, 2000.0,
                                          float(st.session_state.get("desc_rch", 50.0)), 1.0, key="desc_rch")
                    rgap = r3.number_input("Distância entre recortes (mm)", 0.5, 200.0,
                                           float(st.session_state.get("desc_rgap", 10.0)), 0.5, key="desc_rgap")
                    spec["recorte"] = {"w": rcw, "h": rch, "gap": rgap}

            e1, e2 = st.columns(2)
            spec["esp"] = e1.number_input("Espessura (mm)", 0.4, 25.0, 2.0, 0.1, key="desc_esp")
            spec["comp"] = comp_input(e2, "desc_comp")
            nome = st.text_input("Nome da peça", f"Peca_{forma}", key="desc_nome")
            spec["name"] = nome
            try:
                prims = flanges.peca_por_descricao(spec)
                dxf = flanges.dxf_bytes([(prims, 0, 0)])
                png = flanges.preview_png(prims)
                pdf = flanges.preview_pdf(prims, esp=spec["esp"], obs=nome)
                cP, cI = st.columns([1, 1])
                with cP:
                    st.image(png, use_container_width=True)
                with cI:
                    bw, bh = prims["bbox"]
                    st.metric("Tamanho", f"{bw:g} × {bh:g} mm")
                    gx = spec.get("_grid")
                    st.metric("Recortes / furos", f"{len(prims['holes'])}" + (f"  ({gx[0]}×{gx[1]})" if gx else ""))
                    st.metric("Peso (inox 304)", f"{flanges.peso_kg(prims):.3f} kg")
                    st.download_button("⬇  Baixar arquivos (.zip: DXF + PDF + PNG)",
                                       data=zip_flange(nome or "peca", dxf, png, pdf),
                                       file_name=f"{nome or 'peca'}.zip", mime="application/zip",
                                       use_container_width=True)
                    cd1, cd2 = st.columns(2)
                    cd1.download_button("DXF", data=dxf, file_name=f"{nome or 'peca'}.dxf",
                                        mime="image/vnd.dxf", use_container_width=True)
                    cd2.download_button("PDF", data=pdf, file_name=f"{nome or 'peca'}.pdf",
                                        mime="application/pdf", use_container_width=True)
                qlib = st.number_input("Quantidade (p/ nesting)", 1, 999, 1, 1, key="desc_qlib")
                if st.button("➕ Adicionar à biblioteca", type="primary", use_container_width=True):
                    lib = st.session_state.setdefault("flange_lib", [])
                    if len(lib) >= 10:
                        st.warning("A biblioteca já tem 10 peças.")
                    else:
                        import copy
                        lib.append({"prims": copy.deepcopy(prims), "qtd": int(qlib), "name": nome})
                        st.success(f"'{nome}' adicionado à biblioteca ({len(lib)}/10).")
            except Exception as e:
                st.error("Erro ao gerar a peça: " + str(e))

    # ------------------------------------------------- Placa numérica
    elif secao == "placa":
        st.caption("Gera **placa numérica** (número residencial) com o número **vazado** (recortado) e "
                   "furos de fixação — tamanhos padrão ou personalizado. Também dá para **subir um DXF "
                   "de modelo** e guardá-lo idêntico.")
        # tolerância a versão antiga de metallo_cad
        MODELOS_PL = getattr(flanges, "MODELOS_PLACA",
                             ["Nenhum", "Cacos", "Ripas diagonais", "Ondas", "Treliça", "Cantos"])
        ACAB_PL = getattr(flanges, "ACABAMENTOS",
                          {"Grafite": "#3b3b3b", "Preto": "#141414", "Branco": "#eeeeee",
                           "Prata": "#c6c8cc", "Cobre / Corten": "#a85a2e"})
        _tem_residencial = hasattr(flanges, "placa_residencial_prims")
        if not _tem_residencial or not hasattr(flanges, "MODELOS_PLACA"):
            st.warning("⚠️ A pasta **metallo_cad** está desatualizada. Substitua a pasta **kit** inteira "
                       "pela última versão para liberar os modelos decorativos e o acabamento. "
                       "Por enquanto a placa funciona em modo simplificado.")
        tab_g, tab_u = st.tabs(["Gerar placa", "Meus modelos (DXF)"])
        with tab_g:
            with st.container(border=True):
                ct1, ct2 = st.columns(2)
                texto = ct1.text_input("Texto (ex.: CASA, sobrenome) — opcional", "CASA", key="pl_txt")
                numero = ct2.text_input("Número (use vírgula p/ várias placas: 66, 102, 305)", "66", key="pl_num")
                orient = st.radio("Orientação", ["Vertical (retrato)", "Horizontal (paisagem)"],
                                  horizontal=True, key="pl_orient")
                PRESETS = {"45 × 16 cm": (450, 160), "55 × 20 cm": (550, 200), "65 × 23 cm": (650, 230),
                           "75 × 27 cm": (750, 270), "85 × 30 cm": (850, 300), "95 × 34 cm": (950, 340),
                           "105 × 37 cm": (1050, 370), "Personalizado": None}
                psel = st.selectbox("Tamanho", list(PRESETS), index=2, key="pl_size")
                if PRESETS[psel] is None:
                    a, b = st.columns(2)
                    dimA = a.number_input("Maior medida (mm)", 50.0, 3000.0, 650.0, 5.0, key="pl_A")
                    dimB = b.number_input("Menor medida (mm)", 30.0, 1500.0, 230.0, 5.0, key="pl_B")
                    big, small = max(dimA, dimB), min(dimA, dimB)
                else:
                    big, small = max(PRESETS[psel]), min(PRESETS[psel])
                if orient.startswith("Vertical"):
                    L, W = small, big
                else:
                    L, W = big, small
                st.caption(f"Chapa: {L:g} × {W:g} mm ({orient.split()[0].lower()})")

                cm1, cm2 = st.columns(2)
                modelo = cm1.selectbox("Padrão da faixa (topo/base)", MODELOS_PL,
                                       index=0, key="pl_modelo")
                cor_nome = cm2.selectbox("Acabamento (cor)", list(ACAB_PL), key="pl_cor")
                FONTES_PL = getattr(flanges, "FONTES_PLACA", {"Sans (DejaVu)": "DejaVu Sans"})
                cfn1, cfn2, cfn3 = st.columns(3)
                fonte_nome = cfn1.selectbox("Fonte do número", list(FONTES_PL), key="pl_fonte")
                usar_ponte = cfn2.checkbox("Pontes (stencil)", True, key="pl_ponte_on",
                                           help="Liga o miolo do 0, 4, 6, 8, 9… para não cair no corte.")
                ponte_mm = cfn3.number_input("Largura da ponte (mm)", 1.0, 30.0, 4.0, 0.5, key="pl_ponte_w",
                                             disabled=not usar_ponte)
                fix = st.radio("Fixação", ["Sem fixação (prisioneiro no verso)", "Furo frontal", "Com dobras (abas)"],
                               horizontal=True, key="pl_fix")
                c1, c2, c3 = st.columns(3)
                nf = c1.number_input("Furos (se furo frontal)", 0, 4, 2, 1, key="pl_nf")
                df = c2.number_input("Ø furo (mm)", 2.0, 20.0, 6.0, 0.5, key="pl_df")
                raio = c3.number_input("Raio do canto (mm)", 0.0, 100.0, 6.0, 1.0, key="pl_raio")
                c4, c5 = st.columns(2)
                esp = c4.number_input("Espessura (mm)", 0.4, 6.0, 1.2, 0.1, key="pl_esp")
                comp = comp_input(c5, "pl_comp")
                nome_auto("pl_nome", f"Placa_{(texto or numero or 'num').strip()}")
                nome = st.text_input("Nome do arquivo", key="pl_nome")
                numeros = [n.strip() for n in str(numero).split(",") if n.strip()] or [""]
                fonte_fam = FONTES_PL.get(fonte_nome)
                ponte_val = float(ponte_mm) if usar_ponte else 0.0

                def _gera_placa(num_str, nm):
                    if _tem_residencial:
                        pr = flanges.placa_residencial_prims(
                            L, W, num_str, texto=texto,
                            layout=("texto_numero" if str(texto).strip() else "so_numero"),
                            modelo=modelo, cor=ACAB_PL.get(cor_nome),
                            n_furos=int(nf), d_furo=df, raio=raio,
                            dobras=(fix == "Com dobras (abas)") if not fix.startswith("Sem fixação") else False,
                            comp=comp, esp=esp, name=nm, fonte=fonte_fam, ponte=ponte_val)
                    else:
                        pr = flanges.placa_numerica_prims(
                            L, W, num_str, n_furos=int(nf), d_furo=df, raio=raio,
                            comp=comp, esp=esp, name=nm)
                    if fix.startswith("Sem fixação"):
                        pr["holes"] = [h for h in pr["holes"] if not (h[0] == "circle")]
                    return pr

                try:
                    num0 = numeros[0]
                    nome0 = nome if len(numeros) == 1 else f"{nome}_{num0}"
                    prims = _gera_placa(num0, nome0)
                    dxf = flanges.dxf_bytes([(prims, 0, 0)]); png = flanges.preview_png(prims)
                    mock = flanges.placa_mock_png(prims) if hasattr(flanges, "placa_mock_png") else None
                    pdf = flanges.preview_pdf(prims, esp=esp, obs=f"{nome0} · {cor_nome} · modelo {modelo}")
                    cP, cI = st.columns([1, 1])
                    with cP:
                        if mock:
                            tV, tT = st.tabs(["✨ Visual (acabamento)", "📐 Técnico (corte)"])
                            with tV:
                                st.image(mock, use_container_width=True)
                            with tT:
                                st.image(png, use_container_width=True)
                        else:
                            st.image(png, use_container_width=True)
                        if len(numeros) > 1:
                            st.caption(f"Pré-visualização da 1ª de **{len(numeros)} placas**: {', '.join(numeros)}")
                    with cI:
                        st.metric("Chapa", f"{L:g} × {W:g} mm")
                        st.metric("Acabamento", cor_nome)
                        st.metric("Peso (inox 304)", f"{flanges.peso_kg(prims):.3f} kg")
                        if len(numeros) == 1:
                            st.download_button("⬇  Baixar (.zip: DXF + PDF + PNG)",
                                               data=zip_flange(nome0 or "placa", dxf, png, pdf),
                                               file_name=f"{nome0 or 'placa'}.zip", mime="application/zip",
                                               use_container_width=True)
                            d1, d2 = st.columns(2)
                            d1.download_button("DXF", data=dxf, file_name=f"{nome0 or 'placa'}.dxf",
                                               mime="image/vnd.dxf", use_container_width=True)
                            d2.download_button("PDF", data=pdf, file_name=f"{nome0 or 'placa'}.pdf",
                                               mime="application/pdf", use_container_width=True)
                        else:
                            pecas_lote = []
                            for nx in numeros:
                                nmx = f"{nome}_{nx}"
                                px = _gera_placa(nx, nmx)
                                pecas_lote.append({"nome": nmx, "dxf": flanges.dxf_bytes([(px, 0, 0)]),
                                                   "png": flanges.preview_png(px),
                                                   "pdf": flanges.preview_pdf(px, esp=esp, obs=nmx)})
                            st.download_button(f"⬇  Baixar LOTE ({len(numeros)} placas .zip)",
                                               data=zip_lote(pecas_lote),
                                               file_name=f"{nome}_lote.zip", mime="application/zip",
                                               use_container_width=True)
                    st.caption("Camadas no DXF: **CORTE** (contorno), **FUROS**, **DECORACAO** (modelo) "
                               "e **DOBRA** (abas). Pontes mantêm o miolo dos números preso.")
                    if len(numeros) == 1:
                        qlib = st.number_input("Quantidade (p/ nesting)", 1, 999, 1, 1, key="pl_qlib")
                        if st.button("➕ Adicionar à biblioteca", use_container_width=True):
                            lib = st.session_state.setdefault("flange_lib", [])
                            if len(lib) >= 10:
                                st.warning("A biblioteca já tem 10 peças.")
                            else:
                                import copy
                                lib.append({"prims": copy.deepcopy(prims), "qtd": int(qlib), "name": nome0})
                                st.success(f"'{nome0}' adicionado à biblioteca ({len(lib)}/10).")
                except Exception as e:
                    st.error("Erro ao gerar a placa: " + str(e))

        with tab_u:
            _ui_biblioteca_dxf("pllib")


    # ------------------------------------------------- Ralo / grelha
    elif secao == "ralo":
        st.caption("Gera as **duas peças do ralo** já compatíveis para montagem: a **tampa "
                   "superior** (aparente) e a **chapa de apoio inferior** (encaixe no trilho). "
                   "A malha de oblongos é idêntica nas duas; muda só o contorno externo e o furo central.")
        tab_bib, tab_meus, tab_ger = st.tabs(["📚 Biblioteca (DXF)", "🗂 Meus ralos", "Gerar ralo"])
        with tab_meus:
            _rl = ralos_lib.listar_ralos()
            if not _rl:
                st.info("Nenhum ralo salvo. Gere um na aba **Gerar ralo** e clique em "
                        "**Salvar na biblioteca** — os tamanhos ficam aqui para baixar em lote ou individual.")
            else:
                _pecas_r = []
                for _m in _rl:
                    try:
                        _pr = ralo_lib.gerar(_m["params"]["L"], _m["params"]["W"],
                                             esp=_m["params"].get("esp", 1.5), nome=_m["nome"])
                        _pecas_r.append((_m, _pr))
                    except Exception:
                        _pecas_r.append((_m, None))
                _validos = [(m, r) for m, r in _pecas_r if r is not None]
                _tot = sum(int(m.get("qtd", 1)) for m, _ in _validos)
                st.caption(f"{len(_validos)} tamanho(s) · {_tot} conjunto(s) no total (com as quantidades).")
                if _validos:
                    def _empilha(chave, gap):
                        _it = []; _y = 0.0
                        for _m, _r in _validos:
                            for _c in range(int(_m.get("qtd", 1))):
                                _h = _r[chave]["bbox"][1]
                                _it.append((_r[chave], 0.0, _y - _h / 2.0)); _y -= _h + gap
                        return ralo_lib.dxf_bytes(_it)
                    _lt1, _lt2 = st.columns(2)
                    _lt1.download_button("\u2b07 LOTE — SUPERIORES (grelhas, 1 dxf)", data=_empilha("sup", 40.0),
                                         file_name="ralos_lote_SUPERIORES.dxf", mime="image/vnd.dxf",
                                         use_container_width=True, key="rl_lote_sup")
                    _lt2.download_button("\u2b07 LOTE — INFERIORES (apoios, 1 dxf)", data=_empilha("inf", 40.0),
                                         file_name="ralos_lote_INFERIORES.dxf", mime="image/vnd.dxf",
                                         use_container_width=True, key="rl_lote_inf")
                st.markdown("---")
                for _m, _r in _pecas_r:
                    with st.container(border=True):
                        _cc = st.columns([3, 1, 1, 1])
                        if _r is not None:
                            _i = _r["info"]
                            _cc[0].markdown(f"**{_m['nome']}** · {_i['L']:.0f}×{_i['W']:.0f} mm · "
                                            f"{_i['n_colunas']}×{_i['n_fileiras']} furos · "
                                            f"inferior {_i['L_inferior']:.0f}×{_i['W_inferior']:.0f}")
                        else:
                            _cc[0].markdown(f"**{_m['nome']}** (erro ao regenerar)")
                        _nq = int(_cc[1].number_input("Qtd", 1, 999, int(_m.get("qtd", 1)), 1,
                                                      key=f"rl_q_{_m['_arquivo']}"))
                        if _nq != int(_m.get("qtd", 1)):
                            ralos_lib.atualizar_qtd(_m["_arquivo"], _nq)
                        if _cc[2].button("Ver", key=f"rl_v_{_m['_arquivo']}", use_container_width=True):
                            st.session_state["rl_sel"] = _m["_arquivo"]
                        if _cc[3].button("Remover", key=f"rl_rm_{_m['_arquivo']}", use_container_width=True):
                            ralos_lib.remover_ralo(_m["_arquivo"])
                            st.rerun()
                        if _r is not None and st.session_state.get("rl_sel") == _m["_arquivo"]:
                            _v1, _v2 = st.columns(2)
                            _v1.image(flanges.preview_png(ralo_lib.preview_prims(_r["sup"])), use_container_width=True)
                            _v2.image(flanges.preview_png(ralo_lib.preview_prims(_r["inf"])), use_container_width=True)
                            _desl = _r["info"]["W"] / 2 + _r["info"]["W_inferior"] / 2 + 40
                            _dd = st.columns(3)
                            _dd[0].download_button("DXF superior", data=ralo_lib.dxf_bytes([(_r["sup"], 0, 0)]),
                                                   file_name=f"{_m['nome']}_superior.dxf", mime="image/vnd.dxf",
                                                   key=f"rl_ds_{_m['_arquivo']}", use_container_width=True)
                            _dd[1].download_button("DXF inferior", data=ralo_lib.dxf_bytes([(_r["inf"], 0, 0)]),
                                                   file_name=f"{_m['nome']}_inferior.dxf", mime="image/vnd.dxf",
                                                   key=f"rl_di_{_m['_arquivo']}", use_container_width=True)
                            _dd[2].download_button("DXF conjunto", data=ralo_lib.dxf_bytes([(_r["sup"], 0, 0), (_r["inf"], 0, -_desl)]),
                                                   file_name=f"{_m['nome']}_conjunto.dxf", mime="image/vnd.dxf",
                                                   key=f"rl_dc_{_m['_arquivo']}", use_container_width=True)
        with tab_bib:
            _ui_biblioteca_dxf("ralolib")
        with tab_ger:
            with st.container(border=True):
                cr1, cr2, cr3 = st.columns(3)
                Lr = cr1.number_input("Comprimento L (mm)", 200.0, 6000.0, 1000.0, 10.0, key="ralo_L")
                Wr = cr2.number_input("Largura W (mm)", 60.0, 1000.0, 150.0, 5.0, key="ralo_W")
                espr = cr3.number_input("Espessura (mm)", 0.4, 6.0, 1.5, 0.1, key="ralo_esp")
                nome_auto("ralo_nome", f"Ralo_{int(Lr)}x{int(Wr)}")
                nome_r = st.text_input("Nome base", key="ralo_nome")
                try:
                    rr = ralo_lib.gerar(Lr, Wr, esp=espr, nome=nome_r or "Ralo")
                    sup, inf, info = rr["sup"], rr["inf"], rr["info"]
                    sup_pv = ralo_lib.preview_prims(sup); inf_pv = ralo_lib.preview_prims(inf)
                    dxf_sup = ralo_lib.dxf_bytes([(sup, 0, 0)])
                    dxf_inf = ralo_lib.dxf_bytes([(inf, 0, 0)])
                    # DXF combinado: as duas peças empilhadas (mantendo o mesmo eixo X)
                    desloc = Wr / 2 + info["W_inferior"] / 2 + 40
                    dxf_par = ralo_lib.dxf_bytes([(sup, 0, 0), (inf, 0, -desloc)])
                    png_sup = flanges.preview_png(sup_pv); png_inf = flanges.preview_png(inf_pv)
                    pdf_sup = flanges.preview_pdf(sup_pv, esp=espr, obs="tampa superior (aparente)")
                    pdf_inf = flanges.preview_pdf(inf_pv, esp=espr, obs="chapa de apoio (trilho)")

                    ca, cb = st.columns(2)
                    with ca:
                        st.markdown("**Superior (tampa)**")
                        st.image(png_sup, use_container_width=True)
                        st.caption(f"{Lr:g} × {Wr:g} mm · {info['total_oblongos_sup']} recortes "
                                   f"(inclui oblongo central 33×7) · ~{flanges.peso_kg(sup):.2f} kg")
                    with cb:
                        st.markdown("**Inferior (apoio)**")
                        st.image(png_inf, use_container_width=True)
                        st.caption(f"{info['L_inferior']:g} × {info['W_inferior']:g} mm · "
                                   f"{info['total_oblongos_inf']} oblongos + furo Ø6,3 · ~{flanges.peso_kg(inf):.2f} kg")

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Colunas", info["n_colunas"])
                    m2.metric("Fileiras", info["n_fileiras"])
                    m3.metric("Margem lateral (sup)", f"{info['margem_lateral_sup']:.0f} mm")
                    m4.metric("Gap entre fileiras", f"{info['gap_fileira']:.1f} mm")
                    st.caption(f"Passo entre colunas fixo de **55 mm** (25 + 30). "
                               f"Margens fixas 23 mm (topo/base superior) e 12 mm (topo/base inferior). "
                               f"Furo Ø6,3 da inferior deslocado 13,3 mm à esquerda do centro.")

                    import io as _io, zipfile as _zip
                    buf = _io.BytesIO()
                    with _zip.ZipFile(buf, "w", _zip.ZIP_DEFLATED) as z:
                        z.writestr(f"superior/{nome_r}_superior.dxf", dxf_sup)
                        z.writestr(f"superior/{nome_r}_superior.pdf", pdf_sup)
                        z.writestr(f"superior/{nome_r}_superior.png", png_sup)
                        z.writestr(f"inferior/{nome_r}_inferior.dxf", dxf_inf)
                        z.writestr(f"inferior/{nome_r}_inferior.pdf", pdf_inf)
                        z.writestr(f"inferior/{nome_r}_inferior.png", png_inf)
                        z.writestr(f"{nome_r}_conjunto.dxf", dxf_par)
                    st.download_button("⬇  Baixar TUDO (.zip: pastas superior/ + inferior/ + conjunto)",
                                       data=buf.getvalue(), file_name=f"{nome_r}.zip",
                                       mime="application/zip", use_container_width=True)
                    d1, d2, d3 = st.columns(3)
                    d1.download_button("DXF superior", data=dxf_sup, file_name=f"{nome_r}_superior.dxf",
                                       mime="image/vnd.dxf", use_container_width=True)
                    d2.download_button("DXF inferior", data=dxf_inf, file_name=f"{nome_r}_inferior.dxf",
                                       mime="image/vnd.dxf", use_container_width=True)
                    d3.download_button("DXF conjunto", data=dxf_par, file_name=f"{nome_r}_conjunto.dxf",
                                       mime="image/vnd.dxf", use_container_width=True)
                    st.caption("No .zip: a pasta **superior/** traz a tampa (DXF+PDF+PNG) e **inferior/** o apoio; "
                               "o **conjunto** fica na raiz. Camadas: **CORTE** e **FUROS**.")
                    st.markdown("---")
                    _sv1, _sv2 = st.columns([1, 1.3])
                    _qtd_ral = int(_sv1.number_input("Quantidade", 1, 999, 1, 1, key="ralo_qtdlib"))
                    if _sv2.button("\U0001F4E5 Salvar na biblioteca", key="ralo_envlib", use_container_width=True):
                        ralos_lib.salvar_ralo(nome_r, {"L": Lr, "W": Wr, "esp": espr}, _qtd_ral)
                        st.success(f"'{nome_r}' (×{_qtd_ral}) salvo. Veja na aba \U0001F5C2 Meus ralos.")
                except ValueError as e:
                    st.warning(str(e))
                except Exception as e:
                    st.error("Erro ao gerar o ralo: " + str(e))


    # ------------------------------------------------- Planificação (caldeiraria)
    elif secao == "planificacao":
        st.caption("Desenvolve formas 3D em **chapa plana** para corte (caldeiraria / traçagem): "
                   "virola, cone e tronco de cone. Gera o contorno já planificado em DXF + PDF + PNG.")
        forma = st.selectbox("Forma a planificar",
                             ["Virola / cilindro", "Cone", "Tronco de cone (redução)"], key="pn_forma")
        esp = st.number_input("Espessura (mm)", 0.4, 50.0, 3.0, 0.1, key="pn_esp")
        fibra = st.checkbox("Compensar fibra neutra (somar espessura ao diâmetro)", value=True, key="pn_fibra",
                            help="Na calandragem o comprimento real usa o diâmetro médio = interno + espessura.")
        try:
            if forma.startswith("Virola"):
                cc = st.columns(2)
                D = cc[0].number_input("Diâmetro interno (mm)", 10.0, 6000.0, 300.0, 1.0, key="pn_D")
                H = cc[1].number_input("Altura / comprimento (mm)", 5.0, 6000.0, 500.0, 1.0, key="pn_H")
                Dref = D + (esp if fibra else 0)
                prims = planificacao.cilindro(Dref, H, esp=esp, name=f"Virola_D{int(D)}")
            elif forma == "Cone":
                cc = st.columns(2)
                D = cc[0].number_input("Diâmetro da base (mm)", 10.0, 6000.0, 300.0, 1.0, key="pn_Dc")
                h = cc[1].number_input("Altura do cone (mm)", 5.0, 6000.0, 200.0, 1.0, key="pn_hc")
                Dref = D + (esp if fibra else 0)
                prims = planificacao.cone(Dref, h, esp=esp, name=f"Cone_D{int(D)}")
            else:
                cc = st.columns(3)
                D = cc[0].number_input("Diâmetro maior (mm)", 10.0, 6000.0, 400.0, 1.0, key="pn_Dt")
                d = cc[1].number_input("Diâmetro menor (mm)", 5.0, 6000.0, 200.0, 1.0, key="pn_dt")
                h = cc[2].number_input("Altura (mm)", 5.0, 6000.0, 300.0, 1.0, key="pn_ht")
                Df = D + (esp if fibra else 0); df = d + (esp if fibra else 0)
                prims = planificacao.tronco_cone(Df, df, h, esp=esp, name=f"Tronco_{int(D)}_{int(d)}")
            nome = prims["name"]
            dxf = flanges.dxf_bytes([(prims, 0, 0)]); png = flanges.preview_png(prims)
            pdf = flanges.preview_pdf(prims, esp=esp, obs=prims["info"]["tipo"])
            cP, cI = st.columns([1, 1])
            with cP:
                st.image(png, use_container_width=True)
            with cI:
                bw, bh = prims["bbox"]
                st.metric("Tamanho da chapa", f"{bw:.0f} × {bh:.0f} mm")
                st.metric("Peso (inox 304)", f"{planificacao.peso_kg(prims):.2f} kg")
                info = prims["info"]
                rot = {"geratriz": "Geratriz", "raio_setor": "Raio do setor",
                       "angulo_setor_g": "Ângulo do setor (°)", "raio_maior_R1": "Raio externo R1",
                       "raio_menor_R2": "Raio interno R2", "larg_chapa": "Largura (πD)",
                       "alt_chapa": "Altura", "perimetro": "Perímetro"}
                linhas = [f"**{rot.get(k, k)}:** {v:.1f} mm" for k, v in info.items()
                          if isinstance(v, (int, float)) and k in rot]
                st.markdown("  \n".join(linhas))
                st.download_button("⬇  Baixar (.zip: DXF + PDF + PNG)", data=zip_flange(nome, dxf, png, pdf),
                                   file_name=f"{nome}.zip", mime="application/zip", use_container_width=True)
                d1, d2 = st.columns(2)
                d1.download_button("DXF", data=dxf, file_name=f"{nome}.dxf",
                                   mime="image/vnd.dxf", use_container_width=True)
                d2.download_button("PDF", data=pdf, file_name=f"{nome}.pdf",
                                   mime="application/pdf", use_container_width=True)
            st.caption("A linha reta do setor é a **emenda** (solda). Some o desconto de calandragem "
                       "conforme a sua máquina/material, se necessário.")
        except Exception as e:
            st.error("Erro na planificação: " + str(e))

        with st.expander("📷 Anexar rascunho (referência para preencher as cotas)"):
            st.caption("Suba uma foto do seu rascunho/croqui com as medidas para olhar enquanto preenche os campos.")
            rasc = st.file_uploader("Foto do rascunho", type=["png", "jpg", "jpeg"], key="pn_rasc")
            if rasc is not None:
                st.image(rasc, caption="Rascunho (referência) — digite as cotas nos campos acima.",
                         use_container_width=True)
            st.info("A leitura **automática** das cotas a partir da foto não roda dentro do app (offline). "
                    "Para eu gerar a peça direto do rascunho, me envie a foto **na conversa do chat**: "
                    "eu leio as medidas e devolvo o DXF/PDF.")

        with st.expander("📖 Glossário rápido do ramo"):
            st.markdown(
                "- **Virola / anel / aro / coroa**: cilindro aberto (chapa calandrada que vira tubo).\n"
                "- **Calandrar**: curvar a chapa em cilindro ou cone nos rolos da calandra.\n"
                "- **Geratriz**: a lateral inclinada do cone (do vértice à base).\n"
                "- **Tronco de cone / redução**: cone sem a ponta (liga dois diâmetros diferentes).\n"
                "- **Traçagem / planificação**: abrir a peça 3D em chapa plana para cortar.\n"
                "- **Quina**: o canto/aresta da dobra. **Aba / pestana**: a borda dobrada.\n"
                "- **Cantoneira**: perfil em \"L\". **Chata**: barra chata. **Gola / luva**: anel curto de reforço.\n"
                "- **Bitola / espessura**: grossura da chapa. **Chapa lisa / xadrez**: sem ou com relevo antiderrapante.")

    # ------------------------------------------------- Gerar em lote
    elif secao == "lote":
        st.caption("Gere **várias peças de uma vez**: uma descrição por linha (mesma linguagem do "
                   "interpretador). Sai um único **.zip** com todas (DXF + PDF + PNG). Use **3x ...** "
                   "no começo da linha para repetir a peça.")
        exemplo = ("disco 100 com 6 furos 8.5 em circulo 80\n"
                   "anel 200 interno 150\n"
                   "chapa 300x200 furo central 20\n"
                   "2x disco 80 furo 10\n"
                   "rodela 120")
        txt = st.text_area("Peças (uma por linha)", exemplo, height=170, key="lote_txt")
        c1, c2, c3 = st.columns(3)
        esp = c1.number_input("Espessura padrão (mm)", 0.4, 25.0, 2.0, 0.1, key="lote_esp")
        inc_pdf = c2.checkbox("Incluir PDF de cada peça", True, key="lote_pdf")
        inc_png = c3.checkbox("Incluir PNG", True, key="lote_png")
        with st.expander("🏷️  Etiquetas de identificação (opcional)"):
            l1, l2, l3 = st.columns(3)
            ger_et = l1.checkbox("Gerar etiquetas (PDF)", False, key="lote_et")
            obra_et = l2.text_input("Obra / cliente (topo da etiqueta)", "", key="lote_etobra")
            barras_et = l3.checkbox("Código de barras", True, key="lote_etbar")
            l4, l5 = st.columns(2)
            etw = l4.number_input("Largura (mm)", 30.0, 150.0, 80.0, 5.0, key="lote_etw")
            eth = l5.number_input("Altura (mm)", 20.0, 100.0, 40.0, 5.0, key="lote_eth")
        if st.button("⚙️  Gerar lote", type="primary", use_container_width=True):
            linhas = [l.strip() for l in txt.splitlines() if l.strip()]
            pecas = []; resumo = []; itens_et = []
            for i, l in enumerate(linhas, 1):
                q = 1; desc = l
                mq = re.match(r"^\s*(\d+)\s*[xX]\s+(.*)$", l)
                if mq:
                    q = max(int(mq.group(1)), 1); desc = mq.group(2)
                try:
                    spec = flanges.parse_descricao(desc); spec["esp"] = esp
                    base = (re.sub(r"[^\w\- ]+", "", desc).strip().replace(" ", "_")[:30] or f"peca{i}")
                    spec["name"] = base
                    prims = flanges.peca_por_descricao(spec)
                    dxf = flanges.dxf_bytes([(prims, 0, 0)])
                    png = flanges.preview_png(prims) if inc_png else None
                    pdf = flanges.preview_pdf(prims, esp=esp, obs=desc) if inc_pdf else None
                    for k in range(q):
                        nome = base if q == 1 else f"{base}_{k + 1}"
                        pecas.append({"nome": nome, "dxf": dxf, "png": png, "pdf": pdf})
                    bw, bh = prims["bbox"]
                    itens_et.append({"titulo": obra_et, "destaque": base[:24],
                                     "linhas": [desc[:40], f"{bw:.0f}×{bh:.0f} mm · {esp:g} mm",
                                                f"Furos: {len(prims['holes'])}"],
                                     "codigo": base, "qtd": q})
                    resumo.append({"#": i, "Descrição": desc, "Forma": spec.get("forma", "?"),
                                   "Qtd": q, "Tamanho (mm)": f"{bw:.0f}×{bh:.0f}",
                                   "Recortes/furos": len(prims["holes"]), "Status": "ok"})
                except Exception as e:
                    resumo.append({"#": i, "Descrição": desc, "Forma": "—", "Qtd": q,
                                   "Tamanho (mm)": "—", "Recortes/furos": 0, "Status": f"erro: {str(e)[:40]}"})
            extras = {}
            if ger_et and itens_et:
                extras["etiquetas.pdf"] = promobile.etiqueta_generica_pdf(
                    itens_et, tamanho=(etw, eth), barras=barras_et)
            st.session_state["lote_zip"] = zip_lote(pecas, extras) if pecas else None
            st.session_state["lote_resumo"] = resumo
            st.session_state["lote_n"] = len(pecas)
        if st.session_state.get("lote_resumo"):
            st.dataframe(pd.DataFrame(st.session_state["lote_resumo"]),
                         use_container_width=True, hide_index=True)
            ok = sum(1 for r in st.session_state["lote_resumo"] if r["Status"] == "ok")
            falhas = len(st.session_state["lote_resumo"]) - ok
            st.caption(f"{ok} linha(s) gerada(s)" + (f" · {falhas} com erro" if falhas else "")
                       + f" · {st.session_state.get('lote_n', 0)} arquivo(s) no zip.")
            if st.session_state.get("lote_zip"):
                st.download_button(f"⬇  Baixar lote ({st.session_state['lote_n']} peças .dxf)",
                                   data=st.session_state["lote_zip"], file_name="lote_pecas.zip",
                                   mime="application/zip", use_container_width=True)

    # ------------------------------------------------- ProMobile (importar lista)
    elif secao == "promobile":
        st.caption("Importe a lista do **ProMobile** (CSV ou Excel), informe o raio e gere os **IGS** "
                   "de cada perfil + os **adesivos** de identificação por obra (com código de barras).")
        up = st.file_uploader("Lista do ProMobile (.csv) ou relatório da máquina (.xlsx)",
                              type=["csv", "xlsx", "xls"], key="pmb_up")
        pecas = []
        if up is not None:
            try:
                fonte, pecas, rep = ler_lista_arquivo(up)
            except Exception as e:
                st.error("Não consegui ler o arquivo: " + str(e))
        if pecas:
            obra_auto = pecas[0].get("obra", "")
            st.success(f"{len(pecas)} peça(s) lida(s). Obra: **{obra_auto or '—'}**")
            df = pd.DataFrame([{"ID": p["id"], "Perfil": p["rotulo"], "Tipo": p["tipo"],
                                "Comp (mm)": p["comprimento"], "Qtd": p["qtd"],
                                "Esp (mm)": p.get("esp") or "", "Material": p["material"],
                                "Módulo": p["modulo"]} for p in pecas])
            st.dataframe(df, use_container_width=True, hide_index=True, height=260)

            st.markdown("**Parâmetros**")
            c1, c2, c3 = st.columns(3)
            raio = c1.number_input("Raio dos cantos do metalon (mm)", 0.0, 20.0, 0.0, 0.5, key="pmb_raio")
            esp_cant = c2.number_input("Espessura da cantoneira (mm)", 0.5, 12.0, 2.0, 0.1, key="pmb_espc",
                                       help="O CSV não traz a espessura da cantoneira; informe a usada.")
            obra = c3.text_input("Obra (sai no adesivo)", obra_auto, key="pmb_obra")
            c4, c5, c6 = st.columns(3)
            ades_w = c4.number_input("Adesivo: largura (mm)", 30.0, 150.0, 80.0, 5.0, key="pmb_aw")
            ades_h = c5.number_input("Adesivo: altura (mm)", 20.0, 100.0, 40.0, 5.0, key="pmb_ah")
            barras = c6.checkbox("Código de barras no adesivo", True, key="pmb_bar")
            cc1, cc2, cc3 = st.columns(3)
            ger_igs = cc1.checkbox("Gerar IGS", True, key="pmb_igs")
            ger_step = cc2.checkbox("Gerar STEP", False, key="pmb_step")
            por_peca = cc3.checkbox("1 IGS por peça (senão, por geometria única)", False, key="pmb_pp")

            if st.button("⚙️  Gerar arquivos (.zip)", type="primary", use_container_width=True):
                for p in pecas:
                    p["obra"] = obra
                import tempfile
                from pathlib import Path
                buf = io.BytesIO()
                resumo = []; n_igs = 0; erros = []
                # agrupa por geometria se não for por peça
                grupos = {}
                for p in pecas:
                    chave = p["id"] if por_peca else (p["tipo"], p["secao"], p.get("esp"), p["comprimento"])
                    grupos.setdefault(chave, []).append(p)
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    if ger_igs or ger_step:
                        with tempfile.TemporaryDirectory() as d:
                            d = Path(d)
                            for chave, grp in grupos.items():
                                p0 = grp[0]; qt = sum(g["qtd"] for g in grp)
                                ids = ",".join(str(g["id"]) for g in grp)
                                try:
                                    r = promobile.solido(p0, raio_metalon=raio, esp_cantoneira=esp_cant)
                                    nome = r.name if por_peca else f"{promobile._slug(p0['rotulo'])}_{p0['comprimento']:g}mm_x{qt}"
                                    if ger_igs:
                                        fp = d / f"{nome}.igs"; exporters.to_iges(r, fp)
                                        z.write(fp, f"{promobile._slug(obra) or 'obra'}/IGS/{nome}.igs"); n_igs += 1
                                    if ger_step:
                                        fp = d / f"{nome}.step"; exporters.to_step(r, fp)
                                        z.write(fp, f"{promobile._slug(obra) or 'obra'}/STEP/{nome}.step")
                                except Exception as e:
                                    erros.append(f"{p0['rotulo']} {p0['comprimento']:g}: {str(e)[:60]}")
                    # adesivos
                    try:
                        pdf = promobile.etiqueta_pdf(pecas, tamanho=(ades_w, ades_h), barras=barras)
                        z.writestr(f"{promobile._slug(obra) or 'obra'}/adesivos.pdf", pdf)
                    except Exception as e:
                        erros.append("adesivos: " + str(e)[:60])
                    # resumo CSV
                    linhas = ["ID;Perfil;Tipo;Comprimento_mm;Qtd;Espessura_mm;Material;Modulo;Obra;CodItem"]
                    for p in pecas:
                        linhas.append(f"{p['id']};{p['rotulo']};{p['tipo']};{p['comprimento']:g};{p['qtd']};"
                                       f"{p.get('esp') or ''};{p['material']};{p['modulo']};{obra};{p.get('cod_item','')}")
                    z.writestr(f"{promobile._slug(obra) or 'obra'}/resumo.csv",
                               "\n".join(linhas).encode("utf-8-sig"))
                st.session_state["pmb_zip"] = buf.getvalue()
                st.session_state["pmb_msg"] = (f"{len(grupos)} geometria(s) · {n_igs} IGS gerado(s) · "
                                               f"{sum(p['qtd'] for p in pecas)} adesivo(s).")
                st.session_state["pmb_err"] = erros
            if st.session_state.get("pmb_zip"):
                st.success(st.session_state.get("pmb_msg", ""))
                if st.session_state.get("pmb_err"):
                    st.warning("Alguns itens falharam:\n- " + "\n- ".join(st.session_state["pmb_err"][:8]))
                st.download_button("⬇  Baixar pacote da obra (.zip)", data=st.session_state["pmb_zip"],
                                   file_name=f"{promobile._slug(obra) or 'obra'}_promobile.zip",
                                   mime="application/zip", use_container_width=True)
            st.caption("**IGS é geometria 3D (CadQuery)** — confira o arquivo na sua máquina antes de produzir. "
                       "Adesivos, resumo e a leitura da lista são validados aqui.")
        else:
            st.info("Suba a lista do ProMobile (.csv ou .xlsx) para começar.")

    # ------------------------------------------------- Produção (fila de corte)
    elif secao == "producao":
        st.caption("Fila de corte por **ordem de produção**: suba a lista (ProMobile ou nesting em "
                   "CSV/Excel), monte a fila e o operador imprime a etiqueta de cada peça **na ordem do "
                   "corte**, marcando como concluída para avançar.")
        up = st.file_uploader("Lista de peças (.csv ou .xlsx) — ProMobile ou relatório da máquina",
                              type=["csv", "xlsx", "xls"], key="prod_up")
        pecas = []; rep = None; fonte = None
        if up is not None:
            try:
                fonte, pecas, rep = ler_lista_arquivo(up)
                if fonte == "maquina":
                    st.success("Relatório da máquina lido — o **nesting já está pronto**; dá para usar a "
                               "ordem de corte das barras.")
            except Exception as e:
                st.error("Não consegui ler o arquivo: " + str(e))

        cfg1, cfg2, cfg3 = st.columns(3)
        ades_w = cfg1.number_input("Etiqueta: largura (mm)", 30.0, 150.0, 80.0, 5.0, key="prod_aw")
        ades_h = cfg2.number_input("Etiqueta: altura (mm)", 20.0, 100.0, 40.0, 5.0, key="prod_ah")
        barras = cfg3.checkbox("Código de barras", True, key="prod_bar")

        if pecas:
            if fonte == "maquina" and rep and rep.get("barras"):
                st.markdown("**Opção A — usar a ordem do nesting da máquina (recomendado):**")
                segm = nest_report.fila_producao(rep)
                st.caption(f"{len(segm)} peças, organizadas por barra na ordem de corte do relatório.")
                if st.button("🏭  Montar fila NA ORDEM DA MÁQUINA", type="primary", use_container_width=True):
                    fila = []
                    for it in segm:
                        fila.append({"seq": it["seq"], "id": it["id"], "rotulo": f"{it['perfil']} {it['comprimento']:g}mm",
                                     "comprimento": it["comprimento"], "obra": "",
                                     "modulo": f"Barra {it['barra']}", "material": "",
                                     "cod": it.get("nome") or it["id"], "unidade": "1/1",
                                     "status": "pendente"})
                    st.session_state["prod_fila"] = fila; st.rerun()
                st.markdown("---")
                st.markdown("**Opção B — montar manualmente (editar ordem):**")
            else:
                st.markdown("**1) Confira a ordem** (edite a coluna *Ordem* se precisar) e monte a fila:")
            base = pd.DataFrame([{"Ordem": i + 1, "ID": p["id"], "Peça": p["rotulo"],
                                  "Comp (mm)": p["comprimento"], "Qtd": p["qtd"],
                                  "Obra": p.get("obra", "")} for i, p in enumerate(pecas)])
            ed = st.data_editor(base, hide_index=True, use_container_width=True, key="prod_ed",
                                column_config={"Ordem": st.column_config.NumberColumn(min_value=1, step=1)})
            if st.button("▶️  Montar fila de produção", use_container_width=True):
                ordem = list(ed["Ordem"]) if "Ordem" in ed else list(range(1, len(pecas) + 1))
                idx_ord = sorted(range(len(pecas)), key=lambda k: (ordem[k], k))
                fila = []; seq = 0
                for k in idx_ord:
                    p = pecas[k]
                    for u in range(int(p["qtd"])):
                        seq += 1
                        fila.append({"seq": seq, "id": p["id"], "rotulo": p["rotulo"],
                                     "comprimento": p["comprimento"], "obra": p.get("obra", ""),
                                     "modulo": p.get("modulo", ""), "material": p.get("material", ""),
                                     "cod": p.get("cod_item") or p.get("id"),
                                     "unidade": f"{u + 1}/{int(p['qtd'])}", "status": "pendente"})
                st.session_state["prod_fila"] = fila
                st.rerun()

        fila = st.session_state.get("prod_fila")
        if fila:
            st.divider()
            n = len(fila); feitas = sum(1 for f in fila if f["status"] == "concluida")
            st.markdown("**2) Produção**")
            st.progress(feitas / n if n else 0.0, text=f"{feitas} / {n} peças concluídas")
            atual_i = next((i for i, f in enumerate(fila) if f["status"] == "pendente"), None)

            def _item_etq(f):
                linhas = [f["rotulo"], f"Comp.: {f['comprimento']:g} mm   ·   peça {f['unidade']}"]
                if f.get("micro_junta"):
                    linhas.append("⚠ MICRO-JUNTA (não cortar 100%)")
                if f.get("modulo"):
                    linhas.append(f"Módulo: {f['modulo']}")
                if f.get("material"):
                    linhas.append(f["material"])
                return {"titulo": f.get("obra", ""), "destaque": f"#{f['seq']}  PEÇA {f['id']}",
                        "linhas": linhas, "codigo": f.get("cod", ""), "qtd": 1}

            if atual_i is None:
                st.success("✅ Todas as peças desta fila foram concluídas!")
            else:
                f = fila[atual_i]
                with st.container(border=True):
                    st.markdown(f"### ➡️ Cortando agora: #{f['seq']} de {n}")
                    cA, cB = st.columns([2, 1])
                    cA.markdown(f"**Peça {f['id']}** — {f['rotulo']}  \n"
                                f"Comprimento: **{f['comprimento']:g} mm** · unidade {f['unidade']}"
                                + (f"  \nMódulo: {f['modulo']}" if f.get("modulo") else "")
                                + (f"  \nObra: {f['obra']}" if f.get("obra") else ""))
                    pdf_atual = promobile.etiqueta_generica_pdf([_item_etq(f)], tamanho=(ades_w, ades_h), barras=barras)
                    cB.download_button("🖨️  Imprimir etiqueta", data=pdf_atual,
                                       file_name=f"etiqueta_{f['seq']:03d}_{f['id']}.pdf",
                                       mime="application/pdf", use_container_width=True, key=f"prt_{f['seq']}")
                    if cB.button("✅  Concluída → próxima", type="primary", use_container_width=True, key=f"ok_{f['seq']}"):
                        fila[atual_i]["status"] = "concluida"; st.rerun()
                # próximas
                prox = [x for x in fila if x["status"] == "pendente"][1:4]
                if prox:
                    st.caption("Próximas: " + "  →  ".join(f"#{x['seq']} {x['rotulo']} ({x['comprimento']:g})" for x in prox))

            ce1, ce2, ce3 = st.columns(3)
            todas = promobile.etiqueta_generica_pdf([_item_etq(f) for f in fila], tamanho=(ades_w, ades_h), barras=barras)
            ce1.download_button("⬇  Todas as etiquetas (ordem)", data=todas, file_name="etiquetas_producao.pdf",
                                mime="application/pdf", use_container_width=True)
            restantes = [f for f in fila if f["status"] == "pendente"]
            if restantes:
                pend = promobile.etiqueta_generica_pdf([_item_etq(f) for f in restantes], tamanho=(ades_w, ades_h), barras=barras)
                ce2.download_button("⬇  Só as pendentes", data=pend, file_name="etiquetas_pendentes.pdf",
                                    mime="application/pdf", use_container_width=True)
            if ce3.button("🔄  Reiniciar fila", use_container_width=True):
                st.session_state.pop("prod_fila", None); st.rerun()

            with st.expander("Ver fila completa / status"):
                st.dataframe(pd.DataFrame([{"#": f["seq"], "ID": f["id"], "Peça": f["rotulo"],
                                            "Comp (mm)": f["comprimento"], "Unid.": f["unidade"],
                                            "Status": "✅ ok" if f["status"] == "concluida" else "⏳ pendente"}
                                           for f in fila]),
                             hide_index=True, use_container_width=True, height=280)
        elif not pecas:
            st.info("Suba a lista de peças (na ordem de corte) para montar a fila de produção.")

    # ------------------------------------------------- Nesting de tubos (linear)
    elif secao == "nesttubo":
        st.caption("Distribui as peças nas **barras de estoque** (nesting linear), aproveitando ao "
                   "máximo e marcando **micro-juntas** nas peças curtas da ponta — para a máquina mover "
                   "o tubo sem cortá-lo por completo.")
        itens = st.session_state.setdefault("nest_tubo_itens", [])

        tabD, tabI, tabG = st.tabs(["✍️ Digitar/editar", "📥 Importar lista", "🔧 Do gerador de peças"])
        with tabD:
            st.caption("Edite a lista de peças (perfil, comprimento em mm e quantidade).")
            base = pd.DataFrame(itens if itens else [{"Perfil": "Metalon 40x20", "Comprimento (mm)": 2650, "Qtd": 4}])
            base = base.rename(columns={"perfil": "Perfil", "comprimento": "Comprimento (mm)", "qtd": "Qtd"})
            for col, dv in [("Perfil", ""), ("Comprimento (mm)", 0), ("Qtd", 1)]:
                if col not in base:
                    base[col] = dv
            ed = st.data_editor(base[["Perfil", "Comprimento (mm)", "Qtd"]], num_rows="dynamic",
                                use_container_width=True, key="nt_ed",
                                column_config={"Comprimento (mm)": st.column_config.NumberColumn(min_value=0.0, step=10.0),
                                               "Qtd": st.column_config.NumberColumn(min_value=1, step=1)})
            if st.button("💾 Salvar lista", use_container_width=True):
                novos = []
                for _, r in ed.iterrows():
                    if float(r["Comprimento (mm)"] or 0) > 0:
                        novos.append({"perfil": str(r["Perfil"]).strip() or "Perfil",
                                      "comprimento": float(r["Comprimento (mm)"]), "qtd": int(r["Qtd"] or 1)})
                st.session_state["nest_tubo_itens"] = novos; st.rerun()
        with tabI:
            st.caption("Suba uma lista (CSV do ProMobile ou Excel da máquina) e some ao nesting.")
            up = st.file_uploader("Lista (.csv/.xlsx)", type=["csv", "xlsx", "xls"], key="nt_up")
            if up is not None:
                try:
                    fonte, pl, rep = ler_lista_arquivo(up)
                    if fonte == "maquina":
                        st.info(f"Relatório da máquina: {len(pl)} tipo(s) de peça.")
                    else:
                        st.info(f"{len(pl)} peça(s) na lista.")
                    if st.button("➕ Adicionar ao nesting", type="primary"):
                        for p in pl:
                            itens.append({"perfil": p["perfil"], "comprimento": p["comprimento"], "qtd": p["qtd"]})
                        st.session_state["nest_tubo_itens"] = itens; st.success("Adicionadas."); st.rerun()
                except Exception as e:
                    st.error("Erro ao ler: " + str(e))
        with tabG:
            enviados = st.session_state.get("nest_tubo_lista", [])
            if enviados:
                st.caption(f"{len(enviados)} peça(s) enviada(s) do gerador de tubos:")
                st.dataframe(pd.DataFrame(enviados), hide_index=True, use_container_width=True)
                cc1, cc2 = st.columns(2)
                if cc1.button("➕ Adicionar todas ao nesting", type="primary", use_container_width=True):
                    itens.extend(enviados); st.session_state["nest_tubo_itens"] = itens
                    st.session_state["nest_tubo_lista"] = []; st.success("Adicionadas."); st.rerun()
                if cc2.button("🗑️ Limpar enviadas", use_container_width=True):
                    st.session_state["nest_tubo_lista"] = []; st.rerun()
            else:
                st.info("Gere um tubo na aba **Tubo com furos** e use *Enviar para o nesting de tubos*.")

        st.divider()
        if itens:
            st.markdown(f"**Lista atual: {sum(int(i['qtd']) for i in itens)} peça(s)**  ·  "
                        + ", ".join(f"{i['qtd']}×{i['perfil']} {i['comprimento']:g}" for i in itens[:6])
                        + (" …" if len(itens) > 6 else ""))
            if st.button("🧹 Limpar lista do nesting"):
                st.session_state["nest_tubo_itens"] = []; st.session_state.pop("nest_plano", None); st.rerun()

        st.markdown("**Estoque e máquina**")
        s1, s2, s3, s4 = st.columns(4)
        barra = s1.number_input("Comprimento da barra (mm)", 500.0, 12000.0, 6000.0, 100.0, key="nt_barra")
        kerf = s2.number_input("Corte / kerf (mm)", 0.0, 20.0, 3.0, 0.5, key="nt_kerf")
        zona = s3.number_input("Zona de micro-junta (mm)", 0.0, 2000.0, 700.0, 50.0, key="nt_zona",
                               help="Últimos X mm da barra onde peças curtas recebem micro-junta.")
        minmj = s4.number_input("Peça curta até (mm)", 0.0, 2000.0, 700.0, 50.0, key="nt_minmj",
                                help="Peças menores que isso, caindo na zona, recebem micro-junta.")

        if st.button("⚙️  Calcular nesting", type="primary", use_container_width=True, disabled=not itens):
            plano = nesting_linear.empacotar(itens, barra=barra, kerf=kerf, zona_mj=zona, min_mj=minmj)
            st.session_state["nest_plano"] = plano
            st.session_state["nest_params"] = (barra, zona)

        plano = st.session_state.get("nest_plano")
        if plano:
            barra0, zona0 = st.session_state.get("nest_params", (barra, zona))
            r = nesting_linear.resumo(plano, barra=barra0)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Barras necessárias", r["barras"])
            m2.metric("Peças", r["pecas"])
            m3.metric("Aproveitamento", f"{r['aproveitamento']*100:.1f}%")
            m4.metric("Micro-juntas", r["micro_juntas"])
            st.caption(f"Sobra total: ~{r['sobra_total_m']:.2f} m (somando as pontas de todas as barras).")
            try:
                st.image(nesting_linear.plano_png(plano, barra=barra0, zona_mj=zona0),
                         caption="Plano de corte (faixa rosa = zona de micro-junta · MJ = peça presa)",
                         use_container_width=True)
            except Exception:
                pass
            for p in plano:
                if p.get("impossiveis"):
                    st.warning(f"{p['perfil']}: {len(p['impossiveis'])} peça(s) maiores que a barra — ignoradas.")
            # plano em CSV
            linhas = ["Perfil;Barra;Sequencia;Comprimento_mm;Micro_junta;Inicio_mm;Fim_mm"]
            for it in nesting_linear.sequencia_corte(plano):
                linhas.append(f"{it['perfil']};{it['barra']};{it['seq']};{it['comprimento']:g};"
                               f"{'SIM' if it['micro_junta'] else 'nao'};{it['ini']:g};{it['fim']:g}")
            csv_plano = "\n".join(linhas).encode("utf-8-sig")
            cD1, cD2 = st.columns(2)
            cD1.download_button("⬇  Plano de corte (CSV)", data=csv_plano, file_name="plano_corte_tubos.csv",
                                mime="text/csv", use_container_width=True)
            if cD2.button("🏭 Enviar para Produção (na ordem)", use_container_width=True):
                seq = nesting_linear.sequencia_corte(plano)
                fila = []
                for it in seq:
                    fila.append({"seq": it["seq"], "id": it["id"] or f"{it['barra']}",
                                 "rotulo": f"{it['perfil']} {it['comprimento']:g}mm",
                                 "comprimento": it["comprimento"], "obra": "", "modulo": f"Barra {it['barra']}",
                                 "material": "", "cod": it["id"] or f"{it['perfil']}-{it['comprimento']:g}",
                                 "unidade": "1/1", "micro_junta": it["micro_junta"], "status": "pendente"})
                st.session_state["prod_fila"] = fila
                st.success("Fila enviada! Abra a aba **Produção** para imprimir as etiquetas na ordem de corte.")

    # ------------------------------------------------- Nesting (chapa única)
    elif secao == "nesting":
        st.caption("Encaixa todas as peças da biblioteca (até 10 modelos) numa **chapa só** e gera um "
                   "único DXF. O encaixe é por caixa, em fileiras (prático para flanges).")
        lib = st.session_state.get("flange_lib", [])
        if not lib:
            st.info("Sua biblioteca está vazia. Crie peças na aba **Flanges (DXF inox)** e clique "
                    "em **Adicionar à biblioteca**.")
        else:
            st.markdown(f"**Biblioteca ({len(lib)}/10)**")
            for i, it in enumerate(lib):
                pr = it["prims"]
                bw, bh = pr["bbox"]
                cc1, cc2, cc3 = st.columns([3, 1, 1])
                cc1.write(f"**Peça {i+1}** — {it.get('name','peça')}  ·  {bw:g}×{bh:g} mm")
                nq = cc2.number_input("Qtd", 1, 999, int(it["qtd"]), 1, key=f"nq_{i}")
                lib[i]["qtd"] = int(nq)
                if cc3.button("Remover", key=f"rm_{i}"):
                    lib.pop(i); st.rerun()
            if st.button("🗑 Limpar biblioteca", use_container_width=True):
                st.session_state["flange_lib"] = []; st.rerun()

            st.markdown("**Chapa**")
            s1, s2, s3 = st.columns(3)
            sheet_w = s1.number_input("Largura útil da chapa (mm)", 100.0, 6000.0, 1200.0, 10.0, key="nest_w")
            gap = s2.number_input("Espaço entre peças (mm)", 0.0, 100.0, 8.0, 1.0, key="nest_gap")
            margin = s3.number_input("Margem da borda (mm)", 0.0, 100.0, 12.0, 1.0, key="nest_m")
            if st.button("🧩 GERAR NESTING", type="primary", use_container_width=True):
                pares = [(it["prims"], it["qtd"]) for it in lib]
                placed, sw, sh, ap = flanges.nest(pares, sheet_w=sheet_w, gap=gap, margin=margin)
                m1, m2, m3 = st.columns(3)
                m1.metric("Peças encaixadas", len(placed))
                m2.metric("Chapa usada", f"{sw:g} × {sh:.0f} mm")
                m3.metric("Aproveitamento", f"{ap:.1f}%")
                st.image(flanges.nest_preview_png(placed, sw, sh), use_container_width=True)
                st.download_button("⬇  Baixar arquivos do nesting (.zip)",
                                   data=zip_flange("nesting_flanges", flanges.nest_dxf_bytes(placed),
                                                   flanges.nest_preview_png(placed, sw, sh)),
                                   file_name="nesting_flanges.zip", mime="application/zip",
                                   use_container_width=True)

    # ------------------------------------------------- Gerar etiqueta
    elif secao == "etiqueta":
        st.caption("Gera os **adesivos/etiquetas por peça** de uma ordem de produção (1 adesivo por "
                   "página, no tamanho físico escolhido). Cada etiqueta traz descrição/medida, "
                   "material, data e a OP — e o cliente, se você marcar.")
        with st.container(border=True):
            c1, c2 = st.columns(2)
            ordem = c1.text_input("Ordem de produção (OP)", "", placeholder="ex.: 2026-0457")
            hoje = datetime.date.today().strftime("%d/%m/%Y")
            data_lbl = c2.text_input("Data", hoje)
            c3, c4 = st.columns([1, 2])
            tam_lbl = c3.selectbox("Tamanho da etiqueta", list(etiquetas.TAMANHOS.keys()) + ["Personalizado"])
            inc_cli = c4.checkbox("Incluir nome do cliente", value=False)
            cliente = ""
            if inc_cli:
                cliente = c4.text_input("Nome do cliente", "", placeholder="ex.: Marcenaria Duarte")
            if tam_lbl == "Personalizado":
                cp1, cp2 = st.columns(2)
                tw = cp1.number_input("Largura (mm)", 20.0, 300.0, 80.0, 1.0, key="etq_tw")
                th = cp2.number_input("Altura (mm)", 15.0, 200.0, 50.0, 1.0, key="etq_th")
                tamanho = (tw, th)
            else:
                tamanho = etiquetas.TAMANHOS[tam_lbl]

            st.markdown("**Peças da ordem** (uma linha por peça; a coluna Qtd define quantos adesivos)")
            base_df = pd.DataFrame(
                [{"Descrição / medida": "", "Material": "", "Qtd": 1}])
            edit = st.data_editor(
                base_df, num_rows="dynamic", use_container_width=True, key="etq_itens",
                column_config={
                    "Descrição / medida": st.column_config.TextColumn(width="large"),
                    "Material": st.column_config.TextColumn(),
                    "Qtd": st.column_config.NumberColumn(min_value=1, step=1, default=1),
                })
            if st.button("GERAR ETIQUETAS", type="primary", use_container_width=True):
                itens = []
                for _, row in edit.iterrows():
                    desc = str(row.get("Descrição / medida", "") or "").strip()
                    if not desc:
                        continue
                    itens.append({"descricao": desc,
                                  "material": str(row.get("Material", "") or "").strip(),
                                  "qtd": int(row.get("Qtd", 1) or 1)})
                if not itens:
                    st.warning("Preencha ao menos uma peça (descrição).")
                else:
                    pdf = etiquetas.gerar_etiquetas_pdf(
                        itens, tamanho=tamanho, data=data_lbl, ordem=ordem,
                        cliente=(cliente if inc_cli else None))
                    n = sum(it["qtd"] for it in itens)
                    st.success(f"{n} adesivo(s) gerado(s) em {len(itens)} peça(s).")
                    fn = f"etiquetas_OP{ordem or 'sem'}_{tamanho[0]:g}x{tamanho[1]:g}.pdf"
                    st.download_button("⬇  Baixar etiquetas (.pdf)", data=pdf, file_name=fn,
                                       mime="application/pdf", use_container_width=True)

    # ------------------------------------------------- Ajuda
    elif secao == "ajuda":
        _man = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MANUAL_METALLO_IA.pdf")
        if os.path.exists(_man):
            st.download_button("📘  Baixar o MANUAL DO USUÁRIO (PDF)", data=open(_man, "rb").read(),
                               file_name="MANUAL_METALLO_IA.pdf", mime="application/pdf",
                               use_container_width=True, key="dl_manual")
        with st.container(border=True):
            st.markdown(
                "**Como usar**\n\n"
                "1. No início, toque na seção desejada.\n"
                "2. Preencha as medidas (tudo em milímetros).\n"
                "3. Clique em GERAR e baixe o .zip com os arquivos para o laser "
                "(IGES/STEP/DXF) e o desenho técnico em PDF.\n\n"
                "**Tempo de corte (laser 3000 W)**\n\n"
                "- Toda peça gerada já mostra uma estimativa de tempo de corte "
                "(baseada em Aço-carbono e na espessura da peça).\n"
                "- Na aba **⏱ Tempo de corte** você pode: importar um **DXF** e calcular "
                "comprimento de corte, peso e tempo; fazer um **cálculo manual**; e consultar "
                "a **tabela de parâmetros 3000 W** (velocidade, gás, bico, foco) por material.\n"
                "- Informe o custo de máquina (R$/min) para estimar o custo do corte.\n\n"
                "**Peças planas e DXF**\n\n"
                "- **✍️ Peça por descrição**: gere retângulos, discos, anéis/arruelas e polígonos "
                "com furação em linha, em círculo (PCD), em grade ou nos cantos.\n"
                "- **⬛ Flanges** e **🧩 Nesting**: monte uma biblioteca de peças e encaixe tudo numa chapa.\n"
                "- **🏷️ Gerar etiqueta**: monte a lista de peças da OP, escolha o tamanho do adesivo "
                "(60×40, 150×50 ou personalizado) e gere um PDF com 1 adesivo por peça (descrição, "
                "material, data, OP e, se marcar, o cliente).\n\n"
                "Use o botão Início para voltar ao menu."
            )
