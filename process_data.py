import pandas as pd
import requests
import io
from datetime import datetime

# --- Configurações ---
# Estação Meteorológica do INMET em Porto Alegre (Jardim Botânico)
CODIGO_ESTACAO_INMET = "A801"

# Estação Fluviométrica da ANA no Cais Mauá (Porto Alegre)
CODIGO_ESTACAO_ANA = "66900000"

# Períodos de interesse
ANO_PASSADO = "2024"
ANO_ATUAL = "2025"
DATA_INICIO_ATUAL = f"{ANO_ATUAL}-01-01"
# Usamos a data de hoje para o fim do período atual
DATA_FIM_ATUAL = datetime.now().strftime('%Y-%m-%d')


def buscar_dados_chuva(estacao, ano):
    """
    Busca os dados de precipitação de uma estação do INMET para um ano específico.
    """
    print(f"Buscando dados de chuva para o ano de {ano}...")
    # O INMET usa um formato de data diferente na URL para o ano completo
    data_inicio = f"{ano}-01-01"
    data_fim = f"{ano}-12-31"
    if ano == ANO_ATUAL:
        data_fim = DATA_FIM_ATUAL

    url = f"https://apitempo.inmet.gov.br/estacao/{data_inicio}/{data_fim}/{estacao}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Lança um erro para respostas ruins (4xx ou 5xx)
        
        # O request retorna um JSON
        dados_json = response.json()
        df = pd.DataFrame(dados_json)
        
        print(f"  -> Sucesso! {len(df)} registros de chuva encontrados para {ano}.")
        return df

    except requests.exceptions.RequestException as e:
        print(f"  -> ERRO ao buscar dados de chuva para {ano}: {e}")
        return pd.DataFrame()


def buscar_dados_nivel(estacao, ano):
    """
    Busca os dados de nível de uma estação da ANA/SGB para um ano específico.
    """
    print(f"Buscando dados de nível do rio para o ano de {ano}...")
    data_inicio = f"01/01/{ano}"
    data_fim = f"31/12/{ano}"
    if ano == ANO_ATUAL:
        data_fim = datetime.now().strftime('%d/%m/%Y')

    # A API da ANA é um pouco diferente, montamos uma URL de requisição de CSV
    url = (f"https://www.snirh.gov.br/hidroweb/rest/api/documento/gerarTelemetricas"
           f"?codEstains={estacao}&dataInicio={data_inicio}&dataFim={data_fim}&tipoArquivo=3")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # A resposta é um CSV, então lemos com o Pandas diretamente do conteúdo
        # Usamos 'io.StringIO' para tratar o texto da resposta como um arquivo
        # O delimitador é ';', o decimal é ',' e pulamos as 13 primeiras linhas de cabeçalho
        df = pd.read_csv(io.StringIO(response.text), sep=';', decimal=',', skiprows=13)
        
        print(f"  -> Sucesso! {len(df)} registros de nível encontrados para {ano}.")
        return df

    except requests.exceptions.RequestException as e:
        print(f"  -> ERRO ao buscar dados de nível para {ano}: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"  -> ERRO ao processar CSV de nível para {ano}: {e}")
        return pd.DataFrame()

def processar_dados(df_chuva_24, df_chuva_25, df_nivel_24, df_nivel_25):
    """
    Limpa, transforma, combina e unifica todos os dados.
    """
    print("\nIniciando processamento e unificação dos dados...")

    # --- Processamento Chuva ---
    df_chuva = pd.concat([df_chuva_24, df_chuva_25], ignore_index=True)
    if not df_chuva.empty:
        df_chuva['data'] = pd.to_datetime(df_chuva['DT_MEDICAO'] + ' ' + df_chuva['HR_MEDICAO'].astype(str).str.zfill(4).str.slice(0, 2) + ':00:00')
        df_chuva = df_chuva[['data', 'CHUVA']].rename(columns={'CHUVA': 'precipitacao_mm'})
        df_chuva['precipitacao_mm'] = pd.to_numeric(df_chuva['precipitacao_mm'], errors='coerce').fillna(0)
        df_chuva.set_index('data', inplace=True)
        print("  -> Dados de chuva processados.")

    # --- Processamento Nível ---
    df_nivel = pd.concat([df_nivel_24, df_nivel_25], ignore_index=True)
    if not df_nivel.empty:
        # Seleciona apenas as colunas de interesse
        df_nivel = df_nivel[['Data', 'Hora', 'Nivel_1']]
        df_nivel['data'] = pd.to_datetime(df_nivel['Data'] + ' ' + df_nivel['Hora'], format='%d/%m/%Y %H:%M:%S')
        df_nivel = df_nivel[['data', 'Nivel_1']].rename(columns={'Nivel_1': 'nivel_cm'})
        df_nivel['nivel_cm'] = pd.to_numeric(df_nivel['nivel_cm'], errors='coerce')
        df_nivel.set_index('data', inplace=True)
        print("  -> Dados de nível do rio processados.")
    
    # --- Unificação e Reamostragem ---
    # Combina os dois dataframes usando o índice de data
    df_combinado = pd.merge(df_chuva, df_nivel, left_index=True, right_index=True, how='outer')
    
    # Reamostra os dados para uma frequência diária
    # Para chuva, somamos o total do dia.
    # Para o nível, tiramos a média do dia.
    df_diario = df_combinado['precipitacao_mm'].resample('D').sum().to_frame()
    df_diario['nivel_cm'] = df_combinado['nivel_cm'].resample('D').mean()
    
    # Preenche dias sem medição de nível com o último valor válido
    df_diario['nivel_cm'].fillna(method='ffill', inplace=True)
    df_diario.dropna(subset=['nivel_cm'], inplace=True) # Remove dias no início sem dados
    print("  -> Dados reamostrados para frequência diária.")

    # --- Criação das Colunas Finais ---
    df_diario['ano'] = df_diario.index.year
    df_diario['dia_do_ano'] = df_diario.index.dayofyear
    df_diario['nivel_m'] = df_diario['nivel_cm'] / 100
    
    # Reseta o índice para ter a data como uma coluna normal
    df_diario.reset_index(inplace=True)
    df_final = df_diario[['data', 'ano', 'dia_do_ano', 'precipitacao_mm', 'nivel_m']]
    print("  -> Colunas finais para comparação criadas.")

    return df_final

# --- Execução Principal ---
if __name__ == "__main__":
    # 1. Buscar todos os dados
    dados_chuva_2024 = buscar_dados_chuva(CODIGO_ESTACAO_INMET, ANO_PASSADO)
    dados_chuva_2025 = buscar_dados_chuva(CODIGO_ESTACAO_INMET, ANO_ATUAL)
    dados_nivel_2024 = buscar_dados_nivel(CODIGO_ESTACAO_ANA, ANO_PASSADO)
    dados_nivel_2025 = buscar_dados_nivel(CODIGO_ESTACAO_ANA, ANO_ATUAL)

    # 2. Processar os dados
    if not any([df.empty for df in [dados_chuva_2024, dados_chuva_2025, dados_nivel_2024, dados_nivel_2025]]):
        df_resultado = processar_dados(dados_chuva_2024, dados_chuva_2025, dados_nivel_2024, dados_nivel_2025)
        
        # 3. Salvar o arquivo final
        nome_arquivo_saida = "dados_comparativos_2024_2025.csv"
        df_resultado.to_csv(nome_arquivo_saida, index=False, decimal='.', sep=',')
        print(f"\nProcesso concluído! Arquivo '{nome_arquivo_saida}' salvo com {len(df_resultado)} linhas.")
    else:
        print("\nProcesso interrompido devido a falha na busca de um ou mais conjuntos de dados.")
