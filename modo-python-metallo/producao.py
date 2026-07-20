"""
Módulo de produção do Metallo: login por funcionário, persistência (SQLite),
ordem de produção da semana (planilha .csv/.xlsx ou foto .jpg/.png), apontamento
diário, termômetro de meta e relatórios (dia/semana) guardados por 1 ano.

Persistência
------------
Os dados ficam num banco SQLite em DATA_DIR (variável de ambiente) ou ./dados.
No Render, monte um DISCO PERSISTENTE e aponte DATA_DIR para ele — senão o banco
é apagado a cada novo deploy/reinício. Relatórios com mais de 365 dias são
removidos automaticamente.
"""
from __future__ import annotations
import os
import io
import sqlite3
import hashlib
import datetime as _dt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "dados"))
DB_PATH = os.path.join(DATA_DIR, "metallo_producao.db")
RETENCAO_DIAS = 365


# --------------------------------------------------------------------- banco
def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            login TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ordens(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            semana TEXT NOT NULL,
            meta INTEGER NOT NULL,
            fonte TEXT,
            arquivo BLOB,
            arquivo_nome TEXT,
            criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS apontamentos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ordem_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            qtd INTEGER NOT NULL,
            obs TEXT,
            criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS relatorios(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            periodo TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            pdf BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessoes(
            token TEXT PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            expira TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS itens(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ordem_id INTEGER NOT NULL,
            descricao TEXT NOT NULL,
            material TEXT,
            qtd_plan INTEGER DEFAULT 0,
            extra INTEGER DEFAULT 0,
            concluido INTEGER DEFAULT 0,
            obs TEXT DEFAULT '',
            ordem_seq INTEGER DEFAULT 0
        );
        """)
    # migrações para bancos já existentes (ignora se a coluna já existe)
    with _conn() as c:
        for ddl in ("ALTER TABLE itens ADD COLUMN concluido INTEGER DEFAULT 0",
                    "ALTER TABLE itens ADD COLUMN obs TEXT DEFAULT ''",
                    "ALTER TABLE ordens ADD COLUMN meta_dia INTEGER DEFAULT 0"):
            try:
                c.execute(ddl)
            except Exception:
                pass
    prune_relatorios()


# --------------------------------------------------------------------- sessões (manter logado)
def criar_sessao(usuario_id, dias=30):
    token = os.urandom(24).hex()
    exp = (_dt.datetime.now() + _dt.timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as c:
        c.execute("INSERT INTO sessoes(token,usuario_id,expira) VALUES(?,?,?)",
                  (token, usuario_id, exp))
    return token


def usuario_por_token(token):
    if not token:
        return None
    with _conn() as c:
        s = c.execute("SELECT * FROM sessoes WHERE token=?", (token,)).fetchone()
        if not s or s["expira"] < _agora():
            if s:
                c.execute("DELETE FROM sessoes WHERE token=?", (token,))
            return None
        u = c.execute("SELECT id,nome,login FROM usuarios WHERE id=?", (s["usuario_id"],)).fetchone()
    return dict(u) if u else None


def encerrar_sessao(token):
    if token:
        with _conn() as c:
            c.execute("DELETE FROM sessoes WHERE token=?", (token,))


# --------------------------------------------------------------------- auth
def _hash(senha, salt):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"),
                               salt.encode("utf-8"), 200_000).hex()


def criar_usuario(nome, login, senha):
    login = login.strip().lower()
    if not nome.strip() or not login or len(senha) < 4:
        return False, "Preencha nome, login e senha (mín. 4 caracteres)."
    salt = os.urandom(16).hex()
    try:
        with _conn() as c:
            c.execute("INSERT INTO usuarios(nome,login,senha_hash,salt,criado_em) VALUES(?,?,?,?,?)",
                      (nome.strip(), login, _hash(senha, salt), salt, _agora()))
        return True, "Funcionário cadastrado."
    except sqlite3.IntegrityError:
        return False, "Esse login já existe."


def autenticar(login, senha):
    login = (login or "").strip().lower()
    with _conn() as c:
        u = c.execute("SELECT * FROM usuarios WHERE login=?", (login,)).fetchone()
    if u and _hash(senha, u["salt"]) == u["senha_hash"]:
        return {"id": u["id"], "nome": u["nome"], "login": u["login"]}
    return None


def _agora():
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------- ordens / apontamentos
def criar_ordem(usuario_id, semana, meta, fonte, arquivo_bytes=None, arquivo_nome=None, itens=None):
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO ordens(usuario_id,semana,meta,fonte,arquivo,arquivo_nome,criado_em) "
            "VALUES(?,?,?,?,?,?,?)",
            (usuario_id, semana, int(meta), fonte,
             sqlite3.Binary(arquivo_bytes) if arquivo_bytes else None,
             arquivo_nome, _agora()))
        oid = cur.lastrowid
    if itens:
        definir_itens(oid, itens)
    return oid


def atualizar_meta(ordem_id, meta):
    with _conn() as c:
        c.execute("UPDATE ordens SET meta=? WHERE id=?", (int(meta), ordem_id))


def atualizar_meta_dia(ordem_id, meta_dia):
    with _conn() as c:
        c.execute("UPDATE ordens SET meta_dia=? WHERE id=?", (int(meta_dia), ordem_id))


# --------------------------------------------------------------------- itens (peças/atividades)
def definir_itens(ordem_id, itens):
    """Substitui a lista de itens da ordem (descricao, material, qtd_plan, extra, concluido)."""
    with _conn() as c:
        c.execute("DELETE FROM itens WHERE ordem_id=?", (ordem_id,))
        for i, it in enumerate(itens):
            desc = str(it.get("descricao", "") or "").strip()
            if not desc:
                continue
            c.execute("INSERT INTO itens(ordem_id,descricao,material,qtd_plan,extra,concluido,obs,ordem_seq) "
                      "VALUES(?,?,?,?,?,?,?,?)",
                      (ordem_id, desc, str(it.get("material", "") or ""),
                       int(it.get("qtd_plan", 0) or 0), 1 if it.get("extra") else 0,
                       1 if it.get("concluido") else 0, str(it.get("obs", "") or ""), i))


def itens_da_ordem(ordem_id):
    with _conn() as c:
        return c.execute("SELECT * FROM itens WHERE ordem_id=? ORDER BY ordem_seq, id",
                         (ordem_id,)).fetchall()


def ordem_ativa(usuario_id):
    with _conn() as c:
        return c.execute("SELECT * FROM ordens WHERE usuario_id=? ORDER BY id DESC LIMIT 1",
                         (usuario_id,)).fetchone()


def registrar_apontamento(ordem_id, data, qtd, obs=""):
    with _conn() as c:
        c.execute("INSERT INTO apontamentos(ordem_id,data,qtd,obs,criado_em) VALUES(?,?,?,?,?)",
                  (ordem_id, data, int(qtd), obs or "", _agora()))


def apontamentos(ordem_id):
    with _conn() as c:
        return c.execute("SELECT * FROM apontamentos WHERE ordem_id=? ORDER BY data, id",
                         (ordem_id,)).fetchall()


def total_produzido(ordem_id):
    with _conn() as c:
        r = c.execute("SELECT COALESCE(SUM(qtd),0) t FROM apontamentos WHERE ordem_id=?",
                      (ordem_id,)).fetchone()
    return int(r["t"])


def produzido_no_dia(ordem_id, data):
    with _conn() as c:
        r = c.execute("SELECT COALESCE(SUM(qtd),0) t FROM apontamentos WHERE ordem_id=? AND data=?",
                      (ordem_id, data)).fetchone()
    return int(r["t"])


# --------------------------------------------------------------------- relatórios
def salvar_relatorio(usuario_id, tipo, periodo, pdf_bytes):
    with _conn() as c:
        c.execute("INSERT INTO relatorios(usuario_id,tipo,periodo,criado_em,pdf) VALUES(?,?,?,?,?)",
                  (usuario_id, tipo, periodo, _agora(), sqlite3.Binary(pdf_bytes)))
    prune_relatorios()


def listar_relatorios(usuario_id):
    with _conn() as c:
        return c.execute("SELECT id,tipo,periodo,criado_em FROM relatorios "
                         "WHERE usuario_id=? ORDER BY id DESC", (usuario_id,)).fetchall()


def relatorio_pdf(rel_id):
    with _conn() as c:
        r = c.execute("SELECT pdf FROM relatorios WHERE id=?", (rel_id,)).fetchone()
    return bytes(r["pdf"]) if r else None


def prune_relatorios():
    limite = (_dt.date.today() - _dt.timedelta(days=RETENCAO_DIAS)).strftime("%Y-%m-%d")
    with _conn() as c:
        c.execute("DELETE FROM relatorios WHERE substr(criado_em,1,10) < ?", (limite,))


# --------------------------------------------------------------------- termômetro
def termometro_png(meta, produzido, titulo="Meta da semana"):
    meta = max(int(meta), 1)
    frac = max(0.0, min(produzido / meta, 1.0))
    pct = produzido / meta * 100.0
    cor = "#d62728" if frac < 0.34 else ("#f59e0b" if frac < 0.67 else "#2ca02c")

    fig = plt.figure(figsize=(3.2, 5.0), dpi=130)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 64); ax.set_ylim(0, 100)
    ax.set_aspect("equal"); ax.axis("off")
    cx, tw = 30, 12
    yb, yt = 22, 82                      # base e topo do tubo
    rb = 10                              # raio do bulbo
    # contorno (bulbo + tubo)
    ax.add_patch(Circle((cx, yb - rb + 3), rb, fc="white", ec="#333", lw=2, zorder=1))
    ax.add_patch(FancyBboxPatch((cx - tw / 2, yb), tw, yt - yb,
                 boxstyle="round,pad=0,rounding_size=6", fc="white", ec="#333", lw=2, zorder=2))
    # preenchimento
    ax.add_patch(Circle((cx, yb - rb + 3), rb - 3, fc=cor, ec="none", zorder=3))
    ax.add_patch(Rectangle((cx - (tw - 6) / 2, yb), tw - 6, max((yt - yb) * frac, 0.1),
                 fc=cor, ec="none", zorder=3))
    # marcas 0/25/50/75/100%
    for f in (0, .25, .5, .75, 1):
        yy = yb + (yt - yb) * f
        ax.plot([cx + tw / 2, cx + tw / 2 + 3], [yy, yy], color="#333", lw=1)
        ax.text(cx + tw / 2 + 5, yy, f"{int(f*100)}%", fontsize=7.5, va="center")
    # textos
    ax.text(32, 95, titulo, fontsize=10, ha="center", weight="bold")
    ax.text(32, 88, f"{produzido} / {meta}  ({pct:.0f}%)", fontsize=12, ha="center",
            weight="bold", color=cor)
    ax.text(cx, yb - rb + 3, f"{produzido}", fontsize=8, ha="center", va="center",
            color="white", weight="bold", zorder=4)
    buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True); plt.close(fig)
    return buf.getvalue()


# --------------------------------------------------------------------- relatório PDF
def gerar_relatorio_pdf(nome_func, tipo, periodo, meta, produzido, linhas):
    """
    nome_func : nome do funcionário
    tipo      : 'Diário' ou 'Semanal'
    periodo   : texto do período (data ou 'semana X')
    meta      : meta total
    produzido : total produzido no período
    linhas    : lista de (data, qtd, obs)
    """
    from matplotlib.backends.backend_pdf import PdfPages
    buf = io.BytesIO()
    pct = (produzido / meta * 100.0) if meta else 0.0
    with PdfPages(buf) as pp:
        fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))   # A4 paisagem
        ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 297); ax.set_ylim(0, 210); ax.axis("off")
        ax.add_patch(Rectangle((10, 10), 277, 190, fill=False, lw=1.2))
        ax.add_patch(Rectangle((10, 182), 277, 18, fc="black", ec="black"))
        ax.text(15, 191, "METALLO — Relatório de Produção", color="white", fontsize=13,
                va="center", weight="bold")
        ax.text(282, 191, f"{tipo}", color="white", fontsize=11, va="center", ha="right", weight="bold")
        ax.text(15, 173, f"Funcionário: {nome_func}", fontsize=10)
        ax.text(15, 167, f"Período: {periodo}", fontsize=10)
        ax.text(15, 161, f"Gerado em: {_agora()}", fontsize=8.5, color="0.3")
        # resumo
        ax.text(15, 150, f"Meta: {meta}", fontsize=11, weight="bold")
        ax.text(75, 150, f"Produzido: {produzido}", fontsize=11, weight="bold")
        ax.text(150, 150, f"Atingido: {pct:.0f}%", fontsize=11, weight="bold")
        ax.text(220, 150, f"Falta: {max(meta - produzido, 0)}", fontsize=11, weight="bold")
        # barra de progresso
        ax.add_patch(Rectangle((15, 138), 200, 7, fill=False, ec="#333", lw=1))
        ax.add_patch(Rectangle((15, 138), 200 * max(0, min(produzido / meta if meta else 0, 1)), 7,
                     fc=("#2ca02c" if pct >= 67 else "#f59e0b" if pct >= 34 else "#d62728"), ec="none"))
        # tabela de apontamentos
        ax.text(15, 128, "Apontamentos", fontsize=11, weight="bold")
        ax.text(15, 122, "Data", fontsize=9, weight="bold")
        ax.text(60, 122, "Qtd", fontsize=9, weight="bold")
        ax.text(85, 122, "Observações", fontsize=9, weight="bold")
        ax.plot([15, 282], [120, 120], color="0.5", lw=0.6)
        y = 114
        for (d, q, o) in linhas[:22]:
            ax.text(15, y, str(d), fontsize=8.5)
            ax.text(60, y, str(q), fontsize=8.5)
            ax.text(85, y, str(o)[:120], fontsize=8.5)
            y -= 5
        pp.savefig(fig); plt.close(fig)
    return buf.getvalue()
