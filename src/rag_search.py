import os
import chromadb
from chromadb.utils import embedding_functions
import requests
import json
import sqlite3 # NOVA IMPORTAÇÃO: Vamos conectar ao banco de metadados!

class SteamRAG:
    def __init__(self):
        """
        Inicializa a conexão dupla: ChromaDB (Semântico) e SQLite (Metadados).
        """
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 1. Configurando caminho do ChromaDB
        self.chroma_path = os.path.join(self.current_dir, '..', 'data', 'chroma_db')
        
        # 2. Configurando caminho do SQLite
        self.sqlite_path = os.path.join(self.current_dir, '..', 'data', 'games_metadata.db')
        
        print("Conectando aos bancos de dados (ChromaDB e SQLite)...")
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
        
        self.collection = self.client.get_collection(
            name="steam_reviews",
            embedding_function=self.embed_fn
        )

    def retrieve_context(self, query, n_results=10): # ALTERAÇÃO: Mudamos de 5 para 10 reviews
        """
        Busca as reviews no ChromaDB e enriquece com Nome e Tags do SQLite.
        """
        print(f"\n🔍 Buscando 10 referências no banco para: '{query}'...")
        
        resultados = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        contexto_formatado = ""
        jogos_vistos = {} # Usamos um dicionário como "cache" para não fazer a mesma busca no SQLite várias vezes
        cursor = self.conn.cursor()
        
        for i, review in enumerate(resultados['documents'][0]):
            app_id = resultados['metadatas'][0][i]['app_id']
            
            # Se ainda não fomos no SQLite procurar o nome e as tags desse jogo, nós vamos agora:
            if app_id not in jogos_vistos:
                # Busca o Título
                cursor.execute("SELECT title FROM Games WHERE app_id = ?", (app_id,))
                row = cursor.fetchone()
                title = row[0] if row else f"Jogo Desconhecido ({app_id})"
                
                # Busca até 5 Tags do jogo
                cursor.execute("""
                    SELECT t.tag_name
                    FROM Tags t
                    JOIN Game_Tags gt ON t.tag_id = gt.tag_id
                    WHERE gt.app_id = ?
                    LIMIT 5
                """, (app_id,))
                tags = [r[0] for r in cursor.fetchall()]
                
                # Salva no cache
                jogos_vistos[app_id] = {'title': title, 'tags': tags}
            
            info = jogos_vistos[app_id]
            tags_str = ", ".join(info['tags'])
            
            # Montamos o texto perfeito para o Llama ler
            contexto_formatado += f"\n--- Review {i+1} ---\n"
            contexto_formatado += f"Jogo: {info['title']}\n"
            contexto_formatado += f"Categorias: {tags_str}\n"
            contexto_formatado += f"Opinião do Jogador: {review}\n"
            
        return contexto_formatado

    def ask_ollama(self, prompt, model="llama3.2"):
        """
        Envia o prompt para a API local do Ollama e imprime a resposta.
        """
        url = "http://localhost:11434/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True 
        }
        
        print("\n🤖 Resposta da IA:\n")
        try:
            response = requests.post(url, json=payload, stream=True)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    json_data = json.loads(decoded_line)
                    print(json_data.get("response", ""), end="", flush=True)
            print("\n")
                    
        except requests.exceptions.ConnectionError:
            print("\n❌ ERRO: Não foi possível conectar ao Ollama.")

    def run_chat(self, user_query):
        """
        Orquestra o pipeline RAG completo.
        """
        # 1. Recupera o contexto enriquecido
        contexto = self.retrieve_context(user_query)
        
        # 2. Monta o Prompt com Regras Estritas (Engenharia de Prompt)
        system_prompt = f"""
        Você é um assistente especialista e detalhista em recomendar jogos da Steam.
        Abaixo estão opiniões reais de jogadores sobre determinados jogos, incluindo o nome oficial do jogo e suas categorias (tags).
        
        REGRAS OBRIGATÓRIAS:
        1. Baseie-se EXCLUSIVAMENTE nas opiniões fornecidas abaixo.
        2. Refira-se aos jogos SEMPRE PELO NOME (ex: Hollow Knight). Nunca use o ID numérico do jogo na sua resposta final.
        3. Forneça uma resposta detalhada, longa e bem elaborada. Explore os pontos positivos e negativos citados nas reviews.
        4. OBRIGATÓRIO: Em algum momento da sua resposta, liste as principais categorias/tags dos jogos recomendados.
        5. Responda sempre em Português.

        OPINIÕES DOS JOGADORES E METADADOS (CONTEXTO):
        {contexto}
        
        PERGUNTA DO USUÁRIO:
        {user_query}
        """
        
        # 3. Pede para a IA gerar a resposta
        self.ask_ollama(system_prompt)

if __name__ == "__main__":
    rag = SteamRAG()
    
    print("="*50)
    print(" 🎮 STEAM RAG ASSISTANT v2.0 - Llama 3.2 ")
    print("="*50)
    
    while True:
        pergunta = input("\nFaça uma pergunta sobre jogos (ou digite 'sair'): ")
        
        if pergunta.lower().strip() == 'sair':
            break
            
        rag.run_chat(pergunta)