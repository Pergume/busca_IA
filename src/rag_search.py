import os
import chromadb
from chromadb.utils import embedding_functions
import requests
import json
import sqlite3 

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

    def retrieve_context(self, query, n_results=10):
        """
        Busca as reviews no ChromaDB e enriquece com Nome e Tags do SQLite.
        """
        print(f"\n🔍 Buscando referências no banco para: '{query}'...")
        
        resultados = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        contexto_formatado = ""
        jogos_vistos = {} 
        cursor = self.conn.cursor()
        
        for i, review in enumerate(resultados['documents'][0]):
            app_id = resultados['metadatas'][0][i]['app_id']
            
            if app_id not in jogos_vistos:
                cursor.execute("SELECT title FROM Games WHERE app_id = ?", (app_id,))
                row = cursor.fetchone()
                title = row[0] if row else f"Jogo Desconhecido ({app_id})"
                
                cursor.execute("""
                    SELECT t.tag_name
                    FROM Tags t
                    JOIN Game_Tags gt ON t.tag_id = gt.tag_id
                    WHERE gt.app_id = ?
                    LIMIT 5
                """, (app_id,))
                tags = [r[0] for r in cursor.fetchall()]
                
                jogos_vistos[app_id] = {'title': title, 'tags': tags}
            
            info = jogos_vistos[app_id]
            tags_str = ", ".join(info['tags'])
            
            contexto_formatado += f"\n--- Review {i+1} ---\n"
            contexto_formatado += f"Jogo: {info['title']}\n"
            contexto_formatado += f"Categorias: {tags_str}\n"
            contexto_formatado += f"Opinião do Jogador: {review}\n"
            
        return contexto_formatado

    def ask_ollama(self, prompt, model="llama3.1"):
        """
        Envia o prompt para a API local do Ollama e imprime a resposta.
        """
        url = "http://localhost:11434/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True 
        }
        
        print("\n🤖 Resposta da IA (Llama 3.1):\n")
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
        contexto = self.retrieve_context(user_query)
        
        # O PROMPT DE FERRO: Regras estritas para forçar especificidade e evitar alucinação
        system_prompt = f"""
        Você é um assistente curador de jogos da Steam. O seu objetivo é analisar e recomendar jogos baseando-se APENAS nos dados fornecidos no contexto.
        
        REGRAS DE RESPOSTA OBRIGATÓRIAS:
        1. Você só pode mencionar detalhes, mecânicas ou qualidades que estejam EXPRESSAMENTE ESCRITOS nas opiniões dos jogadores no contexto. Não invente nada.
        2. É OBRIGATÓRIO extrair e usar uma citação direta (entre aspas) de um jogador para CADA jogo recomendado. Se não houver opinião clara para o jogo, não o recomende.
        3. Escreva um resumo ÚNICO e detalhado para cada jogo. É ESTRITAMENTE PROIBIDO repetir frases genéricas de introdução (como "é um jogo de ação e aventura..." ou "a atmosfera é mantida"). Vá direto aos detalhes específicos citados pelos jogadores.
        4. OBRIGATÓRIO: Liste as categorias (tags) do jogo.
        5. Nunca use números de ID numérico na resposta final, use apenas o nome do jogo.

        CONTEXTO (Use apenas estas informações):
        {contexto}
        
        PERGUNTA DO USUÁRIO:
        {user_query}
        """
        
        self.ask_ollama(system_prompt, model="llama3.1")

if __name__ == "__main__":
    rag = SteamRAG()
    
    print("="*50)
    print(" 🎮 STEAM RAG ASSISTANT v2.2 - Llama 3.1 ")
    print("="*50)
    
    while True:
        pergunta = input("\nFaça uma pergunta sobre jogos (or digite 'sair'): ")
        
        if pergunta.lower().strip() == 'sair':
            break
            
        rag.run_chat(pergunta)