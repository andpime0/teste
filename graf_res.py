import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import sqlite3
import calendar

st.set_page_config(page_title="BestCare Pro | Sistema Integrado", page_icon="🧪", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em;
                       background-color: #2F5597; color: white; }
    .client-card { background-color: #e3f2fd; padding: 20px; border-radius: 10px;
                   border-left: 5px solid #2196f3; }
    .clinical-card { background-color: #f1f8e9; padding: 20px; border-radius: 10px;
                     border-left: 5px solid #4caf50; }
    .cal-day { background:#fff; border-radius:8px; padding:8px; min-height:90px;
               border:1px solid #e0e0e0; margin:2px; font-size:0.85em; }
    .cal-inicial { background:#e8f5e9; border-left:4px solid #43a047; }
    .cal-desenv  { background:#fff3e0; border-left:4px solid #fb8c00; }
    .cal-rest    { background:#fafafa; color:#999; }
    </style>
    """, unsafe_allow_html=True)

# ---------- PACIENTE ----------
PACIENTE = {"nome": "José Oliveira", "idade": 55, "fc_max": 145, "fc_rep": 72, "vo2_prev": 35.4}
DATA_INICIO_PROGRAMA = date(2026, 4, 13)  # segunda-feira

def calc_karvonen(int_min, int_max):
    fcr = PACIENTE["fc_max"] - PACIENTE["fc_rep"]
    return int(fcr*int_min + PACIENTE["fc_rep"]), int(fcr*int_max + PACIENTE["fc_rep"])

# ---------- BASE DE DADOS ----------
DB_PATH = "bestcare_v3.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS sessoes_v3 (
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
    return conn

def seed_se_vazio(conn):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM sessoes_v3")
    if c.fetchone()[0] > 0:
        return
    hoje = date.today()
    rng = np.random.default_rng(42)  # determinístico mas realista
    for i in range(1, 16):
        f = i/15
        fase = "Inicial" if i <= 6 else "Desenvolvimento"
        # FC progressiva: Inicial 101-116, Desenv 116-127
        fc_alvo = 101 + (127-101)*f
        fc_media = int(fc_alvo + rng.normal(0, 3))
        fc_pico = fc_media + int(rng.integers(8, 15))
        # PA: pré ~135/85, pós sobe na inicial mais que na desenv (adaptação)
        pa_sist_pre = int(134 + rng.normal(0, 4))
        pa_diast_pre = int(84 + rng.normal(0, 3))
        delta_sist = int(18 - 6*f + rng.normal(0, 3))   # cai com adaptação
        delta_diast = int(2 + rng.normal(0, 2))
        pa_sist_pos = pa_sist_pre + delta_sist
        pa_diast_pos = pa_diast_pre + delta_diast
        # PSE desce (mesma carga, menos esforço percebido)
        pse = int(round(15 - 3*f + rng.normal(0, 0.4)))
        reps = int(80 + 70*f + rng.integers(-10, 10))
        series = 9 if fase == "Inicial" else 12
        n_ex = 6 if fase == "Inicial" else 7
        glic_a = int(150 - 25*f + rng.normal(0, 8))
        glic_p = int(115 - 15*f + rng.normal(0, 6))
        rir = int(round(4 - 2*f))
        data_s = (hoje - timedelta(days=(16-i)*2)).isoformat()
        c.execute("""INSERT INTO sessoes_v3
            (data, semana, fase, tipo, fc_media, fc_pico,
             pa_sist_pre, pa_diast_pre, pa_sist_pos, pa_diast_pos,
             pse, reps_total, series_total, n_exercicios,
             glic_antes, glic_apos, rir_medio, relatorio_clinico, validado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (data_s, (i//3)+1, fase, "Misto", fc_media, fc_pico,
             pa_sist_pre, pa_diast_pre, pa_sist_pos, pa_diast_pos,
             pse, reps, series, n_ex, glic_a, glic_p, rir,
             f"Sessão {i} ({fase}): resposta hemodinâmica estável. ΔPA sist {delta_sist} mmHg."))
    conn.commit()

def carregar_sessoes(conn):
    return pd.read_sql_query("SELECT * FROM sessoes_v3 ORDER BY data", conn)

def carregar_reports_cliente(conn):
    return pd.read_sql_query("SELECT * FROM reports_cliente ORDER BY data_envio DESC", conn)

def inserir_report_cliente(conn, glic, pse, reps, comentario):
    c = conn.cursor()
    c.execute("""INSERT INTO reports_cliente (data_envio, glic_antes, pse, reps_total, comentario)
                 VALUES (?,?,?,?,?)""",
              (datetime.now().isoformat(timespec="minutes"), glic, pse, reps, comentario))
    conn.commit()

# ---------- INIT ----------
conn = init_db()
seed_se_vazio(conn)
df_hist = carregar_sessoes(conn)

# ---------- CALENDÁRIO DO PROGRAMA ----------
def gerar_calendario():
    """3x/semana (Seg, Qua, Sex). Sem 1-2 Inicial, Sem 3-5 Desenvolvimento."""
    plano = {}
    for semana in range(5):
        for dia_offset, tipo_sessao in zip([0,2,4], ["Força + Aeróbio", "Aeróbio", "Força + Aeróbio"]):
            d = DATA_INICIO_PROGRAMA + timedelta(weeks=semana, days=dia_offset)
            fase = "Inicial" if semana < 2 else "Desenvolvimento"
            plano[d] = {"fase": fase, "tipo": tipo_sessao, "semana": semana+1}
    return plano

PLANO = gerar_calendario()

# ---------- SIDEBAR ----------
st.sidebar.image("[cdn-icons-png.flaticon.com](https://cdn-icons-png.flaticon.com/512/822/822118.png)", width=80)
st.sidebar.title("BestCare Pro")
user_role = st.sidebar.radio("Portal:", ["👤 Área do Cliente (José)", "🩺 Área Clínica (Equipa)"])

# ============================================================
# ÁREA DO CLIENTE
# ============================================================
if user_role == "👤 Área do Cliente (José)":
    st.title(f"Bem-vindo, {PACIENTE['nome']} 👋")
    tabs = st.tabs(["🚀 Próximo Treino", "📅 Meu Calendário", "💪 Plano de Treino",
                    "📈 A Minha Evolução", "📋 Meus Relatórios"])

    # --- Próximo treino ---
    with tabs[0]:
        hoje = date.today()
        proximos = sorted([d for d in PLANO if d >= hoje])
        prox = proximos[0] if proximos else None
        if prox:
            info = PLANO[prox]
            st.markdown(f'<div class="client-card"><h4>🎯 Próxima sessão: '
                        f'{prox.strftime("%A, %d %b")} — Fase {info["fase"]} ({info["tipo"]})</h4></div>',
                        unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🏃 Cardio (Zonas Alvo)")
            if prox and PLANO[prox]["fase"] == "Inicial":
                low, high = calc_karvonen(0.40, 0.60); zona = "Moderada (Fase Inicial)"
            else:
                low, high = calc_karvonen(0.60, 0.75); zona = "Moderada-Intensa (Desenvolvimento)"
            st.metric("FC Alvo", f"{low} - {high} bpm", zona)
            fig = go.Figure(go.Indicator(mode="gauge+number", value=(low+high)//2,
                gauge={'axis':{'range':[60,150]},'bar':{'color':"#2F5597"},
                       'steps':[{'range':[60,low],'color':"#e8f5e9"},
                                {'range':[low,high],'color':"#a5d6a7"},
                                {'range':[high,150],'color':"#ffcdd2"}]}))
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("🏋️ Força (Prescrição)")
            st.write("**Repetições:** 12 a 15 por série")
            st.write("**Esforço (PSE):** 'Cansado' (13-14)")
            st.info("💡 Deve sentir que conseguia fazer +2/3 reps no fim de cada série (RiR 2-3).")

        st.divider()
        with st.form("registo_jose"):
            st.subheader("📝 Registar Dados da Sessão")
            ca, cb = st.columns(2)
            g_antes = ca.number_input("Glicose Pré-Treino (mg/dL)", 40, 300, 130)
            pse_jose = cb.slider("Como se sentiu? (PSE 6-20)", 6, 20, 13)
            reps_jose = st.number_input("Total de Repetições", 0, 500, 150)
            coment = st.text_area("Comentário (opcional)", "")
            if st.form_submit_button("Submeter ao Treinador"):
                inserir_report_cliente(conn, g_antes, pse_jose, reps_jose, coment)
                st.success("✅ Dados enviados e gravados na BD! O treinador irá validar.")

    # --- Calendário ---
    with tabs[1]:
        st.subheader("📅 Plano das próximas 5 semanas")
        st.caption("🟢 Fase Inicial · 🟠 Fase Desenvolvimento · ⚪ Descanso")
        # vista por semana
        for semana in range(5):
            inicio_sem = DATA_INICIO_PROGRAMA + timedelta(weeks=semana)
            st.markdown(f"**Semana {semana+1}** — início {inicio_sem.strftime('%d/%m')}")
            cols = st.columns(7)
            for i, nome in enumerate(["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]):
                d = inicio_sem + timedelta(days=i)
                with cols[i]:
                    if d in PLANO:
                        info = PLANO[d]
                        cls = "cal-inicial" if info["fase"]=="Inicial" else "cal-desenv"
                        st.markdown(f'<div class="cal-day {cls}"><b>{nome} {d.day}</b><br>'
                                    f'{info["tipo"]}<br><small>{info["fase"]}</small></div>',
                                    unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="cal-day cal-rest"><b>{nome} {d.day}</b><br>'
                                    f'<small>Descanso</small></div>', unsafe_allow_html=True)

    # --- Plano de treino ---
    with tabs[2]:
        fase_sel = st.radio("Fase do plano:", ["Inicial", "Desenvolvimento"], horizontal=True)
        st.subheader(f"Sessão tipo — Fase {fase_sel}")
        if fase_sel == "Inicial":
            aer = pd.DataFrame([
                ["Aquecimento Geral","Bicicleta estática","5-10 min","PSE 6-10","-"],
                ["Aeróbio","Caminhada (lenta)","30 min","PSE 11-12 (leve)","-"],
                ["Alongamentos","Tai-chi","10 min","PSE 6","-"]],
                columns=["Fase","Tipo","Tempo","Intensidade","Recuperação"])
            forca = pd.DataFrame([
                ["1","Agachamento (Smith)","Quadrícepe","1-2","10-15","60-90\""],
                ["2","Lat Pulldown","Dorsal","1-2","10-15","60-90\""],
                ["3","Bench Press (Smith)","Peitoral","1-2","10-15","60-90\""],
                ["4","DB Bicep Curl","Bícepe","1-2","10-15","60-90\""],
                ["5","Tricep Extension","Trícepe","1-2","10-15","60-90\""],
                ["6","Abdominal Crunch","Core","1-2","10-15","60-90\""]],
                columns=["Ordem","Exercício","Grupo","Séries","Reps","Recuperação"])
        else:
            aer = pd.DataFrame([]
                ["Aquecimento Geral","Bicicleta estática","5-10 min","PSE 6-10","-"],
                
