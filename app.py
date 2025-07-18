import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Observatório Guaíba", layout="wide")

# --- 2. CARREGAMENTO E CACHE DOS DADOS ---
@st.cache_data
def carregar_dados():
    """
    Carrega os dados consolidados do arquivo CSV, converte a coluna de data
    e a define como índice do DataFrame.
    """
    caminho_arquivo = "dados_consolidados_guaiba_chuva.csv"
    if not os.path.exists(caminho_arquivo):
        st.error(f"Arquivo de dados '{caminho_arquivo}' não encontrado. "
                 f"Por favor, execute primeiro o script '1_processamento_dados.py'.")
        st.stop() # Interrompe a execução se os dados não existirem
    
    df = pd.read_csv(caminho_arquivo, sep=';', decimal=',')
    df['Data'] = pd.to_datetime(df['Data'])
    df.set_index('Data', inplace=True)
    return df

# --- FUNÇÃO CACHEADA PARA CÁLCULO DE CORRELAÇÃO ---
@st.cache_data
def calcular_correlacao_com_lag(df, max_lag=15):
    """
    Calcula a correlação entre o nível do rio e a precipitação com diferentes lags.
    
    Args:
        df (pd.DataFrame): DataFrame com 'Nivel_m' e 'Precipitacao_mm'.
        max_lag (int): Número máximo de dias de atraso a serem testados.
        
    Returns:
        tuple: Contendo o melhor lag (int), a melhor correlação (float), 
               e um dicionário com todas as correlações por lag.
    """
    correlacoes = {}
    for lag in range(1, max_lag + 1):
        # Cria uma nova coluna com a soma da chuva nos 'lag' dias anteriores.
        # .shift(1) garante que estamos olhando para dias passados, não o dia atual.
        chuva_acumulada = df['Precipitacao_mm'].shift(1).rolling(window=lag).sum()
        
        # Calcula a correlação de Pearson entre o nível do rio e a chuva acumulada.
        corr = df['Nivel_m'].corr(chuva_acumulada)
        
        if pd.notna(corr):
            correlacoes[lag] = corr
            
    if not correlacoes:
        return None, None, None
        
    # Encontra o lag com a maior correlação
    melhor_lag = max(correlacoes, key=correlacoes.get)
    melhor_corr = correlacoes[melhor_lag]
    
    return melhor_lag, melhor_corr, correlacoes

# Carrega os dados na inicialização do app.
df = carregar_dados()

# --- 3. TÍTULO E INTRODUÇÃO ---
st.title("🌊 Observatório Guaíba: Análise Comparativa das Cheias")
st.markdown("""
Esta aplicação analisa a relação entre o volume de chuvas e o nível do Rio Guaíba, 
com foco na comparação entre o período da enchente histórica de 2024 e o mesmo período de 2025.
Utilize as visualizações abaixo para explorar os dados.
""")

# --- 4. LÓGICA PRINCIPAL E VISUALIZAÇÕES ---
# Define os períodos de análise.
inicio_periodo_2024 = '2024-04-30'
fim_periodo_2024 = '2024-06-30'
inicio_periodo_2025 = '2025-04-30'
fim_periodo_2025 = '2025-06-30'

# Filtra os DataFrames para cada período.
df_2024 = df.loc[inicio_periodo_2024:fim_periodo_2024]
df_2025 = df.loc[inicio_periodo_2025:fim_periodo_2025]

# --- SEÇÃO DE ANÁLISE COMPARATIVA ---
st.header("Análise Comparativa: Enchente de 2024 vs. 2025")
st.markdown("Comparação direta do nível do rio durante o período crítico (30/Abr a 30/Jun).")

# Gráfico comparativo do Nível do Rio
fig_comparativa = go.Figure()
fig_comparativa.add_trace(go.Scatter(
    x=df_2024.index.strftime('%d-%b'), y=df_2024['Nivel_m'], mode='lines',
    name='Nível do Rio em 2024', line=dict(color='rgba(220, 53, 69, 0.8)', width=3)
))
fig_comparativa.add_trace(go.Scatter(
    x=df_2025.index.strftime('%d-%b'), y=df_2025['Nivel_m'], mode='lines',
    name='Nível do Rio em 2025', line=dict(color='rgba(25, 135, 84, 0.8)', width=3)
))
fig_comparativa.add_hline(y=3.0, line_dash="dash", line_color="blue",
                          annotation_text="Cota de Inundação (3.0m)", 
                          annotation_position="bottom right")
fig_comparativa.update_layout(
    title='Nível do Rio Guaíba: 2024 vs. 2025', xaxis_title='Data',
    yaxis_title='Nível do Rio (metros)', legend_title='Ano', hovermode='x unified'
)
st.plotly_chart(fig_comparativa, use_container_width=True)

# --- MÉTRICAS PRINCIPAIS ---
st.subheader("Resumo dos Períodos")
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Período Crítico de 2024")
    pico_24, chuva_24 = df_2024['Nivel_m'].max(), df_2024['Precipitacao_mm'].sum()
    st.metric(label="Pico do Nível do Rio", value=f"{pico_24:.2f} m", delta="Histórico", delta_color="inverse")
    st.metric(label="Chuva Acumulada no Período", value=f"{chuva_24:.1f} mm")
with col2:
    st.markdown("#### Período Comparativo de 2025")
    pico_25, chuva_25 = df_2025['Nivel_m'].max(), df_2025['Precipitacao_mm'].sum()
    delta_nivel = pico_25 - pico_24
    st.metric(label="Pico do Nível do Rio", value=f"{pico_25:.2f} m", delta=f"{delta_nivel:.2f} m vs 2024")
    st.metric(label="Chuva Acumulada no Período", value=f"{chuva_25:.1f} mm")

# --- SEÇÃO DE ANÁLISE DETALHADA POR ANO ---
st.header("Análise Detalhada por Ano")
ano_detalhe = st.selectbox("Selecione o ano para ver o detalhe:", [2024, 2025], index=0, key="detalhe")
df_detalhe = df_2024 if ano_detalhe == 2024 else df_2025
fig_detalhe = make_subplots(specs=[[{"secondary_y": True}]])
fig_detalhe.add_trace(go.Bar(x=df_detalhe.index, y=df_detalhe['Precipitacao_mm'], name='Precipitação (mm)', marker_color='lightblue'), secondary_y=False)
fig_detalhe.add_trace(go.Scatter(x=df_detalhe.index, y=df_detalhe['Nivel_m'], name='Nível do Rio (m)', line=dict(color='darkblue', width=3)), secondary_y=True)
fig_detalhe.add_hline(y=3.0, line_dash="dash", line_color="red", secondary_y=True, annotation_text="Cota de Inundação", annotation_position="bottom right")
fig_detalhe.update_layout(title_text=f'Chuva Diária vs. Nível do Rio em {ano_detalhe}', hovermode='x unified')
fig_detalhe.update_yaxes(title_text='Precipitação (mm)', secondary_y=False)
fig_detalhe.update_yaxes(title_text='Nível do Rio (m)', secondary_y=True)
st.plotly_chart(fig_detalhe, use_container_width=True)

# --- NOVA SEÇÃO: FASE 3 - ANÁLISE DE CORRELAÇÃO ---
st.header("Análise de Correlação: O Atraso entre a Chuva e a Cheia")
st.markdown("""
O nível do rio não sobe instantaneamente. Existe um **atraso (lag)** entre a precipitação e o pico da cheia. 
Esta análise calcula a correlação entre a chuva acumulada em diferentes janelas de tempo (1 a 15 dias) e o nível do rio, 
para descobrir qual período de chuva tem maior impacto.
""")

ano_corr = st.selectbox("Selecione o ano para a análise de correlação:", [2024, 2025], index=0, key="correlacao")
df_corr = df_2024 if ano_corr == 2024 else df_2025

# Executa a função de cálculo
melhor_lag, melhor_corr, todas_correlacoes = calcular_correlacao_com_lag(df_corr.copy())

if melhor_lag:
    st.success(f"**Resultado para {ano_corr}:** A correlação mais forte (**{melhor_corr:.2f}**) foi encontrada com um atraso de **{melhor_lag} dias**.")
    
    col_corr1, col_corr2 = st.columns(2)
    
    with col_corr1:
        # Gráfico 1: Barras mostrando a correlação para cada lag
        fig_corr_barras = go.Figure()
        fig_corr_barras.add_trace(go.Bar(
            x=list(todas_correlacoes.keys()),
            y=list(todas_correlacoes.values()),
            marker_color='skyblue'
        ))
        # Destaca a barra com a maior correlação
        fig_corr_barras.add_trace(go.Bar(
            x=[melhor_lag],
            y=[melhor_corr],
            marker_color='salmon',
            name='Melhor Atraso'
        ))
        fig_corr_barras.update_layout(
            title=f'Correlação por Atraso (Lag) em {ano_corr}',
            xaxis_title='Atraso em dias (Lag)',
            yaxis_title='Coeficiente de Correlação',
            showlegend=False
        )
        st.plotly_chart(fig_corr_barras, use_container_width=True)
        
    with col_corr2:
        # Gráfico 2: Dispersão para visualizar a relação no melhor lag
        df_plot_corr = df_corr.copy()
        df_plot_corr['Chuva_Acumulada'] = df_plot_corr['Precipitacao_mm'].shift(1).rolling(window=melhor_lag).sum()
        
        fig_scatter = go.Figure()
        fig_scatter.add_trace(go.Scatter(
            x=df_plot_corr['Chuva_Acumulada'],
            y=df_plot_corr['Nivel_m'],
            mode='markers',
            marker=dict(color='rgba(220, 53, 69, 0.6)')
        ))
        fig_scatter.update_layout(
            title=f'Nível do Rio vs. Chuva Acumulada nos {melhor_lag} dias anteriores',
            xaxis_title=f'Chuva Acumulada nos {melhor_lag} dias (mm)',
            yaxis_title='Nível do Rio (m)'
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
else:
    st.warning(f"Não foi possível calcular a correlação para {ano_corr}. Verifique os dados de entrada.")

# --- 5. SEÇÃO "SOBRE" NA BARRA LATERAL---
st.sidebar.title("Sobre o Projeto")

url_foto = "https://imgur.com/a/1aVvt6F" 
st.sidebar.image(url_foto, caption="Gustavu Vinícius de Sousa Martins", use_column_width=True)

# --- INFORMAÇÕES ATUALIZADAS ---
st.sidebar.info(
    """
    Este projeto foi desenvolvido como requisito para a conclusão da disciplina de 
    **Análise de Dados**, como parte do curso de **Análise e Desenvolvimento de Sistemas** da **Universidade Estácio de Sá**.
    
    **Autor:** Gustavu Vinícius de Sousa Martins
    
    O objetivo é aplicar técnicas de análise de dados para gerar insights de 
    relevância para a comunidade de Porto Alegre, RS, a partir de dados públicos.
    
    **Fontes de Dados:**
    - **Nível do Rio:** Agência Nacional de Águas (ANA)
    - **Dados de Chuva:** Instituto Nacional de Meteorologia (INMET)
    """
)
st.sidebar.markdown("---")
st.sidebar.markdown("Para ver o código-fonte, acesse o [repositório no GitHub](https://github.com/SEU-USUARIO/SEU-REPOSITORIO).") # <--- SUBSTITUA PELO SEU LINK DO GITHUB
