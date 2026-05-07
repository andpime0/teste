import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Relatório Clínico Interativo", layout="wide")

# --- BARRA LATERAL: INPUT DE DADOS ---
st.sidebar.header("Configuração do Paciente")
nome = st.sidebar.text_input("Nome do Paciente", "José")

tipo_treino = st.sidebar.text_input("Tipo de Treino", "Treino Aeróbio")
duracao_treino = st.sidebar.number_input("Duração da sessão (min)", 1, 300, 45)

st.sidebar.subheader("Frequência Cardíaca (bpm)")
fc_obs = st.sidebar.slider("FC Máxima Observada", 60, 220, 145)
fc_prev = st.sidebar.slider("FC Máxima Prevista (Ref)", 60, 220, 161)

st.sidebar.subheader("Capacidade Aeróbia")
vo2_obs = st.sidebar.number_input("VO2máx Observado (ml/kg/min)", 0.0, 80.0, 27.2)
vo2_prev = st.sidebar.number_input("VO2máx Previsto (ml/kg/min)", 0.1, 80.0, 35.4)

st.sidebar.subheader("Parâmetros da Sessão de Treino")
cardio_durante = st.sidebar.slider("Cardiofrequencímetro (durante) - bpm", 40, 220, 130)
pa_antes = st.sidebar.text_input("PA antes", "120/80")
pa_apos = st.sidebar.text_input("PA após", "130/85")
glicose_antes = st.sidebar.number_input("Medição glucose antes (mg/dL)", 40, 500, 98)
glicose_apos = st.sidebar.number_input("Medição glucose após (mg/dL)", 40, 500, 110)
pse_durante = st.sidebar.slider("PSE durante (0-10)", 0, 10, 4)
pse_apos = st.sidebar.slider("PSE após (0-10)", 0, 10, 5)

# --- CÁLCULOS AUTOMÁTICOS ---
fai_resultado = ((vo2_prev - vo2_obs) / vo2_prev) * 100

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


def criar_gauge(label, valor, referencia, unidade, cor):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=valor,
            title={"text": f"{label} ({unidade})"},
            gauge={
                "axis": {"range": [0, referencia * 1.2 if referencia > 0 else 100]},
                "bar": {"color": cor},
                "threshold": {"line": {"color": "black", "width": 4}, "value": referencia},
            },
        )
    )
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
    return fig


col1, col2 = st.columns(2)

with col1:
    st.plotly_chart(criar_gauge("FC Máxima", fc_obs, fc_prev, "bpm", "#2F5597"), use_container_width=True)
    st.caption(f"Alvo esperado: {fc_prev} bpm")

with col2:
    st.plotly_chart(criar_gauge("VO2máx", vo2_obs, vo2_prev, "ml/kg/min", "#A2AD00"), use_container_width=True)
    st.caption(f"Valor previsto: {vo2_prev} ml/kg/min")

st.markdown("---")

col3, col4 = st.columns([2, 1])

with col3:
    fig_fai = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=fai_resultado,
            title={"text": "FAI (Functional Aerobic Impairment)"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": fai_cor},
                "steps": [
                    {"range": [0, 27], "color": "#E8F5E9"},
                    {"range": [27, 40], "color": "#FFFDE7"},
                    {"range": [40, 100], "color": "#FFEBEE"},
                ],
            },
        )
    )
    fig_fai.update_layout(height=300)
    st.plotly_chart(fig_fai, use_container_width=True)

with col4:
    st.subheader("Análise Clínica")
    st.metric("Percentagem de Défice", f"{fai_resultado:.1f}%")
    st.markdown("**Classificação:**")
    st.markdown(
        f"<div style='padding:10px; border-radius:5px; background-color:{fai_cor}; color:white; font-weight:bold; text-align:center;'>{fai_desc}</div>",
        unsafe_allow_html=True,
    )
    st.info("O FAI reflete a perda de capacidade funcional em relação ao esperado para a idade.")

st.markdown("---")
st.subheader("🧾 Relatório da Sessão de Treino")

gerar_relatorio = st.button("Gerar relatório da sessão")

if gerar_relatorio:
    st.success("Relatório gerado com sucesso.")

    st.markdown(
        f"""
        <div style='border:1px solid #d9d9d9; border-radius:10px; padding:18px; margin-bottom:14px;'>
            <h4 style='margin-top:0;'>Resumo da sessão</h4>
            <p><b>Paciente:</b> {nome}</p>
            <p><b>Treino:</b> {tipo_treino}</p>
            <p><b>Duração:</b> {duracao_treino} minutos</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Cardiofrequencímetro (durante)", f"{cardio_durante} bpm")
    l2.metric("PA (antes)", pa_antes)
    l3.metric("PA (após)", pa_apos)
    l4.metric("PSE (durante/após)", f"{pse_durante} / {pse_apos}")

    g1, g2, g3 = st.columns(3)
    g1.metric("Glucose (antes)", f"{glicose_antes} mg/dL")
    g2.metric("Glucose (após)", f"{glicose_apos} mg/dL")
    g3.metric("Δ Glucose", f"{glicose_apos - glicose_antes:+.0f} mg/dL")

    st.markdown("### Dados realizados na sessão")
    c1, c2, c3 = st.columns(3)
    c1.metric("FC máxima observada", f"{fc_obs} bpm")
    c2.metric("VO2máx observado", f"{vo2_obs:.1f} ml/kg/min")
    c3.metric("FAI", f"{fai_resultado:.1f}%")

# Rodapé com as referências enviadas nas imagens
st.markdown("---")
st.write("**Referências bibliográficas:**")
st.caption("- Bruce RA, Kusumi F, Hosmer D. Maximal oxygen intake and nomographic assessment of functional aerobic impairment in cardiovascular disease.")
st.caption("- Franklin BA, Gordon S, Timmis GC. Fundamentals of exercise testing.")
