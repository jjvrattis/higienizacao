import streamlit as st
import pandas as pd
import re
import base64
import os
import datetime
from io import StringIO

st.set_page_config(page_title="Processador de Planilhas CAEDU", page_icon="📊", layout="wide")

# Funções de processamento
def limpa_cpf_google_sheets(cpf):
    """
    Replica exatamente a fórmula do Google Sheets:
    =ARRAYFORMULA(IF(C2:C="";;RIGHT("00000000000"&REGEXREPLACE(TO_TEXT(C2:C);"[^\d]";"");11)))
    """
    # Se vazio, retorna vazio (IF(C2:C="";;...))
    if pd.isna(cpf) or cpf == '':
        return ''
    
    # Converte para texto (TO_TEXT(C2:C))
    cpf_str = str(cpf)
    
    # Remove tudo que não é dígito (REGEXREPLACE(TO_TEXT(C2:C);"[^\d]";""))
    cpf_apenas_digitos = re.sub(r'[^\d]', '', cpf_str)
    
    # Adiciona 11 zeros à esquerda e pega os últimos 11 (RIGHT("00000000000"&...;11))
    cpf_formatado = ("00000000000" + cpf_apenas_digitos)[-11:]
    
    return cpf_formatado

def separar_telefones_multiplos(telefone_str):
    """
    Separa múltiplos telefones em uma string
    """
    if pd.isna(telefone_str) or telefone_str == '':
        return []
    
    telefone_str = str(telefone_str)
    
    # Padrões para separar telefones
    separadores = [r'\s*[;,/]\s*', r'\s*-\s*(?=\d)', r'\s+(?=\d{2}\s*\d{4,5}[-\s]?\d{4})']
    
    telefones = [telefone_str]
    for separador in separadores:
        novos_telefones = []
        for tel in telefones:
            novos_telefones.extend(re.split(separador, tel))
        telefones = novos_telefones
    
    # Limpar e filtrar telefones válidos
    telefones_limpos = []
    for tel in telefones:
        tel_limpo = re.sub(r'[^\d]', '', tel.strip())
        if len(tel_limpo) >= 8:  # Mínimo 8 dígitos
            telefones_limpos.append(tel_limpo)
    
    return telefones_limpos

def limpa_nome(nome, apenas_primeiro_nome=True):
    """
    Limpa o nome e opcionalmente extrai apenas o primeiro nome
    """
    if pd.isna(nome) or nome == '':
        return ''
    
    nome_str = str(nome).strip().upper()
    
    if apenas_primeiro_nome:
        return nome_str.split()[0] if nome_str else ''
    else:
        return nome_str

def processar_arquivo(df, config):
    """
    Processa o DataFrame com base nas configurações fornecidas
    """
    # Extrair configurações
    nome_col = config['nome_col']
    cpf_col = config['cpf_col']
    telefone_cols = config['telefone_cols']
    apenas_primeiro_nome = config['apenas_primeiro_nome']
    remover_sem_telefone = config['remover_sem_telefone']
    max_telefones = config['max_telefones']
    
    # Lista para armazenar os dados processados
    dados_processados = []
    
    # Contador para acompanhar o progresso
    total_registros = len(df)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for index, row in df.iterrows():
        # Atualizar progresso
        if index % 100 == 0:
            progress = int((index / total_registros) * 100)
            progress_bar.progress(progress)
            status_text.text(f"Processando registro {index + 1}/{total_registros}")
        
        # Extrair dados
        nome_original = row.iloc[nome_col] if nome_col < len(row) else ''
        cpf_original = row.iloc[cpf_col] if cpf_col < len(row) else ''
        
        # Processar nome
        nome_limpo = limpa_nome(nome_original, apenas_primeiro_nome)
        
        # Processar CPF com a fórmula do Google Sheets
        cpf_formatado = limpa_cpf_google_sheets(cpf_original)
        
        # Processar telefones
        telefones_processados = []
        for tel_col in telefone_cols:
            if tel_col < len(row):
                telefone_original = row.iloc[tel_col]
                telefones_separados = separar_telefones_multiplos(telefone_original)
                telefones_processados.extend(telefones_separados)
        
        # Garantir máximo de telefones conforme configurado
        telefones_processados = telefones_processados[:max_telefones]
        
        # Preencher com strings vazias se necessário
        while len(telefones_processados) < max_telefones:
            telefones_processados.append('')
        
        # Adicionar à lista conforme configuração
        if not remover_sem_telefone or any(tel for tel in telefones_processados if tel):
            registro = {
                'Nome': nome_limpo,
                'CPF': cpf_formatado
            }
            
            # Adicionar telefones
            for i, tel in enumerate(telefones_processados):
                registro[f'DDD/Telefone {i+1}'] = tel
                
            dados_processados.append(registro)
    
    # Completar a barra de progresso
    progress_bar.progress(100)
    status_text.text("Processamento concluído!")
    
    # Criar DataFrame final
    df_final = pd.DataFrame(dados_processados)
    
    return df_final

def get_download_link(df, filename="dados_processados.csv"):
    """
    Gera um link para download do DataFrame como CSV
    """
    csv = df.to_csv(sep=';', index=False, encoding='utf-8')
    b64 = base64.b64encode(csv.encode('utf-8')).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Baixar arquivo CSV</a>'
    return href

# Interface do Streamlit
st.title("Processador de Planilhas CAEDU")
st.markdown("""
Esta aplicação permite processar planilhas CAEDU, formatando CPFs, nomes e telefones.
Arraste e solte seu arquivo CSV para começar.
""")

# Sidebar para configurações
st.sidebar.header("Configurações")

# Upload de arquivo
uploaded_file = st.file_uploader("Arraste e solte seu arquivo CSV aqui", type=['csv'])

if uploaded_file is not None:
    # Carregar o arquivo
    try:
        # Tentar diferentes encodings
        encodings = ['latin-1', 'utf-8', 'cp1252']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(uploaded_file, sep=';', encoding=encoding, low_memory=False)
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            st.error("Não foi possível ler o arquivo. Tente converter para CSV com codificação Latin-1 ou UTF-8.")
        else:
            st.success(f"Arquivo carregado com sucesso! {len(df)} registros encontrados.")
            
            # Mostrar primeiras linhas
            st.subheader("Visualização dos dados originais")
            st.dataframe(df.head(5))
            
            # Configurações de processamento
            st.sidebar.subheader("Índices das Colunas")
            st.sidebar.info("Os índices começam em 0. Verifique a visualização acima para identificar as colunas corretas.")
            
            # Configurar índices das colunas
            nome_col = st.sidebar.number_input("Índice da coluna de Nome", min_value=0, value=5)
            cpf_col = st.sidebar.number_input("Índice da coluna de CPF", min_value=0, value=4)
            
            # Configurar colunas de telefone
            st.sidebar.subheader("Colunas de Telefone")
            tel_col1 = st.sidebar.number_input("Índice da coluna de Telefone 1", min_value=0, value=43)
            tel_col2 = st.sidebar.number_input("Índice da coluna de Telefone 2", min_value=0, value=44)
            tel_col3 = st.sidebar.number_input("Índice da coluna de Telefone 3", min_value=0, value=45)
            tel_col4 = st.sidebar.number_input("Índice da coluna de Telefone 4", min_value=0, value=46)
            
            telefone_cols = [tel_col1, tel_col2, tel_col3, tel_col4]
            
            # Opções adicionais
            st.sidebar.subheader("Opções de Formatação")
            apenas_primeiro_nome = st.sidebar.checkbox("Extrair apenas o primeiro nome", value=True)
            remover_sem_telefone = st.sidebar.checkbox("Remover registros sem telefone", value=True)
            max_telefones = st.sidebar.slider("Número máximo de telefones por registro", min_value=1, max_value=10, value=4)
            
            # Botão para processar
            if st.button("Processar Dados"):
                # Configuração para processamento
                config = {
                    'nome_col': nome_col,
                    'cpf_col': cpf_col,
                    'telefone_cols': telefone_cols,
                    'apenas_primeiro_nome': apenas_primeiro_nome,
                    'remover_sem_telefone': remover_sem_telefone,
                    'max_telefones': max_telefones
                }
                
                # Processar dados
                with st.spinner("Processando dados..."):
                    df_processado = processar_arquivo(df, config)
                
                # Mostrar estatísticas
                st.subheader("Estatísticas do Processamento")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Registros Originais", len(df))
                
                with col2:
                    st.metric("Registros Processados", len(df_processado))
                
                with col3:
                    st.metric("Registros com Telefone", len(df_processado[df_processado['DDD/Telefone 1'] != '']))
                
                # Mostrar resultado
                st.subheader("Dados Processados")
                st.dataframe(df_processado.head(10))
                
                # Criar pasta de destino se não existir
                pasta_destino = r"C:\Users\Joaov\Downloads\Sinergy"
                if not os.path.exists(pasta_destino):
                    os.makedirs(pasta_destino)
                
                # Adicionar data e hora ao nome do arquivo
                data_hora_atual = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = f"Caedu_IBIUNA_formatado_{data_hora_atual}.csv"
                caminho_completo = os.path.join(pasta_destino, nome_arquivo)
                
                # Link para download
                st.markdown(get_download_link(df_processado, nome_arquivo), unsafe_allow_html=True)
                
                # Salvar arquivo localmente
                df_processado.to_csv(caminho_completo, sep=';', index=False, encoding='utf-8')
                st.success(f"Arquivo salvo como: {caminho_completo}")
    
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {str(e)}")

# Rodapé
st.markdown("---")
st.markdown("Desenvolvido para processamento de planilhas CAEDU")