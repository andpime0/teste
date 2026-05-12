import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os

st.set_page_config(
    page_title="CardioRehab | José Oliveira",
    page_icon="🫀",
    layout="wide",
)

# ============================================================
# DADOS CLÍNICOS DO JOSÉ (fixos — caso de estudo)
# ============================================================
PACIENTE = {
    "nome": "José Oliveira",
    "idade": 55,
    "sexo": "Masculino",
    "altura_cm": 174,
    "peso_kg": 88,
    "historial": "Pós-EAM (4 meses) com colocação de stent. Diabetes tipo II.",
    "medicacao": ["Beta-bloqueador (Bisoprolol 5mg)", "Estatina (Atorvastatina 40mg)", "Metformina 1000mg"],
    "fc_max_teste": 145,
    "fc_repouso_inicial": 78,
    "vo2_inicial": 27.2,
    "vo2_previsto": 35.4,
    "hba1c_inicial": 7.8,
    "data_inicio": datetime(2026, 2, 16),
}

PROGRAMA_SEMANAS = 12
SESSOES_POR_SEMANA = 3

# ============================================================
# GERAÇÃO DE DADOS FICTÍCIOS DE EVOLUÇÃO
# ============================================================
@st.cache_data
def gerar_evolucao_jose():
    """Gera 36 sessões com evolução fisiológica realista."""
    np.random.seed(42)
    sessoes = []
    data_atual = PACIENTE["data_inicio"]

    for sem in range(PROGRAMA_SEMANAS):
        # Progressão fisiológica esperada ao longo das 12 semanas
        fator = sem / (PROGRAMA_SEMANAS - 1)  # 0 → 1

        fc_repouso_base = PACIENTE["fc_repouso_inicial"] - 10 * fator  # 78 → 68
        vo2_base = PACIENTE["vo2_inicial"] + 6.5 * fator                 # 27.2 → 33.7
        fai_base = ((PACIENTE["vo2_previsto"] - vo2_base) / PACIENTE["vo2_previsto"]) * 100
        hba1c_base = PACIENTE["hba1c_inicial"] - 1.0 * fator             # 7.8 → 6.8

        for s in range(SESSOES_POR_SEMANA):
            # Variabilidade intra-semana
            ruido_fc = np.random.normal(0, 2)
            ruido_pse = np.random.choice([-1, 0, 0, 0, 1])

            # Intensidade progride; PSE estabiliza por adaptação
            intensidade_pct = 0.50 + 0.25 * fator + np.random.normal(0, 0.02)
            fc_durante = int(fc_repouso_base + (PACIENTE["fc_max_teste"] - fc_repouso_base) * intensidade_pct + ruido_fc)
            duracao = int(25 + 20 * fator)  # 25 → 45 min

            pa_sis_antes = int(128 + np.random.normal(0, 4))
            pa_dia_antes = int(82 + np.random.normal(0, 3))
            pa_sis_apos = pa_sis_antes + int(np.random.normal(8, 3))
            pa_dia_apos = pa_dia_antes + int(np.random.normal(2, 2))

            glic_antes = int(np.random.normal(135 - 20 * fator, 15))
            glic_apos = glic_antes - int(np.random.normal(25, 8))

            pse_durante = max(11, min(15, int(12 + fator * 1.5 + ruido_pse)))
            pse_apos = max(10, pse_durante - np.random.choice([1, 2]))

            sintomas_possiveis = ["Nenhum"] * 18 + ["Fadiga ligeira", "Falta de ar leve"]
            sintoma = np.random.choice(sintomas_possiveis)

            sessoes.append({
                "data": data_atual,
                "semana": sem + 1,
                "sessao_n": len(sessoes) + 1,
                "tipo": "Aeróbio contínuo" if sem < 4 else ("Aeróbio + Força" if sem < 8 else "Intervalado moderado"),
                "duracao_min": duracao,
                "fc_repouso": int(fc_repouso_base + np.random.normal(0, 1.5)),
                "fc_media_durante": fc_durante,
                "fc_pico": fc_durante + int(np.random.normal(8, 3)),
                "vo2_estimado": round(vo2_base + np.random.normal(0, 0.4), 1),
                "fai": round(fai_base + np.random.normal(0, 0.6), 1),
                "pa_antes": f"{pa_sis_antes}/{pa_dia_antes}",
                "pa_apos": f"{pa_sis_apos}/{pa_dia_apos}",
                "glic_antes": max(80, glic_antes),
                "glic_apos": max(70, glic_apos),
                "pse_durante": pse_durante,
                "pse_apos": pse_apos,
                "sintomas": sintoma,
                "hba1c": round(hba1c_base, 2) if s == 0 and sem % 4 == 0 else None,
            })
            data_atual += timedelta(days=2 if s < 2 else 3)

    return pd.DataFrame(sessoes)

df_sessoes = gerar_evolucao_jose()

# ============================================================
# PERSISTÊNCIA DE DADOS REPORTADOS PELO CLIENTE
# ============================================================
DADOS_CLIENTE_FILE = "dados_cliente_jose.json"

def carregar_dados_cliente():
    if os.path.exists(DADOS_CLIENTE_FILE):
        with open(DADOS_CLIENTE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"glicemias": [], "feedbacks": []}

def guardar_dados_cliente(dados):
    with open(DADOS_CLIENTE_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

if "dados_cliente" not in st.session_state:
    st.session_state.dados_cliente = carregar_dados_cliente()

# ============================================================
# NAVEGAÇÃO
# ============================================================
st.sidebar.markdown("# 🫀 CardioRehab")
st.sidebar.caption("Sistema de reabilitação cardíaca")
st.sidebar.markdown("---")

perfil = st.sidebar.radio(
    "Perfil:",
    ["👤 Cliente — José", "🩺 Equipa Clínica"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Programa iniciado em\n**{PACIENTE['data_inicio'].strftime('%d/%m/%Y')}**")
sessoes_concluidas = len(df_sessoes)
st.sidebar.caption(f"Sessões registadas: **{sessoes_concluidas}/{PROGRAMA_SEMANAS * SESSOES_POR_SEMANA}**")

# ============================================================
# PERFIL CLIENTE
# ============================================================
if perfil == "👤 Cliente — José":
    st.title(f"Olá, {PACIENTE['nome'].split()[0]} 👋")
    st.caption(f"Semana {df_sessoes['semana'].max()} do seu programa de reabilitação")

    # --- PROGRESSO GERAL ---
    progresso = sessoes_concluidas / (PROGRAMA_SEMANAS * SESSOES_POR_SEMANA)
    st.progress(progresso, text=f"{int(progresso * 100)}% do programa concluído")

    st.markdown("---")

    # --- CHECK-UP PRÉ-TREINO ---
    st.subheader("🩺 Check-up Pré-Treino")
    c1, c2 = st.columns([2, 1])

    with c1:
        glicose = st.number_input(
            "A sua glicemia agora (mg/dL):",
            min_value=40, max_value=500, value=120, step=1,
        )

        if glicose < 100:
            st.error("🔴 **Glicemia baixa.** Coma 15g de hidratos rápidos (sumo, fruta) e espere 15 min antes de treinar.")
            pode_treinar = False
        elif glicose <= 250:
            st.success("🟢 **Zona segura.** Está pronto para o seu treino. Tenha água e um snack por perto!")
            pode_treinar = True
        elif glicose <= 300:
            st.warning("🟡 **Glicemia elevada.** Treino ligeiro apenas, e só se se sentir bem. Verifique cetonas se possível.")
            pode_treinar = True
        else:
            st.error("🔴 **Não treine hoje.** Hidrate-se bem e contacte a equipa clínica.")
            pode_treinar = False

    with c2:
        if st.button("✅ Registar medição", use_container_width=True):
            st.session_state.dados_cliente["glicemias"].append({
                "data": datetime.now().isoformat(timespec="minutes"),
                "valor": glicose,
                "pode_treinar": pode_treinar,
            })
            guardar_dados_cliente(st.session_state.dados_cliente)
            st.toast("Medição guardada ✅")

    st.markdown("---")

    # --- O SEU PROGRESSO ---
    st.subheader("📈 O seu progresso")

    col_a, col_b, col_c = st.columns(3)
    fai_inicial = df_sessoes.iloc[0]["fai"]
    fai_atual = df_sessoes.iloc[-1]["fai"]
    vo2_inicial = df_sessoes.iloc[0]["vo2_estimado"]
    vo2_atual = df_sessoes.iloc[-1]["vo2_estimado"]
    fc_rep_inicial = df_sessoes.iloc[0]["fc_repouso"]
    fc_rep_atual = df_sessoes.iloc[-1]["fc_repouso"]

    col_a.metric("Capacidade aeróbia", f"{vo2_atual:.1f}", f"+{vo2_atual - vo2_inicial:.1f} ml/kg/min")
    col_b.metric("Coração em repouso", f"{fc_rep_atual} bpm", f"{fc_rep_atual - fc_rep_inicial} bpm", delta_color="inverse")
    col_c.metric("Défice funcional", f"{fai_atual:.1f}%", f"{fai_atual - fai_inicial:.1f} pp", delta_color="inverse")

    st.caption("💡 Quanto mais baixo o défice funcional, mais perto está dos valores esperados para a sua idade.")

    st.markdown("---")

    # --- OBJETIVO DESTA SEMANA ---
    col_obj, col_motiv = st.columns(2)
    with col_obj:
        st.info("**🎯 Objetivo desta semana**")
        ultima_sem = df_sessoes[df_sessoes["semana"] == df_sessoes["semana"].max()]
        dur_alvo = ultima_sem["duracao_min"].max()
        st.write(f"- 3 sessões de **{dur_alvo} minutos**")
        st.write(f"- Tipo: **{ultima_sem.iloc[-1]['tipo']}**")
        st.write("- Esforço alvo: **'Algo cansado'** (Borg 12–13)")

    with col_motiv:
        st.success("**💪 Está a ir bem!**")
        st.write(f"O seu coração em repouso desceu **{fc_rep_inicial - fc_rep_atual} batimentos**.")
        st.write("Isto significa que o seu coração está mais eficiente — bombeia mais sangue com menos esforço.")

    st.markdown("---")

    # --- FEEDBACK PÓS-SESSÃO ---
    st.subheader("💬 Como correu o seu último treino?")
    with st.form("feedback_form", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            borg = st.select_slider(
                "Esforço percebido:",
                options=list(range(6, 21)),
                value=12,
                format_func=lambda x: f"{x} — {'Repouso' if x<=7 else 'Muito leve' if x<=9 else 'Leve' if x<=11 else 'Algo cansado' if x<=13 else 'Cansado' if x<=15 else 'Muito cansado' if x<=17 else 'Extremo'}",
            )
        with col_f2:
            sintomas = st.multiselect(
                "Sintomas durante ou após:",
                ["Nenhum", "Falta de ar invulgar", "Dor no peito", "Tonturas", "Palpitações", "Fadiga excessiva"],
                default=["Nenhum"],
            )

        notas = st.text_area("Notas adicionais (opcional):", placeholder="Ex: senti-me mais cansado que o habitual…")

        if st.form_submit_button("📨 Enviar à equipa clínica", use_container_width=True):
            st.session_state.dados_cliente["feedbacks"].append({
                "data": datetime.now().isoformat(timespec="minutes"),
                "borg": borg,
                "sintomas": sintomas,
                "notas": notas,
            })
            guardar_dados_cliente(st.session_state.dados_cliente)
            st.success("✅ Feedback enviado! A equipa vai rever antes da próxima sessão.")

# ============================================================
# PERFIL EQUIPA CLÍNICA
# ============================================================
else:
    st.title("🩺 Dashboard Clínico")
    st.caption(f"{PACIENTE['nome']} · {PACIENTE['idade']} anos · {PACIENTE['historial']}")

    # --- ALERTAS AUTOMÁTICOS ---
    alertas = []
    for fb in st.session_state.dados_cliente.get("feedbacks", [])[-5:]:
        if fb["borg"] >= 16:
            alertas.append(f"⚠️ PSE elevado ({fb['borg']}) reportado em {fb['data']}")
        sintomas_red = [s for s in fb["sintomas"] if s in ["Dor no peito", "Tonturas", "Palpitações"]]
        if sintomas_red:
            alertas.append(f"🚨 Sintoma de alerta: {', '.join(sintomas_red)} ({fb['data']})")

    for g in st.session_state.dados_cliente.get("glicemias", [])[-5:]:
        if not g["pode_treinar"]:
            alertas.append(f"⚠️ Glicemia fora de zona segura: {g['valor']} mg/dL ({g['data']})")

    if alertas:
        with st.expander(f"🔔 {len(alertas)} alerta(s) recente(s)", expanded=True):
            for a in alertas:
                st.warning(a)

    # --- TABS ---
    tab_overview, tab_sessao, tab_metab = st.tabs(["📊 Overview do Programa", "🔍 Sessão Individual", "🧪 Marcadores Metabólicos"])

    # ========== TAB 1: OVERVIEW ==========
    with tab_overview:
        st.subheader("Evolução fisiológica ao longo das 12 semanas")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Sessões concluídas", f"{len(df_sessoes)}/{PROGRAMA_SEMANAS * SESSOES_POR_SEMANA}")
        col2.metric("VO₂ atual", f"{df_sessoes.iloc[-1]['vo2_estimado']:.1f} ml/kg/min",
                    f"+{df_sessoes.iloc[-1]['vo2_estimado'] - df_sessoes.iloc[0]['vo2_estimado']:.1f}")
        col3.metric("FAI atual", f"{df_sessoes.iloc[-1]['fai']:.1f}%",
                    f"{df_sessoes.iloc[-1]['fai'] - df_sessoes.iloc[0]['fai']:.1f} pp",
                    delta_color="inverse")
        col4.metric("FC repouso", f"{df_sessoes.iloc[-1]['fc_repouso']} bpm",
                    f"{df_sessoes.iloc[-1]['fc_repouso'] - df_sessoes.iloc[0]['fc_repouso']} bpm",
                    delta_color="inverse")

        st.markdown("---")

        # Gráfico VO2 + FAI
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_sessoes["data"], y=df_sessoes["vo2_estimado"],
            name="VO₂ estimado", line=dict(color="#2F5597", width=2.5),
            yaxis="y1",
        ))
        fig.add_trace(go.Scatter(
            x=df_sessoes["data"], y=df_sessoes["fai"],
            name="FAI (%)", line=dict(color="#C00000", width=2.5, dash="dot"),
            yaxis="y2",
        ))
        fig.add_hline(y=PACIENTE["vo2_previsto"], line_dash="dash", line_color="green",
                      annotation_text="VO₂ previsto", annotation_position="top right")
        fig.update_layout(
            title="Capacidade aeróbia vs. défice funcional",
            xaxis_title="Data",
            yaxis=dict(title="VO₂ (ml/kg/min)", side="left"),
            yaxis2=dict(title="FAI (%)", side="right", overlaying="y", showgrid=False),
            height=400, hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Gráfico FC repouso + PSE
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig2 = px.line(df_sessoes, x="data", y="fc_repouso", title="FC de repouso (bpm)",
                           color_discrete_sequence=["#2F5597"])
            fig2.update_traces(line_width=2.5)
            fig2.update_layout(height=320, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

        with col_g2:
            df_pse = df_sessoes.groupby("semana")[["pse_durante", "pse_apos"]].mean().reset_index()
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=df_pse["semana"], y=df_pse["pse_durante"], name="PSE durante", line=dict(color="#FF9900", width=2.5)))
            fig3.add_trace(go.Scatter(x=df_pse["semana"], y=df_pse["pse_apos"], name="PSE após", line=dict(color="#A2AD00", width=2.5)))
            fig3.update_layout(title="Esforço percebido (Borg) por semana", xaxis_title="Semana",
                               yaxis_title="PSE", height=320, hovermode="x unified")
            st.plotly_chart(fig3, use_container_width=True)

    # ========== TAB 2: SESSÃO INDIVIDUAL ==========
    with tab_sessao:
        st.subheader("Drill-down por sessão")

        sessao_idx = st.select_slider(
            "Selecione a sessão:",
            options=df_sessoes["sessao_n"].tolist(),
            value=df_sessoes["sessao_n"].iloc[-1],
            format_func=lambda x: f"Sessão {x} — {df_sessoes[df_sessoes['sessao_n']==x].iloc[0]['data'].strftime('%d/%m/%Y')}",
        )
        s = df_sessoes[df_sessoes["sessao_n"] == sessao_idx].iloc[0]

        st.markdown(f"### Sessão {s['sessao_n']} · Semana {s['semana']}")
        st.caption(f"{s['tipo']} · {s['duracao_min']} min · {s['data'].strftime('%d/%m/%Y')}")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("FC repouso", f"{s['fc_repouso']} bpm")
        col2.metric("FC média durante", f"{s['fc_media_durante']} bpm")
        col3.metric("FC pico", f"{s['fc_pico']} bpm")
        col4.metric("VO₂ estimado", f"{s['vo2_estimado']:.1f}")

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("PA antes", s["pa_antes"])
        col6.metric("PA após", s["pa_apos"])
        col7.metric("Glicose antes", f"{s['glic_antes']} mg/dL")
        col8.metric("Glicose após", f"{s['glic_apos']} mg/dL", f"{s['glic_apos'] - s['glic_antes']:+d}")

        col9, col10, col11 = st.columns(3)
        col9.metric("PSE durante", f"{s['pse_durante']}/20")
        col10.metric("PSE após", f"{s['pse_apos']}/20")
        col11.metric("FAI", f"{s['fai']:.1f}%")

        st.markdown(f"**Sintomas reportados:** {s['sintomas']}")

        # Gauge do FAI desta sessão
        fai_val = s["fai"]
        if fai_val < 27:
            fai_cor, fai_desc = "green", "Normal"
        elif fai_val <= 40:
            fai_cor, fai_desc = "#FFCC00", "Comprometimento Leve"
        elif fai_val <= 54:
            fai_cor, fai_desc = "#FF9900", "Comprometimento Moderado"
        else:
            fai_cor, fai_desc = "#FF3300", "Comprometimento Marcado"

        fig_fai = go.Figure(go.Indicator(
            mode="gauge+number",
            value=fai_val,
            title={"text": f"FAI — {fai_desc}"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": fai_cor},
                "steps": [
                    {"range": [0, 27], "color": "#E8F5E9"},
                    {"range": [27, 40], "color": "#FFFDE7"},
                    {"range": [40, 100], "color": "#FFEBEE"},
                ],
            },
        ))
        fig_fai.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_fai, use_container_width=True)

    # ========== TAB 3: MARCADORES METABÓLICOS ==========
    with tab_metab:
        st.subheader("Marcadores metabólicos e cardiovasculares")

        # HbA1c
        df_hba1c = df_sessoes[df_sessoes["hba1c"].notna()][["data", "hba1c"]]
        fig_hba1c = go.Figure()
        fig_hba1c.add_trace(go.Scatter(x=df_hba1c["data"], y=df_hba1c["hba1c"],
                                       mode="lines+markers", name="HbA1c",
                                       line=dict(color="#C00000", width=2.5)))
        fig_hba1c.add_hline(y=7.0, line_dash="dash", line_color="green", annotation_text="Alvo < 7.0%")
        fig_hba1c.update_layout(title="Evolução da HbA1c (%)", xaxis_title="Data",
                                yaxis_title="HbA1c (%)", height=320)
        st.plotly_chart(fig_hba1c, use_container_width=True)

        # Glicemia pré vs pós-treino
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            df_glic = df_sessoes.groupby("semana")[["glic_antes", "glic_apos"]].mean().reset_index()
            fig_g = go.Figure()
            fig_g.add_trace(go.Scatter(x=df_glic["semana"], y=df_glic["glic_antes"], name="Pré-treino", line=dict(color="#2F5597")))
            fig_g.add_trace(go.Scatter(x=df_glic["semana"], y=df_glic["glic_apos"], name="Pós-treino", line=dict(color="#A2AD00")))
            fig_g.update_layout(title="Glicemia média por semana", xaxis_title="Semana",
                                yaxis_title="mg/dL", height=320, hovermode="x unified")
            st.plotly_chart(fig_g, use_container_width=True)

        with col_m2:
            # PA sistólica antes/após
            df_pa = df_sessoes.copy()
            df_pa["pa_sis_antes"] = df_pa["pa_antes"].str.split("/").str[0].astype(int)
            df_pa["pa_sis_apos"] = df_pa["pa_apos"].str.split("/").str[0].astype(int)
            df_pa_sem = df_pa.groupby("semana")[["pa_sis_antes", "pa_sis_apos"]].mean().reset_index()

            fig_pa = go.Figure()
            fig_pa.add_trace(go.Scatter(x=df_pa_sem["semana"], y=df_pa_sem["pa_sis_antes"], name="PAS antes", line=dict(color="#2F5597")))
            fig_pa.add_trace(go.Scatter(x=df_pa_sem["semana"], y=df_pa_sem["pa_sis_apos"], name="PAS após", line=dict(color="#FF9900")))
            fig_pa.update_layout(title="Pressão arterial sistólica por semana", xaxis_title="Semana",
                                 yaxis_title="mmHg", height=320, hovermode="x unified")
            st.plotly_chart(fig_pa, use_container_width=True)

        st.markdown("---")
        st.subheader("📋 Resumo clínico")
        st.markdown(f"""
        - **Capacidade aeróbia:** {df_sessoes.iloc[0]['vo2_estimado']:.1f} → **{df_sessoes.iloc[-1]['vo2_estimado']:.1f} ml/kg/min** (+{df_sessoes.iloc[-1]['vo2_estimado'] - df_sessoes.iloc[0]['vo2_estimado']:.1f})
        - **FAI:** {df_sessoes.iloc[0]['fai']:.1f}% → **{df_sessoes.iloc[-1]['fai']:.1f}%** ({df_sessoes.iloc[-1]['fai'] - df_sessoes.iloc[0]['fai']:.1f} pp)
        - **FC repouso:** {df_sessoes.iloc[0]['fc_repouso']} → **{df_sessoes.iloc[-1]['fc_repouso']} bpm**
        - **HbA1c:** {df_hba1c.iloc[0]['hba1c']:.1f}% → **{df_hba1c.iloc[-1]['hba1c']:.1f}%**
        - **Adesão:** {len(df_sessoes)}/{PROGRAMA_SEMANAS * SESSOES_POR_SEMANA} sessões ({len(df_sessoes)/(PROGRAMA_SEMANAS * SESSOES_POR_SEMANA)*100:.0f}%)
        """)
