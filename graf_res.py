import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Relatório Clínico Interativo", layout="wide")

# --- BARRA LATERAL: INPUT DE DADOS ---
st.sidebar.header("Configuração do Paciente")
nome = st.sidebar.text_input("Nome do Paciente", "José")

st.sidebar.subheader("Frequência Cardíaca (bpm)")
fc_obs = st.sidebar.slider("FC Máxima Observada", 60, 220, 145)
fc_prev = st.sidebar.slider("FC Máxima Prevista (Ref)", 60, 220, 161)

st.sidebar.subheader("Capacidade Aeróbica")
vo2_obs = st.sidebar.number_input("VO2máx Observado (ml/kg/min)", 0.0, 80.0, 27.2)
vo2_prev = st.sidebar.number_input("VO2máx Previsto (ml/kg/min)", 0.1, 80.0, 35.4)

# --- CÁLCULOS AUTOMÁTICOS ---
# Cálculo do FAI conforme a fórmula de Excel: ((C9-C8)/C9)*100
fai_resultado = ((vo2_prev - vo2_obs) / vo2_prev) * 100

# Lógica de Classificação FAI (baseada na sua tabela de Excel)
if fai_resultado < 27:
    fai_desc = "Normal / Abaixo do limiar clínico"
    fai_cor = "green"
elif fai_resultado <= 40:
    fai_desc = "Comprometimento Leve"
    fai_cor = "#FFCC00"
elif fai_resultado <= 54:
    fai_desc = "Comprometimento Moderado"
    fai_cor = "#FF9900"
elif fai_resultado <= 68:
    fai_desc = "Comprometimento Marcado"
    fai_cor = "#FF3300"
else:
    fai_desc = "Comprometimento Extremo"
    fai_cor = "darkred"

# --- INTERFACE PRINCIPAL ---
st.title(f"📊 Avaliação Funcional: {nome}")
st.markdown("---")

# Função para criar os velocímetros (Gauges)
def criar_gauge(label, valor, referencia, unidade, cor):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = valor,
        title = {'text': f"{label} ({unidade})"},
        gauge = {
            'axis': {'range': [0, referencia * 1.2 if referencia > 0 else 100]},
            'bar': {'color': cor},
            'threshold': {'line': {'color': "black", 'width': 4}, 'value': referencia}
        }))
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
    return fig

# Linha 1: FC e VO2máx (Observado vs Esperado)
col1, col2 = st.columns(2)

with col1:
    st.plotly_chart(criar_gauge("FC Máxima", fc_obs, fc_prev, "bpm", "#2F5597"), use_container_width=True)
    st.caption(f"Alvo esperado: {fc_prev} bpm")

with col2:
    st.plotly_chart(criar_gauge("VO2máx", vo2_obs, vo2_prev, "ml/kg/min", "#A2AD00"), use_container_width=True)
    st.caption(f"Valor previsto: {vo2_prev} ml/kg/min")

st.markdown("---")

# Linha 2: Análise do FAI
col3, col4 = st.columns([2, 1])

with col3:
    # Gráfico do FAI (Défice)
    fig_fai = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = fai_resultado,
        title = {'text': "FAI (Functional Aerobic Impairment)"},
        gauge = {
            'axis': {'range': [0, 100]},
            'bar': {'color': fai_cor},
            'steps': [
                {'range': [0, 27], 'color': "#E8F5E9"},
                {'range': [27, 40], 'color': "#FFFDE7"},
                {'range': [40, 100], 'color': "#FFEBEE"}
            ]
        }))
    fig_fai.update_layout(height=300)
    st.plotly_chart(fig_fai, use_container_width=True)

with col4:
    st.subheader("Análise Clínica")
    st.metric("Percentagem de Défice", f"{fai_resultado:.1f}%")
    st.markdown(f"**Classificação:**")
    st.markdown(f"<div style='padding:10px; border-radius:5px; background-color:{fai_cor}; color:white; font-weight:bold; text-align:center;'>{fai_desc}</div>", unsafe_allow_html=True)
    st.info("O FAI reflete a perda de capacidade funcional em relação ao esperado para a idade.")

# Rodapé com as referências enviadas nas imagens
st.markdown("---")
st.write("**Referências bibliográficas:**")
st.caption("- Bruce RA, Kusumi F, Hosmer D. Maximal oxygen intake and nomographic assessment of functional aerobic impairment in cardiovascular disease.")
st.caption("- Franklin BA, Gordon S, Timmis GC. Fundamentals of exercise testing.")
