import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# 1. CONFIGURAÇÃO DE PÁGINA
st.set_page_config(page_title="Offshore Portfolio Analytics", layout="wide")

st.markdown("""
    <style>
    [data-testid="stDataFrame"] { width: 100%; }
    th { min-width: 110px !important; text-align: center !important; white-space: pre-wrap !important; }
    h1, h2, h3 { color: #0E1F40; font-family: 'Segoe UI', sans-serif; }
    .metric-container { 
        background-color: #F0F2F6; 
        padding: 15px; 
        border-radius: 10px; 
        border-left: 5px solid #0E1F40;
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# Cores adaptadas para um visual institucional offshore
CORES_OFFSHORE = ['#A3B1C6', '#6D7D92', '#4A5568', '#2D3748', '#1A202C']
COR_BENCH = '#CBD5E0'

st.title("🌎 Offshore Asset Allocation | Manager View")

st.sidebar.header("International Settings")
arquivo = st.sidebar.file_uploader("Upload Excel Base 100", type=['xlsx'])

def calculate_max_drawdown(return_series):
    comp_ret = (1 + return_series).cumprod()
    peak = comp_ret.cummax()
    drawdown = (comp_ret - peak) / peak
    return drawdown.min()

if arquivo:
    try:
        # Carregamento (Header duplo conforme padrão do código original)
        df_base100 = pd.read_excel(arquivo, header=[0, 1], index_col=0, parse_dates=True)
        
        # Filtro de data
        start, end = st.sidebar.slider("Analysis Period:", 
                                     df_base100.index.min().to_pydatetime(), 
                                     df_base100.index.max().to_pydatetime(), 
                                     (df_base100.index.min().to_pydatetime(), df_base100.index.max().to_pydatetime()))
        
        df_f = df_base100.loc[start:end].copy()
        # Conversão de Base 100 para Retornos Diários
        ret_diarios = df_f.pct_change().dropna()
        num_dias = len(ret_diarios)

        # --- LÓGICA DE BENCHMARKS OFFSHORE ---
        # Identificação das colunas para os benchmarks compostos
        msci_col = next((col for col in df_f.columns if "MSCI WORLD" in col[1].upper()), None)
        bbg_col = next((col for col in df_f.columns if "BLOOMBERG US" in col[1].upper() or "GLOBAL AGG" in col[1].upper()), None)
        cpi_col = next((col for col in df_f.columns if "CPI" in col[1].upper()), None)

        # --- BLOCO 1: DEFINIÇÃO DE PESOS ---
        st.subheader("🏗️ Portfolio Construction")
        perfis = ["Ultra Conservador", "Conservador", "Moderado", "Arrojado", "Agressivo"]
        
        # Estrutura baseada nas classes da imagem fornecida
        df_pesos = pd.DataFrame({"Classe": [c[0] for c in df_f.columns], "Ativo": [c[1] for c in df_f.columns]})
        for p in perfis: df_pesos[p] = 0.0
        
        edited = st.data_editor(df_pesos, hide_index=True, use_container_width=True)

        # --- CÁLCULOS DE PERFORMANCE E RISCO ---
        metrics, risk_decomp, perf_acum = {}, {}, pd.DataFrame(index=ret_diarios.index)
        cov_matrix = ret_diarios.cov() * 252

        for p in perfis:
            w = np.array(edited[p]) / 100
            ret_p = ret_diarios.dot(w)
            
            # Métricas Anualizadas
            r_anual = (1 + (1 + ret_p).prod() - 1)**(252/num_dias) - 1 if num_dias > 0 else 0
            vol_p = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
            max_dd = calculate_max_drawdown(ret_p)
            
            metrics[p] = {
                "Retorno Anual": r_anual, 
                "Volatilidade": vol_p, 
                "Max Drawdown": max_dd
            }
            perf_acum[p] = (1 + ret_p).cumprod() - 1
            
            # Decomposição de Risco
            if vol_p > 0:
                risk_decomp[p] = pd.Series((w * np.dot(cov_matrix, w)) / vol_p**2, index=[c[0] for c in df_f.columns]).groupby(level=0).sum()

        # --- RESULTADOS ---
        st.markdown("---")
        res_df = pd.DataFrame(metrics)
        st.write("📊 **Consolidated Risk & Return (USD)**")
        st.dataframe(res_df.style.format("{:.2%}"), use_container_width=True)

        # --- GRÁFICO DE PERFORMANCE ---
        st.subheader("📈 Cumulative Performance")
        fig_comp = go.Figure()

        # Adicionar Benchmarks Dinâmicos conforme sua regra
        if msci_col and bbg_col:
            bench_data = {
                "Ultra Conservador": ret_diarios[bbg_col],
                "Conservador": (ret_diarios[msci_col] * 0.10) + (ret_diarios[bbg_col] * 0.90),
                "Moderado": (ret_diarios[msci_col] * 0.20) + (ret_diarios[bbg_col] * 0.80)
            }
            
            # Exibir no gráfico o benchmark do perfil selecionado ou o Moderado por padrão
            bench_moderado = (1 + bench_data["Moderado"]).cumprod() - 1
            fig_comp.add_trace(go.Scatter(x=bench_moderado.index, y=bench_moderado, 
                                        name="Benchmark (20/80)", line=dict(color=COR_BENCH, dash='dot')))

        for i, p in enumerate(perfis):
            fig_comp.add_trace(go.Scatter(x=perf_acum.index, y=perf_acum[p], name=p, 
                                        line=dict(color=CORES_OFFSHORE[i], width=2.5)))

        fig_comp.update_layout(template="simple_white", yaxis_tickformat='.1%', height=500, hovermode="x unified")
        st.plotly_chart(fig_comp, use_container_width=True)

        # --- ANÁLISE DE RISCO (BARRA DE CLASSES) ---
        st.markdown("---")
        col_risk, col_dd = st.columns(2)
        
        with col_risk:
            st.subheader("🏢 Allocation by Asset Class")
            df_c = edited.groupby("Classe")[perfis].sum().T
            fig_bar = go.Figure()
            for c in df_c.columns:
                fig_bar.add_trace(go.Bar(name=c, x=perfis, y=df_c[c]/100))
            fig_bar.update_layout(barmode='stack', template="simple_white", yaxis_tickformat='.0%', height=400)
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_dd:
            st.subheader("⚠️ Risk Contribution")
            df_rd = pd.DataFrame(risk_decomp).fillna(0)
            st.dataframe(df_rd.style.format("{:.1%}").background_gradient(cmap='YlOrRd'), use_container_width=True, height=400)

    except Exception as e:
        st.error(f"Erro no processamento dos dados offshore: {e}")
        st.info("Certifique-se que o Excel possui as colunas da imagem: Treasury, Bloomberg US Corporate, S&P, etc.")

else:
    st.info("Aguardando upload do arquivo Excel com dados em base 100.")