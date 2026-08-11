# Steam RAG Assistant (Llama 3.2)

Um sistema de recomendação de jogos e assistente virtual construído com a arquitetura **RAG (Retrieval-Augmented Generation)**. Este projeto extrai opiniões reais de jogadores da Steam, processa o significado semântico desses textos e utiliza um LLM local para responder perguntas e recomendar jogos com base em dados reais, eliminando as alucinações comuns das IAs.

Desenvolvido para rodar **100% offline e localmente**, otimizado para hardwares com recursos limitados de memória (como APUs sem VRAM dedicada).

---

## Como Funciona a Arquitetura

O sistema é dividido em duas partes principais: **Processamento de Dados (Pipeline)** e **Inferência (Chat)**.

1. **Scraping** — Coleta milhares de reviews da Steam e limpa o "lixo" (ASCII art, textos vazios).
2. **Metadados (SQLite)** — Busca o nome real do jogo e suas tags (ex: *Metroidvania*, *Souls-like*) na API do SteamSpy para dar contexto à IA.
3. **Embedding (ChromaDB)** — Converte as reviews para o formato matemático (vetores multidimensionais) para que a IA consiga entender o significado e a "vibe" do texto, não apenas palavras-chave.
4. **Geração (Ollama + Llama 3.2)** — O usuário faz uma pergunta, o sistema busca as opiniões mais relevantes matematicamente e pede para o Llama 3.2 ler esse "dossiê" antes de responder.

---

## Estrutura do Projeto

```
meu_projeto_rag/
├── data/                       # Pasta gerada automaticamente pelos scripts
│   ├── chroma_db/              # Banco de dados vetorial (Embeddings)
│   ├── reviews_raw/            # Arquivos CSV com as reviews limpas
│   └── games_metadata.db       # Banco de dados relacional (SQLite)
├── src/                        # Código-fonte do projeto
│   ├── 01_steam_scraper.py     # Baixa e limpa as reviews da Steam
│   ├── 02_metadata_db.py       # Baixa nomes e tags e salva no SQLite
│   ├── 03_embedder.py          # Vetoriza os textos e salva no ChromaDB
│   ├── 04_rag_search.py        # O Orquestrador: Chat interativo com a IA
│   ├── test_db.py              # Script de teste do SQLite
│   └── test_chroma.py          # Script de teste de busca semântica
├── .gitignore                  # Arquivos ignorados pelo Git (venv, data, etc.)
├── requirements.txt            # Dependências do projeto
└── README.md                   # Este arquivo
```

---

## Tecnologias e Bibliotecas Utilizadas

| Categoria | Tecnologia |
|---|---|
| Linguagem | Python 3 |
| LLM Engine | Ollama (Modelo Llama 3.2 de 3B parâmetros) |
| Bancos de Dados | ChromaDB (Vetorial) e SQLite (Relacional) |
| Embeddings | HuggingFace `sentence-transformers` (Modelo `paraphrase-multilingual-MiniLM-L12-v2`) |
| Manipulação de Dados | Pandas |
| Web Scraping | Requests (Consumo direto de APIs REST) |

---

## Como Instalar e Configurar

### Pré-requisitos

- Python 3 instalado
- Ollama instalado no sistema (Windows/Linux/Mac)

### Baixando o Modelo de IA

Abra o seu terminal e baixe o modelo Llama 3.2 através do Ollama:

```bash
ollama pull llama3.2
```

### Configurando o Ambiente Python

Clone este repositório, crie um ambiente virtual e instale as dependências:

```bash
# Clone o repositório
git clone https://github.com/SEU_USUARIO/busca_IA.git
cd busca_IA

# Crie e ative o ambiente virtual (Linux/Mac)
python3 -m venv venv
source venv/bin/activate

# Instale os pacotes necessários
pip install -r requirements.txt
```

> Se você ainda não tiver o `requirements.txt`, instale manualmente com:
> ```bash
> pip install pandas requests chromadb sentence-transformers tqdm
> ```

---

## Como Rodar o Pipeline (Passo a Passo)

Para que a IA tenha o que responder, precisamos alimentar o banco de dados. Siga a ordem abaixo:

### Passo 1: Coletar as Reviews

Edite o arquivo `src/01_steam_scraper.py` e coloque o `APP_ID` do jogo desejado. Depois rode:

```bash
python src/01_steam_scraper.py
```

*(Isso criará um arquivo CSV na pasta `data/reviews_raw/`)*

### Passo 2: Coletar os Metadados (Nome e Tags)

Edite o arquivo `src/02_metadata_db.py` e adicione o ID do jogo na lista de testes no final do arquivo.

```bash
python src/02_metadata_db.py
```

*(Isso populará o `data/games_metadata.db`)*

### Passo 3: Criar o Cérebro Semântico (Vetorização)

Este passo lê todos os CSVs baixados e converte os textos em matemática. Pode demorar alguns minutos dependendo da sua CPU.

```bash
python src/03_embedder.py
```

*(Você pode testar se funcionou rodando `python src/test_chroma.py`)*

### Passo 4: Iniciar o Assistente IA

Com o Ollama rodando em segundo plano e os dados salvos, inicie o chat interativo:

```bash
python src/04_rag_search.py
```

Agora é só fazer sua pergunta (ex: *"Me recomende um jogo com história sombria"*).

---

## Próximos Passos (Roadmap)

- [ ] Migração do processamento pesado para a nuvem (Google Colab)
- [ ] Implementação de Busca Híbrida em Dois Passos: filtrar os IDs dos jogos no SQLite por tags antes de fazer a busca semântica no ChromaDB, garantindo respostas matematicamente balanceadas entre múltiplos jogos
- [ ] Interface gráfica simples com Streamlit
