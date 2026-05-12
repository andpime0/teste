import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sqlite3
import json

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="BestCare Pro | José Oliveira", page_icon="🧪", layout="wide")

# --- ESTILO CSS PARA OS GRÁFICOS ---
st.markdown("""<style> .main { background-color: #f5f7f9; } .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); } </style>""", unsafe_allow_html=True)

# --- DADOS CLÍNICOS E CÁLCULOS ACSM ---
PACIENTE = {
    "nome": "José Oliveira", "idade": 55, "fc_max_teste": 145, "fc_rep_inicial": 78,
    "vo2_inicial": 27.2, "vo2_prev": 35.4, "hba1c_inicial": 7.8
}

def calcular_karvonen(intensidade, fc_rep):
    # Fórmula de Karvonen para Zonas Alvo
    fcr = PACIENTE["fc_max_teste"] - fc_rep
    return int((fcr * intensidade) + fc_rep)

# --- BASE DE DADOS EVOLUÍDA ---
def inicializar_bd():
    conn = sqlite3.connect("bestcare_v2.db")
    cursor = conn.cursor()
    # Tabela principal com métricas de força (Reps, RiR, Séries)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessoes_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT, semana INTEGER, tipo TEXT,
            fc_media INTEGER, pse INTEGER, 
            reps_total INTEGER, series_total INTEGER, rir_medio INTEGER,
            glic_antes INTEGER, glic_apos INTEGER,
            relatorio TEXT
        )
    """)
    conn.commit()
    return conn

# --- GERAÇÃO DE DADOS HISTÓRICOS (INCLUINDO FORÇA) ---
@st.cache_data
def carregar_dados_iniciais():
    df = pd.DataFrame()
    sessoes = []
    hoje = datetime.now()
    for i in range(1, 25): # 24 sessões anteriores (8 semanas)
        fator = i / 24
        sessoes.append({
            "data": (hoje - timedelta(days=(25-i)*2)).strftime("%Y-%m-%d"),
            "semana": (i // 3) + 1,
            "tipo": "Misto (Aeróbio + Força)",
            "fc_media": int(105 + 15 * fator),
            "pse": int(14 - 3 * fator + np.random.randint(-1, 2)),
            "reps_total": int(80 + 40 * fator),
            "series_total": 8,
            "rir_medio": int(4 - 2 * fator), # RiR diminui conforme a carga aumenta
            "glic_antes": int(145 - 20 * fator),
            "glic_apos": int(110 - 15 * fator),
            "relatorio": f"Sessão {i}: Adaptação hemodinâmica estável."
        })
    return pd.DataFrame(sessoes)

# --- INTERFACE ---
conn = inicializar_bd()
df_hist = carregar_dados_iniciais()

st.sidebar.title("🧪 BestCare System")
menu = st.sidebar.selectbox("Navegação:", ["🚀 Modo Treino (Zonas Alvo)", "📈 Evolução & Heatmap", "📋 Histórico de Relatórios"])

# ============================================================
# 1. MODO TREINO (ZONAS ALVO EM TEMPO REAL)
# ============================================================
if menu == "🚀 Modo Treino (Zonas Alvo)":
    st.title("🚀 Prescrição em Tempo Real")
    st.caption("Fase Atual: Progressão de Intensidade (Semanas 5-8)")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏃 Alvo Aeróbio (Karvonen)")
        # Zona 40-59% FCR
        min_fc = calcular_karvonen(0.40, 72)
        max_fc = calcular_karvonen(0.59, 72)
        
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = (min_fc + max_fc) / 2,
            title = {'text': "FC Alvo (bpm)"},
            gauge = {
                'axis': {'range': [60, 150]},
                'bar': {'color': "#2F5597"},
                'steps': [
                    {'range': [60, min_fc], 'color': "#e8f0fe"},
                    {'range': [min_fc, max_fc], 'color': "#c6f6d5"},
                    {'range': [max_fc, 150], 'color': "#fed7d7"}
                ],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': max_fc}
            }
        ))
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.info(f"Mantenha a pulsação entre **{min_fc}** e **{max_fc}** bpm.")

    with col2:
        st.subheader("🏋️ Alvo Força (RiR & PSE)")
        st.write("**Protocolo:** 2-3 séries por exercício")
        st.metric("Alvo de Repetições", "12 - 15")
        st.metric("RiR (Reps em Reserva)", "2 - 3", help="Deve terminar a série sentindo que ainda conseguia fazer mais 2 ou 3 reps.")
        st.warning("⚠️ **Nota:** Evitar a manobra de Valsalva (não sustenha a respiração).")

    # REGISTO DE SESSÃO
    st.divider()
    with st.form("registo_sessao"):
        st.subheader("📝 Finalizar e Gerar Relatório de Sessão")
        c1, c2, c3 = st.columns(3)
        g_antes = c1.number_input("Glicemia Antes", 40, 300, 120)
        g_apos = c2.number_input("Glicemia Após", 40, 300, 100)
        pse_final = c3.slider("PSE Final (Borg 6-20)", 6, 20, 13)
        
        ca, cb, cc = st.columns(3)
        reps = ca.number_input("Total de Reps Efetuadas", 0, 300, 120)
        rir = cb.slider("RiR Médio Sentido", 0, 5, 2)
        notas = cc.text_area("Notas da sessão")
        
        if st.form_submit_button("💾 Guardar e Gerar Relatório"):
            relatorio_texto = f"O José completou {reps} repetições com RiR de {rir}. Glicemia estável (Variação: {g_apos - g_antes}mg/dL). PSE de {pse_final} condizente com a fase."
            # Inserir no SQL
            cursor = conn.cursor()
            cursor.execute("INSERT INTO sessoes_v2 (data, semana, tipo, fc_media, pse, reps_total, series_total, rir_medio, glic_antes, glic_apos, relatorio) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (datetime.now().strftime("%Y-%m-%d"), 8, "Misto", 115, pse_final, reps, 8, rir, g_antes, g_apos, relatorio_texto))
            conn.commit()
            st.success("Sessão guardada com sucesso! Relatório gerado.")

# ============================================================
# 2. EVOLUÇÃO & HEATMAP (VISÃO INOVADORA)
# ============================================================
elif menu == "📈 Evolução & Heatmap":
    st.title("📊 Análise de Padrões e Evolução")
    
    # Heatmap PSE vs Volume
    st.subheader("🔥 Heatmap: Relação Esforço (PSE) vs Volume de Carga")
    fig_heat = px.density_heatmap(df_hist, x="reps_total", y="pse", z="fc_media",
                                  labels={'reps_total': 'Volume (Total Reps)', 'pse': 'Esforço (PSE)'},
                                  color_continuous_scale="Viridis", text_auto=True)
    st.plotly_chart(fig_heat, use_container_width=True)
    st.caption("Este gráfico ajuda a detetar se o José está a reportar mais esforço para a mesma carga (sinal de fadiga).")

    # Gráfico de Relação FC, PSE e RiR
    st.subheader("🔗 Relação FC, PSE e RiR ao longo das Sessões")
    fig_evol = go.Figure()
    fig_evol.add_trace(go.Scatter(x=df_hist.index, y=df_hist["fc_media"], name="FC Média", line=dict(color="#2F5597")))
    fig_evol.add_trace(go.Scatter(x=df_hist.index, y=df_hist["pse"]*8, name="PSE (Escalado)", line=dict(color="#E46C0A")))
    fig_evol.add_trace(go.Scatter(x=df_hist.index, y=df_hist["rir_medio"]*20, name="RiR (Escalado)", line=dict(color="#A2AD00", dash='dot')))
    
    fig_evol.update_layout(title="Interação entre Marcadores Fisiológicos e Subjetivos", xaxis_title="Número da Sessão")
    st.plotly_chart(fig_evol, use_container_width=True)

# ============================================================
# 3. HISTÓRICO DE RELATÓRIOS
# ============================================================
else:
    st.title("📋 Arquivo de Relatórios de Sessão")
    cursor = conn.cursor()
    cursor.execute("SELECT data, relatorio, pse, rir_medio FROM sessoes_v2 ORDER BY id DESC")
    logs = cursor.fetchall()
    
    for log in logs:
        with st.expander(f"📅 Sessão: {log[0]} | PSE: {log[2]} | RiR: {log[3]}"):
            st.write(log[1])
            st.download_button("Exportar PDF (Simulado)", "Conteúdo do relatório...", file_name=f"relatorio_{log[0]}.txt")
