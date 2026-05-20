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

# Imports para o PDF (ReportLab)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from io import BytesIO

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
# Recuamos 52 semanas (1 ano inteiro)
DATA_INICIO_PROGRAMA = date.today() - timedelta(weeks=52)

def calc_karvonen(int_min, int_max):
    fcr = PACIENTE["fc_max"] - PACIENTE["fc_rep"]
    teto_seguro = 0.70 
    limite_max = min(int_max, teto_seguro)
    return int(fcr*int_min + PACIENTE["fc_rep"]), int(fcr*limite_max + PACIENTE["fc_rep"])

DB_PATH = "bestcare_v11.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
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
    
    rng = np.random.default_rng(42)
    
    # Gerar plano temporal para 52 Semanas (1 Ano)
    sessoes_plan = []
    for week in range(52):
        inicio_semana = DATA_INICIO_PROGRAMA + timedelta(weeks=week)
        # 4 semanas (1 mês) - Fase Inicial
        if week < 4:
            fase = "Inicial"
            dias_treino = [0, 2, 4] 
        # 40 semanas (10 meses) - Fase Desenvolvimento
        elif week < 44:
            fase = "Desenvolvimento"
            dias_treino = [0, 2, 4] 
        # 8 semanas (2 meses) - Fase Manutenção
        else:
            fase = "Manutenção"
            dias_treino = [0, 1, 3, 4] 
            
        for d in dias_treino:
            sessoes_plan.append({
                "data": inicio_semana + timedelta(days=d),
                "semana": week + 1,
                "fase": fase
            })
            
    total_sessoes = len(sessoes_plan)
    
    for i, s in enumerate(sessoes_plan):
        f = i / total_sessoes 
        fase = s["fase"]
        
        if fase == "Inicial":
            series = 9
            n_ex = 6
            reps = int(120 + rng.integers(-10, 10))
        elif fase == "Desenvolvimento":
            series = 12
            n_ex = 7
            reps = int(140 + rng.integers(-15, 15))
        else: 
            series = 16 
            n_ex = 8
            reps = int(160 + rng.integers(-15, 15))
            
        volume = reps * series
        
        # Adaptação Cardiovascular a 1 ano
        fc_repouso = int(76 - (14 * f) + rng.normal(0, 1.5))
        fc_alvo = 102 + (125-102)*f
        fc_media = int(fc_alvo + rng.normal(0, 3))
        fc_pico = fc_media + int(rng.integers(12, 18))
        
        # Pressão Arterial
        pa_sist_pre = int(135 - (15 * f) + rng.normal(0, 2))
        pa_diast_pre = int(85 - (10 * f) + rng.normal(0, 2))
        pa_sist_pos = int(pa_sist_pre + 15 - (5*f) + rng.normal(0, 3))
        pa_diast_pos = int(pa_diast_pre + 5 + rng.normal(0, 2))
        
        # PSE
        pse = int(12 + (2 * f) + rng.integers(-1, 2)) 
        if pse > 14: pse = 14
        
        # Adaptação Metabólica
        glic_a = int(145 - 40*f + rng.normal(0, 4))
        glic_p = int(115 - 25*f + rng.normal(0, 4))
        hba1c = round(6.9 - (1.1 * f) + rng.normal(0, 0.05), 1)
        
        rir = int(2 + rng.integers(0, 2))
        data_s = s["data"].isoformat()
        
        c.execute("""INSERT INTO sessoes_v3
            (data, semana, fase, tipo, fc_repouso, fc_media, fc_pico, pa_sist_pre, pa_diast_pre, pa_sist_pos, pa_diast_pos,
             pse, reps_total, series_total, n_exercicios, glic_antes, glic_apos, hba1c, rir_medio, relatorio_clinico, validado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (data_s, s["semana"], fase, "Misto", fc_repouso, fc_media, fc_pico, pa_sist_pre, pa_diast_pre, pa_sist_pos, pa_diast_pos,
             pse, reps, series, n_ex, glic_a, glic_p, hba1c, rir, f"Sessão validada de acompanhamento anual."))
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

# ---------- FUNÇÃO GERADORA DE PDF CLÍNICO ----------
def gerar_pdf_relatorio(paciente, primeira, ultima, total_sessoes_reg):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle("titulo", parent=styles["Heading1"],
                                   fontSize=16, textColor=colors.HexColor("#2c3e50"),
                                   spaceAfter=12, alignment=1)
    estilo_h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                               fontSize=12, textColor=colors.HexColor("#2980b9"),
                               spaceBefore=14, spaceAfter=6)
    estilo_normal = ParagraphStyle("body", parent=styles["BodyText"],
                                   fontSize=10, leading=14, spaceAfter=6)
    
    story = []
    story.append(Paragraph("🏥 RELATÓRIO CLÍNICO DE EVOLUÇÃO E TRANSIÇÃO DE ALTA", estilo_titulo))
    story.append(Paragraph(f"<b>Data do Relatório:</b> {date.today().strftime('%d/%m/%Y')}", estilo_normal))
    
    story.append(Paragraph("1. IDENTIFICAÇÃO DO DOENTE", estilo_h2))
    tab_id = Table([
        ["Nome", paciente["nome"]],
        ["Idade", f"{paciente['idade']} anos"],
        ["Programa", "Reabilitação e Exercício Clínico Integrado (1 Ano / 52 Semanas)"],
        ["Sessões Validadas", str(total_sessoes_reg)],
    ], colWidths=[5*cm, 11*cm])
    tab_id.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ecf0f1")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bdc3c7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tab_id)
    
    story.append(Paragraph("2. ANÁLISE DE EVOLUÇÃO FISIOLÓGICA E METABÓLICA", estilo_h2))
    tab_ev = Table([
        ["Parâmetro", "Basal", "Atual"],
        ["FC de Repouso (bpm)", str(primeira["fc_repouso"]), str(ultima["fc_repouso"])],
        ["PA Pré-esforço (mmHg)", 
         f"{primeira['pa_sist_pre']}/{primeira['pa_diast_pre']}", 
         f"{ultima['pa_sist_pre']}/{ultima['pa_diast_pre']}"],
        ["Glicemia Pré-treino (mg/dL)", str(primeira["glic_antes"]), str(ultima["glic_antes"])],
        ["HbA1c (%)", f"{primeira['hba1c']}", f"{ultima['hba1c']}"],
    ], colWidths=[7*cm, 4.5*cm, 4.5*cm])
    tab_ev.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2980b9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bdc3c7")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tab_ev)
    
    story.append(Paragraph("<b>Parecer Evolutivo:</b>", estilo_normal))
    story.append(Paragraph(
        "Observa-se uma consolidação fisiológica notória. A adaptação cardiovascular permitiu uma "
        "otimização do débito cardíaco com redução visível da FC de repouso e normalização dos valores "
        "tensionais. A nível metabólico, o planeamento progressivo do volume e intensidade induziu uma "
        "melhoria acentuada na sensibilidade à insulina, refletida de forma expressiva na queda da HbA1c "
        "para níveis de controlo não-patológicos.", estilo_normal))
        
    # ---------- NOVA SECÇÃO DO PDF: PREVISÕES VO2 MAX ----------
    story.append(Paragraph("3. MODELAÇÃO CARDIORESPIRATÓRIA E PREVISÃO DE VO₂ MÁX", estilo_h2))
    tab_pred = Table([
        ["Fase Clínica", "Métricas de Adaptação Estimadas", "Impacto no VO₂ Máx Previsto"],
        ["Desenvolvimento\n(10 Meses)", "Redução da FC basal em 0.59%/mês.\nMelhoria de 10.84%/mês no VO₂máx.", "+24.0 mL/kg/min acumulados\n(Meta: ~59.4 mL/kg/min)"],
        ["Manutenção\n(2 Meses)", "Estabilização da FC basal (platô seguro nos 67 bpm).\nConsolidação da taxa metabólica.", "Retenção estável do pico adquirido\n(Platô: ~59.4 mL/kg/min)"],
    ], colWidths=[3.5*cm, 7.5*cm, 5*cm])
    tab_pred.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27ae60")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bdc3c7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tab_pred)
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("4. INDICAÇÕES DE ESTILO DE VIDA E INTEGRAÇÃO", estilo_h2))
    story.append(Paragraph(
        "O doente encontra-se capacitado e com literacia funcional suficiente para adotar um "
        "comportamento autónomo. Para garantir a consolidação dos ganhos a longo prazo, indicam-se "
        "as seguintes guidelines baseadas na Fase de Manutenção:", estilo_normal))
        
    bullets = [
        ("Gestão Cardiovascular (Aeróbio):", 
         "Manter atividade aeróbia 5 dias por semana (caminhada rápida intervalada com intensidade cíclica). "
         "Somar pelo menos 150 minutos semanais mantendo uma zona de RPE 14-17 (moderada)."),
        ("Treino de Força e Hipertrofia:", 
         "Manter a rotina de 2 a 4 dias por semana (não consecutivos) focada em exercícios multiarticulares "
         "(Agachamento, Deadlift, Bench Press). Realizar entre 6 a 12 repetições com RiR de 2 a 3."),
        ("Rotina Ativa no Dia-a-Dia:", 
         "Privilegiar o transporte ativo, evitar o uso de elevadores e quebrar ciclos de sedentarismo "
         "prolongado a cada 90 minutos."),
        ("Sinais de Alerta e Monitorização:", 
         "O utente está familiarizado com a monitorização de sinais vitais e da Escala de Esforço de Borg. "
         "Aconselhada verificação semanal em casa da Glicemia de jejum e Pressão Arterial, contactando a "
         "equipa de tratamento primário em caso de recrudescimento sistemático dos valores."),
    ]
    for titulo, texto in bullets:
        story.append(Paragraph(f"• <b>{titulo}</b> {texto}", estilo_normal))
        
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph(
        "<i>Equipa de Fisiologia do Exercício | BestCare Pro</i>",
        ParagraphStyle("ass", parent=estilo_normal, alignment=2, textColor=colors.HexColor("#7f8c8d"))
    ))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

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
            ["Aquecimento específico", "Agachamento", "Quadrícepe", "2-5", "3-4 (80% da carga)", "90\"-3'"],
            ["1", "Deadlift / Hang Clean", "Dorsal · Dorsal/Deltoide", "2-5", "6-12", "90s-3min (hip.) / 2-5min (força)"],
            ["2", "Squat / Hang Snatch", "Quadrícepe · Potência", "2-5", "6-12", "90s-3min (hip.) / 2-5min (força)"],
            ["3", "Bench Press", "Peitoral", "2-5", "6-12", "90s-3min (hip.) / 2-5min (força)"],
            ["4", "Bicep / Tricep DB superset", "Braços", "2-5", "6-12", "90s-3min"],
            ["5", "L-Sit (com progressões)", "Core", "2-5", "10-15s", "90s-3min"]
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
        
        # Contador cumulativo de horas de treino
        n_sessoes_feitas = len(df_hist)
        horas_totais = n_sessoes_feitas * 0.5  
        h_int = int(horas_totais)
        m_int = int(round((horas_totais - h_int) * 60))
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #2c3e50 0%, #2980b9 100%); 
                        color: white; padding: 22px; border-radius: 10px; margin: 12px 0 18px 0;
                        box-shadow: 0 4px 10px rgba(0,0,0,0.08);">
                <div style="font-size: 0.95em; opacity: 0.85; letter-spacing: 0.5px;">⏱️ TEMPO ACUMULADO DE TREINO</div>
                <div style="font-size: 2.2em; font-weight: 700; margin-top: 6px;">
                    Já treinou {h_int}h{m_int:02d}min!
                </div>
                <div style="font-size: 0.9em; opacity: 0.85; margin-top: 4px;">
                    {n_sessoes_feitas} sessões validadas · continue o excelente trabalho 💪
                </div>
            </div>
        """, unsafe_allow_html=True)

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
                    st.rerun()

    with tabs[1]:
        st.subheader("📅 Plano de Atividade do Programa")
        vista_calendario = st.radio("Selecione a Vista:", ["Por Fase (Detalhe Semanal)", "Vista Global (Programa Completo)"], horizontal=True)
        meses_pt = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        dias_pt = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

        if vista_calendario == "Por Fase (Detalhe Semanal)":
            fase_atual = st.selectbox("Visualizar calendário para a fase:", ["Inicial", "Desenvolvimento", "Manutenção"])
            if fase_atual == "Inicial":
                config = {0:"Força + Aeróbio", 1:"Aeróbio", 2:"Força + Aeróbio", 3:"Aeróbio", 4:"Força + Aeróbio"}
                cls = "cal-inicial"
                inicio_fase = DATA_INICIO_PROGRAMA
                n_semanas = 4
            elif fase_atual == "Desenvolvimento":
                config = {0:"Força + Aeróbio", 1:"Aeróbio", 2:"Força + Aeróbio", 3:"Aeróbio", 4:"Força + Aeróbio"}
                cls = "cal-desenv"
                inicio_fase = DATA_INICIO_PROGRAMA + timedelta(weeks=4)
                n_semanas = 40
            else:
                config = {0:"Força + Aeróbio", 1:"Força + Aeróbio", 2:"Aeróbio", 3:"Força + Aeróbio", 4:"Força + Aeróbio"}
                cls = "cal-manutencao"
                inicio_fase = DATA_INICIO_PROGRAMA + timedelta(weeks=44)
                n_semanas = 8
                
            st.caption(f"Fase **{fase_atual}** · {n_semanas} semanas · {len(config)} sessões/semana")
            
            if n_semanas <= 8:
                intervalos = [(1, n_semanas)]
            else:
                intervalos = [(i, min(i+3, n_semanas)) for i in range(1, n_semanas+1, 4)]
                
            for ini, fim in intervalos:
                if n_semanas > 8:
                    container = st.expander(f"Semanas {ini} – {fim}", expanded=(ini == 1))
                else:
                    container = st.container()
                with container:
                    for sem in range(ini, fim+1):
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
            st.info("Visão macro do processo de reabilitação estruturado a longo prazo (1 Ano / 52 Semanas).")
            st.markdown("🟢 **Semanas 1-4:** Fase Inicial | 🟠 **Semanas 5-44:** Fase Desenvolvimento | 🔴 **Semanas 45-52:** Manutenção")
            for bloco in range(13):
                inicio_bloco = DATA_INICIO_PROGRAMA + timedelta(weeks=bloco*4)
                st.markdown(f"**Mês Clínico {bloco+1}** (A partir de {meses_pt[inicio_bloco.month-1]})")
                cols = st.columns(4)
                for sem_no_bloco in range(4):
                    sem_total = (bloco * 4) + sem_no_bloco + 1
                    with cols[sem_no_bloco]:
                        if sem_total <= 4: cls_global = "cal-inicial"; titulo = "Fase Inicial"
                        elif sem_total <= 44: cls_global = "cal-desenv"; titulo = "Desenvolvimento"
                        else: cls_global = "cal-manutencao"; titulo = "Manutenção"
                        st.markdown(f'<div class="cal-day {cls_global}"><b>Semana {sem_total}</b><br><small>{titulo}</small></div>', unsafe_allow_html=True)
                st.write("")

    with tabs[2]:
        st.subheader("💪 Orientação Técnica por Fase")
        fase_view = st.radio("Selecione a Fase para consultar:", ["Inicial", "Desenvolvimento", "Manutenção"], horizontal=True)
        render_prescricao_geral(fase_view)
        st.divider()
        render_sessao_tipo(fase_view)

    with tabs[3]:
        st.subheader("📊 O meu progresso de Saúde Global (Visão Anual)")
        if df_hist.empty:
            st.info("Ainda não existem registos.")
        else:
            df_plot = df_hist.copy()
            df_plot["data"] = pd.to_datetime(df_plot["data"])
            col_a, col_b = st.columns(2)
            with col_a:
                fig_pa = go.Figure()
                fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_sist_pre"], mode="lines+markers", name="Sistólica (Pré)", line=dict(color="#3498db", dash="dot")))
                fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_sist_pos"], mode="lines+markers", name="Sistólica (Pós)", line=dict(color="#2980b9")))
                fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_diast_pre"], mode="lines+markers", name="Diastólica (Pré)", line=dict(color="#e67e22", dash="dot")))
                fig_pa.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["pa_diast_pos"], mode="lines+markers", name="Diastólica (Pós)", line=dict(color="#d35400")))
                fig_pa.update_layout(title="Adaptação da Pressão Arterial", yaxis_title="mmHg", legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_pa, use_container_width=True)

                fig_glic = go.Figure()
                fig_glic.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["glic_antes"], mode="lines+markers", name="Pré-Treino", line=dict(color="#9b59b6")))
                fig_glic.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["glic_apos"], mode="lines+markers", name="Pós-Treino", line=dict(color="#8e44ad")))
                fig_glic.update_layout(title="Controlo de Glicémia", yaxis_title="mg/dL", legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_glic, use_container_width=True)

            with col_b:
                fig_fc = go.Figure()
                fig_fc.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["fc_repouso"], mode="lines+markers", name="FC Repouso", line=dict(color="#2ecc71")))
                fig_fc.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["fc_media"], mode="lines+markers", name="FC Média (Treino)", line=dict(color="#f1c40f")))
                fig_fc.add_trace(go.Scatter(x=df_plot["data"], y=df_plot["fc_pico"], mode="lines+markers", name="FC Máx (Pico Treino)", line=dict(color="#e74c3c")))
                fig_fc.update_layout(title="Frequência Cardíaca (Repouso e Esforço)", yaxis_title="bpm", legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_fc, use_container_width=True)

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
                    pse_base = 12.5 + (sem * 0.02) + (rng_musc.normal(0, 0.3))
                    if g == "Quadrícepe": pse_base += 0.8
                    if g == "Core": pse_base -= 0.6
                    if pse_base > 14: pse_base = 14
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
            sem = c_b.number_input("Semana", 1, 52, 1)
            fase = st.selectbox("Fase", ["Inicial", "Desenvolvimento", "Manutenção"])
            txt = st.text_area("Notas Clínicas")
            if st.form_submit_button("💾 Gravar"):
                conn.cursor().execute("INSERT INTO sessoes_v3 (data, semana, fase, tipo, relatorio_clinico, validado) VALUES (?,?,?,?,?,1)", (dt.isoformat(), int(sem), fase, "Misto", txt))
                conn.commit()
                st.success("✅ Relatório guardado!")
                st.rerun()

        # ================= ZONA DE RELATÓRIO FINAL COM MÉTRICAS PREDITIVAS =================
        st.divider()
        st.subheader("🎓 Relatório Final de Caso Clínico")
        st.info("Produção automática de relatório completo para a equipa de tratamento com análise da evolução anual, modelação preditiva de capacidade funcional e transição autónoma.")
        
        if st.button("📄 Gerar Relatório Final do Caso Clínico", type="primary"):
            if not df_hist.empty:
                primeira = df_hist.iloc[0]
                ultima = df_hist.iloc[-1]
                total_sessoes_reg = len(df_hist)
                
                relatorio_md = f"""
### 🏥 RELATÓRIO CLÍNICO DE EVOLUÇÃO E TRANSIÇÃO DE ALTA
**Data do Relatório:** {date.today().strftime('%d/%m/%Y')}

**1. IDENTIFICAÇÃO DO DOENTE**
* **Nome:** {PACIENTE['nome']}
* **Idade:** {PACIENTE['idade']} anos
* **Programa:** Reabilitação e Exercício Clínico Integrado (1 Ano / 52 Semanas)
* **Sessões Validadas:** {total_sessoes_reg}

---

**2. ANÁLISE DE EVOLUÇÃO FISIOLÓGICA E METABÓLICA**
Apresenta-se a comparação direta entre os parâmetros basais (Início do programa) e os parâmetros consolidados na Fase de Manutenção:

* **Frequência Cardíaca de Repouso:** {primeira['fc_repouso']} bpm ➔ **{ultima['fc_repouso']} bpm**
* **Pressão Arterial (Pré-esforço):** {primeira['pa_sist_pre']}/{primeira['pa_diast_pre']} mmHg ➔ **{ultima['pa_sist_pre']}/{ultima['pa_diast_pre']} mmHg**
* **Glicemia em Jejum (Pré-treino):** {primeira['glic_antes']} mg/dL ➔ **{ultima['glic_antes']} mg/dL**
* **Hemoglobina Glicada (HbA1c):** {primeira['hba1c']}% ➔ **{ultima['hba1c']}%**

**Parecer Evolutivo:**
Observa-se uma consolidação fisiológica notória. A adaptação cardiovascular permitiu uma otimização do débito cardíaco com redução visível da FC de repouso e normalização dos valores tensionais. A nível metabólico, o planeamento progressivo do volume e intensidade induziu uma melhoria acentuada na sensibilidade à insulina, refletida de forma expressiva na queda da HbA1c para níveis de controlo não-patológicos.

---

**3. MODELAÇÃO CARDIORESPIRATÓRIA E PREVISÃO DE VO₂ MÁX**
Com base nos modelos biométricos e de carga inseridos no programa clínico, estruturou-se a seguinte análise preditiva do comportamento funcional:

* **Fase de Desenvolvimento (Duração: 10 Meses):**
  * *Adaptação Autonómica:* Verificou-se uma redução da FC basal à taxa de **0,59%/mês** (conduzindo à meta linear de queda de 7% após 1 ano, estabelecendo a FC basal de 72 bpm para 67 bpm).
  * *Evolução de Potência Aeróbia:* Registou-se uma melhoria linear de **10,84%/mês no VO₂máx** (considerando a assiduidade de 20 sessões/mês, resultando num incremento de **+2,4 mL/kg/min/mês**). O ganho acumulado estimado nesta fase fixa-se em **+24,0 mL/kg/min**, elevando a aptidão funcional do doente para valores ótimos de **~59,4 mL/kg/min**.

* **Fase de Manutenção (Duração: 2 Meses):**
  * *Adaptação Fisiológica:* Platô e estabilização segura da FC basal (ancorada nos 67 bpm).
  * *Evolução de Potência Aeróbia:* **Consolidação e retenção total** dos ganhos máximos adquiridos na fase anterior. O modelo preditivo aponta para a manutenção estável do teto de **~59,4 mL/kg/min**, focando a atividade na manutenção da bioenergética muscular sem necessidade de incrementos adicionais de sobrecarga cardíaca.

---

**4. INDICAÇÕES DE ESTILO DE VIDA E INTEGRAÇÃO (A entregar à equipa de tratamento)**
O doente encontra-se capacitado e com literacia funcional suficiente para adotar um comportamento autónomo. Para garantir a consolidação dos ganhos a longo prazo, indicam-se as seguintes guidelines baseadas na Fase de Manutenção:

* **Gestão Cardiovascular (Aeróbio):** Manter atividade aeróbia 5 dias por semana (ex: caminhada rápida intervalada com intensidade cíclica). Somar pelo menos 150 minutos semanais mantendo uma zona de RPE 14-17 (moderada).
* **Treino de Força e Hipertrofia:** Manter a rotina de 2 a 4 dias por semana (não consecutivos) focada em exercícios multiarticulares (Agachamento, Deadlift, Bench Press). Realizar entre 6 a 12 repetições mantendo um RiR (Reps in Reserve) de 2 a 3.
* **Rotina Ativa no Dia-a-Dia:** Privilegiar o transporte ativo, evitar o uso de elevadores e quebrar ciclos de sedentarismo prolongado a cada 90 minutos.
* **Sinais de Alerta e Monitorização:** O utente está familiarizado com a monitorização de sinais vitais e da Escala de Esforço de Borg. É aconselhada a verificação semanal em casa da Glicemia de jejum e Pressão Arterial, contactando a equipa de tratamento primário caso se verifique um recrudescimento sistemático dos valores.

**Assinatura:** *Equipa de Fisiologia do Exercício | BestCare Pro*
                """
                
                st.markdown(f"""
                <div style="background-color: #ffffff; padding: 30px; border-radius: 8px; border-left: 5px solid #27ae60; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-top: 20px;">
                    {relatorio_md}
                </div>
                """, unsafe_allow_html=True)
                
                # Download em PDF
                pdf_bytes = gerar_pdf_relatorio(PACIENTE, primeira, ultima, total_sessoes_reg)
                st.download_button(
                    label="📥 Descarregar Relatório (PDF)",
                    data=pdf_bytes,
                    file_name=f"Alta_Clinica_{PACIENTE['nome'].replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
            else:
                st.warning("⚠️ Não existem dados suficientes na base de dados para produzir o relatório de evolução.")

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
