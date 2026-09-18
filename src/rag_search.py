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
        self.chroma_path = os.path.join(self.current_dir, '..', 'data', 'chroma_db')
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

    def retrieve_context(self, query):
        """
        Busca Híbrida de Dois Passos.
        """
        print(f"\n🔍 Buscando referências no banco para: '{query}'...")
        
        # Passo 1: Busca ampla para descobrir os 3 jogos
        busca_inicial = self.collection.query(
            query_texts=[query],
            n_results=50 
        )
        
        jogos_relevantes = []
        for meta in busca_inicial['metadatas'][0]:
            app_id = meta['app_id']
            if app_id not in jogos_relevantes:
                jogos_relevantes.append(app_id)
            if len(jogos_relevantes) == 3: 
                break
                
        contexto_formatado = ""
        cursor = self.conn.cursor()
        
        # Passo 2: Busca profunda (5 opiniões EXCLUSIVAS de cada jogo)
        for app_id in jogos_relevantes:
            cursor.execute("SELECT title FROM Games WHERE app_id = ?", (app_id,))
            row = cursor.fetchone()
            title = row[0] if row else f"Jogo Desconhecido ({app_id})"
            
            cursor.execute("""
                SELECT t.tag_name FROM Tags t
                JOIN Game_Tags gt ON t.tag_id = gt.tag_id
                WHERE gt.app_id = ? LIMIT 5
            """, (app_id,))
            tags = [r[0] for r in cursor.fetchall()]
            tags_str = ", ".join(tags)
            
            reviews_do_jogo = self.collection.query(
                query_texts=[query],
                n_results=5,
                where={"app_id": app_id} 
            )
            
            contexto_formatado += f"\n[JOGO]: {title}\n"
            contexto_formatado += f"[CATEGORIAS]: {tags_str}\n"
            contexto_formatado += f"[OPINIÕES RETIRADAS DO BANCO DE DADOS]:\n"
            
            # Adiciona apenas as reviews, sem numeração excessiva para não confundir a IA
            for review in reviews_do_jogo['documents'][0]:
                contexto_formatado += f"- \"{review}\"\n"
                
        return contexto_formatado

    def ask_ollama(self, system_prompt, user_query, model="llama3.1"):
        """
        Usa a API de CHAT do Ollama. Isso resolve o problema do "Loop Infinito".
        """
        url = "http://localhost:11434/api/chat"
        
        # Agora nós separamos o que é regra (system) do que é a pergunta (user)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
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
                    # No endpoint de chat, a resposta vem dentro de message -> content
                    if "message" in json_data and "content" in json_data["message"]:
                        print(json_data["message"]["content"], end="", flush=True)
            print("\n")
                    
        except requests.exceptions.ConnectionError:
            print("\n❌ ERRO: Não foi possível conectar ao Ollama.")

    def run_chat(self, user_query):
        """
        Orquestra o pipeline RAG completo.
        """
        contexto = self.retrieve_context(user_query)
        
        system_prompt = f"""Você é um curador de jogos profissional da Steam. 

O usuário fará uma pergunta e você DEVE responder baseando-se EXCLUSIVAMENTE nas informações abaixo.

CONTEXTO DE DADOS:
{contexto}

REGRAS DE FORMATAÇÃO E RESPOSTA OBRIGATÓRIAS:
1. Você deve recomendar os 3 jogos listados no contexto, criando um parágrafo bem escrito e fluído para cada um.
2. É ESTRITAMENTE PROIBIDO fazer listas gigantes de opiniões. Sintetize as opiniões para explicar o porquê o jogo é bom.
3. Você DEVE mencionar as mecânicas de gameplay que os jogadores citaram.
4. Escolha apenas UMA (1) citação curta de um jogador por jogo e coloque entre aspas para ilustrar seu argumento.
5. Liste as categorias de cada jogo.
6. Nunca invente fatos que não estejam nas opiniões fornecidas.
"""
        
        # Envia separadamente as regras e a pergunta do usuário
        self.ask_ollama(system_prompt, user_query, model="llama3.1")

if __name__ == "__main__":
    rag = SteamRAG()
    
    print("="*50)
    print(" 🎮 STEAM RAG ASSISTANT v3.0 (Chat Mode) ")
    print("="*50)
    
    while True:
        pergunta = input("\nFaça uma pergunta sobre jogos (ou digite 'sair'): ")
        
        if pergunta.lower().strip() == 'sair':
            break
            
        rag.run_chat(pergunta)