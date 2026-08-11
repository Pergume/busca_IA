import os
import chromadb
from chromadb.utils import embedding_functions

def test_semantic_search():
    """
    Este script prova que a vetorização funcionou fazendo uma busca puramente
    semântica (baseada em significado, não em palavras exatas) no seu ChromaDB.
    """
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    chroma_path = os.path.join(current_dir, '..', 'data', 'chroma_db')
    
    if not os.path.exists(chroma_path):
        print("Erro: Pasta do ChromaDB não encontrada.")
        return

    print("Conectando ao ChromaDB...")
    client = chromadb.PersistentClient(path=chroma_path)
    
    print("Carregando modelo de Embedding (do cache local)...")
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    collection = client.get_collection(
        name="steam_reviews",
        embedding_function=embed_fn
    )
    
    total_docs = collection.count()
    print(f"\nSucesso! O banco contém um total de {total_docs} vetores (reviews) gravados.")
    print("-" * 50)
    
    # Sinta-se livre para mudar essa frase para qualquer conceito que quiser!
    busca = "Um jogo com atmosfera sombria, difícil e que pune erros."
    
    print(f"\nRealizando busca semântica por: '{busca}'\n")
    
    # query() é a função mágica do ChromaDB. Ela converte a frase de busca
    # em vetor e traz os "n_results" vetores mais próximos matematicamente.
    resultados = collection.query(
        query_texts=[busca],
        n_results=3 # Traz as 3 reviews que mais chegam perto da 'vibe' da frase
    )
    #teste
    for i in range(len(resultados['documents'][0])):
        review = resultados['documents'][0][i]
        metadados = resultados['metadatas'][0][i]
        distancia = resultados['distances'][0][i] # Quão parecido é matematicamente
        
        print(f"--- Resultado {i+1} ---")
        print(f"AppID do Jogo: {metadados['app_id']}")
        print(f"Distância Vetorial: {distancia:.4f} (Quanto menor, mais parecido)")
        # Cortamos a review em 200 caracteres apenas para não poluir muito o terminal
        print(f"Review Recuperada: {review[:200]}...\n")

if __name__ == "__main__":
    test_semantic_search()