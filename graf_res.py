import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Prescrição Clínica - José", layout="wide")

# Estilo para o Relatório
st.title("📋 Prescrição de Exercício Clínico: José")
st.subheader("Enquadramento: Pós-Enfarte (IAM) + Diabetes Tipo 2")
st.info("Diretrizes: ACSM & AHA/ACC Guidelines")

# --- LÓGICA DE PRESCRIÇÃO DEFINIDA ---
# Baseado em 60% da FCmáx (161 bpm) para segurança pós-IAM
fc_alvo = 110
tempo_alvo = 30
rpe_alvo = 12 # Escala de Borg (Esforço moderado)

# --- INTERFACE ---
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 🎯 Metas Diárias")
    st.metric("Frequência Cardíaca Alvo", f"{fc_alvo} bpm")
    st.metric("Duração da Sessão", f"{tempo_alvo} min")
    st.metric("Intensidade (Borg)", "12 (Ligeiro-Moderado)")

with col2:
    # Gráfico de Velocímetro de Segurança
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = fc_alvo,
        title = {'text': "Zona de Treino Segura (bpm)"},
        gauge = {
            'axis': {'range': [0, 180]},
            'bar': {'color': "#1a73e8"},
            'steps': [
                {'range': [0, 90], 'color': "#eeeeee"},
                {'range': [90, 115], 'color': "#c6f6d5"},
                {'range': [115, 180], 'color': "#fed7d7"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 5},
                'thickness': 0.8,
                'value': 125 # Limite de Isquemia/Segurança
            }
        }
    ))
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# --- TABELA DE PRESCRIÇÃO DETALHADA ---
st.write("### Plano de Treino Estruturado")

dados_prescricao = {
    "Componente": ["Frequência", "Intensidade Aeróbica", "Tempo", "Tipo de Exercício", "Resistência Muscular"],
    "Prescrição Definida": ["5 dias por semana", "110 bpm", "30 minutos", "Caminhada em plano ou Bicicleta", "2 dias por semana"],
    "Notas de Segurança": ["Controlo glicémico", "Sem picos de esforço", "Contínuo", "Baixo impacto", "Cargas leves (12-15 reps)"]
}
st.table(dados_prescricao)

# --- ALERTAS CLÍNICOS ---
st.error("⚠️ **Protocolo de Segurança:** Se a glicemia estiver < 100 mg/dL, ingerir 15g de HC. Parar se houver dor no peito ou tonturas.")
