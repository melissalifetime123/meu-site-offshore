import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
from dateutil.relativedelta import relativedelta

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Offshore Portfolio Analytics", layout="wide")

# Estilo para melhorar a estética do Dashboard
st.markdown("""
    <style>
    [data-testid="stDataFrame"] { width: 100%; }
    h1, h2, h3 { color: #1C2C54; font-family: 'Segoe UI', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: #f0f2f6; border-radius: 4px; padding: 10px; }
    .stTabs [aria-selected="true"] { background-color: #1C2C54 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. FUNÇÃO DE CARREGAMENTO (BLINDADA CONTRA ERROS)
@st.cache_data
def load_offshore_data(file):
    try:
        # Lê o Excel
        df = pd.read_excel(file)
        
        # CORREÇÃO DEFINITIVA DO ERRO 'int':
        # Convertemos cada nome de coluna para string ANTES de qualquer tratamento
        df.columns = [str(c).replace('\n', ' ').replace('"', '').strip() for c in df.columns]
        
        # Converte a coluna Date para formato de data real
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date']).sort_values('Date').set_index('Date')
        
        # Garante que os valores de rentabilidade são numéricos
        df = df.apply(pd.to_numeric, errors='coerce').ffill()
        return df
    except Exception as e:
        st.error(f"Erro ao processar o ficheiro: {e}")
        return None

# --- SIDEBAR (BARRA LATERAL À ESQUERDA) ---
with st.sidebar:
    st.title("📂 Configurações")
    uploaded_file = st.file_uploader("Upload do ficheiro 'database.xlsx'", type=["xlsx", "xls"])
    
    st.divider()
    
    # Variáveis globais de data
    start_date = None
    end_date = None

    if uploaded_file:
        st.subheader("🗓️ Timeframe")
        
        # Carregamos temporariamente para definir os limites do filtro
        df_temp = load_offshore_data(uploaded_file)
        
        if df_temp is not None and not df_temp.empty:
            min_db = df_temp.index.min().to_pydatetime()
            max_db = df_temp.index.max().to_pydatetime()
            
            # Opções de Seleção de Período
            opcoes_tempo = ["Máximo", "YTD (Este Ano)", "12 Meses", "24 Meses", "Personalizado"]
            selecao = st.radio("Selecione o período de análise:", opcoes_tempo, index=2)

            # Lógica para definir as datas
            if selecao == "Máximo":
                start_date, end_date = min_db, max_db
            elif selecao == "YTD (Este Ano)":
                start_date = datetime.datetime(max_db.year, 1, 1)
                end_date = max_db
            elif selecao == "12 Meses":
                start_date = max_db - relativedelta(months=12)
                end_date = max_db
            elif selecao == "24 Meses":
                start_date = max_db - relativedelta(months=24)
                end_date = max_db
            elif selecao == "Personalizado":
                periodo = st.date_input(
                    "Defina o intervalo manualmente:",
                    value=(min_db, max_db),
                    min_value=min_db,
                    max_value=max_db
                )
                if isinstance(periodo, tuple) and len(periodo) == 2:
                    start_date, end_date = periodo

            # Ajuste caso a data calculada seja anterior à primeira data do Excel
            if start_date and start_date < min_db:
                start_date = min_db
                
            if start_date and end_date:
                st.success(f"📍 **Período Selecionado:**\n{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}")

# --- ÁREA PRINCIPAL ---
if uploaded_file and start_date and end_date:
    df_raw = load_offshore_data(uploaded_file)
    
    if df_raw is not None:
        # Filtragem por data
        mask = (df_raw.index >= pd.Timestamp(start_date)) & (df_raw.index <= pd.Timestamp(end_date))
        df_filtered = df_raw.loc[mask]

        if df_filtered.empty:
            st.warning("⚠️ Não existem dados para o período selecionado.")
        else:
            st.title("📊 Offshore Performance Analytics")
            
            # 3. MATRIZ DE ALOCAÇÃO
            st.subheader("⚖️ Alocação por Perfil de Risco")
            perfis_df = pd.DataFrame({
                "Classe": ['Cash', 'High Yield', 'Investment Grade', 'Treasury 10y', 'Equity', 'Alternatives'],
                "Ultra Conservador": [90, 0, 10, 0, 0, 0],
                "Conservador": [60, 0, 30, 10, 0, 0],
                "Moderado": [20, 10, 30, 10, 20, 10],
                "Arrojado": [5, 15, 15, 5, 45, 15],
                "Agressivo": [0, 15, 5, 0, 60, 20]
            })
            
            # Tabela editável
            edited_df = st.data_editor(perfis_df, hide_index=True, use_container_width=True)
            
            perfil_ativo = st.select_slider(
                "Mudar Perfil Visualizado:", 
                options=["Ultra Conservador", "Conservador", "Moderado", "Arrojado", "Agressivo"], 
                value="Moderado"
            )

            # 4. CÁLCULOS FINANCEIROS
            # Rentabilidade mensal
            returns = df_filtered.pct_change().dropna()
            
            # Pesos do perfil selecionado
            weights = edited_df.set_index("Classe")[perfil_ativo] / 100
            
            # Cálculo do retorno da carteira (Soma ponderada)
            # Nota: O código assume que as colunas do Excel têm os mesmos nomes que a coluna 'Classe'
            user_portfolio_return = sum(returns[asset] * weights[asset] for asset in weights.index if asset in returns.columns)
            
            # 5. CARTÕES DE PERFORMANCE (KPIs)
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                total_ret = (1 + user_portfolio_return).prod() - 1
                st.metric(f"Retorno {perfil_ativo}", f"{total_ret:.2%}")
            with c2:
                vol = user_portfolio_return.std() * np.sqrt(12)
                st.metric("Volatilidade (a.a.)", f"{vol:.2%}")
            with c3:
                # Benchmark Global Agg (se existir no Excel)
                if 'Bloomberg Global Aggregate' in returns.columns:
                    b_ret = (1 + returns['Bloomberg Global Aggregate']).prod() - 1
                    st.metric("Global Aggregate", f"{b_ret:.2%}")
                else: st.metric("Global Aggregate", "N/D")
            with c4:
                # Inflação (CPI)
                if 'CPI' in returns.columns:
                    cpi_ret = (1 + returns['CPI']).prod() - 1
                    st.metric("Inflação (CPI)", f"{cpi_ret:.2%}")
                else: st.metric("CPI", "N/D")

            # 6. GRÁFICOS
            st.divider()
            tab1, tab2 = st.tabs(["📈 Performance Acumulada", "🧱 Evolução por Ativo"])
            
            with tab1:
                fig = go.Figure()
                
                # Linha da Carteira do Utilizador
                cum_user = (1 + user_portfolio_return).cumprod() * 100
                fig.add_trace(go.Scatter(x=cum_user.index, y=cum_user, name=f"Carteira: {perfil_ativo}", line=dict(color='#1C2C54', width=4)))
                
                # Linha da Inflação (CPI)
                if 'CPI' in returns.columns:
                    cum_cpi = (1 + returns['CPI']).cumprod() * 100
                    fig.add_trace(go.Scatter(x=cum_cpi.index, y=cum_cpi, name="CPI (Inflação)", line=dict(color='#ef4444', dash='dash')))
                
                fig.update_layout(template="simple_white", hovermode="x unified", title="Base 100")
                st.plotly_chart(fig, use_container_width=True)

            with tab2:
                # Gráfico de área empilhada
                comp_df = pd.DataFrame(index=df_filtered.index)
                for asset, w in weights.items():
                    if w > 0 and asset in df_filtered.columns:
                        # Normaliza cada classe pelo peso inicial e evolução do ativo
                        comp_df[asset] = w * (df_filtered[asset] / df_filtered[asset].iloc[0]) * 100
                
                fig_area = go.Figure()
                for col in comp_df.columns:
                    fig_area.add_trace(go.Scatter(x=comp_df.index, y=comp_df[col], name=col, stackgroup='one', mode='none'))
                
                fig_area.update_layout(template="simple_white", title="Composição da Carteira ao Longo do Tempo")
                st.plotly_chart(fig_area, use_container_width=True)

else:
    st.info("👋 Bem-vindo! Por favor, carrega o ficheiro Excel na barra lateral à esquerda para visualizar a análise.")