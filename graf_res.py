import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import sqlite3
import scipy.stats as stats
import base64
import os

st.set_page_config(page_title="BestCare Pro | Sistema Integrado", page_icon="🫀", layout="wide")

# ---------- ESTILOS CLÍNICOS E TABELAS ----------
st.markdown("""
    <style>
    .main { background-color: #f4f6f9; }
    h1, h2, h3 { color: #2c3e50; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    /* Tabelas de Prescrição Estilizadas */
    .prescricao-table {
        width: 100%; border-collapse: collapse; margin: 10px 0;
        background-color: white; border-radius: 8px; overflow: hidden;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .prescricao-table th { background-color: #2c3e50; color: white; padding: 12px; text-align: left; }
    .prescricao-table td { padding: 10px; border-bottom: 1px solid #eee; font-size: 0.9em; }
    .header-fase { padding: 10px; color: white; font-weight: bold; border-radius: 5px; margin-bottom: 5px; }
    
    /* Cartões de Métricas e Dashboards */
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 4px solid #2980b9; }
    .stButton>button { width: 100%; border-radius: 6px; height: 3em; border: none; font-weight: 600;
                       background-color: #2c3e50; color: white; transition: all 0.3s ease; }
    .stButton>button:hover { background-color: #34495e; color: white; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    .client-card { background-color: #ffffff; padding: 20px; border-radius: 8px; 
                   box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-top: 4px solid #2980b9; }
                   
    /* Calendário modernizado */
    .cal-day { background:#fff; border-radius:6px; padding:10px; min-height:95px; 
               border:1px solid #e1e8ed; margin:2px; font-size:0.85em; box-shadow: 0 1px 2px rgba(0,0,0,0.02); }
    .cal-inicial { border-left: 4px solid #2ecc71; background-color: #f9fdfa; }
    .cal-desenv  { border-left: 4px solid #f39c12; background-color: #fffcf8; }
    .cal-manutencao { border-left: 4px solid #e74c3c; background-color: #fef9f8; }
    .cal-rest    { background:#f5f7f9; color:#95a5a6; border-color: #ecf0f1; }
    hr { margin-top: 1.5em; margin-bottom: 1.5em; border: 0; border-top: 1px solid #ecf0f1; }
    </style>
    """, unsafe_allow_html=True)

# ---------- PACIENTE E BASE DE DADOS ----------
PACIENTE = {"nome": "José Oliveira", "idade": 55, "fc_max": 145, "fc_rep": 72, "vo2_prev": 35.4}
DATA_INICIO_PROGRAMA = date.today() - timedelta(weeks=5)

def calc_karvonen(int_min, int_max):
    fcr = PACIENTE["fc_max"] - PACIENTE["fc_rep"]
    return int(fcr*int_min + PACIENTE["fc_rep"]), int(fcr*int_max + PACIENTE["fc_rep"])

DB_PATH = "bestcare_v8.db"

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
        data_envio TEXT, pa_sist_pre INTEGER, pa_diast_pre INTEGER, 
        glic_antes INTEGER, pse INTEGER, reps_total INTEGER, 
        comentario TEXT, lido INTEGER DEFAULT 0)""")
    conn.commit()
    return conn

def seed_se_vazio(conn):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM sessoes_v3")
    if c.fetchone()[0] > 0:
        return
    
    hoje = date.today()
    rng = np.random.default_rng(42)

    for i in range(1, 16):
        f = i/15
        fase = "Inicial" if i <= 6 else "Desenvolvimento"
        
        # Cargas e Volumes
        series = 9 if fase == "Inicial" else 12
        n_ex = 6 if fase == "Inicial" else 7
        reps = int(80 + 70*f + rng.integers(-10, 10))
        volume = reps * series
        
        # Dinâmica Fisiológica
        fc_alvo = 102 + (118-102)*f
        fc_media = int(fc_alvo + rng.normal(0, 2))
        fc_pico = fc_media + int(rng.integers(10, 15))
        
        pa_sist_pre = int(132 + rng.normal(0, 3))
        pa_diast_pre = int(83 + rng.normal(0, 2))
        pa_sist_pos = int(pa_sist_pre + 16 - (3*f) + rng.normal(0, 3))
        pa_diast_pos = int(pa_diast_pre + 3 + rng.normal(0, 2))
        
        # PSE estabilizada na zona alvo
        pse = int(13 + rng.integers(-1, 2)) 
        if volume > 1500: 
            pse = int(14 + rng.integers(-1, 2))
            
        glic_a = int(145 - 20*f + rng.normal(0, 4))
        glic_p = int(115 - 10*f + rng.normal(0, 4))
        rir = int(2 + rng.integers(0, 2))
        
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
             f"Sessão {i} ({fase}): Utente estável dentro do limiar prescrito."))
    conn.commit()

def carregar_sessoes(conn):
    return pd.read_sql_query("SELECT * FROM sessoes_v3 ORDER BY data", conn)

def carregar_reports_cliente(conn):
    return pd.read_sql_query("SELECT * FROM reports_cliente ORDER BY data_envio DESC", conn)

def inserir_report_cliente(conn, pa_s, pa_d, glic, pse, reps, comentario):
    c = conn.cursor()
    c.execute("""INSERT INTO reports_cliente (data_envio, pa_sist_pre, pa_diast_pre, glic_antes, pse, reps_total, comentario)
                 VALUES (?,?,?,?,?,?,?)""",
              (datetime.now().isoformat(timespec="minutes"), pa_s, pa_d, glic, pse, reps, comentario))
    conn.commit()

# Inicialização
conn = init_db()
seed_se_vazio(conn)
df_hist = carregar_sessoes(conn)

# ---------- CONTEÚDO DAS PRESCRIÇÕES (ÁREA DO UTENTE) ----------
def render_prescricao_geral(fase):
    if fase == "Inicial":
        color = "#2ecc71"
        rows = """
        <tr><td><b>Aeróbio</b></td><td>5 dias/semana</td><td>RPE 11-12 (leve)</td><td>30'/sessão</td><td>Caminhadas/bicicleta</td></tr>
        <tr><td><b>Força</b></td><td>2 dias/semana</td><td>10-15 reps (leve)</td><td>6-10 exerc. (1-2 séries)</td><td>Máquinas/Pesos livres</td></tr>
        <tr><td><b>Flexibilidade</b></td><td>2 dias/semana</td><td>Estáticos/Dinâmicos</td><td>10-15" cada</td><td>Tai-chi/Alongamento</td></tr>
        """
    elif fase == "Desenvolvimento":
        color = "#f39c12"
        rows = """
        <tr><td><b>Aeróbio</b></td><td>5 dias/semana</td><td>RPE 14-17 (moderado)</td><td>30'/sessão</td><td>Bicicleta/Caminhada rápida</td></tr>
        <tr><td><b>Força</b></td><td>3 dias/semana</td><td>10-12 reps (moderado)</td><td>5-10 exerc. (1-3 séries)</td><td>Pesos livres/Calistenia</td></tr>
        <tr><td><b>Flexibilidade</b></td><td>2 dias/semana</td><td>Estáticos</td><td>15" cada</td><td>Ioga/Alongamento</td></tr>
        """
    else: # Manutenção
        color = "#e74c3c"
        rows = """
        <tr><td><b>Aeróbio</b></td><td>5 dias/semana</td><td>RPE 14-17 (moderado)</td><td>30'/sessão</td><td>Ciclos de baixo impacto</td></tr>
        <tr><td><b>Força</b></td><td>4 dias/semana</td><td>6-12 reps (hipertrofia/força)</td><td>5-10 exerc. (2-5 séries)</td><td>Deadlift, Snatch, Bench Press</td></tr>
        <tr><td><b>Flexibilidade</b></td><td>2 dias/semana</td><td>Estáticos/Ioga</td><td>10-15 reps</td><td>Manutenção da ADM</td></tr>
        """
    
    html = f"""
    <div class="header-fase" style="background-color:{color}">Prescrição para a Fase {fase}</div>
    <table class="prescricao-table">
        <tr><th>Componente</th><th>Frequência</th><th>Intensidade</th><th>Tempo</th><th>Tipo</th></tr>
        {rows}
    </table>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_sessao_tipo(fase):
    st.markdown(f"#### 📝 Detalhe da Sessão Tipo - Fase {fase}")
    if fase == "Inicial":
        data = [
            ["1", "Agachamento (Smith)", "Quadrícepe", "1-2", "10-15", "60-90s"],
            ["2", "Lat Pulldown", "Dorsal", "1-2", "10-15", "60-90s"],
            ["3", "Bench Press (Smith)", "Peitoral", "1-2", "10-15", "60-90s"],
            ["4", "Bicep Curl", "Bícepe", "1-2", "10-15", "60-90s"],
            ["5", "Tricep Extension", "Trícepe", "1-2", "10-15", "60-90s"],
            ["6", "Abdominal Crunch", "Core", "1-2", "10-15", "60-90s"]
        ]
    elif fase == "Desenvolvimento":
        data = [
            ["1", "Agachamento (Smith)", "Quadrícepe", "1-3", "10-12", "90s-3min"],
            ["2", "Deadlift", "Dorsal", "1-3", "10-12", "90s-3min"],
            ["3", "Lat Pulldown", "Dorsal", "1-3", "10-12", "90s-3min"],
            ["4", "Bench Press", "Peitoral", "1-3", "10-12", "90s-3min"],
            ["5", "Bicep Curl", "Bícepe", "1-3", "10-12", "90s-3min"],
            ["6", "Abdominal Crunch", "Core", "1-3", "10-12", "90s-3min"]
        ]
    else: # Manutenção
        data = [
            ["1", "Agachamento/Hang Snatch", "Quadrícepe/Potência", "2-5", "6-12", "90s-3min"],
            ["2", "Deadlift", "Dorsal", "2-5", "6-12", "90s-3min"],
            ["3", "Bench Press", "Peitoral", "2-5", "6-12", "90s-3min"],
            ["4", "Bicep/Tricep DB superset", "Braços", "2-5", "6-12", "90s-3min"],
            ["5", "L-Sit (Progression)", "Core", "2-5", "10-15s", "90s-3min"]
        ]
    df = pd.DataFrame(data, columns=["Ordem", "Exercício", "Músculo", "Séries", "Reps", "Recuperação"])
    st.table(df)

# ---------- SIDEBAR COM LOGÓTIPO LOCAL ----------
def get_logo_html(filename="logo.png"):
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        return f"<img src='data:image/png;base64,{data}' width='180' style='margin-bottom: 10px;'>"
    return "<div style='font-size: 50px;'>🫀</div>"

st.sidebar.markdown(f"""
    <div style='text-align: center; padding-bottom: 20px;'>
        {get_logo_html()}
        <h2 style='color: #2c3e50; margin-bottom: 0;'>BestCare Pro</h2>
        <p style='color: #7f8c8d; font-size: 0.85em; font-weight: 500;'>PLATAFORMA CLÍNICA INTEGRADA</p>
    </div>
""", unsafe_allow_html=True)

user_role = st.sidebar.radio("Navegação do Sistema:", ["👤 Portal do Utente", "🩺 Monitorização Clínica"])

st.sidebar.divider()
st.sidebar.markdown("### Processo Clínico")
st.sidebar.info(f"**Utente:** {PACIENTE['nome']}\n\n**Idade:** {PACIENTE['idade']} anos\n\n**Alvo VO₂:** {PACIENTE['vo2_prev']} ml/kg/min")


# ============================================================
# ÁREA DO CLIENTE
# ============================================================
if user_role == "👤 Portal do Utente":
    st.title(f"Olá, Sr. {PACIENTE['nome'].split()[0]}! 👋")
    tabs = st.tabs(["🚀 Próximo Treino", "📅 Meu Calendário", "💪 Plano de Treino", "📈 A Minha Evolução", "📋 Meus Relatórios"])

    # --- ABA 0: PRÓXIMO TREINO ---
    with tabs[0]:
        st.markdown(f'<div class="client-card"><h4>🎯 Próxima sessão disponível no calendário.</h4></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🏃 Cardio (Zonas Alvo)")
            low, high = calc_karvonen(0.60, 0.75)
            st.metric("FC Alvo Atual", f"{low} - {high} bpm", "Moderada-Intensa")
            fig = go.Figure(go.Indicator(mode="gauge+number", value=(low+high)//2,
                gauge={'axis':{'range':[60,150]},'bar':{'color':"#2F5597"},
                       'steps':[{'range':[60,low],'color':"#e8f5e9"}, {'range':[low,high],'color':"#a5d6a7"}, {'range':[high,150],'color':"#ffcdd2"}]}))
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("🏋️ Dica de Força")
            st.info("💡 Lembre-se: Deve sentir que conseguia fazer +2/3 reps no fim de cada série (RiR 2-3).")

        st.divider()
        with st.form("registo_jose"):
            st.subheader("📝 Registar Dados da Sessão (Pós-Treino)")
            c_pa, c_pb = st.columns(2)
            pa_s_pre = c_pa.number_input("PA Sistólica (Pré-treino)", 90, 200, 120)
            pa_d_pre = c_pb.number_input("PA Diastólica (Pré-treino)", 50, 130, 80)
            ca, cb = st.columns(2)
            g_antes = ca.number_input("Glicose Pré-Treino (mg/dL)", 40, 300, 130)
            pse_jose = cb.slider("Como se sentiu? (PSE 6-20)", 6, 20, 13)
            reps_jose = st.number_input("Total de Repetições", 0, 500, 150)
            coment = st.text_area("Comentário (opcional)", "")
            if st.form_submit_button("Submeter ao Treinador"):
                inserir_report_cliente(conn, pa_s_pre, pa_d_pre, g_antes, pse_jose, reps_jose, coment)
                st.success("✅ Dados enviados e gravados na BD!")

    # --- ABA 1: CALENDÁRIO ---
    with tabs[1]:
        st.subheader("📅 Plano de Atividade Semanal")
        fase_atual = st.selectbox("Visualizar calendário para a fase:", ["Inicial", "Desenvolvimento", "Manutenção"])
        
        if fase_atual == "Inicial":
            config = {0:"Força + Aeróbio", 1:"Aeróbio", 2:"Aeróbio", 3:"Força + Aeróbio", 4:"Aeróbio"}
            cls = "cal-inicial"
        elif fase_atual == "Desenvolvimento":
            config = {0:"Força + Aeróbio", 2:"Força + Aeróbio", 4:"Força + Aeróbio", 1:"Aeróbio", 3:"Aeróbio"}
            cls = "cal-desenv"
        else:
            config = {0:"Força + Aeróbio", 1:"Força + Aeróbio", 3:"Força + Aeróbio", 4:"Força + Aeróbio", 2:"Aeróbio"}
            cls = "cal-manutencao"

        for sem in range(1, 3):
            st.markdown(f"**Semana {sem}**")
            cols = st.columns(7)
            dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
            for i in range(7):
                with cols[i]:
                    if i in config:
                        st.markdown(f'<div class="cal-day {cls}"><b>{dias[i]}</b><br>{config[i]}<br><small>30 min</small></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="cal-day cal-rest"><b>{dias[i]}</b><br>Descanso</div>', unsafe_allow_html=True)

    # --- ABA 2: PLANO DE TREINO ---
    with tabs[2]:
        st.subheader("💪 Orientação Técnica por Fase")
        fase_view = st.radio("Selecione a Fase para consultar:", ["Inicial", "Desenvolvimento", "Manutenção"], horizontal=True)
        render_prescricao_geral(fase_view)
        st.divider()
        render_sessao_tipo(fase_view)

    # --- ABA 3: EVOLUÇÃO ---
    with tabs[3]:
        st.subheader("📊 O meu progresso ao longo do tempo")
        if not df_hist.empty:
            df_plot = df_hist.copy()
            df_plot["data"] = pd.to_datetime(df_plot["data"])
            fig_pa = go.Figure()
            fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_sist_pos"], mode="lines+markers", name="PA Sistólica (pós)"))
            fig_pa.update_layout(title="Pressão Arterial pós-treino", yaxis_title="mmHg")
            st.plotly_chart(fig_pa, use_container_width=True)

    # --- ABA 4: HISTÓRICO ---
    with tabs[4]:
        st.subheader("📁 Histórico de Sessões")
        st.dataframe(df_hist[["data", "semana", "fase", "fc_media", "pa_sist_pos", "pse"]], hide_index=True, use_container_width=True)

# ============================================================
# ÁREA CLÍNICA (EQUIPA)
# ============================================================
else:
    st.title("🩺 Painel de Monitorização Clínica")
    tabs_clin = st.tabs(["📈 Evolução Biométrica e Muscular", "🔥 Análise de Carga", "📥 Registos do Cliente", "📝 Gestão de Relatórios", "🧪 Análise Estatística"])

    # --- ABA CLÍNICA 0: EVOLUÇÃO BIOMÉTRICA E MUSCULAR ---
    with tabs_clin[0]:
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
                st.subheader("Pressão Arterial (Pré vs Pós)")
                fig_pa = go.Figure()
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_sist_pre"], name="Sistólica Pré", line=dict(dash="dot", color="blue")))
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_sist_pos"], name="Sistólica Pós", line=dict(color="blue")))
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_diast_pre"], name="Diastólica Pré", line=dict(dash="dot", color="orange")))
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_diast_pos"], name="Diastólica Pós", line=dict(color="orange")))
                st.plotly_chart(fig_pa, use_container_width=True)
            
            st.divider()
            
            st.subheader("💪 Relação Gráfica: Esforço Percebido (PSE) por Grupo Muscular")
            st.caption("Evolução neuromuscular simulada de acordo com as cargas prescritas ao longo de todo o processo.")
            
            dados_musculos = []
            rng_musc = np.random.default_rng(42)
            semanas_registadas = df_c["semana"].unique()
            
            for sem in semanas_registadas:
                for g in ["Quadrícepe", "Dorsal", "Peitoral", "Bícepe", "Trícepe", "Core"]:
                    pse_base = 13.2 + (rng_musc.normal(0, 0.3))
                    if g == "Quadrícepe": pse_base += 0.8
                    if g == "Core": pse_base -= 0.6
                    dados_musculos.append({"Semana": int(sem), "Grupo Muscular": g, "PSE Específica": round(pse_base, 1)})
            
            df_musc = pd.DataFrame(dados_musculos)
            fig_musc = px.line(df_musc, x="Semana", y="PSE Específica", color="Grupo Muscular", markers=True)
            fig_musc.update_layout(yaxis=dict(range=[6, 20]), xaxis_title="Semana de Treino", yaxis_title="PSE Local (6-20)")
            st.plotly_chart(fig_musc, use_container_width=True)

    # --- ABA CLÍNICA 1: ANÁLISE DE CARGA ---
    with tabs_clin[1]:
        st.subheader("🔥 Relação entre Volume de Treino e Esforço Percebido")
        if not df_hist.empty:
            df_h = df_hist.copy()
            df_h["volume_total"] = df_h["reps_total"] * df_h["series_total"]
            fig_heat = go.Figure(go.Histogram2dContour(x=df_h["volume_total"], y=df_h["pse"], colorscale="RdYlGn_r", contours=dict(coloring="heatmap", showlines=False)))
            fig_heat.add_trace(go.Scatter(x=df_h["volume_total"], y=df_h["pse"], mode="markers", marker=dict(size=10, color=df_h["fc_media"], colorscale="RdYlGn_r", showscale=True)))
            fig_heat.update_layout(xaxis_title="Volume (Reps x Séries)", yaxis_title="PSE (6-20)")
            st.plotly_chart(fig_heat, use_container_width=True)

    # --- ABA CLÍNICA 2: REGISTOS DO CLIENTE ---
    with tabs_clin[2]:
        st.subheader("📥 Submissões Recentes (App Cliente)")
        df_envios = carregar_reports_cliente(conn)
        if df_envios.empty:
            st.info("Sem submissões pendentes.")
        else:
            st.dataframe(df_envios, hide_index=True, use_container_width=True)

    # --- ABA CLÍNICA 3: GESTÃO DE RELATÓRIOS ---
    with tabs_clin[3]:
        st.subheader("✍️ Publicar Relatório de Sessão")
        with st.form("relatorio_clinico_form"):
            c_a, c_b = st.columns(2)
            dt = c_a.date_input("Data", value=date.today())
            sem = c_b.number_input("Semana", 1, 12, 1)
            fase = st.selectbox("Fase", ["Inicial", "Desenvolvimento", "Manutenção"])
            txt = st.text_area("Notas Clínicas / Conclusão")
            if st.form_submit_button("💾 Gravar na Base de Dados"):
                cur = conn.cursor()
                cur.execute("INSERT INTO sessoes_v3 (data, semana, fase, tipo, relatorio_clinico, validado) VALUES (?,?,?,?,?,1)", (dt.isoformat(), int(sem), fase, "Misto", txt))
                conn.commit()
                st.success("✅ Relatório guardado com sucesso!")

    # --- ABA CLÍNICA 4: ANÁLISE ESTATÍSTICA ---
    with tabs_clin[4]:
        st.subheader("🧪 Análise Estatística")
        if df_hist.empty:
            st.info("Dados insuficientes para análise.")
        else:
            st.markdown("#### 1. Correlação: Carga Externa vs. Esforço (PSE)")
            vol = df_hist['reps_total'] * df_hist['series_total']
            res_corr, p_corr = stats.pearsonr(vol, df_hist['pse'])
            
            col1, col2 = st.columns(2)
            col1.metric("Coeficiente r", f"{res_corr:.2f}")
            p_text = "< 0.001" if p_corr < 0.001 else f"{p_corr:.4f}"
            col2.metric("P-Valor", p_text)
            
            fig_reg = px.scatter(df_hist, x=vol, y="pse", labels={'x':'Volume Total', 'pse':'PSE (6-20)'})
            z = np.polyfit(vol, df_hist['pse'], 1)
            p = np.poly1d(z)
            fig_reg.add_trace(go.Scatter(x=vol, y=p(vol), mode='lines', name='Linha de Regressão', line=dict(color='red', dash='dash')))
            st.plotly_chart(fig_reg, use_container_width=True)
