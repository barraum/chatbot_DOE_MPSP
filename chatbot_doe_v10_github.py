import streamlit as st
import requests
import json
from datetime import datetime, date
from bs4 import BeautifulSoup
import re
import os
import time
import unicodedata # Para normalize_and_clean_text_for_fpdf, se usada
import google.generativeai as genai # Mova a importação para cá


# --- Configuração da API do Google Gemini (Executa apenas uma vez por sessão) ---
if 'api_key_setup_attempted' not in st.session_state:
    st.session_state.api_key_setup_attempted = True
    st.session_state.gemini_ready = False 
    print("INFO: Tentando configurar a API Key do Google Gemini...")

    gemini_api_key_to_use = None
    try:
        # 1. Tenta Streamlit Secrets (para deploy no Cloud)
        gemini_api_key_to_use = st.secrets.get("GOOGLE_API_KEY") # Use .get() para evitar KeyError se não existir
        if gemini_api_key_to_use:
            print("INFO: GOOGLE_API_KEY encontrada nos Streamlit Secrets.")
    except Exception: 
        print("INFO: Streamlit Secrets não disponíveis ou GOOGLE_API_KEY não encontrada neles (normal ao rodar localmente sem configurar secrets locais).")
        pass 

    if not gemini_api_key_to_use:
        # 2. Tenta Variável de Ambiente (bom para local e alguns deploys)
        gemini_api_key_to_use = os.getenv('GOOGLE_API_KEY')
        if gemini_api_key_to_use:
            print("INFO: GOOGLE_API_KEY encontrada na variável de ambiente.")
    
    # Removido o fallback para chave hardcoded aqui para segurança no deploy.
    # Para desenvolvimento local, use variáveis de ambiente ou configure st.secrets localmente.
    # Se você PRECISAR de um fallback hardcoded para teste local extremo, adicione-o aqui com MUITO CUIDADO:
    # if not gemini_api_key_to_use:
    #     gemini_api_key_to_use = "SUA_CHAVE_LOCAL_DE_TESTE_SOMENTE" # NUNCA ENVIE PARA O GITHUB
    #     if gemini_api_key_to_use and gemini_api_key_to_use != "SUA_CHAVE_LOCAL_DE_TESTE_SOMENTE":
    #         print("INFO: Usando API Key hardcoded local.")
    #     else:
    #         gemini_api_key_to_use = None


    if gemini_api_key_to_use:
        try:
            genai.configure(api_key=gemini_api_key_to_use)
            print("INFO: API Key do Google Gemini configurada e pronta para uso.")
            st.session_state.gemini_ready = True
        except Exception as e_configure:
            print(f"ERRO: Falha ao configurar genai com a API Key: {e_configure}")
            st.session_state.gemini_ready = False
    else:
        print("AVISO: Nenhuma API Key válida do Gemini encontrada. Análise com Gemini desabilitada.")
        st.session_state.gemini_ready = False

# --- CAMINHOS CONFIGURÁVEIS PELO USUÁRIO ---
PATH_JSON_FILES = "DOE_JSONs_Cloud" 
PATH_HTML_RESOLUTIONS = "DOE_Resolutions_HTML_Cloud"

# --- Constantes para a API do DOE ---
BASE_URL_API_DOE = "https://do-api-web-search.doe.sp.gov.br/v2"
JOURNAL_ID_EXECUTIVO_I = "ca96256b-6ca1-407f-866e-567ef9430123"
SECTION_ID_ATOS_NORMATIVOS = "257b103f-1eb2-4f24-a170-4e553c7e4aac"
ID_MINISTERIO_PUBLICO_SECOND_LEVEL = "d6f11cbc-adff-46cd-7d5e-08db6b94d2bf"
URL_SUMMARY_LIST_PUBLICATIONS = f"{BASE_URL_API_DOE}/summary/list"
URL_PUBLICATION_CONTENT_BASE = f"{BASE_URL_API_DOE}/publications"
ID_TIPO_RESOLUCAO = "a452e8e9-a073-4ed2-99c9-df55add8cdec"

# --- Funções Auxiliares ---
def get_doe_headers():
    return {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Origin": "https://www.doe.sp.gov.br",
        "Referer": "https://www.doe.sp.gov.br/"
    }

def clean_text_content(html_content):
    if not html_content: return None
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    # Remove múltiplas linhas em branco, deixando no máximo uma
    text = re.sub(r'\n\s*\n', '\n\n', text) 
    return text.strip()

def get_publication_content_and_html(slug):
    if not slug: return (None, None, "Slug não fornecido.")
    url = f"{URL_PUBLICATION_CONTENT_BASE}/{slug}"
    try:
        response = requests.get(url, headers=get_doe_headers(), timeout=25)
        response.raise_for_status()
        data = response.json()
        raw_html = data.get("content")
        if not raw_html: return (None, None, "Conteúdo HTML (raw) não encontrado na API.")
        cleaned_text = clean_text_content(raw_html)
        if not cleaned_text: return ("Falha ao limpar o texto do HTML.", raw_html, None)
        return cleaned_text, raw_html, None
    except requests.exceptions.HTTPError as e: return (None, None, f"Erro HTTP {e.response.status_code}")
    except requests.exceptions.RequestException as e: return (None, None, f"Erro na requisição: {e}")
    except json.JSONDecodeError: return (None, None, "Erro ao processar JSON.")
    except Exception as e: return (None, None, f"Erro inesperado: {e}")

def fetch_mp_publications_and_prepare_content(date_str_yyyy_mm_dd):
    all_mp_data = []
    params = {"Date": date_str_yyyy_mm_dd, "JournalId": JOURNAL_ID_EXECUTIVO_I, 
              "SectionId": SECTION_ID_ATOS_NORMATIVOS, "name": "publications"}
    print(f"\nBuscando lista de publicações: Data {date_str_yyyy_mm_dd}")
    try:
        response = requests.get(URL_SUMMARY_LIST_PUBLICATIONS, headers=get_doe_headers(), params=params, timeout=40)
        response.raise_for_status()
        summary_data = response.json()
        pubs_list = summary_data.get("publications", [])
        print(f"  API retornou {len(pubs_list)} publicações para a seção.")

        for pub_summary in pubs_list:
            if pub_summary.get("secondLevelSectionId") == ID_MINISTERIO_PUBLICO_SECOND_LEVEL:
                print(f"  Processando MP: '{pub_summary.get('title')[:40]}...'")
                cleaned_text, raw_html, error_msg = get_publication_content_and_html(pub_summary["slug"])
                
                all_mp_data.append({
                    "id": pub_summary.get("id"), "title": pub_summary.get("title"),
                    "slug": pub_summary.get("slug"), "publicationDate": pub_summary.get("date"),
                    "publicationTypeId": pub_summary.get("publicationTypeId"),
                    "fullContent": cleaned_text if not error_msg else f"Erro: {error_msg}",
                    "rawHtmlContent": raw_html if not error_msg else None
                })
                time.sleep(0.2) # Delay para não sobrecarregar API de conteúdo
        print(f"  {len(all_mp_data)} publicações do MP processadas.")
    except Exception as e:
        print(f"  Erro em fetch_mp_publications: {type(e).__name__} - {e}")
    return all_mp_data

def save_to_json(data, filename_full_path):
    try:
        pasta_json = os.path.dirname(filename_full_path)
        if pasta_json and not os.path.exists(pasta_json): os.makedirs(pasta_json)
        with open(filename_full_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Dados JSON salvos/atualizados em: {filename_full_path}")
    except Exception as e: print(f"Erro ao salvar JSON: {e}")

def load_publications_from_json(filename_full_path):
    try:
        with open(filename_full_path, 'r', encoding='utf-8') as f: data = json.load(f)
        print(f"Dados carregados do JSON: {filename_full_path}")
        return data
    except FileNotFoundError: return []
    except json.JSONDecodeError: print(f"Erro ao decodificar JSON: {filename_full_path}"); return []


def sanitize_filename_for_html(title, publication_id):
    # ... (código da função como antes) ...
    numero_resolucao_formatado = None
    match = re.search(r"RESOLUÇÃO\s*(?:Nº|N\.|PGJ)?\s*([\d\.\s]+/\d{4})", title, re.IGNORECASE)
    if match:
        numero_bruto = match.group(1)
        numero_resolucao_formatado = re.sub(r'[\.\s]', '', numero_bruto).replace("/", "-")
    if numero_resolucao_formatado:
        filename = f"Resolucao_MP_{numero_resolucao_formatado}.html"
    else:
        safe_title_part = re.sub(r'[^\w\s\-\.]', '_', title)
        safe_title_part = re.sub(r'[_ ]+', '_', safe_title_part)[:80]
        filename = f"{safe_title_part}_{publication_id[:8]}.html"
    return filename

def save_resolutions_as_html_files(publications_mp_list, html_base_path):
    # ... (código da função como na sua última versão funcional,
    #      que busca rawHtmlContent se não estiver em pub_data e salva) ...
    if not publications_mp_list: # ... (código como antes)
        print("Nenhuma publicação do MP fornecida para salvar como HTML.")
        return "Nenhuma publicação fornecida."
    if not os.path.exists(html_base_path):
        try:
            os.makedirs(html_base_path)
            print(f"Pasta para HTMLs de Resoluções criada: {html_base_path}")
        except OSError as e:
            print(f"Erro ao criar pasta {html_base_path}: {e}. HTMLs serão salvos na pasta atual.")
            html_base_path = "."
    resolutions_saved_count = 0
    for pub_data in publications_mp_list:
        if pub_data.get("publicationTypeId") == ID_TIPO_RESOLUCAO:
            print(f"\nEncontrada Resolução para salvar como HTML: '{pub_data['title']}'")
            raw_html_to_save = pub_data.get("rawHtmlContent")
            if not raw_html_to_save or "Erro" in (raw_html_to_save or ""):
                print("    HTML bruto não encontrado no cache ou com erro, buscando da API...")
                _, raw_html_to_save, error_msg_html = get_publication_content_and_html(pub_data["slug"])
                if error_msg_html or not raw_html_to_save:
                    st.warning(f"  HTML não obtido para '{pub_data['title']}': {error_msg_html}") # Use st.warning
                    continue
                pub_data["rawHtmlContent"] = raw_html_to_save # Atualiza para cache futuro

            html_filename = sanitize_filename_for_html(pub_data['title'], pub_data['id'])
            full_html_path = os.path.join(html_base_path, html_filename)
            try:
                with open(full_html_path, "w", encoding="utf-8") as f_html:
                    f_html.write(raw_html_to_save)
                print(f"  Resolução salva como HTML: {full_html_path}")
                resolutions_saved_count += 1
            except Exception as e:
                st.error(f"  Erro CRÍTICO ao salvar HTML para '{pub_data['title']}': {type(e).__name__} - {e}") # Use st.error
            time.sleep(0.2) # Pequeno delay
    if resolutions_saved_count == 0:
        return "Nenhuma 'Resolução' do MP encontrada ou salva como HTML."
    else:
        return f"{resolutions_saved_count} resolução(ões) do MP salvas como HTML em '{html_base_path}'."


# --- Funções do Gemini ---
def analyze_text_with_gemini_open_question(publication_text, user_open_question):
    if not st.session_state.get('gemini_ready', False) or not genai: # Checa a flag da sessão
        st.warning("API do Gemini não está configurada. Análise não pode ser realizada.")
        return "API Gemini não está configurada."
    print("\n--- Enviando para análise do Gemini (pergunta aberta) ---")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest') 
        prompt_to_gemini = f"""Analise o seguinte texto de uma publicação do Diário Oficial:
TEXTO DA PUBLICAÇÃO:
'''
{publication_text}
'''
PERGUNTA DO USUÁRIO: {user_open_question}
RESPOSTA:"""
        response = model.generate_content(prompt_to_gemini)
        if response.parts: return response.text.strip()
        else:
            block_reason = "N/A"; block_message = "N/A"
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                 block_reason = response.prompt_feedback.block_reason or "Não especificado"
                 block_message = response.prompt_feedback.block_reason_message or "Sem mensagem adicional"
            return f"BLOCK_OPEN_QUESTION: {block_reason} - {block_message}"
    except Exception as e: return f"ERROR_API_OPEN_QUESTION: {type(e).__name__} - {e}"

DEFAULT_SEARCH_TERMS_CONFIG = [
    {"label": "Eduardo Tostes (e variações)", "terms": ["Dr. Eduardo Tostes", "Eduardo Tostes"]},
    {"label": "Bruno Henrique Rigoni Barros", "terms": ["Bruno Henrique Rigoni Barros"]},
    {"label": "Promotoria de Justiça de Franca", "terms": ["Promotoria de Justiça de Franca", "PJ de Franca", "Comarca de Franca"]} # Adicione variações
]
# Modificar search_publications_for_names_local_and_consolidate para aceitar uma lista de termos
def search_publications_for_terms_local(publications_mp_list, search_terms_list, json_filename_to_update):
    print(f"\nIniciando pesquisa local por termos: {search_terms_list}...")
    found_publications_details = []
    content_was_fetched_in_this_run = False # Para saber se precisa salvar o JSON

    for i, pub_data in enumerate(publications_mp_list):
        current_full_content = pub_data.get("fullContent")
        if not current_full_content or "Erro" in current_full_content or "Conteúdo não" in current_full_content:
            # Lógica para buscar fullContent se necessário (como na versão anterior)
            print(f"    Buscando/Atualizando conteúdo para '{pub_data['title'][:50]}...'")
            cleaned_text, _, error_msg_content = get_publication_content_and_html(pub_data["slug"])
            if error_msg_content: pub_data["fullContent"] = f"Erro: {error_msg_content}"
            else: pub_data["fullContent"] = cleaned_text if cleaned_text else "Conteúdo não extraído."
            current_full_content = pub_data["fullContent"]
            content_was_fetched_in_this_run = True
        
        if "Erro" in current_full_content or "Conteúdo não" in current_full_content or not current_full_content:
            continue

        found_term_in_pub = False
        for term_to_find in search_terms_list:
            if term_to_find.lower() in current_full_content.lower():
                found_term_in_pub = True
                break 
        
        if found_term_in_pub:
            print(f"  ENCONTRADO! '{pub_data['title']}' menciona um dos termos.")
            found_publications_details.append({
                "title": pub_data['title'],
                "fullContent": current_full_content 
            })
    
    if content_was_fetched_in_this_run and publications_mp_list:
        save_to_json(publications_mp_list, json_filename_to_update)

    if not found_publications_details:
        return f"Nenhuma publicação encontrada mencionando os termos: {', '.join(search_terms_list)} (busca local)."

    response_parts = [f"--- Publicações Encontradas Mencionando os Termos: {', '.join(search_terms_list)} (Busca Local) ---"]
    # ... (formatação do resultado como antes) ...
    for pub_info in found_publications_details:
        response_parts.append(f"\nTÍTULO: {pub_info['title']}")
        response_parts.append("CONTEÚDO COMPLETO:")
        response_parts.append(pub_info['fullContent'])
        response_parts.append("-" * 50 + "\n")
    return "\n".join(response_parts)

# --- Lógica Principal da Aplicação Streamlit ---
# @st.cache_data # Cache em load_or_fetch_data_for_date foi removido para refletir mudanças no fullContent imediatamente
def load_or_fetch_data_for_date(target_date_str, json_file_path): # Passar o caminho do JSON
    publications = load_publications_from_json(json_file_path)
    if not publications:
        with st.spinner(f"Buscando dados do DOE para {target_date_str}... (Pode levar alguns minutos)"):
            publications = fetch_mp_publications_and_prepare_content(target_date_str)
            if publications:
                save_to_json(publications, json_file_path) # Salva o JSON com fullContent e rawHtmlContent
    return publications

# Inicializa o estado da sessão
if 'publications_mp' not in st.session_state: st.session_state.publications_mp = []
if 'selected_date' not in st.session_state: st.session_state.selected_date = date.today()
if 'current_action' not in st.session_state: st.session_state.current_action = "Selecione..."
if 'action_result_message' not in st.session_state: st.session_state.action_result_message = None
# Para a Opção 1:
if 'selected_pub_index_for_gemini_str' not in st.session_state: st.session_state.selected_pub_index_for_gemini_str = ""
if 'user_question_gemini' not in st.session_state: st.session_state.user_question_gemini = ""
# Para a Opção "Exibir Detalhes":
if 'selected_pub_index_for_details_str' not in st.session_state: st.session_state.selected_pub_index_for_details_str = ""


def streamlit_app():
    st.set_page_config(page_title="Chatbot DOE - MP", layout="wide")
    st.title("🔎 Chatbot do Diário Oficial - MPSP ⚖️")

    # --- SELEÇÃO DE DATA ---
    st.sidebar.header("Seleção de Data")
    
    # O widget de data atualiza st.session_state.selected_date diretamente se usarmos um callback
    def date_input_on_change():
        # Se a data realmente mudou, limpa as publicações e a ação
        if st.session_state.date_picker_key != st.session_state.selected_date:
            st.session_state.selected_date = st.session_state.date_picker_key
            st.session_state.publications_mp = [] 
            st.session_state.current_action = "Selecione..." 
            st.session_state.action_result_message = None
            # Não precisa de rerun aqui, a mudança do widget já causa um.
        
        if 'last_name_search_result' not in st.session_state:
            st.session_state.last_name_search_result = None

    st.sidebar.date_input(
        "Escolha a data para análise:", 
        value=st.session_state.selected_date,
        min_value=date(2020, 1, 1),
        max_value=date.today(),
        key='date_picker_key', # Chave para o widget
        on_change=date_input_on_change
    )
    target_date_str = st.session_state.selected_date.strftime("%Y-%m-%d")
    json_filename_base = f"DOE_MP_{target_date_str.replace('-', '')}.json"
    json_filename_full_path = os.path.join(PATH_JSON_FILES or ".", json_filename_base)


    if st.sidebar.button(f"Carregar Publicações de {target_date_str}", key="load_data_button"):
        st.session_state.publications_mp = load_or_fetch_data_for_date(target_date_str, json_filename_full_path)
        st.session_state.current_action = "Selecione..." 
        st.session_state.action_result_message = None 
        if not st.session_state.publications_mp:
            st.sidebar.warning(f"Nenhuma publicação do MP para {target_date_str}.")
        # st.rerun() # Geralmente não é necessário aqui, a mudança no estado já causa re-render

    if st.sidebar.button("Limpar Cache da Data Atual", key="clear_cache_button"): # Nome do botão mais claro
        if os.path.exists(json_filename_full_path):
            try:
                os.remove(json_filename_full_path)
                st.sidebar.success(f"Cache JSON para {target_date_str} removido.")
            except Exception as e: st.sidebar.error(f"Erro ao remover cache: {e}")
        else: st.sidebar.info(f"Nenhum cache JSON para {target_date_str}.")
        st.session_state.publications_mp = [] # Limpa da sessão também
        st.session_state.current_action = "Selecione..."
        st.session_state.action_result_message = None
        st.rerun()

    # --- EXIBIÇÃO DAS PUBLICAÇÕES E OPÇÕES ---
    if st.session_state.publications_mp:
        st.header(f"Publicações do MP para {target_date_str} ({len(st.session_state.publications_mp)} encontradas)")
        col1, col2 = st.columns(spec=[0.4, 0.6])
        with col1:
            st.subheader("Lista de Títulos:")
            for i, pub in enumerate(st.session_state.publications_mp):
                st.markdown(f"`{i+1}. {pub['title']}`")
        with col2:
            st.subheader("Ações:")
            
            action_options = [
                "Selecione...", 
                "Analisar publicação específica (Gemini)", 
                "Pesquisar por nomes (Busca Local)",
                "Salvar Resoluções como HTML",
                "Exibir Detalhes da Publicação"
            ]
            
            # def on_main_action_change(): # Renomeado para clareza
            #     # Esta função é chamada quando o selectbox PRINCIPAL de ações muda.
            #     # Atualiza a ação corrente no estado da sessão.
            #     # Limpa qualquer mensagem de resultado de ação anterior.
            #     st.session_state.current_action = st.session_state.action_selectbox_main_key # Pega o valor do widget
            #     st.session_state.action_result_message = None
            #     # Também reseta seleções de sub-opções para evitar persistência indesejada
            #     st.session_state.selected_pub_index_for_gemini_str = ""
            #     st.session_state.user_question_gemini = ""
            #     st.session_state.selected_pub_index_for_details_str = ""

            def on_main_action_change():
                st.session_state.current_action = st.session_state.action_selectbox_main_key
                st.session_state.action_result_message = None
                st.session_state.selected_pub_index_for_gemini_str = ""
                st.session_state.user_question_gemini = ""
                st.session_state.selected_pub_index_for_details_str = ""
                st.session_state.last_name_search_result = None # <--- ADICIONAR ESTA LINHA


            st.selectbox(
                "Escolha uma ação:",
                action_options,
                key='action_selectbox_main_key', # Chave do widget
                index=action_options.index(st.session_state.current_action),
                on_change=on_main_action_change 
            )

            # Exibe a mensagem de resultado da última ação completada, se houver.
            # Esta mensagem será definida pelas próprias lógicas de ação abaixo.
            if st.session_state.action_result_message:
                # Determine o tipo de mensagem (success, info, warning, error)
                if "concluída" in st.session_state.action_result_message.lower() or \
                   "salva" in st.session_state.action_result_message.lower() or \
                   "exibido" in st.session_state.action_result_message.lower() : # Ajustar conforme suas mensagens
                    st.success(st.session_state.action_result_message)
                elif "Nenhuma" in st.session_state.action_result_message or "AVISO" in st.session_state.action_result_message.upper():
                    st.info(st.session_state.action_result_message)
                else: # Para outros tipos de mensagens ou erros
                    st.warning(st.session_state.action_result_message)
                # NÃO limpe action_result_message aqui. O on_change do selectbox principal fará isso.

            # Lógica para cada ação
            elif st.session_state.current_action == "Analisar publicação específica (Gemini)":
                if st.session_state.get('gemini_ready', False) and genai: 
                    pub_numbers_gemini = [str(i+1) for i in range(len(st.session_state.publications_mp))]
                    
                    # Callback para quando o selectbox de publicação para Gemini muda
                    def on_gemini_pub_select_change():
                        st.session_state.selected_pub_index_for_gemini_str = st.session_state.gemini_pub_selector_key # Atualiza o estado
                        st.session_state.user_question_gemini = "" # Limpa a pergunta anterior ao mudar de publicação
                        st.session_state.action_result_message = None # Limpa mensagens de resultado de outras ações

                    selected_pub_index_str_from_widget_gemini = st.selectbox(
                        "Selecione o Nº da publicação para análise Gemini:", 
                        options=[""] + pub_numbers_gemini, 
                        key="gemini_pub_selector_key", # Chave para o widget
                        index=([""] + pub_numbers_gemini).index(st.session_state.selected_pub_index_for_gemini_str) if st.session_state.selected_pub_index_for_gemini_str in ([""] + pub_numbers_gemini) else 0,
                        on_change=on_gemini_pub_select_change
                    )

                    # Se a seleção no widget é diferente do que está no estado (após o on_change ter rodado)
                    # Isso pode não ser mais necessário se o on_change já atualiza e o Streamlit re-renderiza.
                    # Mas para garantir a limpeza da pergunta e da mensagem, o rerun pode ser útil.
                    if selected_pub_index_str_from_widget_gemini != st.session_state.selected_pub_index_for_gemini_str:
                        # O on_change já deve ter atualizado selected_pub_index_for_gemini_str
                        # e limpado a user_question_gemini e action_result_message.
                        # Um rerun aqui força a atualização da UI com a pergunta limpa.
                        st.rerun()


                    if st.session_state.selected_pub_index_for_gemini_str: # Procede se uma publicação foi selecionada
                        pub_idx_gemini = int(st.session_state.selected_pub_index_for_gemini_str) - 1
                        selected_pub_data_gemini = st.session_state.publications_mp[pub_idx_gemini]
                        
                        st.markdown(f"**Analisando:** `{selected_pub_data_gemini['title']}`")
                        
                        # O text_area agora usa o valor do session_state
                        st.session_state.user_question_gemini = st.text_area(
                            "Sua pergunta para o Gemini:", 
                            value=st.session_state.user_question_gemini, # Usa o valor do estado
                            height=100, 
                            key=f"gemini_q_ta_{pub_idx_gemini}" 
                        )

                        if st.button("Analisar com Gemini", key=f"gemini_btn_analyze_{pub_idx_gemini}"):
                            if st.session_state.user_question_gemini: # Usa a pergunta do estado
                                content_to_analyze = selected_pub_data_gemini.get("fullContent")
                                # ... (lógica para buscar fullContent se não existir, como antes) ...
                                if not content_to_analyze or "Erro" in content_to_analyze or "Conteúdo não" in content_to_analyze:
                                    st.warning("Conteúdo completo desta publicação não está disponível.")
                                else:
                                    with st.spinner("Gemini está pensando..."):
                                        result = analyze_text_with_gemini_open_question(content_to_analyze, st.session_state.user_question_gemini)
                                    st.subheader("Resposta do Gemini:")
                                    st.markdown(result)
                                    st.session_state.action_result_message = f"Análise da pub {st.session_state.selected_pub_index_for_gemini_str} concluída."
                            else:
                                st.warning("Por favor, digite sua pergunta para o Gemini.")
                            
                            # Após a ação, resetar tudo para um estado limpo
                            # st.session_state.current_action = "Selecione..."
                            # st.session_state.selected_pub_index_for_gemini_str = "" 
                            # st.session_state.user_question_gemini = "" 
                            # st.rerun() 
                else:
                    st.warning("API do Gemini não configurada ou inicialização falhou.")


            elif st.session_state.current_action == "Pesquisar por nomes (Busca Local)": # Renomear para "Pesquisa Local Avançada"
                st.subheader("Pesquisa Local Avançada")

                search_options = {
                    "Eduardo Tostes": ["Dr. Eduardo Tostes", "Eduardo Tostes"],
                    "Bruno H. R. Barros": ["Bruno Henrique Rigoni Barros"],
                    "Promotoria de Franca": ["Promotoria de Justiça de Franca", "PJ de Franca", "Comarca de Franca"],
                    "Outro termo...": [] # Placeholder para entrada customizada
                }
                
                # Usar um estado para a seleção do tipo de pesquisa
                if 'search_type_local' not in st.session_state:
                    st.session_state.search_type_local = list(search_options.keys())[0] # Padrão para o primeiro

                st.session_state.search_type_local = st.radio(
                    "O que você gostaria de pesquisar localmente?",
                    options=list(search_options.keys()),
                    key="local_search_type_radio"
                )

                terms_to_search_this_time = []
                if st.session_state.search_type_local == "Outro termo...":
                    custom_term = st.text_input("Digite o termo para pesquisar:", key="custom_search_term_local")
                    if custom_term: # Só adiciona se o usuário digitou algo
                        terms_to_search_this_time = [custom_term]
                else:
                    terms_to_search_this_time = search_options[st.session_state.search_type_local]

                if st.button("Iniciar Pesquisa Local", key="start_local_search_btn"):
                    if terms_to_search_this_time:
                        json_filename_base_for_search = f"DOE_MP_{target_date_str.replace('-', '')}.json"
                        json_filename_full_path_for_search = os.path.join(PATH_JSON_FILES or ".", json_filename_base_for_search)
                        
                        with st.spinner("Realizando busca local..."):
                            search_result_string = search_publications_for_terms_local(
                                st.session_state.publications_mp, 
                                terms_to_search_this_time,
                                json_filename_full_path_for_search
                            )
                        # Armazena no estado para exibição após o rerun
                        st.session_state.last_name_search_result = search_result_string 
                        st.session_state.action_result_message = "Busca local concluída." 
                    else:
                        st.session_state.last_name_search_result = "Nenhum termo de pesquisa fornecido."
                        st.session_state.action_result_message = "Por favor, forneça um termo de pesquisa."
                    
                    # Não reseta current_action aqui para manter o submenu visível
                    # st.session_state.current_action = "Selecione..."
                    st.rerun() # Para exibir o last_name_search_result e a action_result_message

            # Exibição do resultado da busca local (fora do elif, mas dentro da col2)
            if st.session_state.current_action == "Pesquisar por nomes (Busca Local)" and st.session_state.get('last_name_search_result'):
                st.subheader("Resultado da Pesquisa Local:")
                st.text(st.session_state.last_name_search_result)
                # Botão para limpar resultados da busca e permitir nova busca dentro da mesma opção
                if st.button("Limpar Resultado da Busca", key="clear_search_res_btn"):
                    st.session_state.last_name_search_result = None
                    st.session_state.action_result_message = None # Também limpa a mensagem de status
                    # Não precisa resetar current_action, usuário ainda está nesta opção
                    st.rerun()

            elif st.session_state.current_action == "Salvar Resoluções como HTML":
                with st.spinner("Salvando resoluções como HTML..."):
                    status_msg = save_resolutions_as_html_files(st.session_state.publications_mp, PATH_HTML_RESOLUTIONS)
                if "Nenhuma" in status_msg: st.info(status_msg)
                else: st.success(status_msg)
                st.session_state.action_result_message = status_msg
                st.session_state.current_action = "Selecione..."
                st.rerun()

            elif st.session_state.current_action == "Exibir Detalhes da Publicação":
                if st.session_state.publications_mp:
                    pub_numbers_details = [str(i+1) for i in range(len(st.session_state.publications_mp))]
                    
                    # Guardar o valor atual do seletor de detalhes para comparar
                    previous_detail_selection = st.session_state.get('selected_pub_index_for_details_str', "")

                    selected_pub_idx_str_details = st.selectbox(
                        "Selecione o Nº da publicação para ver os detalhes:", 
                        options=[""] + pub_numbers_details,
                        key="details_pub_selector_key", # Chave única
                        index=([""] + pub_numbers_details).index(st.session_state.selected_pub_index_for_details_str) if st.session_state.selected_pub_index_for_details_str in ([""] + pub_numbers_details) else 0
                    )

                    # Se a seleção no selectbox de detalhes mudou
                    if selected_pub_idx_str_details != st.session_state.selected_pub_index_for_details_str:
                        st.session_state.selected_pub_index_for_details_str = selected_pub_idx_str_details
                        st.session_state.action_result_message = None # LIMPA A MENSAGEM DE RESULTADO ANTERIOR
                        st.rerun() # Re-renderiza para mostrar os detalhes da nova seleção

                    # Se uma publicação está selecionada (e não é a string vazia)
                    if st.session_state.selected_pub_index_for_details_str:
                        pub_index = int(st.session_state.selected_pub_index_for_details_str) - 1
                        selected_pub_data = st.session_state.publications_mp[pub_index]
                        
                        # Busca/Verifica fullContent (COPIE A LÓGICA DE BUSCA DE CONTEÚDO DA OPÇÃO 1 SE NECESSÁRIO AQUI)
                        current_fc = selected_pub_data.get("fullContent")
                        if not current_fc or "Erro" in (current_fc or "") or "Conteúdo não" in (current_fc or ""):
                            with st.spinner("Carregando conteúdo..."):
                                cleaned_text, _, error_msg_fc = get_publication_content_and_html(selected_pub_data["slug"])
                                if error_msg_fc:
                                    st.session_state.publications_mp[pub_index]["fullContent"] = f"Erro: {error_msg_fc}"
                                else:
                                    st.session_state.publications_mp[pub_index]["fullContent"] = cleaned_text if cleaned_text else "Conteúdo não extraído."
                                
                                # Salva o JSON principal se o conteúdo foi buscado/atualizado
                                json_filename_base_for_update = f"DOE_MP_{target_date_str.replace('-', '')}.json"
                                json_filename_full_path_for_update = os.path.join(PATH_JSON_FILES or ".", json_filename_base_for_update)
                                save_to_json(st.session_state.publications_mp, json_filename_full_path_for_update)
                                selected_pub_data = st.session_state.publications_mp[pub_index] # Pega os dados atualizados
                                current_fc = selected_pub_data.get("fullContent") # Atualiza current_fc

                        st.markdown(f"#### Detalhes da Publicação") # Título geral
                        st.markdown(f"**Título:** {selected_pub_data.get('title', 'N/A')}")
                        st.markdown(f"**ID:** `{selected_pub_data.get('id', 'N/A')}`")
                        st.markdown(f"**Data da Publicação (API):** `{selected_pub_data.get('publicationDate', 'N/A')}`")
                        st.markdown(f"**Hierarquia:** `{selected_pub_data.get('hierarchy', 'N/A')}`")
                        
                        st.subheader("Conteúdo:")
                        if "Erro" in current_fc or "Conteúdo não" in current_fc or not current_fc.strip():
                            st.warning(current_fc if current_fc.strip() else "Conteúdo não disponível ou vazio.")
                        else:
                            markdown_friendly_content = current_fc.replace('\n\n', '<br><br>').replace('\n', '  \n')
                            with st.expander("Ver Conteúdo Completo da Publicação", expanded=True):
                                st.markdown(markdown_friendly_content, unsafe_allow_html=True)
                        
                        json_string_to_download = json.dumps(selected_pub_data, indent=4, ensure_ascii=False)
                        st.download_button(
                            label="Baixar Dados JSON Completos desta Publicação",
                            data=json_string_to_download,
                            file_name=f"pub_detalhes_{selected_pub_data.get('id', 'desconhecido')}.json",
                            mime="application/json",
                            key=f"download_json_details_{selected_pub_data.get('id')}"
                        )
                        # NÃO definimos action_result_message aqui para "Detalhes exibidos",
                        # pois isso causaria a mensagem persistente.
                        # A mensagem de resultado é mais para ações que "concluem" algo.
                else:
                    st.info("Carregue as publicações primeiro.")

    elif not st.session_state.publications_mp and st.session_state.selected_date:
        st.info(f"Nenhuma publicação do MP carregada para {st.session_state.selected_date.strftime('%Y-%m-%d')}. Clique em 'Carregar Publicações'.")

if __name__ == '__main__':

    # Garante que as pastas existem ao iniciar a app
    for path_to_create in [PATH_JSON_FILES, PATH_HTML_RESOLUTIONS]:
        if path_to_create and not os.path.exists(path_to_create):
            try: 
                os.makedirs(path_to_create)
                print(f"INFO: Pasta '{path_to_create}' criada ou já existente.")
            except OSError as e: 
                print(f"AVISO: Não foi possível criar a pasta '{path_to_create}': {e}")
    
    if not st.session_state.get('gemini_ready', False): # Checa a flag da sessão
        # Este aviso pode ser mostrado na sidebar dentro da streamlit_app se preferir
        print("\nAVISO NO CONSOLE: API Key/Lib Gemini não configurada. Análise com Gemini desabilitada.")
       
    streamlit_app()