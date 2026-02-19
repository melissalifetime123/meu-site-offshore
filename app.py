import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
from dateutil.relativedelta import relativedelta

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Offshore Analytics Pro", layout="wide")

# 2. FUNÇÃO DE CARREGAMENTO REESCRITA (RESOLVE O ERRO 'INT')
@st.cache_data
def load_offshore_data(file):
    try:
        # Lê o Excel
        df = pd.read_excel(file)
        
        # --- LIMPEZA RADICAL DE COLUNAS ---
        # Força todos os nomes de colunas a serem strings e remove espaços
        df.columns = [str(c).strip() for c in df.columns]
        
        # Remove colunas que começam por "Unnamed" ou que são apenas números (o que causa o erro .upper)
        cols_a_manter = [c for c in df.columns if "Unnamed" not in c and not c.isdigit()]
        df = df[cols_a_manter]
        
        # Limpa quebras de linha nos nomes das colunas (ex: "Investment\nGrade")
        df.columns = [c.replace('\n', ' ').replace('  ', ' ') for c in df.columns]
        
        # Converte a coluna Date
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date']).sort_values('Date').set_index('Date')
        
        # Garante que os dados são numéricos
        df = df.apply(pd.to_numeric, errors='coerce').ffill()
        
        return df
    except Exception as e:
        st.error(f"Erro ao processar colunas: {e}")
        return None

# --- SIDEBAR (BARRA LATERAL) ---
with st.sidebar:
    st.title("📂 Dados")
    uploaded_file = st.file_uploader("Upload database.xlsx", type=["xlsx"])
    
    st.divider()
    start_date, end_date = None, None

    if uploaded_file:
        df_raw = load_offshore_data(uploaded_file)
        
        if df_raw is not None:
            st.subheader("🗓️ Filtro de Datas")
            min_d, max_d = df_raw.index.min().to_pydatetime(), df_raw.index.max().to_pydatetime()
            
            # Opções de período
            timerange = st.radio("Período:", ["Máximo", "YTD", "12 Meses", "24 Meses", "Personalizado"])
            
            if timerange == "Máximo": start_date, end_date = min_d, max_d
            elif timerange == "YTD": start_date, end_date = datetime.datetime(max_d.year, 1, 1), max_d
            elif timerange == "12 Meses": start_date, end_date = max_d - relativedelta(months=12), max_d
            elif timerange == "24 Meses": start_date, end_date = max_d - relativedelta(months=24), max_d
            elif timerange == "Personalizado":
                res = st.date_input("Intervalo:", value=(min_d, max_d), min_value=min_d, max_value=max_d)
                if isinstance(res, tuple) and len(res) == 2: start_date, end_date = res

# --- DASHBOARD PRINCIPAL ---
if uploaded_file and start_date and end_date:
    # Aplicar filtro de data
    df = df_raw.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)].copy()
    
    st.title("📊 Offshore Portfolio Analytics")
    
    # 3. TABELA DE PESOS (CLASSE DE ATIVOS)
    st.subheader("⚖️ Alocação Alvo")
    # Definimos as classes que esperamos encontrar no Excel
    classes_esperadas = ['Cash', 'High Yield', 'Investment Grade', 'Treasury 10y', 'Equity', 'Alternatives']
    
    perfis_df = pd.DataFrame({
        "Classe": classes_esperadas,
        "Peso (%)": [20.0, 10.0, 30.0, 10.0, 20.0, 10.0]
    })
    
    edit_df = st.data_editor(perfis_df, hide_index=True, use_container_width=True)
    pesos = edit_df.set_index("Classe")["Peso (%)"] / 100

    # 4. CÁLCULOS DE RENTABILIDADE
    # Calcula variação percentual
    returns = df.pct_change().fillna(0)
    
    # Criar a série da Carteira apenas com ativos que existem no Excel
    ativos_validos = [c for c in pesos.index if c in returns.columns]
    portfolio_rt = sum(returns[asset] * pesos[asset] for asset in ativos_validos)
    
    # 5. GRÁFICOS
    st.divider()
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Gráfico Base 100
        cum_portfolio = (1 + portfolio_rt).cumprod() * 100
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cum_portfolio.index, y=cum_portfolio, name="Minha Carteira", line=dict(color='#1C2C54', width=3)))
        
        # Adicionar Benchmark se existir
        bench = 'Bloomberg Global Aggregate'
        if bench in df.columns:
            cum_bench = (df[bench] / df[bench].iloc[0]) * 100
            fig.add_trace(go.Scatter(x=cum_bench.index, y=cum_bench, name="Global Agg", line=dict(color='#BDC3C7', dash='dot')))
            
        fig.update_layout(title="Evolução Patrimonial (Base 100)", template="simple_white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Resumo de Métricas
        total_ret = (cum_portfolio.iloc[-1] / 100) - 1
        vol = portfolio_rt.std() * np.sqrt(12)
        
        st.metric("Retorno no Período", f"{total_ret:.2%}")
        st.metric("Volatilidade Anualizada", f"{vol:.2%}")
        st.write("---")
        st.write("**Ativos Identificados:**")
        st.write(", ".join(ativos_validos))

else:
    st.info("💡 Carregue o ficheiro 'database.xlsx' na barra lateral para começar.")