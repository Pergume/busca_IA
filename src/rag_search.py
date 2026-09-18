import os
import chromadb
from chromadb.utils import embedding_functions
import requests
import json
import sqlite3 

class SteamRAG:
    def __init__(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.chroma_path = os.path.join(self.current_dir, '..', 'data', 'chroma_db')
        self.sqlite_path = os.path.join(self.current_dir, '..', 'data', 'games_metadata.db')
        
        print("Conectando aos bancos de dados (ChromaDB e SQLite)...")
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.collection = self.client.get_collection(name="steam_reviews", embedding_function=self.embed_fn)

    def retrieve_context(self, query):
        print(f"\n🔍 Buscando referências no banco para: '{query}'...")
        
        busca_inicial = self.collection.query(query_texts=[query], n_results=50)
        
        jogos_relevantes = []
        for meta in busca_inicial['metadatas'][0]:
            app_id = meta['app_id']
            if app_id not in jogos_relevantes:
                jogos_relevantes.append(app_id)
            if len(jogos_relevantes) == 3: 
                break
                
        contexto_formatado = ""
        cursor = self.conn.cursor()
        
        for app_id in jogos_relevantes:
            cursor.execute("SELECT title, synopsis FROM Games WHERE app_id = ?", (app_id,))
            row = cursor.fetchone()
            title = row[0] if row else f"Jogo Desconhecido ({app_id})"
            synopsis = row[1] if row and row[1] else "Sinopse indisponível."
            
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
            contexto_formatado += f"[SINOPSE OFICIAL]: {synopsis}\n"
            contexto_formatado += f"[OPINIÕES DOS JOGADORES]:\n"
            
            for review in reviews_do_jogo['documents'][0]:
                contexto_formatado += f"- \"{review}\"\n"
                
        return contexto_formatado

    def run_chat(self, user_query):
        contexto = self.retrieve_context(user_query)
        
        system_prompt = f"""Você é um curador de jogos profissional.

Baseie-se EXCLUSIVAMENTE nos dados fornecidos abaixo:
{contexto}

REGRAS:
1. Recomende os jogos encontrados no contexto de forma fluida.
2. Inicie o resumo de cada jogo usando a [SINOPSE OFICIAL] para dar uma curtíssima introdução sobre a ambientação e premissa.
3. Depois, cruze as [OPINIÕES DOS JOGADORES] para explicar as mecânicas, pontos fortes e fracos mencionados por eles.
4. Você só pode mencionar detalhes do gameplay que estejam escritos nas opiniões dos jogadores. Não invente nada.
5. É OBRIGATÓRIO listar as categorias de cada jogo.
6. É OBRIGATÓRIO colocar uma citação literal e entre aspas de uma das opiniões dos jogadores para embasar sua recomendação.
"""
        self.ask_ollama(system_prompt, user_query, model="llama3.1")

if __name__ == "__main__":
    rag = SteamRAG()
    
    print("="*50)
    print(" 🎮 STEAM RAG ASSISTANT v3.5 ")
    print("="*50)
    
    while True:
        pergunta = input("\nFaça uma pergunta sobre jogos (ou digite 'sair'): ")
        if pergunta.lower().strip() == 'sair':
            break
        rag.run_chat(pergunta)