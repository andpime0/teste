import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import sqlite3
import scipy.stats as stats

# ---------- CONFIGURAÇÃO DA PÁGINA ----------
st.set_page_config(page_title="BestCare Pro | Gestão Clínica", page_icon="🧪", layout="wide")

# ---------- ESTILO CUSTOMIZADO (CSS) ----------
st.markdown("""
    <style>
    .main { background-color: #f9f9fb; }
    .stMetric { 
        background-color: #ffffff; padding: 20px; border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee;
    }
    .stButton>button { 
        width: 100%; border-radius: 8px; height: 3em;
        background-color: #2F5597; color: white; transition: 0.3s;
    }
    .stButton>button:hover { border: 1px solid #2F5597; color: #2F5597; background: white; }
    .client-card { 
        background-color: #e3f2fd; padding: 20px; border-radius: 10px;
        border-left: 5px solid #2196f3; margin-bottom: 20px;
    }
    .cal-day { 
        background:#fff; border-radius:8px; padding:8px; min-height:90px;
        border:1px solid #e0e0e0; margin:2px; font-size:0.85em; 
    }
    .cal-inicial { background:#e8f5e9; border-left:4px solid #43a047; }
    .cal-desenv  { background:#fff3e0; border-left:4px solid #fb8c00; }
    .cal-rest    { background:#fafafa; color:#999; }
    </style>
    """, unsafe_allow_html=True)

# ---------- CONSTANTES E DADOS DO PACIENTE ----------
PACIENTE = {"nome": "José Oliveira", "idade": 55, "fc_max": 145, "fc_rep": 72, "vo2_prev": 35.4}
DATA_INICIO_PROGRAMA = date(2026, 4, 13)
DB_PATH = "bestcare_pro_v4.db"

# ---------- LÓGICA DE BASE DE DADOS ----------
@st.cache_resource
def get_conn():
    """Mantém a conexão ativa de forma eficiente."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS sessoes_v4 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT, semana INTEGER, fase TEXT, tipo TEXT,
        fc_media INTEGER, fc_pico INTEGER,
        pa_sist_pre INTEGER, pa_diast_pre INTEGER,
        pa_sist_pos INTEGER, pa_diast_pos INTEGER,
        pse INTEGER, reps_total INTEGER, series_total INTEGER, n_exercicios INTEGER,
        glic_antes INTEGER, glic_apos INTEGER, rir_medio INTEGER,
        relatorio_cliente TEXT, relatorio_clinico TEXT,
        validado INTEGER DEFAULT 0)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS reports_cliente (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_envio TEXT, glic_antes INTEGER, pse INTEGER,
        reps_total INTEGER, comentario TEXT, lido INTEGER DEFAULT 0)""")
    conn.commit()

def seed_data():
    """Popula a BD com dados simulados realistas se estiver vazia."""
    conn = get_conn()
    c = conn.cursor()
    if c.execute("SELECT COUNT(*) FROM sessoes_v4").fetchone()[0] == 0:
        hoje = date.today()
        rng = np.random.default_rng(42)
        for i in range(1, 16):
            f = i/15
            fase = "Inicial" if i <= 6 else "Desenvolvimento"
            fc_media = int((101 + (127-101)*f) + rng.normal(0, 3))
            pse = int(round(15 - 3*f + rng.normal(0, 0.4)))
            reps = int(80 + 70*f + rng.integers(-10, 10))
            data_s = (hoje - timedelta(days=(16-i)*2)).isoformat()
            
            c.execute("INSERT INTO sessoes_v4 (data, semana, fase, tipo, fc_media, fc_pico, pa_sist_pre, pa_diast_pre, pa_sist_pos, pa_diast_pos, pse, reps_total, series_total, n_exercicios, glic_antes, glic_apos, rir_medio, relatorio_clinico, validado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (data_s, (i//3)+1, fase, "Misto", fc_media, fc_media+12, 134, 84, 145, 88, pse, reps, 12, 7, 140, 110, 3, "Sessão estável.", 1))
                      (data_s, (i//3)+1, fase, "Misto", fc_media, fc_media+12, 134, 84, 145, 88, pse, reps, 12, 7, 140, 110, 3, "Sessão estável.", 1)
        conn.commit()

# ---------- FUNÇÕES AUXILIARES ----------
def calc_karvonen(int_min, int_max):
    fcr = PACIENTE["fc_max"] - PACIENTE["fc_rep"]
    return int(fcr*int_min + PACIENTE["fc_rep"]), int(fcr*int_max + PACIENTE["fc_rep"])

def gerar_plano_calendario():
    plano = {}
    for semana in range(5):
        for dia_offset, tipo in zip([0,2,4], ["Força + Aeróbio", "Aeróbio", "Força + Aeróbio"]):
            d = DATA_INICIO_PROGRAMA + timedelta(weeks=semana, days=dia_offset)
            plano[d] = {"fase": "Inicial" if semana < 2 else "Desenvolvimento", "tipo": tipo, "semana": semana+1}
    return plano

# ---------- INICIALIZAÇÃO ----------
init_db()
seed_data()
conn = get_conn()
PLANO = gerar_plano_calendario()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/822/822118.png", width=70)
    st.title("BestCare Pro")
    st.caption("Sistema Integrado de Reabilitação")
    user_role = st.radio("Selecione o Portal:", ["👤 Área do Utente (José)", "🩺 Área Clínica (Equipa)"])
    st.divider()
    st.info(f"Paciente: **{PACIENTE['nome']}**\nAlvo VO₂: {PACIENTE['vo2_prev']} ml/kg/min")

# ============================================================
# ÁREA DO UTENTE
# ============================================================
if user_role == "👤 Área do Utente (José)":
    st.title(f"Olá, Sr. {PACIENTE['nome'].split()[0]}! 👋")
    t_utente = st.tabs(["🚀 Próximo Treino", "📅 Calendário", "📈 Evolução", "📂 Histórico"])

    with t_utente[0]: # Próximo Treino
        hoje = date.today()
        proximos = sorted([d for d in PLANO if d >= hoje])
        if proximos:
            prox_data = proximos[0]
            info = PLANO[prox_data]
            st.markdown(f'<div class="client-card"><h3>🎯 Próxima Sessão: {prox_data.strftime("%d/%m (%A)")}</h3>'
                        f'Fase: <b>{info["fase"]}</b> | Tipo: <b>{info["tipo"]}</b></div>', unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🏃 Alvo Cardíaco")
                low, high = (calc_karvonen(0.4, 0.6) if info["fase"] == "Inicial" else calc_karvonen(0.6, 0.75))
                fig_gauge = go.Figure(go.Indicator(mode="gauge+number", value=(low+high)//2,
                    gauge={'axis':{'range':[60, 150]}, 'bar':{'color':"#2F5597"},
                           'steps':[{'range':[60, low], 'color':'#f1f8e9'}, {'range':[low, high], 'color':'#a5d6a7'}]}))
                fig_gauge.update_layout(height=250, margin=dict(t=0, b=0))
                st.plotly_chart(fig_gauge, use_container_width=True)
                st.metric("Intervalo Recomendado", f"{low} - {high} bpm")

            with c2:
                st.subheader("🏋️ Prescrição de Força")
                st.write("**Intensidade:** Cansado (PSE 13-14)")
                st.write("**Volume:** 12-15 repetições")
                st.info("RiR 2-3: Deve terminar sentindo que conseguia fazer mais 2 ou 3 repetições.")

            st.divider()
            with st.form("registo_sessao"):
                st.subheader("📝 Registar Dados da Sessão")
                col_a, col_b = st.columns(2)
                glic = col_a.number_input("Glicémia Pré-Treino (mg/dL)", 40, 400, 120)
                # Alertas de Segurança em Tempo Real
                if glic < 90: st.warning("⚠️ Glicémia baixa: Ingira 15g de hidratos antes de começar.")
                elif glic > 250: st.error("🚨 Glicémia alta: Contacte o seu fisiologista antes de treinar.")
                
                pse_val = col_b.slider("Como se sentiu? (6-20)", 6, 20, 13)
                coment = st.text_area("Notas para a equipa clínica...")
                if st.form_submit_button("Enviar Registo"):
                    c = conn.cursor()
                    c.execute("INSERT INTO reports_cliente (data_envio, glic_antes, pse, reps_total, comentario) VALUES (?,?,?,?,?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), glic, pse_val, 0, coment))
                    conn.commit()
                    st.success("Dados enviados com sucesso!")

    with t_utente[1]: # Calendário
        st.subheader("📅 O Meu Plano de 5 Semanas")
        for sem in range(5):
            st.write(f"**Semana {sem+1}**")
            cols = st.columns(7)
            data_sem = DATA_INICIO_PROGRAMA + timedelta(weeks=sem)
            for i, dia_nome in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
                d = data_sem + timedelta(days=i)
                with cols[i]:
                    if d in PLANO:
                        cls = "cal-inicial" if PLANO[d]["fase"] == "Inicial" else "cal-desenv"
                        st.markdown(f'<div class="cal-day {cls}"><b>{dia_nome} {d.day}</b><br><small>{PLANO[d]["tipo"]}</small></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="cal-day cal-rest"><b>{dia_nome} {d.day}</b><br><small>Folga</small></div>', unsafe_allow_html=True)

    with t_utente[2]: # Evolução
        df = pd.read_sql("SELECT data, glic_antes, glic_apos, fc_media, pse FROM sessoes_v4", conn)
        if not df.empty:
            fig_evol = px.line(df, x="data", y=["glic_antes", "glic_apos"], title="Tendência da Glicémia (mg/dL)", markers=True)
            st.plotly_chart(fig_evol, use_container_width=True)

# ============================================================
# 🩺 ÁREA CLÍNICA (EQUIPA)
# ============================================================
else:
    st.title("🩺 Painel de Monitorização Fisiológica")
    t_clinica = st.tabs(["📊 Carga de Treino", "🔬 Biométrica", "🧪 Estatística", "📥 Pedidos"])

    df_hist = pd.read_sql("SELECT * FROM sessoes_v4", conn)

    with t_clinica[0]: # Carga
        if not df_hist.empty:
            df_hist["volume"] = df_hist["reps_total"] * df_hist["series_total"]
            fig_carga = px.scatter(df_hist, x="volume", y="pse", color="fc_media", size="fc_pico",
                                  title="Volume vs Esforço Percebido", labels={"pse":"PSE (6-20)", "volume":"Volume Total"})
            st.plotly_chart(fig_carga, use_container_width=True)

    with t_clinica[1]: # Biométrica
        if not df_hist.empty:
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.bar(df_hist, x="data", y=["pa_sist_pos", "pa_diast_pos"], barmode="group", title="Pressão Arterial Pós-Sessão"), use_container_width=True)
            c2.plotly_chart(px.line(df_hist, x="data", y="rir_medio", title="Evolução da Reserva de Repetições (RiR)"), use_container_width=True)

    with t_clinica[2]: # Estatística (Refinada com Tendência Manual)
        st.subheader("Análise de Regressão: Volume vs PSE")
        if not df_hist.empty:
            x = df_hist['reps_total'] * df_hist['series_total']
            y = df_hist['pse']
            
            # Cálculo de regressão simples com Scipy
            slope, intercept, r_val, p_val, std_err = stats.linregress(x, y)
            line = slope * x + intercept

            col1, col2, col3 = st.columns(3)
            col1.metric("Correlação (r)", f"{r_val:.2f}")
            col2.metric("P-Valor", f"{p_val:.4f}")
            col3.metric("R²", f"{r_val**2:.2f}")

            fig_reg = px.scatter(df_hist, x=x, y=y, labels={'x':'Volume de Treino', 'y':'PSE'})
            fig_reg.add_traces(go.Scatter(x=x, y=line, mode='lines', name='Tendência', line=dict(color='red', dash='dash')))
            st.plotly_chart(fig_reg, use_container_width=True)
            
            if p_val < 0.05:
                st.success("✅ Existe uma relação estatisticamente significativa entre a carga e o esforço.")
            else:
                st.info("ℹ️ A relação entre volume e esforço ainda não atingiu significância estatística.")

    with t_clinica[3]: # Pedidos do Utente
        st.subheader("📥 Mensagens e Registos do Sr. José")
        df_msgs = pd.read_sql("SELECT * FROM reports_cliente ORDER BY id DESC", conn)
        st.table(df_msgs)
