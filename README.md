# Chatbot do Diário Oficial - Ministério Público de São Paulo (MPSP)

Este projeto é uma aplicação Streamlit desenvolvida para facilitar a busca e análise de publicações do Diário Oficial do Estado de São Paulo (DOE-SP), com foco específico nas seções do Ministério Público. A aplicação permite aos usuários selecionar uma data, visualizar as publicações do MP para aquele dia e interagir com um modelo de linguagem (Gemini da Google) para analisar textos específicos ou realizar buscas por nomes.

**Link para a Aplicação (Streamlit Community Cloud):**
[https://chatbot-doe-mpsp.streamlit.app/](https://chatbot-doe-mpsp.streamlit.app/) 

## Funcionalidades Principais

*   **Busca por Data:** Permite ao usuário selecionar uma data específica para carregar as publicações do Ministério Público (Caderno Executivo I > Atos Normativos).
*   **Listagem de Títulos:** Exibe os títulos das publicações do MP encontradas para a data selecionada.
*   **Análise com IA (Gemini):**
    *   **Pergunta Aberta:** O usuário pode selecionar uma publicação específica e fazer uma pergunta em linguagem natural para o modelo Gemini analisar o conteúdo completo da publicação.
    *   **Busca Local por Nomes:** Realiza uma busca por nomes pré-definidos ("Dr. Eduardo Tostes", "Eduardo Tostes", "Bruno Henrique Rigoni Barros") no conteúdo completo das publicações do dia.
*   **Exportação de Resoluções:** Identifica publicações do tipo "Resolução" do MP e permite salvá-las individualmente em formato HTML.
*   **Cache de Dados:** Utiliza arquivos JSON locais (na estrutura de pastas da aplicação) para armazenar em cache os dados já buscados para uma data, otimizando buscas futuras.

## Como Usar a Aplicação Online

1.  Acesse o link da aplicação: (https://chatbot-doe-mpsp.streamlit.app/)
2.  Na barra lateral, selecione a data desejada.
3.  Clique em "Carregar Publicações de [data]".
4.  A lista de títulos das publicações do MP aparecerá na área principal.
5.  Na coluna "Ações" à direita, escolha a funcionalidade desejada:
    *   **Analisar publicação específica (Gemini):** Selecione o número da publicação e digite sua pergunta.
    *   **Pesquisar por nomes (Busca Local):** A busca será executada automaticamente para os nomes configurados.
    *   **Salvar Resoluções como HTML:** As resoluções do MP da data selecionada serão salvas como arquivos HTML.
    *   **Exibir Detalhes da Publicação:** Selecione uma publicação para ver seus metadados e conteúdo limpo.

## Tecnologias Utilizadas

*   **Python:** Linguagem de programação principal.
*   **Streamlit:** Framework para criação da interface web interativa.
*   **Requests:** Para realizar requisições HTTP à API do DOE-SP.
*   **BeautifulSoup4:** Para parsear e extrair texto do conteúdo HTML das publicações.
*   **Google Generative AI (Gemini):** Para funcionalidades de análise de texto baseadas em IA.

## Configuração para Desenvolvimento Local (Opcional)

Se você deseja rodar este projeto localmente:

1.  **Clone o Repositório:**
    ```bash
    git clone https://github.com/barraum/chatbot_DOE_MPSP.git 
    cd chatbot_DOE_MPSP
    ```

2.  **Crie e Ative um Ambiente Virtual (Recomendado):**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure a API Key do Google Gemini:**
    *   Obtenha uma API Key em [Google AI Studio](https://aistudio.google.com/app/apikey).
    *   A forma mais segura é configurar a variável de ambiente `GOOGLE_API_KEY`.
    *   Alternativamente, para teste local rápido, você pode editar o script Python no bloco de configuração da API Key e inserir sua chave diretamente (NÃO FAÇA COMMIT DESTA ALTERAÇÃO SE O REPOSITÓRIO FOR PÚBLICO).
    *   Se for rodar localmente e quiser simular o `st.secrets` usado no deploy do Streamlit Cloud, crie uma pasta `.streamlit` na raiz do projeto e, dentro dela, um arquivo `secrets.toml` com o conteúdo:
        ```toml
        GOOGLE_API_KEY = "SUA_CHAVE_API_AQUI"
        ```
        Lembre-se de adicionar `.streamlit/secrets.toml` ao seu `.gitignore`.

5.  **Execute a Aplicação Streamlit:**
    ```bash
    streamlit run "chatbot_doe v10_github.py" 
    ```
    (Ajuste o nome do arquivo .py se for diferente).

## Estrutura de Pastas (Geradas pela Aplicação)

*   `DOE_JSONs_Cloud/`: Armazena o cache (em formato JSON) dos dados das publicações buscadas para cada data.
*   `DOE_Resolutions_HTML_Cloud/`: Armazena os arquivos HTML das resoluções salvas.

*(No desenvolvimento local, você pode alterar os nomes dessas pastas no topo do script Python).*

## Como Contribuir

Sugestões e contribuições são bem-vindas! Se você tem ideias para novas funcionalidades, melhorias ou encontrou algum bug:

1.  Abra uma **Issue** neste repositório para discutir sua ideia ou o problema.
2.  Se for implementar uma mudança, faça um **Fork** do repositório.
3.  Crie um **Branch** para sua feature (`git checkout -b feature/NomeDaFeature`).
4.  Faça seus commits (`git commit -am 'Adiciona alguma feature'`).
5.  Faça o Push para o seu branch (`git push origin feature/NomeDaFeature`).
6.  Abra um **Pull Request**.

## Autor

*   **Bruno Barros** - [barraum](https://github.com/barraum) *(Seu perfil GitHub)*

## Agradecimentos

*   Agradecimento especial ao assistente de IA que auxiliou no desenvolvimento e depuração deste projeto.
