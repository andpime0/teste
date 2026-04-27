import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Calculadora Clínica", layout="wide")

# --- BARRA LATERAL PARA INPUT DE DADOS ---
st.sidebar.header("Configuração do Paciente")
nome = st.sidebar.text_input("Nome do Paciente", "José")
idade = st.sidebar.number_input("Idade", 18, 100, 55)

st.sidebar.markdown("---")
st.sidebar.subheader("Dados do Teste")
# Criamos sliders para você ajustar os valores na hora
fc_max_obs = st.sidebar.slider("FC Máxima Observada (bpm)", 60, 220, 145)
fc_ref = st.sidebar.slider("FC Referência (Ex: Bruce)", 60, 220, 161)
vo2_obs = st.sidebar.slider("VO2máx Observado", 5.0, 80.0, 27.2)
vo2_ref = st.sidebar.slider("VO2máx Referência", 5.0, 80.0, 26.5)

# --- CORPO DO RELATÓRIO ---
st.title(f"📊 Avaliação Clínica: {nome}")
st.write(f"Paciente de {idade} anos")

col1, col2 = st.columns(2)

def criar_gauge(label, valor, referencia, unidade, cor):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = valor,
        title = {'text': f"{label} ({unidade})"},
        gauge = {
            'axis': {'range': [0, referencia * 1.2]},
            'bar': {'color': cor},
            'threshold': {'line': {'color': "red", 'width': 5}, 'value': referencia}
        }))
    return fig

with col1:
    st.plotly_chart(criar_gauge("FC Máxima", fc_max_obs, fc_ref, "bpm", "#2F5597"))

with col2:
    st.plotly_chart(criar_gauge("VO2máx", vo2_obs, vo2_ref, "ml/kg/min", "#A2AD00"))

st.success(f"Relatório gerado para {nome}. Ajuste os valores na barra lateral para simular outro caso.")
