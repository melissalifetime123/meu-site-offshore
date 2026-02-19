import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
from dateutil.relativedelta import relativedelta

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Offshore Portfolio Analytics", layout="wide")

st.markdown("""
    <style>
    [data-testid="stDataFrame"] { width: 100%; }
    h1, h2, h3 { color: #1C2C54; font-family: 'Segoe UI', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: #f0f2f6; border-radius: 4px; padding: 10px; }
    .stTabs [aria-selected="true"] { background-color: #1C2C54 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. FUNÇÃO DE CARREGAMENTO (CORRIGIDA PARA EVITAR O ERRO DE 'INT')
@st.cache_data
def load_offshore_data(file):
    try:
        # Lemos o Excel
        df = pd.read_excel(file)
        
        # SOLUÇÃO DO ERRO: Convertemos o nome da coluna para string ANTES de tratar o texto
        new_columns = []
        for c in df.columns:
            column_name = str(c) # Garante que vira texto (resolve o erro do 'int')
            column_name = column_name.replace('\n', ' ').replace('"', '').strip()
            new_columns.append(column_name)
        
        df.columns = new_columns
        
        # Converte a coluna Date
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date']).sort_values('Date').set_index('Date')
        
        # Garante que os valores das células são números
        df = df.apply(pd.to_numeric, errors='coerce').ffill()
        return df
    except Exception as e:
        st.error(f"Erro ao processar o ficheiro: {e}")
        return None

# --- SIDEBAR: TIMEFRAME ---
with st.sidebar:
    st.title("📂 Configurações")
    uploaded_file = st.file_uploader("Upload 'database.xlsx'", type=["xlsx", "xls"])
    
    st.divider()
    
    start_date = None
    end_date = None

    if uploaded_file:
        st.subheader("🗓️ Timeframe")
        df_temp = load_offshore_data(uploaded_file)
        
        if df_temp is not None and not df_temp.empty:
            min_db = df_temp.index.min().to_pydatetime()
            max_db = df_temp.index.max().to_pydatetime()
            
            opcoes = ["Máximo", "YTD", "12 Meses", "24 Meses", "Personalizado"]
            selecao = st.radio("Selecione o período:", opcoes, index=2)

            if selecao == "Máximo":
                start_date, end_date = min_db, max_db
            elif selecao == "YTD":
                start_date = datetime.datetime(max_db.year, 1, 1)
                end_date = max_db
            elif selecao == "12 Meses":
                start_date = max_db - relativedelta(months=12)
                end_date = max_db
            elif selecao == "24 Meses":
                start_date = max_db - relativedelta(months=24)
                end_date = max_db
            elif selecao == "Personalizado":
                periodo = st.date_input("Intervalo:", value=(min_db, max_db), min_value=min_db, max_value=max_db)
                if isinstance(periodo, tuple) and len(periodo) == 2:
                    start_date, end_date = periodo

            if start_date and start_date < min_db: start_date = min_db
            if start_date and end_date:
                st.success(f"Período: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")

# --- ÁREA PRINCIPAL ---
if uploaded_file and start_date and end_date:
    df_raw = load_offshore_data(uploaded_file)
    
    if df_raw is not None:
        mask = (df_raw.index >= pd.Timestamp(start_date)) & (df_raw.index <= pd.Timestamp(end_date))
        df_filtered = df_raw.loc[mask]

        if not df_filtered.empty:
            st.title("📊 Offshore Performance Analytics")
            
            # Matriz de Perfis
            perfis_df = pd.DataFrame({
                "Classe": ['Cash', 'High Yield', 'Investment Grade', 'Treasury 10y', 'Equity', 'Alternatives'],
                "Ultra Conservador": [90, 0, 10, 0, 0, 0],
                "Conservador": [60, 0, 30, 10, 0, 0],
                "Moderado": [20, 10, 30, 10, 20, 10],
                "Arrojado": [5, 15, 15, 5, 45, 15],
                "Agressivo": [0, 15, 5, 0, 60, 20]
            })
            
            edited_df = st.data_editor(perfis_df, hide_index=True, use_container_width=True)
            perfil_ativo = st.select_slider("Perfil Visualizado:", options=["Ultra Conservador", "Conservador", "Moderado", "Arrojado", "Agressivo"], value="Moderado")

            # Cálculos
            returns = df_filtered.pct_change().dropna()
            weights = edited_df.set_index("Classe")[perfil_ativo] / 100
            
            # Retorno do Usuário
            user_ret = sum(returns[asset] * weights[asset] for asset in weights.index if asset in returns.columns)
            
            # KPIs
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Retorno Total", f"{(1 + user_ret).prod() - 1:.2%}")
            with c2:
                st.metric("Volatilidade (aa)", f"{user_ret.std() * np.sqrt(12):.2%}")
            with c3:
                if 'CPI' in returns.columns:
                    st.metric("CPI", f"{(1 + returns['CPI']).prod() - 1:.2%}")

            # Gráficos
            tab1, tab2 = st.tabs(["📈 Evolução", "🧱 Alocação"])
            with tab1:
                fig = go.Figure()
                cum_ret = (1 + user_ret).cumprod() * 100
                fig.add_trace(go.Scatter(x=cum_ret.index, y=cum_ret, name="Sua Carteira", line=dict(color='#1C2C54', width=3)))
                if 'Bloomberg Global Aggregate' in returns.columns:
                    bench = (1 + returns['Bloomberg Global Aggregate']).cumprod() * 100
                    fig.add_trace(go.Scatter(x=bench.index, y=bench, name="Benchmark Agg", line=dict(dash='dot')))
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                # Composição de área
                comp_df = pd.DataFrame(index=df_filtered.index)
                for asset, w in weights.items():
                    if w > 0 and asset in df_filtered.columns:
                        comp_df[asset] = w * (df_filtered[asset] / df_filtered[asset].iloc[0]) * 100
                fig_area = go.Figure()
                for col in comp_df.columns:
                    fig_area.add_trace(go.Scatter(x=comp_df.index, y=comp_df[col], name=col, stackgroup='one', mode='none'))
                st.plotly_chart(fig_area, use_container_width=True)

else:
    st.info("Aguardando ficheiro Excel...")