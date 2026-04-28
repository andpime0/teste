import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Avaliação Clínica Avançada", layout="wide")

# --- BARRA LATERAL ---
st.sidebar.header("Dados do Paciente")
nome = st.sidebar.text_input("Nome", "José")
vo2_obs = st.sidebar.number_input("VO2máx Observado (ml/kg/min)", 0.0, 80.0, 27.2)
vo2_prev = st.sidebar.number_input("VO2máx Previsto (ml/kg/min)", 0.1, 80.0, 35.4)

# Cálculo automático do FAI (%)
fai_resultado = ((vo2_prev - vo2_obs) / vo2_prev) * 100

# Lógica do FAI Level (Baseado na sua fórmula do Excel)
if fai_resultado < 27:
    fai_desc = "Normal / Abaixo do limiar clínico"
    fai_cor = "green"
elif fai_resultado <= 40:
    fai_desc = "Comprometimento Leve"
    fai_cor = "#FFCC00" # Amarelo
elif fai_resultado <= 54:
    fai_desc = "Comprometimento Moderado"
    fai_cor = "#FF9900" # Laranja
elif fai_resultado <= 68:
    fai_desc = "Comprometimento Marcado"
    fai_cor = "#FF3300" # Vermelho
else:
    fai_desc = "Comprometimento Extremo"
    fai_cor = "darkred"

# --- INTERFACE ---
st.title(f"📊 Avaliação Funcional Aeróbica: {nome}")
st.markdown("---")

col1, col2, col3 = st.columns(3)

# Função para gráficos
def criar_gauge(label, valor, max_range, unidade, cor, threshold=None):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = valor,
        title = {'text': f"{label} ({unidade})"},
        gauge = {
            'axis': {'range': [0, max_range]},
            'bar': {'color': cor},
            'threshold': {'line': {'color': "black", 'width': 3}, 'value': threshold} if threshold else None
        }))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
    return fig

with col1:
    st.plotly_chart(criar_gauge("VO2 Máximo", vo2_obs, 60, "ml/kg/min", "#A2AD00", vo2_prev), use_container_width=True)

with col2:
    # Gráfico do FAI (Invertido: quanto mais alto, pior)
    st.plotly_chart(criar_gauge("FAI (Défice)", fai_resultado, 100, "%", fai_cor), use_container_width=True)

with col3:
    st.markdown("### Resultado FAI")
    st.metric("Percentagem de Défice", f"{fai_resultado:.1f}%")
    st.markdown(f"**Nível:** <span style='color:{fai_cor}; font-size:20px; font-weight:bold;'>{fai_desc}</span>", unsafe_allow_html=True)
    st.info("O FAI quantifica o défice funcional aeróbico. Valores elevados indicam maior risco cardiovascular.")

st.markdown("---")
st.write("**Referência:** Franklin BA, Gordon S, Timmis GC. Fundamentals of exercise testing.")
