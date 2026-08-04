import sqlite3
import pandas as pd

def test_database(db_path='data/games_metadata.db'):
    """
    Conecta ao banco de dados SQLite e realiza consultas de teste
    para verificar se os dados foram inseridos e relacionados corretamente.
    """
    try:
        # Conecta ao banco em modo apenas leitura
        conn = sqlite3.connect(db_path)
        
        print("--- JOGOS CADASTRADOS ---")
        # Usamos o Pandas aqui apenas porque ele imprime tabelas no terminal de um jeito muito bonito
        games_df = pd.read_sql_query("SELECT app_id, title, developer FROM Games;", conn)
        print(games_df.to_string(index=False))
        print("\n" + "="*50 + "\n")
        
        print("--- ESTATÍSTICAS DE TAGS ---")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Tags;")
        total_tags = cursor.fetchone()[0]
        print(f"Total de tags únicas registradas: {total_tags}")
        print("\n" + "="*50 + "\n")
        
        print("--- TESTE DE RELACIONAMENTO (Quais tags o jogo tem?) ---")
        # Esta é a query real que usaremos no projeto para buscar as tags de um jogo específico
        query = """
            SELECT g.title, t.tag_name
            FROM Games g
            JOIN Game_Tags gt ON g.app_id = gt.app_id
            JOIN Tags t ON gt.tag_id = t.tag_id
            WHERE g.app_id = 367520  -- AppID do Hollow Knight
            LIMIT 10;                -- Limitamos a 10 para não poluir a tela
        """
        tags_df = pd.read_sql_query(query, conn)
        print(f"Amostra de 10 tags do jogo Hollow Knight:")
        print(tags_df.to_string(index=False))
        
    except sqlite3.Error as e:
        print(f"Erro ao ler o banco de dados: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    test_database()