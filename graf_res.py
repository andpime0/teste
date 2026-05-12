import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sqlite3

st.set_page_config(
    page_title="BestCare | José Oliveira",
    page_icon="🫀",
    layout="wide",
)

# ============================================================
# DADOS CLÍNICOS DO JOSÉ (fixos — caso de estudo)
# ============================================================
PACIENTE = {
    "nome": "José Oliveira",
    "idade": 55,
    "sexo": "Masculino",
    "altura_cm": 174,
    "peso_kg": 88,
    "historial": "Pós-EAM (4 meses) com colocação de stent. Diabetes tipo II.",
    "medicacao": ["Beta-bloqueador (Bisoprolol 5mg)", "Estatina (Atorvastatina 40mg)", "Metformina 1000mg"],
    "fc_max_teste": 145,
    "fc_repouso_inicial": 78,
    "vo2_inicial": 27.2,
    "vo2_previsto": 35.4,
    "hba1c_inicial": 7.8,
    "data_inicio": datetime(2026, 2, 16),
}

PROGRAMA_SEMANAS = 12
SESSOES_POR_SEMANA = 3

# ============================================================
# GERAÇÃO DE DADOS FICTÍCIOS DE EVOLUÇÃO
# ============================================================
@st.cache_data
def gerar_evolucao_jose():
    """Gera 36 sessões com evolução fisiológica realista."""
    np.random.seed(42)
    sessoes = []
    data_atual = PACIENTE["data_inicio"]

    for sem in range(PROGRAMA_SEMANAS):
        fator = sem / (PROGRAMA_SEMANAS - 1)  # 0 → 1
        fc_repouso_base = PACIENTE["fc_repouso_inicial"] - 10 * fator
        vo2_base = PACIENTE["vo2_inicial"] + 6.5 * fator
        fai_base = ((PACIENTE["vo2_previsto"] - vo2_base) / PACIENTE["vo2_previsto"]) * 100
        hba1c_base = PACIENTE["hba1c_inicial"] - 1.0 * fator

        for s in range(SESSOES_POR_SEMANA):
            ruido_fc = np.random.normal(0, 2)
            ruido_pse = np.random.choice([-1, 0, 0, 0, 1])
            intensidade_pct = 0.50 + 0.25 * fator + np.random.normal(0, 0.02)
            
            fc_durante = int(
                fc_repouso_base
                + (PACIENTE["fc_max_teste"] - fc_repouso_base) * intensidade_pct
                + ruido_fc
            )
            duracao = int(25 + 20 * fator)

            pa_sis_antes = int(128 + np.random.normal(0, 4))
            pa_dia_antes = int(82 + np.random.normal(0, 3))
            pa_sis_apos = pa_sis_antes + int(np.random.normal(8, 3))
            pa_dia_apos = pa_dia_antes + int(np.random.normal(2, 2))

            glic_antes = int(np.random.normal(135 - 20 * fator, 15))
            glic_apos = glic_antes - int(np.random.normal(25, 8))

            pse_durante = max(11, min(15, int(12 + fator * 1.5 + ruido_pse)))
            pse_apos = max(10, pse_durante - np.random.choice([1, 2]))

            sintomas_possiveis = ["Nenhum"] * 18 + ["Fadiga ligeira", "Falta de ar leve"]
            sintoma = np.random.choice(sintomas_possiveis)

            sessoes.append({
                "data": data_atual,
                "semana": sem + 1,
                "sessao_n": len(sessoes) + 1,
                "tipo": "Aeróbio contínuo" if sem < 4 else ("Aeróbio + Força" if sem < 8 else "Intervalado moderado"),
                "duracao_min": duracao,
                "fc_repouso": int(fc_repouso_base + np.random.normal(0, 1.5)),
                "fc_media_durante": fc_durante,
                "fc_pico": fc_durante + int(np.random.normal(8, 3)),
                "vo2_máx": round(vo2_base + np.random.normal(0, 0.4), 1),
                "fai": round(fai_base + np.random.normal(0, 0.6), 1),
                "pa_antes": f"{pa_sis_antes}/{pa_dia_antes}",
                "pa_apos": f"{pa_sis_apos}/{pa_dia_apos}",
                "glic_antes": max(80, glic_antes),
                "glic_apos": max(70, glic_apos),
                "pse_durante": pse_durante,
                "pse_apos": pse_apos,
                "sintomas": sintoma,
                "hba1c": round(hba1c_base, 2) if s == 0 and sem % 4 == 0 else None,
            })
            data_atual += timedelta(days=2 if s < 2 else 3)

    return pd.DataFrame(sessoes)

# ============================================================
# BASE DE DADOS E PERSISTÊNCIA (SQLITE)
# ============================================================
DB_FILE = "bestcare_jose.db"

def get_db_connection():
    return sqlite3.connect(DB_FILE)

def inicializar_bd():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessoes_jose (
                sessao_n INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                semana INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                duracao_min INTEGER NOT NULL,
                fc_repouso INTEGER NOT NULL,
                fc_media_durante INTEGER NOT NULL,
                fc_pico INTEGER NOT NULL,
                vo2_max REAL NOT NULL,
                fai REAL NOT NULL,
                pa_antes TEXT NOT NULL,
                pa_apos TEXT NOT NULL,
                glic_antes INTEGER NOT NULL,
                glic_apos INTEGER NOT NULL,
                pse_durante INTEGER NOT NULL,
                pse_apos INTEGER NOT NULL,
                sintomas TEXT NOT NULL,
                hba1c REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS glicemias_jose (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                valor INTEGER NOT NULL,
                pode_treinar INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedbacks_jose (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                borg INTEGER NOT NULL,
                sintomas TEXT NOT NULL,
                notas TEXT
            )
        """)

def carregar_sessoes_sql():
    with get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM sessoes_jose ORDER BY sessao_n", conn)
    if df.empty:
        return None
    df = df.rename(columns={"vo2_max": "vo2_máx"})
    df["data"] = pd.to_datetime(df["data"])
    return df

def guardar_sessoes_sql(df):
    df_sql = df.copy().rename(columns={"vo2_máx": "vo2_max"})
    df_sql["data"] = pd.to_datetime(df_sql["data"]).dt.strftime("%Y-%m-%dT%H:%M:%S")
    with get_db_connection() as conn:
        conn.execute("DELETE FROM sessoes_jose")
        df_sql.to_sql("sessoes_jose", conn, if_exists="append", index=False)

def obter_sessoes_jose():
    inicializar_bd()
    df_sql = carregar_sessoes_sql()
    if df_sql is not None:
        return df_sql
    df_novo = gerar_evolucao_jose()
    guardar_sessoes_sql(df_novo)
    return df_novo

df_sessoes = obter_sessoes_jose()

# ============================================================
# GESTÃO DO CLIENTE (FEEDBACKS E GLICEMIAS)
# ============================================================
def carregar_dados_cliente_sql():
    with get_db_connection() as conn:
        df_glic = pd.read_sql_query("SELECT data, valor, pode_treinar FROM glicemias_jose ORDER BY id", conn)
        df_fb = pd.read_sql_query("SELECT data, borg, sintomas, notas FROM feedbacks_jose ORDER BY id", conn)

    glicemias = df_glic.assign(pode_treinar=df_glic["pode_treinar"].astype(bool)).to_dict(orient="records") if not df_glic.empty else []
    feedbacks = []
    if not df_fb.empty:
        feedbacks = [
            {
                "data": r["data"],
                "borg": int(r["borg"]),
                "sintomas": json.loads(r["sintomas"]),
                "notas": r["notas"] or "",
            }
            for _, r in df_fb.iterrows()
        ]
    return {"glicemias": glicemias, "feedbacks": feedbacks}

def guardar_glicemia_sql(data, valor, pode_treinar):
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO glicemias_jose (data, valor, pode_treinar) VALUES (?, ?, ?)",
            (data, valor, int(pode_treinar))
        )

def guardar_feedback_sql(data, borg, sintomas, notas):
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO feedbacks_jose (data, borg, sintomas, notas) VALUES (?, ?, ?, ?)",
            (data, borg, json.dumps(sintomas, ensure_ascii=False), notas)
        )

if "dados_cliente" not in st.session_state:
    st.session_state.dados_cliente = carregar_dados_cliente_sql()

# ============================================================
# NAVEGAÇÃO E INTERFACE
# ============================================================
st.sidebar.markdown("# 🫀 BestCare")
st.sidebar.caption("Reabilitação Funcional")
st.sidebar.markdown("---")

perfil = st.sidebar.radio(
    "Perfil:",
    ["👤 Cliente — José", "🩺 Equipa Clínica"],
    label_visibility="collapsed",
)

# --- CONTEÚDO ---
if perfil == "👤 Cliente — José":
    st.title(f"Olá, {PACIENTE['nome'].split()[0]} 👋")
    
    # Check de Glicemia
    with st.expander("🩺 Check-up de Segurança Pré-Treino", expanded=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            glicose = st.number_input("A sua glicemia agora (mg/dL):", 40, 500, 120)
            if glicose < 100:
                st.error("🔴 Glicemia baixa. Coma 15g de hidratos e espere 15 min.")
                pode_treinar = False
            elif glicose <= 250:
                st.success("🟢 Zona segura. Bom treino!")
                pode_treinar = True
            else:
                st.error("🔴 Não treine hoje. Contacte a equipa.")
                pode_treinar = False
        with c2:
            if st.button("✅ Registar medição", use_container_width=True):
                agora = datetime.now().strftime("%Y-%m-%d %H:%M")
                guardar_glicemia_sql(agora, glicose, pode_treinar)
                st.session_state.dados_cliente = carregar_dados_cliente_sql()
                st.toast("Guardado!")

    # Progresso
    st.subheader("📈 O seu progresso")
    vo2_atual = df_sessoes.iloc[-1]["vo2_máx"]
    fc_rep_atual = df_sessoes.iloc[-1]["fc_repouso"]
    
    col1, col2 = st.columns(2)
    col1.metric("Capacidade aeróbia", f"{vo2_atual:.1f} ml/kg/min")
    col2.metric("Coração em repouso", f"{fc_rep_atual} bpm", delta_color="inverse")

    # Feedback pós-treino
    with st.form("feedback"):
        st.subheader("📝 Como correu o treino?")
        borg = st.select_slider("Esforço (Borg):", options=list(range(6, 21)), value=12)
        sintomas = st.multiselect("Sintomas:", ["Nenhum", "Falta de ar", "Dor no peito", "Tonturas"], default=["Nenhum"])
        notas = st.text_area("Notas:")
        if st.form_submit_button("Enviar"):
            guardar_feedback_sql(datetime.now().strftime("%Y-%m-%d %H:%M"), borg, sintomas, notas)
            st.session_state.dados_cliente = carregar_dados_cliente_sql()
            st.success("Enviado com sucesso!")

else:
    st.title("🩺 Dashboard Clínico")
    # Alertas e Gráficos da Equipa
    st.write(f"Paciente: {PACIENTE['nome']}")
    st.plotly_chart(px.line(df_sessoes, x="data", y="vo2_máx", title="Evolução VO2máx"))
