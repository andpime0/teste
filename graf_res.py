import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import sqlite3
import calendar
import scipy.stats as stats
import seaborn as sns
import matplotlib.pyplot as plt

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
DB_PATH = "bestcare_v4.db"

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
    rng = np.random.default_rng(42)  # Gerador de números aleatórios

    for i in range(1, 16):
        f = i/15
        fase = "Inicial" if i <= 6 else "Desenvolvimento"
        
        # --- CÁLCULOS QUE ESTAVAM EM FALTA ---
        fc_alvo = 101 + (127-101)*f
        fc_media = int(fc_alvo + rng.normal(0, 3))
        fc_pico = fc_media + int(rng.integers(8, 15))
        
        pa_sist_pre = int(134 + rng.normal(0, 4))
        pa_diast_pre = int(84 + rng.normal(0, 3))
        delta_sist = int(18 - 6*f + rng.normal(0, 3))
        delta_diast = int(2 + rng.normal(0, 2))
        pa_sist_pos = pa_sist_pre + delta_sist
        pa_diast_pos = pa_diast_pre + delta_diast
        
        pse = int(round(15 - 3*f + rng.normal(0, 0.4)))
        reps = int(80 + 70*f + rng.integers(-10, 10))
        series = 9 if fase == "Inicial" else 12
        n_ex = 6 if fase == "Inicial" else 7
        glic_a = int(150 - 25*f + rng.normal(0, 8))
        glic_p = int(115 - 15*f + rng.normal(0, 6))
        rir = int(round(4 - 2*f))
        
        data_s = (hoje - timedelta(days=(16-i)*2)).isoformat()
        # ---------------------------------------

        c.execute("""INSERT INTO sessoes_v3
            (data, semana, fase, tipo, fc_media, fc_pico,
             pa_sist_pre, pa_diast_pre, pa_sist_pos, pa_diast_pos,
             pse, reps_total, series_total, n_exercicios,
             glic_antes, glic_apos, rir_medio, relatorio_clinico, validado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (data_s, (i//3)+1, fase, "Misto", fc_media, fc_pico,
             pa_sist_pre, pa_diast_pre, pa_sist_pos, pa_diast_pos,
             pse, reps, series, n_ex, glic_a, glic_p, rir,
             f"Sessão {i} ({fase}): resposta hemodinâmica estável.",))
    
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
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/822/822118.png", width=80)
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
                ["Aquecimento Geral", "Bicicleta estática", "5-10 min", "PSE 6-10 (muito leve)", "-"],
                ["Aeróbio",           "Caminhada (lenta)",  "30 min",   "PSE 11-12 (leve)",      "-"],
                ["Alongamentos",      "Tai-chi",            "10 min",   "PSE 6 (muito leve)",    "-"],
            ], columns=["Fase", "Tipo", "Tempo", "Intensidade", "Recuperação"])

            forca = pd.DataFrame([
                ["Aq. específico", "Agachamento (Smith)",   "Quadrícepe", "1-2", "3-4 (80% carga)", "60-90\""],
                ["1", "Agachamento (Smith)",                "Quadrícepe", "1-2", "10-15",           "60-90\""],
                ["2", "Lat Pulldown",                       "Dorsal",     "1-2", "10-15",           "60-90\""],
                ["3", "Bench Press (Smith)",                "Peitoral",   "1-2", "10-15",           "60-90\""],
                ["4", "DB Bicep Curl",                      "Bícepe",     "1-2", "10-15",           "60-90\""],
                ["5", "Tricep Extension (polia)",           "Trícepe",    "1-2", "10-15",           "60-90\""],
                ["6", "Abdominal Crunch",                   "Core",       "1-2", "10-15",           "60-90\""],
            ], columns=["Ordem", "Exercício", "Grupo Muscular", "Séries", "Repetições", "Recuperação"])
        else:
            aer = pd.DataFrame([
                ["Aquecimento Geral", "Bicicleta estática", "5-10 min", "PSE 6-10 (muito leve)",  "-"],
                ["Aeróbio",           "Caminhada (normal)", "30 min",   "PSE 14-17 (moderado)",   "-"],
                ["Alongamentos",      "Tai-chi",            "10 min",   "PSE 6 (muito leve)",     "-"],
            ], columns=["Fase", "Tipo", "Tempo", "Intensidade", "Recuperação"])

            forca = pd.DataFrame([
                ["Aq. específico", "Agachamento (Smith)",   "Quadrícepe", "1-3", "3-4 (80% carga)", "90\"-3'"],
                ["1", "Agachamento (Smith)",                "Quadrícepe", "1-3", "10-12",           "90\"-3'"],
                ["2", "Deadlift",                           "Dorsal",     "1-3", "10-12",           "90\"-3'"],
                ["3", "Lat Pulldown",                       "Dorsal",     "1-3", "10-12",           "90\"-3'"],
                ["4", "Bench Press (Smith)",                "Peitoral",   "1-3", "10-12",           "90\"-3'"],
                ["5", "DB Bicep Curl",                      "Bícepe",     "1-3", "10-12",           "90\"-3'"],
                ["6", "Tricep Extension (polia)",           "Trícepe",    "1-3", "10-12",           "90\"-3'"],
                ["7", "Abdominal Crunch",                   "Core",       "1-3", "10-12",           "90\"-3'"],
            ], columns=["Ordem", "Exercício", "Grupo Muscular", "Séries", "Repetições", "Recuperação"])

        st.markdown("#### 🏃 Treino Aeróbio")
        st.dataframe(aer, hide_index=True, use_container_width=True)

        st.markdown("#### 🏋️ Treino de Força (antes do aeróbio)")
        st.dataframe(forca, hide_index=True, use_container_width=True)

        st.caption("Referência: ACSM's Guidelines for Exercise Testing and Prescription, 12.ª ed.")

    # --- A Minha Evolução ---
    with tabs[3]:
        st.subheader("📊 O meu progresso ao longo do tempo")

        if df_hist.empty:
            st.info("Ainda não existem sessões registadas.")
        else:
            df_plot = df_hist.copy()
            df_plot["data"] = pd.to_datetime(df_plot["data"])

            # Glicemia
            fig_glic = px.line(
                df_plot, x="data", y=["glic_antes", "glic_apos"],
                markers=True, title="Glicemia (pré vs pós-treino)",
                labels={"value": "mg/dL", "data": "Data", "variable": ""},
            )
            st.plotly_chart(fig_glic, use_container_width=True)

            # FC média e pico
            fig_fc = px.line(
                df_plot, x="data", y=["fc_media", "fc_pico"],
                markers=True, title="Frequência Cardíaca (média vs pico)",
                labels={"value": "bpm", "data": "Data", "variable": ""},
            )
            st.plotly_chart(fig_fc, use_container_width=True)

            # PA sistólica/diastólica pós-treino
            fig_pa = go.Figure()
            fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_sist_pos"],
                                        mode="lines+markers", name="PA Sistólica (pós)"))
            fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_diast_pos"],
                                        mode="lines+markers", name="PA Diastólica (pós)"))
            fig_pa.update_layout(title="Pressão Arterial pós-treino",
                                 yaxis_title="mmHg", xaxis_title="Data")
            st.plotly_chart(fig_pa, use_container_width=True)

            # PSE
            fig_pse = px.line(df_plot, x="data", y="pse", markers=True,
                              title="Perceção Subjetiva de Esforço (PSE)",
                              labels={"pse": "PSE (6-20)", "data": "Data"})
            st.plotly_chart(fig_pse, use_container_width=True)

    # --- Meus Relatórios ---
    with tabs[4]:
        st.subheader("📁 Histórico de Sessões e Relatórios Clínicos")
        if df_hist.empty:
            st.info("Sem registos disponíveis.")
        else:
            tabela = df_hist[["data", "semana", "fase", "fc_media",
                              "pa_sist_pos", "pa_diast_pos", "pse",
                              "glic_antes", "glic_apos", "relatorio_clinico"]].copy()
            tabela.columns = ["Data", "Semana", "Fase", "FC média (bpm)",
                              "PA sist. pós", "PA diast. pós", "PSE",
                              "Glic. antes", "Glic. após", "Relatório Clínico"]
            st.dataframe(tabela.sort_values("Data", ascending=False),
                         hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("📤 Os meus envios ao treinador")
        df_envios = carregar_reports_cliente(conn)
        if df_envios.empty:
            st.caption("Ainda não submeteste nenhum registo nesta sessão.")
        else:
            st.dataframe(df_envios[["data_envio", "glic_antes", "pse",
                                    "reps_total", "comentario"]],
                         hide_index=True, use_container_width=True)

# ============================================================
# 🩺 ÁREA CLÍNICA (EQUIPA)
# ============================================================
else:
    st.title("🩺 Painel de Monitorização Clínica")
    
    # Criamos as 5 abas de uma só vez (Unificando as versões anteriores)
    tabs_clin = st.tabs([
        "🔥 Análise de Carga", 
        "📈 Evolução Biométrica", 
        "📥 Registos do Cliente", 
        "📝 Gestão de Relatórios",
        "🧪 Análise Estatística"
    ])

    # --- ABA 0: ANÁLISE DE CARGA ---
    with tabs_clin[0]:
        st.subheader("🔥 Relação entre Volume de Treino e Esforço Percebido")
        st.caption("Cada ponto representa uma sessão. A cor indica a FC média.")
        if df_hist.empty:
            st.info("Sem dados disponíveis.")
        else:
            df_h = df_hist.copy()
            df_h["volume_total"] = df_h["reps_total"] * df_h["series_total"]
            
            fig_heat = go.Figure(go.Histogram2dContour(
                x=df_h["volume_total"], y=df_h["pse"],
                colorscale="RdYlGn_r", contours=dict(coloring="heatmap", showlines=False),
                ncontours=20, colorbar=dict(title="Densidade"), opacity=0.85,
            ))
            fig_heat.add_trace(go.Scatter(
                x=df_h["volume_total"], y=df_h["pse"], mode="markers",
                marker=dict(size=10, color=df_h["fc_media"], colorscale="RdYlGn_r", showscale=True,
                            colorbar=dict(title="FC (bpm)", x=1.15), line=dict(color="white", width=1)),
                text=[f"FC {fc} | PSE {p}" for fc, p in zip(df_h["fc_media"], df_h["pse"])],
                hoverinfo="text", name="Sessões"
            ))
            fig_heat.update_layout(xaxis_title="Volume (Reps x Séries)", yaxis_title="PSE (6-20)")
            st.plotly_chart(fig_heat, use_container_width=True)

    # --- ABA 1: EVOLUÇÃO BIOMÉTRICA ---
    with tabs_clin[1]:
        if df_hist.empty:
            st.info("Sem dados.")
        else:
            df_c = df_hist.copy()
            df_c["data"] = pd.to_datetime(df_c["data"])
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("FC média vs RiR")
                fig_rir = go.Figure()
                fig_rir.add_trace(go.Scatter(x=df_c["data"], y=df_c["fc_media"], name="FC Média", mode="lines+markers"))
                fig_rir.add_trace(go.Bar(x=df_c["data"], y=df_c["rir_medio"], name="RiR", opacity=0.3, yaxis="y2"))
                fig_rir.update_layout(yaxis=dict(title="bpm"), yaxis2=dict(title="RiR", overlaying="y", side="right", range=[0, 5]))
                st.plotly_chart(fig_rir, use_container_width=True)
            with c2:
                st.subheader("Pressão Arterial")
                fig_pa = go.Figure()
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_sist_pos"], name="Sistólica Pós"))
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_diast_pos"], name="Diastólica Pós"))
                st.plotly_chart(fig_pa, use_container_width=True)
            
            st.subheader("Glicemia (pré vs pós)")
            fig_g = px.bar(df_c, x="data", y=["glic_antes", "glic_apos"], barmode="group")
            st.plotly_chart(fig_g, use_container_width=True)

    # --- ABA 2: REGISTOS DO CLIENTE ---
    with tabs_clin[2]:
        st.subheader("📥 Submissões Recentes (App Cliente)")
        df_envios = carregar_reports_cliente(conn)
        if df_envios.empty:
            st.info("Sem submissões pendentes.")
        else:
            st.dataframe(df_envios, hide_index=True, use_container_width=True)

    # --- ABA 3: GESTÃO DE RELATÓRIOS ---
    with tabs_clin[3]:
        st.subheader("✍️ Publicar Relatório de Sessão")
        with st.form("relatorio_clinico_final"):
            c_a, c_b = st.columns(2)
            dt = c_a.date_input("Data", value=date.today())
            sem = c_b.number_input("Semana", 1, 12, 1)
            fase = st.selectbox("Fase", ["Inicial", "Desenvolvimento", "Melhoria"])
            txt = st.text_area("Notas Clínicas / Conclusão")
            if st.form_submit_button("💾 Gravar na Base de Dados"):
                cur = conn.cursor()
                cur.execute("INSERT INTO sessoes_v3 (data, semana, fase, tipo, relatorio_clinico, validado) VALUES (?,?,?,?,?,1)",
                            (dt.isoformat(), int(sem), fase, "Misto", txt))
                conn.commit()
                st.success("✅ Relatório guardado com sucesso!")

    # --- ABA 4: ANÁLISE ESTATÍSTICA ---
    with tabs_clin[4]:
        st.subheader("🧪 Análise de Significância Estatística")
        if df_hist.empty:
            st.info("Dados insuficientes para análise.")
        else:
            # 1. Correlação
            st.markdown("#### 1. Correlação: Volume vs. Esforço (PSE)")
            vol = df_hist['reps_total'] * df_hist['series_total']
            res_corr, p_corr = stats.pearsonr(vol, df_hist['pse'])
            
            col1, col2 = st.columns(2)
            col1.metric("Coeficiente r", f"{res_corr:.2f}")
            col2.metric("P-Valor", f"{p_corr:.4f}")
            
            # 2. Regressão
                fig_reg = px.scatter(df_hist, x=vol, y="pse", labels={'x':'Volume', 'pse':'PSE'})
                                 labels={'x':'Volume Total', 'pse':'Esforço (PSE)'},
                                 title="Linha de Tendência (Regressão Linear)")
            st.plotly_chart(fig_reg, use_container_width=True)
            
            # 3. Teste T (Glicemia)
            st.markdown("---")
            st.markdown("#### 2. Teste t: Glicemia (Início vs Atual)")
            g_inicio = df_hist[df_hist['semana'] <= 2]['glic_antes']
            g_atual = df_hist[df_hist['semana'] > 2]['glic_antes']
            
            if len(g_inicio) > 1 and len(g_atual) > 1:
                t_stat, p_val = stats.ttest_ind(g_inicio, g_atual)
                if p_val < 0.05:
                    st.success(f"Diferença significativa encontrada! (p={p_val:.4f})")
                else:
                    st.info(f"Sem diferença estatística relevante (p={p_val:.4f})")
