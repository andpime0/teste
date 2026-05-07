import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Relatório Clínico Interativo", layout="wide")

# --- BARRA LATERAL: INPUT DE DADOS ---
st.sidebar.header("Configuração do Paciente")
nome = st.sidebar.text_input("Nome do Paciente", "José")

tipo_treino = st.sidebar.text_input("Tipo de Treino", "Treino Aeróbico")
duracao_treino = st.sidebar.number_input("Duração da sessão (min)", 1, 300, 45)

st.sidebar.subheader("Frequência Cardíaca (bpm)")
fc_obs = st.sidebar.slider("FC Máxima Observada", 60, 220, 145)
fc_prev = st.sidebar.slider("FC Máxima Prevista (Ref)", 60, 220, 161)

st.sidebar.subheader("Capacidade Aeróbica")
vo2_obs = st.sidebar.number_input("VO2máx Observado (ml/kg/min)", 0.0, 80.0, 27.2)
vo2_prev = st.sidebar.number_input("VO2máx Previsto (ml/kg/min)", 0.1, 80.0, 35.4)

st.sidebar.subheader("Parâmetros da Sessão de Treino")
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
st.subheader("📥 Zona dedicada: Importação Polar Beat")
with st.container(border=True):
    st.markdown("**Importar dados Polar Beat (CSV/XLSX)**")
    upload = st.file_uploader(
        "Carregue o ficheiro exportado do Polar Beat (.csv ou .xlsx)", type=["csv", "xlsx"]
    )

polar_df = None
polar_fig = None
polar_stats = None

if upload is not None:
    try:
        if upload.name.lower().endswith(".csv"):
            polar_df = pd.read_csv(upload)
        else:
            polar_df = pd.read_excel(upload)

        if polar_df.empty:
            st.warning("O ficheiro foi carregado, mas não contém dados.")
        else:
            st.success("Ficheiro importado com sucesso.")
            st.caption("Escolha as colunas que representam o tempo e a frequência cardíaca para gerar o gráfico.")

            cols = polar_df.columns.tolist()
            numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(polar_df[c])]

            default_time_index = 0
            default_fc_index = cols.index(numeric_cols[0]) if numeric_cols else 0

            col_tempo, col_fc = st.columns(2)
            with col_tempo:
                tempo_col = st.selectbox("Coluna de tempo", cols, index=default_time_index)
            with col_fc:
                fc_col = st.selectbox("Coluna de FC (bpm)", cols, index=default_fc_index)

            fc_series = pd.to_numeric(polar_df[fc_col], errors="coerce")
            valid_df = polar_df.loc[fc_series.notna(), [tempo_col, fc_col]].copy()
            valid_df[fc_col] = pd.to_numeric(valid_df[fc_col], errors="coerce")

            if valid_df.empty:
                st.error("Não foi possível identificar valores numéricos de FC na coluna selecionada.")
            else:
                polar_fig = go.Figure()
                polar_fig.add_trace(
                    go.Scatter(
                        x=valid_df[tempo_col],
                        y=valid_df[fc_col],
                        mode="lines",
                        name="FC",
                        line=dict(color="#2F5597", width=2),
                    )
                )
                polar_fig.update_layout(
                    title="Variação da Frequência Cardíaca ao Longo da Sessão",
                    xaxis_title="Tempo",
                    yaxis_title="Frequência Cardíaca (bpm)",
                    template="plotly_white",
                    height=360,
                )
                st.plotly_chart(polar_fig, use_container_width=True)

                polar_stats = {
                    "fc_media": valid_df[fc_col].mean(),
                    "fc_max": valid_df[fc_col].max(),
                    "fc_min": valid_df[fc_col].min(),
                    "pontos": len(valid_df),
                }

                s1, s2, s3, s4 = st.columns(4)
                s1.metric("FC média", f"{polar_stats['fc_media']:.1f} bpm")
                s2.metric("FC máxima (ficheiro)", f"{polar_stats['fc_max']:.0f} bpm")
                s3.metric("FC mínima (ficheiro)", f"{polar_stats['fc_min']:.0f} bpm")
                s4.metric("Pontos registados", f"{polar_stats['pontos']}")

    except Exception as exc:
        st.error(f"Erro ao importar ficheiro: {exc}")

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

    l1, l2, l3 = st.columns(3)
    l1.metric("PA (antes)", pa_antes)
    l2.metric("PA (após)", pa_apos)
    l3.metric("PSE (durante/após)", f"{pse_durante} / {pse_apos}")

    g1, g2, g3 = st.columns(3)
    g1.metric("Glucose (antes)", f"{glicose_antes} mg/dL")
    g2.metric("Glucose (após)", f"{glicose_apos} mg/dL")
    g3.metric("Δ Glucose", f"{glicose_apos - glicose_antes:+.0f} mg/dL")

    st.markdown("### Dados realizados na sessão")
    c1, c2, c3 = st.columns(3)
    c1.metric("FC máxima observada", f"{fc_obs} bpm")
    c2.metric("VO2máx observado", f"{vo2_obs:.1f} ml/kg/min")
    c3.metric("FAI", f"{fai_resultado:.1f}%")

    st.markdown("### Polar Beat (importação)")
    if polar_stats is not None:
        p1, p2, p3 = st.columns(3)
        p1.metric("FC média (ficheiro)", f"{polar_stats['fc_media']:.1f} bpm")
        p2.metric("FC máxima (ficheiro)", f"{polar_stats['fc_max']:.0f} bpm")
        p3.metric("FC mínima (ficheiro)", f"{polar_stats['fc_min']:.0f} bpm")
        if polar_fig is not None:
            st.plotly_chart(polar_fig, use_container_width=True)
    else:
        st.info("Sem ficheiro Polar Beat importado para esta sessão.")

st.markdown("---")
st.write("**Referências bibliográficas:**")
st.caption("- Bruce RA, Kusumi F, Hosmer D. Maximal oxygen intake and nomographic assessment of functional aerobic impairment in cardiovascular disease.")
st.caption("- Franklin BA, Gordon S, Timmis GC. Fundamentals of exercise testing.")
