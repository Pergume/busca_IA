import os
import chromadb
from chromadb.utils import embedding_functions
import requests
import json

class SteamRAG:
    def __init__(self):
        """
        Inicializa a conexão com o banco vetorial ChromaDB e prepara o modelo.
        """
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.chroma_path = os.path.join(self.current_dir, '..', 'data', 'chroma_db')
        
        print("Conectando ao banco de dados semântico...")
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
        
        self.collection = self.client.get_collection(
            name="steam_reviews",
            embedding_function=self.embed_fn
        )

    def retrieve_context(self, query, n_results=5):
        """
        Busca as reviews mais relevantes no ChromaDB com base na pergunta.
        """
        print(f"\n🔍 Buscando no banco referências para: '{query}'...")
        
        resultados = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # Junta todas as reviews encontradas em um único texto grande
        contexto_formatado = ""
        for i, review in enumerate(resultados['documents'][0]):
            app_id = resultados['metadatas'][0][i]['app_id']
            contexto_formatado += f"\n--- Review {i+1} (Jogo ID: {app_id}) ---\n{review}\n"
            
        return contexto_formatado

    def ask_ollama(self, prompt, model="llama3.2"):
        """
        Envia o prompt para a API local do Ollama e imprime a resposta.
        """
        url = "http://localhost:11434/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True # Permite ver a IA digitando palavra por palavra
        }
        
        print("\n🤖 Resposta da IA:\n")
        try:
            # Faz a requisição para o Ollama rodando no seu Linux
            response = requests.post(url, json=payload, stream=True)
            response.raise_for_status()
            
            # Imprime a resposta como se a IA estivesse digitando ao vivo
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    json_data = json.loads(decoded_line)
                    print(json_data.get("response", ""), end="", flush=True)
            print("\n")
                    
        except requests.exceptions.ConnectionError:
            print("\n❌ ERRO: Não foi possível conectar ao Ollama.")
            print("Verifique se o Ollama está rodando no seu Linux Mint.")
            print("Abra outro terminal e digite: ollama serve")

    def run_chat(self, user_query):
        """
        Orquestra o pipeline RAG completo.
        """
        # 1. Recupera o contexto do banco de dados (Retrieval)
        contexto = self.retrieve_context(user_query)
        
        # 2. Monta o Prompt Aumentado (Augmented)
        system_prompt = f"""
        Você é um assistente especialista em recomendar jogos da Steam.
        Abaixo estão algumas opiniões reais de jogadores sobre determinados jogos.
        
        Baseado EXCLUSIVAMENTE nas opiniões fornecidas abaixo, responda à pergunta do usuário.
        Se as opiniões não contiverem a resposta, diga que não tem informações suficientes.
        Responda sempre em Português.

        OPINIÕES DOS JOGADORES (CONTEXTO):
        {contexto}
        
        PERGUNTA DO USUÁRIO:
        {user_query}
        """
        
        # 3. Pede para a IA gerar a resposta (Generation)
        self.ask_ollama(system_prompt)

if __name__ == "__main__":
    rag = SteamRAG()
    
    print("="*50)
    print(" 🎮 STEAM RAG ASSISTANT - Llama 3.2 ")
    print("="*50)
    
    # Loop para você conversar com o seu sistema!
    while True:
        pergunta = input("\nFaça uma pergunta sobre jogos (ou digite 'sair'): ")
        
        if pergunta.lower().strip() == 'sair':
            break
            
        rag.run_chat(pergunta)