import os
import glob
import re
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
from tqdm import tqdm # Para a barra de progresso

class SteamEmbedder:
    def __init__(self):
        """
        Inicializa os caminhos e o banco de dados vetorial ChromaDB.
        """
        # Resolução de caminhos (à prova de falhas)
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.join(self.current_dir, '..')
        self.data_dir = os.path.join(self.project_root, 'data')
        self.chroma_path = os.path.join(self.data_dir, 'chroma_db')
        
        # Garante que a pasta exista
        os.makedirs(self.chroma_path, exist_ok=True)
        
        # 1. Inicializa o cliente do ChromaDB (PersistentClient salva no disco)
        print("Iniciando ChromaDB...")
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        
        # 2. Define a função de Embedding
        # Este é o nosso "Tradutor". Ele roda perfeitamente na sua CPU Ryzen.
        # Sendo multilíngue, ele entende que "Espada" e "Sword" têm vetores parecidos.
        print("Carregando modelo de Embedding (Pode demorar na primeira vez para fazer o download)...")
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
        
        # 3. Cria ou carrega a "Coleção" (como se fosse uma tabela no SQL)
        self.collection = self.client.get_or_create_collection(
            name="steam_reviews",
            embedding_function=self.embed_fn
        )

    def find_csv_files(self):
        """
        Procura por arquivos de reviews limpas tanto na raiz quanto na pasta data.
        """
        # Procura por arquivos que sigam o padrão do nosso scraper
        pattern = "steam_reviews_*_clean.csv"
        files_in_root = glob.glob(os.path.join(self.project_root, pattern))
        files_in_data = glob.glob(os.path.join(self.data_dir, pattern))
        
        # Junta tudo e remove duplicatas (caso existam)
        return list(set(files_in_root + files_in_data))

    def process_and_embed(self, batch_size=500):
        """
        Lê os CSVs e injeta no ChromaDB em lotes (batches) para não sobrecarregar a RAM.
        """
        csv_files = self.find_csv_files()
        
        if not csv_files:
            print("Nenhum arquivo CSV encontrado. Rode o 01_steam_scraper.py primeiro.")
            return

        for file_path in csv_files:
            # Extrai o AppID do nome do arquivo usando Expressão Regular (Regex)
            match = re.search(r'steam_reviews_(\d+)_clean\.csv', file_path)
            if not match:
                continue
                
            app_id = int(match.group(1))
            print(f"\nProcessando arquivo: {os.path.basename(file_path)} (AppID: {app_id})")
            
            # Lê o CSV usando Pandas
            df = pd.read_csv(file_path)
            
            # Remove linhas que possam estar vazias por algum erro de raspagem
            df = df.dropna(subset=['clean_text', 'review_id'])
            
            # Vamos separar os dados em listas para o ChromaDB
            documents = []
            metadatas = []
            ids = []
            
            print(f"Preparando {len(df)} reviews para vetorização...")
            
            # tqdm cria uma barra de progresso no terminal
            for index, row in tqdm(df.iterrows(), total=df.shape[0]):
                # O texto que será transformado em vetor e lido pelo LLM
                documents.append(row['clean_text'])
                
                # O ID único do documento no ChromaDB (precisa ser string)
                ids.append(str(row['review_id']))
                
                # Metadados cruciais para a nossa Busca Híbrida!
                # O ChromaDB permite filtrar por essas tags depois.
                metadatas.append({
                    "app_id": app_id,
                    "voted_up": str(row['voted_up']), # Salvando como string para compatibilidade
                    "author_playtime_forever": float(row['author_playtime_forever'])
                })
            
            # Inserindo em lotes para otimizar o uso da sua RAM de 12GB
            print("Injetando vetores no banco de dados...")
            for i in range(0, len(documents), batch_size):
                # O ChromaDB cuida de passar o 'documents' para o modelo de embeddings
                # gerar os vetores automaticamente antes de salvar.
                self.collection.add(
                    documents=documents[i : i + batch_size],
                    metadatas=metadatas[i : i + batch_size],
                    ids=ids[i : i + batch_size]
                )
            
            print(f"Sucesso! AppID {app_id} vetorizado e salvo no ChromaDB.")

if __name__ == "__main__":
    embedder = SteamEmbedder()
    embedder.process_and_embed()
    print("\nProcesso de vetorização finalizado!")
    print("Você pode olhar a pasta 'data/chroma_db' para ver os arquivos físicos do banco.")