import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sqlite3

# Configuração da página
st.set_page_config(
    page_title="BestCare | José Oliveira",
    page_icon="🫀",
    layout="wide",
)

# ============================================================
# DADOS CLÍNICOS E CONSTANTES
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
DB_FILE = "bestcare_jose.db"

# ============================================================
# FUNÇÕES DE BASE DE DADOS (SQLITE)
# ============================================================
def get_db_connection():
    return sqlite3.connect(DB_FILE)

def inicializar_bd():
    with get_db_connection() as conn:
        # Tabela de Sessões
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessoes_jose (
                sessao_n INTEGER PRIMARY KEY,
                data TEXT, semana INTEGER, tipo TEXT, duracao_min INTEGER,
                fc_repouso INTEGER, fc_media_durante INTEGER, fc_pico INTEGER,
                vo2_max REAL, fai REAL, pa_antes TEXT, pa_apos TEXT,
                glic_antes INTEGER, glic_apos INTEGER, pse_durante INTEGER,
                pse_apos INTEGER, sintomas TEXT, hba1c REAL
            )
        """)
        # Tabela de Glicemias (Registadas pelo Cliente)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS glicemias_jose (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT, valor INTEGER, pode_treinar INTEGER
            )
        """)
        # Tabela de Feedbacks (Borg)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedbacks_jose (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT, borg INTEGER, sintomas TEXT, notas TEXT
            )
        """)

@st.cache_data
def gerar_evolucao_ficticia():
    np.random.seed(42)
    sessoes = []
    data_atual = PACIENTE["data_inicio"]
    for sem in range(PROGRAMA_SEMANAS):
        fator = sem / (PROGRAMA_SEMANAS - 1)
        for s in range(SESSOES_POR_SEMANA):
            vo2_base = PACIENTE["vo2_inicial"] + 6.5 * fator
            sessoes.append({
                "sessao_n": len(sessoes) + 1,
                "data": data_atual.strftime("%Y-%m-%d"),
                "semana": sem + 1,
                "tipo": "Aeróbio contínuo" if sem < 4 else "Intervalado",
                "duracao_min": int(25 + 20 * fator),
                "fc_repouso": int(PACIENTE["fc_repouso_inicial"] - 10 * fator),
                "fc_media_durante": int(110 + 10 * fator),
                "fc_pico": int(125 + 10 * fator),
                "vo2_max": round(vo2_base + np.random.normal(0, 0.3), 1),
                "fai": round(((PACIENTE["vo2_previsto"] - vo2_base) / PACIENTE["vo2_previsto"]) * 100, 1),
                "pa_antes": f"{int(130-5*fator)}/{int(85-3*fator)}",
                "pa_apos": f"{int(140-5*fator)}/{int(88-3*fator)}",
                "glic_antes": int(140 - 20 * fator),
                "glic_apos": int(115 - 20 * fator),
                "pse_durante": int(12 + fator * 2),
                "pse_apos": int(11 + fator * 1),
                "sintomas": "Nenhum",
                "hba1c": round(PACIENTE["hba1c_inicial"] - 1.0 * fator, 2) if s == 0 and sem % 4 == 0 else None
            })
            data_atual += timedelta(days=2)
    return pd.DataFrame(sessoes)

def obter_dados_sessoes():
    inicializar_bd()
    with get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM sessoes_jose", conn)
    if df.empty:
        df_novo = gerar_evolucao_ficticia()
        df_novo.to_sql("sessoes_jose", get_db_connection(), if_exists="replace", index=False)
        return df_novo
    df["data"] = pd.to_datetime(df["data"])
    return df

# Carregamento inicial
df_sessoes = obter_dados_sessoes()

# ============================================================
# SIDEBAR / NAVEGAÇÃO
# ============================================================
st.sidebar.title("🫀 BestCare")
perfil = st.sidebar.radio("Ver como:", ["👤 Cliente (José)", "🩺 Equipa Clínica"])

# ============================================================
# PERFIL CLIENTE
# ============================================================
if perfil == "👤 Cliente (José)":
    st.title(f"Olá, {PACIENTE['nome']} 👋")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Registar Glicemia Pré-Treino")
        glic = st.number_input("Valor (mg/dL):", 40, 400, 120)
        if st.button("Guardar Medição"):
            with get_db_connection() as conn:
                conn.execute("INSERT INTO glicemias_jose (data, valor, pode_treinar) VALUES (?, ?, ?)",
                            (datetime.now().strftime("%Y-%m-%d %H:%M"), glic, 1 if 100 <= glic <= 250 else 0))
            st.success("Medição guardada!")

    with col2:
        st.subheader("Objetivo da Semana")
        st.info(f"Semana {df_sessoes['semana'].max()}: Realizar 3 sessões de 45 min a intensidade moderada.")

# ============================================================
# PERFIL EQUIPA CLÍNICA
# ============================================================
else:
    st.title("🩺 Painel de Monitorização Clínica")
    
    # Métricas de topo
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VO₂máx Atual", f"{df_sessoes.iloc[-1]['vo2_max']} ml/kg/min")
    m2.metric("FAI (Défice)", f"{df_sessoes.iloc[-1]['fai']}%", delta="-5%", delta_color="inverse")
    m3.metric("FC Repouso", f"{df_sessoes.iloc[-1]['fc_repouso']} bpm")
    m4.metric("Sessões", f"{len(df_sessoes)}/36")

    # --- GRÁFICO 1: VO2 e FAI ---
    st.subheader("Evolução Funcional (VO₂máx vs FAI)")
    fig_func = go.Figure()
    fig_func.add_trace(go.Scatter(x=df_sessoes["data"], y=df_sessoes["vo2_max"], name="VO₂máx", line=dict(color="#2F5597", width=3)))
    fig_func.add_trace(go.Scatter(x=df_sessoes["data"], y=df_sessoes["fai"], name="FAI (%)", yaxis="y2", line=dict(color="#C00000", dash="dot")))
    fig_func.update_layout(yaxis2=dict(overlaying="y", side="right"), hovermode="x unified")
    st.plotly_chart(fig_func, use_container_width=True)

    # --- GRÁFICOS 2 e 3: METABÓLICO ---
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Pressão Arterial Sistólica")
        df_sessoes["pas_antes"] = df_sessoes["pa_antes"].str.split("/").str[0].astype(int)
        df_sessoes["pas_apos"] = df_sessoes["pa_apos"].str.split("/").str[0].astype(int)
        fig_pa = px.line(df_sessoes, x="data", y=["pas_antes", "pas_apos"], 
                         labels={"value": "mmHg", "variable": "Momento"},
                         color_discrete_map={"pas_antes": "#2F5597", "pas_apos": "#E46C0A"})
        st.plotly_chart(fig_pa, use_container_width=True)

    with c2:
        st.subheader("Controlo Glicémico (Sessões)")
        fig_glic = px.bar(df_sessoes, x="data", y=["glic_antes", "glic_apos"], barmode="group",
                          color_discrete_sequence=["#2F5597", "#A2AD00"])
        st.plotly_chart(fig_glic, use_container_width=True)

    # Tabela de Dados
    with st.expander("Ver Histórico de Sessões Completo"):
        st.dataframe(df_sessoes.sort_values("sessao_n", ascending=False))
