import pandas as pd
import os

# --- CONFIGURAÇÃO INICIAL ---
# Define o caminho para a pasta onde os arquivos estão localizados.
# Usar os.path.join é uma boa prática para que o código funcione em diferentes sistemas operacionais.
DIRETORIO_PROJETO = r"C:\Users\GUSTAVU\Documents\Projetos\analise_dados"

# Nomes dos arquivos de entrada
ARQUIVO_RIO = "output.csv"
ARQUIVO_CLIMA_2024 = "INMET_S_RS_A801_PORTO ALEGRE - JARDIM BOTANICO_01-01-2024_A_31-12-2024.csv"
ARQUIVO_CLIMA_2025 = "INMET_S_RS_A801_PORTO ALEGRE - JARDIM BOTANICO_01-01-2025_A_30-06-2025.csv"

# Nome do arquivo de saída que será gerado
ARQUIVO_SAIDA = "dados_consolidados_guaiba_chuva.csv"

print("Iniciando o processo de limpeza e consolidação dos dados...")

# --- 1. CARREGANDO E TRATANDO DADOS DO NÍVEL DO RIO GUAÍBA (ANA) ---
print(f"Processando dados do rio do arquivo: {ARQUIVO_RIO}")
try:
    caminho_rio = os.path.join(DIRETORIO_PROJETO, ARQUIVO_RIO)
    
    # Carrega o CSV do nível do rio
    df_rio = pd.read_csv(caminho_rio)
    
    # Renomeia as colunas para facilitar o acesso
    df_rio.columns = ['Timestamp', 'Medicao_str']
    
    # Limpeza da coluna de medição:
    # 1. Remove o " m" do final da string.
    # 2. Substitui a vírgula decimal por ponto.
    # 3. Converte a coluna para o tipo numérico (float).
    df_rio['Nivel_m'] = df_rio['Medicao_str'].str.replace(' m', '', regex=False).str.replace(',', '.', regex=False)
    df_rio['Nivel_m'] = pd.to_numeric(df_rio['Nivel_m'], errors='coerce')
    
    # Converte a coluna de timestamp para o formato datetime do pandas
    df_rio['Timestamp'] = pd.to_datetime(df_rio['Timestamp'], format='%d/%m/%Y %H:%M')
    
    # Define o Timestamp como o índice do DataFrame para facilitar a agregação por dia
    df_rio.set_index('Timestamp', inplace=True)
    
    # Como temos medições a cada 15 minutos, vamos agregar os dados por dia.
    # A média diária do nível do rio é uma boa métrica.
    df_rio_diario = df_rio['Nivel_m'].resample('D').mean().to_frame()
    
    # Remove dias que não tiveram medição
    df_rio_diario.dropna(inplace=True)

    print("Dados do nível do rio processados com sucesso.")

except FileNotFoundError:
    print(f"ERRO: O arquivo {ARQUIVO_RIO} não foi encontrado no diretório {DIRETORIO_PROJETO}.")
    exit() # Encerra o script se o arquivo principal não for encontrado

# --- 2. CARREGANDO E TRATANDO DADOS DE CLIMA (INMET) ---
print(f"Processando dados de clima dos arquivos de 2024 e 2025...")
try:
    caminho_clima_2024 = os.path.join(DIRETORIO_PROJETO, ARQUIVO_CLIMA_2024)
    caminho_clima_2025 = os.path.join(DIRETORIO_PROJETO, ARQUIVO_CLIMA_2025)
    
    # Carrega os dois arquivos de clima
    # Os arquivos do INMET usam ';' como separador, tem problemas de codificação (usamos 'latin1')
    # e possuem 8 linhas de cabeçalho que precisam ser puladas.
    df_clima_2024 = pd.read_csv(caminho_clima_2024, sep=';', encoding='latin1', skiprows=8)
    df_clima_2025 = pd.read_csv(caminho_clima_2025, sep=';', encoding='latin1', skiprows=8)
    
    # Junta os dois DataFrames em um só
    df_clima_total = pd.concat([df_clima_2024, df_clima_2025], ignore_index=True)
    
    # Seleciona as colunas que nos interessam: Data, Hora e Precipitação
    coluna_precipitacao = 'PRECIPITAÇÃO TOTAL, HORÁRIO (mm)'
    df_clima = df_clima_total[['Data', 'Hora UTC', coluna_precipitacao]].copy()
    
    # Renomeia as colunas para nomes mais simples
    df_clima.rename(columns={
        'Data': 'Data',
        'Hora UTC': 'Hora',
        coluna_precipitacao: 'Precipitacao_mm'
    }, inplace=True)

    # --- CORREÇÃO APLICADA AQUI ---
    # Garante que a coluna 'Hora' contenha apenas os dígitos, removendo " UTC" ou outros textos.
    df_clima['Hora'] = df_clima['Hora'].astype(str).str.extract('(\d+)').iloc[:, 0] # <-- ALTERAÇÃO

    # Cria uma coluna de Timestamp completa
    # A hora está no formato '0000', '0100', etc. Formatamos para '00:00', '01:00'
    df_clima['Hora'] = df_clima['Hora'].str.zfill(4).str.slice_replace(2, 0, ':')
    df_clima['Timestamp'] = pd.to_datetime(df_clima['Data'] + ' ' + df_clima['Hora'], format='%Y/%m/%d %H:%M')

    # Limpeza da coluna de precipitação
    df_clima['Precipitacao_mm'] = df_clima['Precipitacao_mm'].str.replace(',', '.').astype(float)
    
    # Define o Timestamp como índice
    df_clima.set_index('Timestamp', inplace=True)
    
    # Agrega os dados de precipitação por dia.
    # Para chuva, queremos a SOMA total do dia.
    df_clima_diario = df_clima['Precipitacao_mm'].resample('D').sum().to_frame()
    
    print("Dados de clima processados com sucesso.")

except FileNotFoundError as e:
    print(f"ERRO: Não foi possível encontrar um dos arquivos de clima. Verifique se os nomes estão corretos. Detalhe: {e}")
    exit()
except Exception as e:
    print(f"Ocorreu um erro inesperado ao processar os dados de clima: {e}")
    exit()

# --- 3. JUNTANDO OS DADOS E SALVANDO O ARQUIVO FINAL ---
print("Juntando os dados de nível do rio e de precipitação...")

# Junta os dois DataFrames diários (nível do rio e clima)
# O índice de ambos é a data, então a junção é direta.
df_final = df_rio_diario.join(df_clima_diario)

# Preenche os dias sem registro de chuva com 0. É uma suposição razoável.
df_final['Precipitacao_mm'].fillna(0, inplace=True)

# Remove qualquer linha que ainda possa ter dados faltantes (ex: um dia sem medição do rio)
df_final.dropna(inplace=True)

# Traz a data do índice para uma coluna chamada 'Data'
df_final.reset_index(inplace=True)
df_final.rename(columns={'Timestamp': 'Data'}, inplace=True) # <-- ALTERAÇÃO (nome da coluna de data)

# Salva o DataFrame consolidado em um novo arquivo CSV
caminho_saida = os.path.join(DIRETORIO_PROJETO, ARQUIVO_SAIDA)
df_final.to_csv(caminho_saida, index=False, decimal=',', sep=';')

print("-" * 50)
print("PROCESSO CONCLUÍDO!")
print(f"Arquivo consolidado foi salvo em: {caminho_saida}")
print("\nVisualização das 5 primeiras linhas do arquivo final:")
print(df_final.head())
print("\nVisualização das 5 últimas linhas do arquivo final:")
print(df_final.tail())

