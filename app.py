import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
from dateutil.relativedelta import relativedelta

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Offshore Portfolio Analytics", layout="wide")

# Estilo CSS para melhorar o visual
st.markdown("""
    <style>
    [data-testid="stDataFrame"] { width: 100%; }
    h1, h2, h3 { color: #1C2C54; font-family: 'Segoe UI', sans-serif; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# 2. FUNÇÃO DE CARREGAMENTO ULTRA-ROBUSTA
@st.cache_data
def load_offshore_data(file):
    try:
        # Lê o Excel - se houver erro de motor, tenta 'openpyxl'
        df = pd.read_excel(file)
        
        # LIMPEZA DE COLUNAS (AQUI MORRE O ERRO 'INT')
        # 1. Garante que tudo é string
        # 2. Remove quebras de linha e espaços extras
        new_columns = []
        for col in df.columns:
            col_str = str(col).strip().replace('\n', ' ').replace('"', '')
            new_columns.append(col_str)
        df.columns = new_columns

        # Converte a coluna Date
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date']).sort_values('Date').set_index('Date')
        
        # Converte dados para numérico (remove colunas totalmente vazias ou de texto inútil)
        df = df.apply(pd.to_numeric, errors='coerce')
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')] # Remove colunas fantasmas do Excel
        df = df.ffill() 
        
        return df
    except Exception as e:
        st.error(f"Erro crítico no processamento: {e}")
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("📂 Painel de Controlo")
    uploaded_file = st.file_uploader("Submeta o ficheiro 'database.xlsx'", type=["xlsx", "xls"])
    st.divider()
    
    start_date, end_date = None, None

    if uploaded_file:
        df_raw = load_offshore_data(uploaded_file)
        
        if df_raw is not None and not df_raw.empty:
            st.subheader("🗓️ Filtro de Tempo")
            min_db = df_raw.index.min().to_pydatetime()
            max_db = df_raw.index.max().to_pydatetime()
            
            periodo_opc = st.radio("Período:", ["Máximo", "YTD", "12 Meses", "24 Meses", "Personalizado"], index=0)

            if periodo_opc == "Máximo": start_date, end_date = min_db, max_db
            elif periodo_opc == "YTD": start_date, end_date = datetime.datetime(max_db.year, 1, 1), max_db
            elif periodo_opc == "12 Meses": start_date, end_date = max_db - relativedelta(months=12), max_db
            elif periodo_opc == "24 Meses": start_date, end_date = max_db - relativedelta(months=24), max_db
            elif periodo_opc == "Personalizado":
                res = st.date_input("Intervalo:", value=(min_db, max_db), min_value=min_db, max_value=max_db)
                if isinstance(res, tuple) and len(res) == 2: start_date, end_date = res

# --- CONTEÚDO PRINCIPAL ---
if uploaded_file and start_date and end_date:
    # Filtragem
    df = df_raw.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)].copy()
    
    if not df.empty:
        st.title("📊 Análise de Performance Offshore")
        
        # 3. MATRIZ DE ALOCAÇÃO (Editável)
        st.subheader("⚖️ Definição de Pesos")
        perfis_df = pd.DataFrame({
            "Classe": ['Cash', 'High Yield', 'Investment Grade', 'Treasury 10y', 'Equity', 'Alternatives'],
            "Peso (%)": [20.0, 10.0, 30.0, 10.0, 20.0, 10.0]
        })
        
        edited_weights = st.data_editor(perfis_df, hide_index=True, use_container_width=True)
        weights_dict = edited_weights.set_index("Classe")["Peso (%)"] / 100

        # 4. CÁLCULOS
        returns = df.pct_change().fillna(0)
        
        # Cálculo da Carteira (ignora colunas que não existem no Excel)
        available_assets = [a for a in weights_dict.index if a in returns.columns]
        portfolio_return = sum(returns[asset] * weights_dict[asset] for asset in available_assets)
        
        # 5. DASHBOARD (KPIs)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Retorno Acumulado", f"{( (1 + portfolio_return).prod() - 1 ):.2%}")
        with c2:
            st.metric("Volatilidade (a.a.)", f"{( portfolio_return.std() * np.sqrt(12) ):.2%}")
        with c3:
            bench = 'Bloomberg Global Aggregate'
            val = f"{( (1 + returns[bench]).prod() - 1 ):.2%}" if bench in returns.columns else "N/A"
            st.metric("Bench. Global Agg", val)
        with c4:
            cpi = 'CPI'
            val_cpi = f"{( (1 + returns[cpi]).prod() - 1 ):.2%}" if cpi in returns.columns else "N/A"
            st.metric("Inflação (CPI)", val_cpi)

        # 6. GRÁFICO DE PERFORMANCE
        st.divider()
        cum_ret = (1 + portfolio_return).cumprod() * 100
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cum_ret.index, y=cum_ret, name="Minha Carteira", line=dict(color='#1C2C54', width=3)))
        
        if 'Bloomberg Global Aggregate' in df.columns:
            cum_bench = (df['Bloomberg Global Aggregate'] / df['Bloomberg Global Aggregate'].iloc[0]) * 100
            fig.add_trace(go.Scatter(x=cum_bench.index, y=cum_bench, name="Benchmark", line=dict(color='#94a3b8', dash='dot')))

        fig.update_layout(title="Evolução Patrimonial (Base 100)", template="simple_white", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Sem dados para as datas selecionadas.")
else:
    st.info("Aguardando ficheiro Excel...")