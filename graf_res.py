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
    # Fixei o limite máximo da intensidade em 70% (0.70) para segurança clínica
    fcr = PACIENTE["fc_max"] - PACIENTE["fc_rep"]
    teto_seguro = 0.70 
    limite_max = min(int_max, teto_seguro)
    return int(fcr*int_min + PACIENTE["fc_rep"]), int(fcr*limite_max + PACIENTE["fc_rep"])
DB_PATH = "bestcare_v9.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Adicionadas colunas fc_repouso e hba1c
    c.execute("""CREATE TABLE IF NOT EXISTS sessoes_v3 (
        id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, semana INTEGER, fase TEXT, tipo TEXT,
        fc_repouso INTEGER, fc_media INTEGER, fc_pico INTEGER, 
        pa_sist_pre INTEGER, pa_diast_pre INTEGER, pa_sist_pos INTEGER, pa_diast_pos INTEGER, 
        pse INTEGER, reps_total INTEGER, series_total INTEGER, n_exercicios INTEGER, 
        glic_antes INTEGER, glic_apos INTEGER, hba1c REAL, rir_medio INTEGER,
        relatorio_cliente TEXT, relatorio_clinico TEXT, validado INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS reports_cliente (
        id INTEGER PRIMARY KEY AUTOINCREMENT, data_envio TEXT, pa_sist_pre INTEGER, pa_diast_pre INTEGER, 
        glic_antes INTEGER, pse INTEGER, reps_total INTEGER, comentario TEXT, lido INTEGER DEFAULT 0)""")
    conn.commit()
    return conn

def seed_se_vazio(conn):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM sessoes_v3")
    if c.fetchone()[0] > 0: return
    hoje = date.today()
    rng = np.random.default_rng(42)
    for i in range(1, 16):
        f = i/15
        fase = "Inicial" if i <= 6 else "Desenvolvimento"
        series = 9 if fase == "Inicial" else 12
        n_ex = 6 if fase == "Inicial" else 7
        reps = int(80 + 70*f + rng.integers(-10, 10))
        volume = reps * series
        
        # Adaptação Cardiovascular
        fc_repouso = int(76 - (8 * f) + rng.normal(0, 1)) # Desce de 76 para ~68
        fc_alvo = 102 + (118-102)*f
        fc_media = int(fc_alvo + rng.normal(0, 2))
        fc_pico = fc_media + int(rng.integers(10, 15))
        
        pa_sist_pre = int(135 - (5 * f) + rng.normal(0, 3))
        pa_diast_pre = int(85 - (3 * f) + rng.normal(0, 2))
        pa_sist_pos = int(pa_sist_pre + 16 - (3*f) + rng.normal(0, 3))
        pa_diast_pos = int(pa_diast_pre + 3 + rng.normal(0, 2))
        
        # Limitar PSE para nunca passar de 14 (Moderado - Segurança Clínica)
        pse = int(13 + rng.integers(-1, 1)) # Mantém flutuação segura entre 12 e 14
        if volume > 1500: 
            pse = 14 # Trava nos 14, mesmo com volumes altos
        
        # Adaptação Metabólica
        glic_a = int(145 - 20*f + rng.normal(0, 4))
        glic_p = int(115 - 10*f + rng.normal(0, 4))
        hba1c = round(6.9 - (0.7 * f) + rng.normal(0, 0.05), 1) # Desce de 6.9% para 6.2%
        
        rir = int(2 + rng.integers(0, 2))
        data_s = (hoje - timedelta(days=(16-i)*2)).isoformat()
        
        c.execute("""INSERT INTO sessoes_v3
            (data, semana, fase, tipo, fc_repouso, fc_media, fc_pico, pa_sist_pre, pa_diast_pre, pa_sist_pos, pa_diast_pos,
             pse, reps_total, series_total, n_exercicios, glic_antes, glic_apos, hba1c, rir_medio, relatorio_clinico, validado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (data_s, (i//3)+1, fase, "Misto", fc_repouso, fc_media, fc_pico, pa_sist_pre, pa_diast_pre, pa_sist_pos, pa_diast_pos,
             pse, reps, series, n_ex, glic_a, glic_p, hba1c, rir, f"Sessão {i} ({fase}): Evolução positiva."))
    conn.commit()

def carregar_sessoes(conn):
    return pd.read_sql_query("SELECT * FROM sessoes_v3 ORDER BY data", conn)

def carregar_reports_cliente(conn):
    return pd.read_sql_query("SELECT * FROM reports_cliente ORDER BY data_envio DESC", conn)

def inserir_report_cliente(conn, pa_s, pa_d, glic, pse, reps, comentario):
    c = conn.cursor()
    c.execute("""INSERT INTO reports_cliente (data_envio, pa_sist_pre, pa_diast_pre, glic_antes, pse, reps_total, comentario)
                 VALUES (?,?,?,?,?,?,?)""", (datetime.now().isoformat(timespec="minutes"), pa_s, pa_d, glic, pse, reps, comentario))
    conn.commit()

conn = init_db()
seed_se_vazio(conn)
df_hist = carregar_sessoes(conn)

# ---------- PRESCRIÇÕES COMO DATAFRAMES NATIVOS DO STREAMLIT ----------
def render_prescricao_geral(fase):
    st.markdown(f"#### Prescrição Geral — {fase}")
    if fase == "Inicial":
        data = [
            ["Aeróbio", "5 dias/semana", "RPE 11-12 (leve)", "30'/sessão", "Caminhadas/Bicicleta"],
            ["Força", "2 dias/semana", "10-15 reps (leve)", "6-10 exerc.", "Máquinas/Pesos livres"],
            ["Flexibilidade", "2 dias/semana", "Lento s/ dor", "10-15\"/cada", "Dinâmicos/Estáticos"]
        ]
    elif fase == "Desenvolvimento":
        data = [
            ["Aeróbio", "5 dias/semana", "RPE 14-17 (moderado)", "30'/sessão", "Caminhada rápida/Bicicleta"],
            ["Força", "3 dias/semana", "10-12 reps (moderada)", "5-10 exerc.", "Pesos livres/Calistenia"],
            ["Flexibilidade", "2 dias/semana", "Lento s/ dor", "15\"/cada", "Dinâmicos/Estáticos"]
        ]
    else:  # Manutenção
        data = [
            ["Aeróbio", "5 dias/semana", "RPE 14-17 (moderada)", "30'/sessão",
             "Caminhada rápida intervalada c/ caminhada lenta (cíclicos baixo impacto)"],
            ["Força (hipertrofia e força muscular)", "4 dias/semana (não consecutivos)",
             "6-12 reps · descanso 90\"-3' (hipertrofia) / 2'-5' (força)",
             "5-10 exerc. · 2-5 séries",
             "Deadlift, Hang Clean, Bench Press, Squat, Hang Snatch, L-Sit"],
            ["Flexibilidade", "2 dias/semana",
             "Dinâmicos: lento c/ execução correta · Estáticos: máxima ROM s/ dor",
             "Dinâmicos: 10 reps · Estáticos: 10-15\"",
             "Estático, dinâmico, ioga ou pilates"]
        ]
    df = pd.DataFrame(data, columns=["Componente", "Frequência", "Intensidade", "Tempo", "Tipo"])
    st.dataframe(df, hide_index=True, use_container_width=True)

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
    else:  # Manutenção
        data = [
            ["1", "Agachamento / Hang Snatch", "Quadrícepe", "2-5", "3-4", "2-5min"],
            ["2", "Deadlift", "Dorsal", "2-5", "6-12", "90s-3min"],
            ["3", "Bench Press", "Peitoral", "2-5", "6-12", "90s-3min"],
            ["4", "DB Bicep curl / Tricep extension", "Bícepe; Trícepe", "2-5", "6-12", "90s-3min"],
            ["5", "L-Sit (com progressões)", "Core", "6-12", "10-15s", "90s-3min"]
        ]
    df = pd.DataFrame(data, columns=["Ordem", "Exercício", "Músculo", "Séries", "Reps", "Recuperação"])
    st.dataframe(df, hide_index=True, use_container_width=True)

# ---------- SIDEBAR COM LOGÓTIPO LOCAL ----------
def get_logo_html(filename="logo.png"):
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        return f"<img src='data:image/png;base64,{data}' width='300' style='margin-bottom: 0px;'>"
    return "<div style='font-size: 40px;'>🫀</div>"

st.sidebar.markdown(f"""
    <div style='text-align: center; padding-bottom: 10px;'>
        {get_logo_html()}
        <h2 style='color: #2c3e50; margin-bottom: 0;'>BestCare Pro</h2>
        <p style='color: #7f8c8d; font-size: 0.85em; font-weight: 550;'>PLATAFORMA CLÍNICA INTEGRADA</p>
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

    with tabs[0]:
        st.markdown(f'<div class="client-card"><h4>🎯 Próxima sessão disponível no calendário.</h4></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🏃 Cardio (Zonas Alvo)")
            low, high = calc_karvonen(0.60, 0.75)
            st.metric("FC Alvo Atual", f"{low} - {high} bpm", "Moderada")
            fig = go.Figure(go.Indicator(mode="gauge+number", value=(low+high)//2,
                gauge={'axis':{'range':[60,150]},'bar':{'color':"#2F5597"},
                       'steps':[{'range':[60,low],'color':"#e8f5e9"}, {'range':[low,high],'color':"#a5d6a7"}, {'range':[high,150],'color':"#ffcdd2"}]}))
            fig.update_layout(height=550, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("🏋️ Dica de Força")
            st.info("💡 Lembre-se: Deve sentir que conseguia fazer +2/3 reps no fim de cada série (RiR 2-3).")
            st.divider()
            with st.form("registo_jose"):
                st.subheader("📝 Registar Dados da Sessão")
                c_pa, c_pb = st.columns(2)
                pa_s_pre = c_pa.number_input("PA Sistólica (Pré)", 90, 200, 120)
                pa_d_pre = c_pb.number_input("PA Diastólica (Pré)", 50, 130, 80)
                ca, cb = st.columns(2)
                g_antes = ca.number_input("Glicose Pré (mg/dL)", 40, 300, 130)
                pse_jose = cb.slider("PSE (6-20)", 6, 20, 13)
                reps_jose = st.number_input("Total de Repetições", 0, 500, 150)
                coment = st.text_area("Comentário (opcional)", "")
                if st.form_submit_button("Submeter ao Treinador"):
                    inserir_report_cliente(conn, pa_s_pre, pa_d_pre, g_antes, pse_jose, reps_jose, coment)
                    st.success("✅ Dados gravados com sucesso!")

    with tabs[1]:
        st.subheader("📅 Plano de Atividade do Programa")
        vista_calendario = st.radio("Selecione a Vista:", ["Por Fase (Detalhe Semanal)", "Vista Global (Programa Completo)"], horizontal=True)
        meses_pt = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        dias_pt = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

        if vista_calendario == "Por Fase (Detalhe Semanal)":
            fase_atual = st.selectbox("Visualizar calendário para a fase:", ["Inicial", "Desenvolvimento", "Manutenção"])
            if fase_atual == "Inicial":
                config = {0:"Força + Aeróbio", 1:"Aeróbio", 2:"Aeróbio", 3:"Força + Aeróbio", 4:"Aeróbio"}
                cls = "cal-inicial"; inicio_fase = DATA_INICIO_PROGRAMA
            elif fase_atual == "Desenvolvimento":
                config = {0:"Força + Aeróbio", 2:"Força + Aeróbio", 4:"Força + Aeróbio", 1:"Aeróbio", 3:"Aeróbio"}
                cls = "cal-desenv"; inicio_fase = DATA_INICIO_PROGRAMA + timedelta(weeks=8)
            else:
                config = {0:"Força + Aeróbio", 1:"Força + Aeróbio", 3:"Força + Aeróbio", 4:"Força + Aeróbio", 2:"Aeróbio"}
                cls = "cal-manutencao"; inicio_fase = DATA_INICIO_PROGRAMA + timedelta(weeks=16)

            for sem in range(1, 3):
                inicio_semana = inicio_fase + timedelta(weeks=sem-1)
                st.markdown(f"**Semana {sem}** (Início a {inicio_semana.day} de {meses_pt[inicio_semana.month-1]})")
                cols = st.columns(7)
                for i in range(7):
                    dia_atual = inicio_semana + timedelta(days=i)
                    str_dia = f"{dias_pt[dia_atual.weekday()]}, {dia_atual.day} {meses_pt[dia_atual.month-1]}"
                    with cols[i]:
                        if i in config:
                            st.markdown(f'<div class="cal-day {cls}"><b>{str_dia}</b><br>{config[i]}<br><small>30 min</small></div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="cal-day cal-rest"><b>{str_dia}</b><br>Descanso</div>', unsafe_allow_html=True)
        else:
            st.info("Visão macro do processo de reabilitação estruturado a longo prazo.")
            st.markdown("🟢 **Semanas 1-8:** Fase Inicial | 🟠 **Semanas 9-16:** Fase Desenvolvimento | 🔴 **Semanas 17+:** Manutenção")
            for mes in range(5):
                inicio_mes = DATA_INICIO_PROGRAMA + timedelta(weeks=mes*4)
                st.markdown(f"**Mês {mes+1}** ({meses_pt[inicio_mes.month-1]})")
                cols = st.columns(4)
                for sem_no_mes in range(4):
                    sem_total = (mes * 4) + sem_no_mes + 1
                    with cols[sem_no_mes]:
                        if sem_total <= 8: cls_global = "cal-inicial"; titulo = "Fase Inicial"
                        elif sem_total <= 16: cls_global = "cal-desenv"; titulo = "Desenvolvimento"
                        else: cls_global = "cal-manutencao"; titulo = "Manutenção"
                        st.markdown(f'<div class="cal-day {cls_global}"><b>Semana {sem_total}</b><br><small>{titulo}</small></div>', unsafe_allow_html=True)
                st.write("")

    with tabs[2]:
        st.subheader("💪 Orientação Técnica por Fase")
        fase_view = st.radio("Selecione a Fase para consultar:", ["Inicial", "Desenvolvimento", "Manutenção"], horizontal=True)
        render_prescricao_geral(fase_view)
        st.divider()
        render_sessao_tipo(fase_view)

    # --- ABA 3: EVOLUÇÃO (ATUALIZADA COM OS NOVOS PARÂMETROS METABÓLICOS) ---
    with tabs[3]:
        st.subheader("📊 O meu progresso de Saúde Global")
        if df_hist.empty:
            st.info("Ainda não existem registos.")
        else:
            df_plot = df_hist.copy()
            df_plot["data"] = pd.to_datetime(df_plot["data"])
            
            # Grelha 2x2 para melhor visualização
            col_a, col_b = st.columns(2)
            
            with col_a:
                # 1. Gráfico de Pressão Arterial
                fig_pa = go.Figure()
                fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_sist_pre"], mode="lines+markers", name="Sistólica (Pré)", line=dict(color="#3498db", dash="dot")))
                fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_sist_pos"], mode="lines+markers", name="Sistólica (Pós)", line=dict(color="#2980b9")))
                fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_diast_pre"], mode="lines+markers", name="Diastólica (Pré)", line=dict(color="#e67e22", dash="dot")))
                fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_diast_pos"], mode="lines+markers", name="Diastólica (Pós)", line=dict(color="#d35400")))
                fig_pa.update_layout(title="Adaptação da Pressão Arterial", yaxis_title="mmHg", legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_pa, use_container_width=True)

                # 2. Gráfico de Glicémia
                fig_glic = go.Figure()
                fig_glic.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["glic_antes"], mode="lines+markers", name="Pré-Treino", line=dict(color="#9b59b6")))
                fig_glic.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["glic_apos"], mode="lines+markers", name="Pós-Treino", line=dict(color="#8e44ad")))
                fig_glic.update_layout(title="Controlo de Glicémia", yaxis_title="mg/dL", legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_glic, use_container_width=True)

            with col_b:
                # 3. Gráfico de Frequência Cardíaca (Múltiplas Zonas)
                fig_fc = go.Figure()
                fig_fc.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["fc_repouso"], mode="lines+markers", name="FC Repouso", line=dict(color="#2ecc71")))
                fig_fc.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["fc_media"], mode="lines+markers", name="FC Média (Treino)", line=dict(color="#f1c40f")))
                fig_fc.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["fc_pico"], mode="lines+markers", name="FC Máx (Pico Treino)", line=dict(color="#e74c3c")))
                fig_fc.update_layout(title="Frequência Cardíaca (Repouso e Esforço)", yaxis_title="bpm", legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_fc, use_container_width=True)

                # 4. Gráfico de Hemoglobina Glicada (HbA1c)
                fig_hba1c = px.line(df_plot, x="data", y="hba1c", markers=True, title="Hemoglobina Glicada (HbA1c)")
                fig_hba1c.update_traces(line_color="#1abc9c")
                fig_hba1c.update_layout(yaxis_title="%", yaxis=dict(range=[5.0, 7.5]))
                st.plotly_chart(fig_hba1c, use_container_width=True)

    with tabs[4]:
        st.subheader("📁 Histórico de Sessões")
        st.dataframe(df_hist[["data", "semana", "fase", "fc_media", "pa_sist_pos", "pse"]], hide_index=True, use_container_width=True)

# ============================================================
# ÁREA CLÍNICA (EQUIPA)
# ============================================================
else:
    st.title("🩺 Painel de Monitorização Clínica")
    tabs_clin = st.tabs(["📈 Evolução Biométrica", "🔥 Análise de Carga", "📥 Registos do Cliente", "📝 Gestão de Relatórios", "🧪 Estatística"])

    with tabs_clin[0]:
        if df_hist.empty: st.info("Sem dados.")
        else:
            df_c = df_hist.copy(); df_c["data"] = pd.to_datetime(df_c["data"])
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
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_sist_pre"], name="Sist. Pré", line=dict(dash="dot", color="blue")))
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_sist_pos"], name="Sist. Pós", line=dict(color="blue")))
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_diast_pre"], name="Diast. Pré", line=dict(dash="dot", color="orange")))
                fig_pa.add_trace(go.Scatter(x=df_c["data"], y=df_c["pa_diast_pos"], name="Diast. Pós", line=dict(color="orange")))
                st.plotly_chart(fig_pa, use_container_width=True)
            
            st.divider()
            st.subheader("💪 Esforço Percebido (PSE) por Grupo Muscular")
            dados_musculos = []
            rng_musc = np.random.default_rng(42)
            for sem in df_c["semana"].unique():
                for g in ["Quadrícepe", "Dorsal", "Peitoral", "Bícepe", "Trícepe", "Core"]:
                    pse_base = 13.2 + (rng_musc.normal(0, 0.3))
                    if g == "Quadrícepe": pse_base += 0.8
                    if g == "Core": pse_base -= 0.6
                    dados_musculos.append({"Semana": int(sem), "Grupo Muscular": g, "PSE Específica": round(pse_base, 1)})
            fig_musc = px.line(pd.DataFrame(dados_musculos), x="Semana", y="PSE Específica", color="Grupo Muscular", markers=True)
            fig_musc.update_layout(yaxis=dict(range=[6, 20]))
            st.plotly_chart(fig_musc, use_container_width=True)

    with tabs_clin[1]:
        st.subheader("🔥 Relação entre Volume de Treino e Esforço Percebido")
        if not df_hist.empty:
            df_h = df_hist.copy(); df_h["volume_total"] = df_h["reps_total"] * df_h["series_total"]
            fig_heat = go.Figure(go.Histogram2dContour(x=df_h["volume_total"], y=df_h["pse"], colorscale="RdYlGn_r", contours=dict(coloring="heatmap", showlines=False)))
            fig_heat.add_trace(go.Scatter(x=df_h["volume_total"], y=df_h["pse"], mode="markers", marker=dict(size=10, color=df_h["fc_media"], colorscale="RdYlGn_r", showscale=True)))
            st.plotly_chart(fig_heat, use_container_width=True)

    with tabs_clin[2]:
        st.subheader("📥 Submissões Recentes (App Cliente)")
        df_envios = carregar_reports_cliente(conn)
        if df_envios.empty: st.info("Sem submissões pendentes.")
        else: st.dataframe(df_envios, hide_index=True, use_container_width=True)

    with tabs_clin[3]:
        st.subheader("✍️ Publicar Relatório de Sessão")
        with st.form("relatorio_clinico_form"):
            c_a, c_b = st.columns(2)
            dt = c_a.date_input("Data", value=date.today())
            sem = c_b.number_input("Semana", 1, 12, 1)
            fase = st.selectbox("Fase", ["Inicial", "Desenvolvimento", "Manutenção"])
            txt = st.text_area("Notas Clínicas")
            if st.form_submit_button("💾 Gravar"):
                conn.cursor().execute("INSERT INTO sessoes_v3 (data, semana, fase, tipo, relatorio_clinico, validado) VALUES (?,?,?,?,?,1)", (dt.isoformat(), int(sem), fase, "Misto", txt))
                conn.commit()
                st.success("✅ Relatório guardado!")

    with tabs_clin[4]:
        st.subheader("🧪 Análise Estatística")
        if df_hist.empty: st.info("Dados insuficientes.")
        else:
            vol = df_hist['reps_total'] * df_hist['series_total']
            res_corr, p_corr = stats.pearsonr(vol, df_hist['pse'])
            col1, col2 = st.columns(2)
            col1.metric("Coeficiente r", f"{res_corr:.2f}")
            col2.metric("P-Valor", "< 0.001" if p_corr < 0.001 else f"{p_corr:.4f}")
            fig_reg = px.scatter(df_hist, x=vol, y="pse", labels={'x':'Volume Total', 'pse':'PSE (6-20)'})
            p = np.poly1d(np.polyfit(vol, df_hist['pse'], 1))
            fig_reg.add_trace(go.Scatter(x=vol, y=p(vol), mode='lines', name='Regressão', line=dict(color='red', dash='dash')))
            st.plotly_chart(fig_reg, use_container_width=True)
