import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sqlite3

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="BestCare Pro | Sistema Integrado", page_icon="🧪", layout="wide")

# --- ESTILO CSS PERSONALIZADO ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; background-color: #2F5597; color: white; }
    .client-card { background-color: #e3f2fd; padding: 20px; border-radius: 10px; border-left: 5px solid #2196f3; }
    .clinical-card { background-color: #f1f8e9; padding: 20px; border-radius: 10px; border-left: 5px solid #4caf50; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÃO DO PACIENTE E CÁLCULOS ---
PACIENTE = {
    "nome": "José Oliveira", "idade": 55, "fc_max": 145, "fc_rep": 72,
    "vo2_prev": 35.4
}

def calc_karvonen(int_min, int_max):
    fcr = PACIENTE["fc_max"] - PACIENTE["fc_rep"]
    low = int((fcr * int_min) + PACIENTE["fc_rep"])
    high = int((fcr * int_max) + PACIENTE["fc_rep"])
    return low, high

# --- GESTÃO DE BASE DE DADOS ---
def init_db():
    conn = sqlite3.connect("bestcare_v3.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessoes_v3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT, semana INTEGER, tipo TEXT,
            fc_media INTEGER, pse INTEGER, 
            reps_total INTEGER, series_total INTEGER, n_exercicios INTEGER,
            glic_antes INTEGER, glic_apos INTEGER, rir_medio INTEGER,
            relatorio TEXT
        )
    """)
    conn.commit()
    return conn

@st.cache_data
def carregar_dados_demo():
    sessoes = []
    hoje = datetime.now()
    for i in range(1, 16):
        fator = i / 15
        sessoes.append({
            "data": (hoje - timedelta(days=(16-i)*2)).strftime("%Y-%m-%d"),
            "semana": (i // 3) + 1,
            "tipo": "Misto",
            "fc_media": int(105 + 12 * fator),
            "pse": int(15 - 3 * fator),
            "reps_total": int(80 + 50 * fator),
            "series_total": 9,
            "n_exercicios": 6,
            "rir_medio": int(4 - 2 * fator),
            "glic_antes": int(150 - 25 * fator),
            "glic_apos": int(115 - 15 * fator),
            "relatorio": f"Sessão {i}: Progressão excelente. Estabilidade hemodinâmica mantida."
        })
    return pd.DataFrame(sessoes)

# --- INICIALIZAÇÃO ---
conn = init_db()
df_hist = carregar_dados_demo()

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/822/822118.png", width=80)
st.sidebar.title("BestCare Pro")
user_role = st.sidebar.radio("Selecione o Portal:", ["👤 Área do Cliente (José)", "🩺 Área Clínica (Equipa)"])

# ============================================================
# 👤 ÁREA DO CLIENTE (JOSÉ)
# ============================================================
if user_role == "👤 Área do Cliente (José)":
    st.title(f"Bem-vindo, {PACIENTE['nome']} 👋")
    
    tabs = st.tabs(["🚀 Próximo Treino", "📈 A Minha Evolução", "📋 Meus Relatórios"])

    with tabs[0]:
        st.markdown('<div class="client-card"><h4>🎯 Alvos para Hoje</h4></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🏃 Cardio (Zonas Alvo)")
            low, high = calc_karvonen(0.40, 0.60)
            st.metric("FC Alvo", f"{low} - {high} bpm", "Zona Moderada")
            # Gráfico Gauge simples para o José
            fig_fc = go.Figure(go.Indicator(mode="gauge+number", value=low+5, 
                                            gauge={'axis': {'range': [60, 150]}, 'bar': {'color': "#2F5597"}}))
            fig_fc.update_layout(height=250)
            st.plotly_chart(fig_fc, use_container_width=True)

        with c2:
            st.subheader("🏋️ Força (Prescrição)")
            st.write("**Repetições:** 12 a 15 por série")
            st.write("**Esforço (PSE):** Sentir-se 'Cansado' (13-14)")
            st.info("💡 **Dica:** Deve sentir que conseguia fazer mais 2 ou 3 reps no final de cada série (RiR 2-3).")

        st.divider()
        with st.form("registo_jose"):
            st.subheader("📝 Registar Dados da Sessão")
            col_a, col_b = st.columns(2)
            g_antes = col_a.number_input("Glicose Pré-Treino (mg/dL)", 40, 300, 130)
            pse_jose = col_b.slider("Como se sentiu? (PSE 6-20)", 6, 20, 13)
            reps_jose = st.number_input("Total de Repetições (Soma de todos os exercícios)", 0, 500, 150)
            if st.form_submit_button("Submeter Dados ao Treinador"):
                st.success("Dados enviados! O seu treinador irá validar e gerar o relatório.")

    with tabs[1]:
        st.subheader("📊 O meu progresso")
        fig_evol_jose = px.line(df_hist, x="data", y=["glic_antes", "glic_apos"], 
                                title="Controlo da minha Glicemia", markers=True)
        st.plotly_chart(fig_evol_jose, use_container_width=True)

    with tabs[2]:
        st.subheader("📁 Histórico de Sessões")
        st.dataframe(df_hist[["data", "relatorio"]].sort_values("data", ascending=False), hide_index=True)

# ============================================================
# 🩺 ÁREA CLÍNICA (EQUIPA)
# ============================================================
else:
    st.title("🩺 Painel de Monitorização Clínica")
    
    tabs_clin = st.tabs(["🔥 Análise de Carga (Heatmap)", "📈 Evolução Biométrica", "📝 Gestão de Relatórios"])

    with tabs_clin[0]:
        st.subheader("🔥 Heatmap: Relação PSE vs Carga de Treino")
        # Criar métrica de Carga (Reps * Séries * Exercícios)
        df_hist["carga_total"] = df_hist["reps_total"] * df_hist["series_total"]
        
        fig_heat = px.density_heatmap(df_hist, x="carga_total", y="pse", z="fc_media",
                                      labels={'carga_total': 'Volume Total (Reps*Séries)', 'pse': 'Esforço (PSE)'},
                                      color_continuous_scale="RdYlGn_r", text_auto=True)
        st.plotly_chart(fig_heat, use_container_width=True)
        st.caption("Interpretação: Zonas vermelhas indicam alta percepção de esforço para a carga atual (possível fadiga/descompensação).")

    with tabs_clin[1]:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.subheader("Interação FC vs RiR")
            fig_rir = go.Figure()
            fig_rir.add_trace(go.Scatter(x=df_hist.index, y=df_hist["fc_media"], name="FC Média"))
            fig_rir.add_trace(go.Bar(x=df_hist.index, y=df_hist["rir_medio"], name="RiR (Reserva)", opacity=0.4))
            st.plotly_chart(fig_rir, use_container_width=True)
        
        with col_c2:
            st.subheader("Tendência de Glicemia")
            fig_bar_g = px.bar(df_hist, x="data", y=["glic_antes", "glic_apos"], barmode="group")
            st.plotly_chart(fig_bar_g, use_container_width=True)

    with tabs_clin[2]:
        st.subheader("✍️ Validar e Gerar Novo Relatório")
        with st.expander("Abrir Formulário de Avaliação"):
            with st.form("relatorio_clinico"):
                c_a, c_b = st.columns(2)
                data_s = c_a.date_input("Data da Sessão")
                semana_s = c_b.number_input("Semana", 1, 12, 8)
                texto_relatorio = st.text_area("Conclusão Clínica da Sessão")
                if st.form_submit_button("💾 Guardar na Base de Dados e Publicar para Cliente"):
                    # Aqui inseriria no SQL (omitido para brevidade, segue a lógica anterior)
                    st.success(f"Relatório de {data_s} publicado!")
        
        st.divider()
        st.write("📂 **Arquivo Digital (SQL):**")
        st.table(df_hist[["data", "semana", "pse", "rir_medio", "relatorio"]].tail(5))
