
import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(APP_DIR, "linha01.db"))
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "troque-este-token")

server = Flask(__name__)

# -------------------------------------------------------------------
# BANCO
# -------------------------------------------------------------------

def conectar():
    return sqlite3.connect(DB_PATH)

def criar_banco():
    with conectar() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS oee_linha01 (
                id TEXT PRIMARY KEY,
                data TEXT,
                turno TEXT,
                plano_diario REAL,
                producao_real REAL,
                absenteismo_pct REAL,
                meta_mensal REAL,
                meta_absenteismo REAL,
                downtime_min REAL,
                oee REAL,
                meta_oee REAL,
                atualizado_em TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS programacao_linha01 (
                id TEXT PRIMARY KEY,
                lote TEXT,
                ordem TEXT,
                modelo TEXT,
                serie TEXT,
                status TEXT,
                total_produzido REAL,
                falta_produzir REAL,
                pendencias TEXT,
                atualizado_em TEXT
            )
        """)

criar_banco()

# -------------------------------------------------------------------
# UTILITÁRIOS
# -------------------------------------------------------------------

def numero(v, default=0):
    if v is None or v == "":
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("%", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return default

def minutos(v):
    if v is None or v == "":
        return 0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if ":" in s:
        try:
            h, m = s.split(":")[:2]
            return int(h) * 60 + int(m)
        except Exception:
            return 0
    return numero(s, 0)

def pct_normalizado(v):
    n = numero(v, 0)
    # Se vier 0.024, converte para 2.4
    if 0 <= n <= 1:
        return n * 100
    return n

def validar_token():
    return request.headers.get("X-Webhook-Token") == WEBHOOK_TOKEN

# -------------------------------------------------------------------
# SITE
# -------------------------------------------------------------------

@server.get("/")
def home():
    return send_from_directory(APP_DIR, "dashboard_linha01.html")

@server.get("/linha01")
def linha01():
    return send_from_directory(APP_DIR, "dashboard_linha01.html")

@server.get("/status")
def status():
    return jsonify({
        "status": "online",
        "dashboard": "Linha 01"
    })

# -------------------------------------------------------------------
# WEBHOOK 1 — OEE / PAINEL 01
# -------------------------------------------------------------------

@server.post("/lark/oee-linha01")
def webhook_oee():
    if not validar_token():
        return jsonify({"status": "erro", "mensagem": "Token incorreto"}), 401

    d = request.get_json(silent=True) or {}

    rid = str(d.get("id", "")).strip()
    if not rid:
        return jsonify({"status": "erro", "mensagem": "ID vazio"}), 400

    with conectar() as con:
        con.execute("""
            INSERT INTO oee_linha01 (
                id, data, turno, plano_diario, producao_real,
                absenteismo_pct, meta_mensal, meta_absenteismo,
                downtime_min, oee, meta_oee, atualizado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data=excluded.data,
                turno=excluded.turno,
                plano_diario=excluded.plano_diario,
                producao_real=excluded.producao_real,
                absenteismo_pct=excluded.absenteismo_pct,
                meta_mensal=excluded.meta_mensal,
                meta_absenteismo=excluded.meta_absenteismo,
                downtime_min=excluded.downtime_min,
                oee=excluded.oee,
                meta_oee=excluded.meta_oee,
                atualizado_em=excluded.atualizado_em
        """, (
            rid,
            str(d.get("data", "")).strip(),
            str(d.get("turno", "")).strip(),
            numero(d.get("plano_diario")),
            numero(d.get("producao_real")),
            pct_normalizado(d.get("absenteismo_pct")),
            numero(d.get("meta_mensal")),
            pct_normalizado(d.get("meta_absenteismo")),
            minutos(d.get("downtime")),
            pct_normalizado(d.get("oee")),
            pct_normalizado(d.get("meta_oee")),
            datetime.now().isoformat(timespec="seconds")
        ))

    return jsonify({"status": "ok", "tipo": "oee", "id": rid})

# -------------------------------------------------------------------
# WEBHOOK 2 — PROGRAMAÇÃO
# -------------------------------------------------------------------

@server.post("/lark/programacao-linha01")
def webhook_programacao():
    if not validar_token():
        return jsonify({"status": "erro", "mensagem": "Token incorreto"}), 401

    d = request.get_json(silent=True) or {}

    rid = str(d.get("id", "")).strip()
    if not rid:
        return jsonify({"status": "erro", "mensagem": "ID vazio"}), 400

    with conectar() as con:
        con.execute("""
            INSERT INTO programacao_linha01 (
                id, lote, ordem, modelo, serie, status,
                total_produzido, falta_produzir, pendencias, atualizado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                lote=excluded.lote,
                ordem=excluded.ordem,
                modelo=excluded.modelo,
                serie=excluded.serie,
                status=excluded.status,
                total_produzido=excluded.total_produzido,
                falta_produzir=excluded.falta_produzir,
                pendencias=excluded.pendencias,
                atualizado_em=excluded.atualizado_em
        """, (
            rid,
            str(d.get("lote", "")).strip(),
            str(d.get("ordem", "")).strip(),
            str(d.get("modelo", "")).strip(),
            str(d.get("serie", "")).strip(),
            str(d.get("status", "")).strip(),
            numero(d.get("total_produzido")),
            numero(d.get("falta_produzir")),
            str(d.get("pendencias", "")).strip(),
            datetime.now().isoformat(timespec="seconds")
        ))

    return jsonify({"status": "ok", "tipo": "programacao", "id": rid})

# -------------------------------------------------------------------
# API USADA PELO HTML
# -------------------------------------------------------------------

@server.get("/api/linha01")
def api_linha01():
    with conectar() as con:
        con.row_factory = sqlite3.Row
        oee = con.execute("""
            SELECT * FROM oee_linha01
            ORDER BY data, turno
        """).fetchall()

        prog = con.execute("""
            SELECT * FROM programacao_linha01
            ORDER BY atualizado_em DESC
            LIMIT 50
        """).fetchall()

    oee = [dict(r) for r in oee]
    prog = [dict(r) for r in prog]

    if not oee:
        # Retorna estrutura vazia; o HTML mantém o fallback visual.
        return jsonify({
            "meta": {
                "linha": "Linha 01",
                "referencia": "Agosto",
                "fonte": "Lark Base — GREE"
            },
            "programacao": [
                {
                    "lote": r["lote"],
                    "ordem": r["ordem"],
                    "modelo": r["modelo"],
                    "serie": r["serie"],
                    "status": r["status"],
                    "totalProduzido": r["total_produzido"],
                    "faltaProduzir": r["falta_produzir"],
                    "pendencias": r["pendencias"]
                } for r in prog
            ]
        })

    plano = sum(r["plano_diario"] or 0 for r in oee)
    producao = sum(r["producao_real"] or 0 for r in oee)
    downtime = sum(r["downtime_min"] or 0 for r in oee)

    abs_vals = [r["absenteismo_pct"] for r in oee if r["absenteismo_pct"] is not None]
    abs_medio = sum(abs_vals) / len(abs_vals) if abs_vals else 0

    meta_mensal_vals = [r["meta_mensal"] for r in oee if (r["meta_mensal"] or 0) > 0]
    meta_mensal = max(meta_mensal_vals) if meta_mensal_vals else 0

    meta_abs_vals = [r["meta_absenteismo"] for r in oee if (r["meta_absenteismo"] or 0) > 0]
    meta_abs = max(meta_abs_vals) if meta_abs_vals else 2.4

    # Agrupa por dia
    por_dia = {}
    por_turno = {}
    for r in oee:
        data = (r["data"] or "").strip()
        turno = (r["turno"] or "Sem turno").strip()

        por_dia.setdefault(data, [0, 0])
        por_dia[data][0] += r["plano_diario"] or 0
        por_dia[data][1] += r["producao_real"] or 0

        por_turno[turno] = por_turno.get(turno, 0) + (r["producao_real"] or 0)

    diario = []
    for data, vals in sorted(por_dia.items()):
        label = data
        # Se vier YYYY-MM-DD, mostra DD/MM
        try:
            dt = datetime.strptime(data[:10], "%Y-%m-%d")
            label = dt.strftime("%d/%m")
        except Exception:
            pass
        diario.append([label, round(vals[0], 2), round(vals[1], 2)])

    turnos = [
        {"nome": k, "valor": round(v, 2)}
        for k, v in sorted(por_turno.items())
    ]

    programacao = [
        {
            "lote": r["lote"],
            "ordem": r["ordem"],
            "modelo": r["modelo"],
            "serie": r["serie"],
            "status": r["status"],
            "totalProduzido": r["total_produzido"],
            "faltaProduzir": r["falta_produzir"],
            "pendencias": r["pendencias"]
        } for r in prog
    ]

    return jsonify({
        "meta": {
            "linha": "Linha 01",
            "referencia": "Agosto",
            "fonte": "Lark Base — GREE"
        },
        "kpis": {
            "planoAcumulado": plano,
            "metaMensal": meta_mensal,
            "producaoAcumulada": producao,
            "absenteismo": abs_medio,
            "metaAbsenteismo": meta_abs,
            "downtimeMin": downtime,
            "downtimeRingPercent": min(100, downtime / 120 * 100) if downtime else 0
        },
        "diario": diario,
        "turnos": turnos,
        "programacao": programacao,
        "programacaoAviso": "Aguardando registros da programação da Linha 01."
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    server.run(host="0.0.0.0", port=port, debug=False)
