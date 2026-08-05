import sqlite3
import requests
import time
import os

class SteamMetadataDB:
    def __init__(self, db_path=None):
        """
        Inicializa a conexão com o banco SQLite e garante que a estrutura
        (tabelas) exista antes de inserirmos qualquer dado.
        """
        # Resolve o problema do caminho relativo
        if db_path is None:
            # Descobre automaticamente onde o 02_metadata_db.py está salvo (pasta src)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Volta um nível (para a raiz do projeto) e aponta para a pasta 'data'
            db_path = os.path.join(current_dir, '..', 'data', 'games_metadata.db')

        # Garante que a pasta 'data' exista
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Conecta ao banco (se o arquivo não existir, o SQLite cria na hora)
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """
        Cria as tabelas usando a modelagem relacional ideal para buscas rápidas.
        Usamos 'IF NOT EXISTS' para rodar este script várias vezes sem quebrar o banco.
        """
        # 1. Tabela de Jogos
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Games (
                app_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                developer TEXT
            )
        ''')

        # 2. Tabela de Tags (Únicas)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT UNIQUE NOT NULL
            )
        ''')

        # 3. Tabela de Associação (Qual jogo tem qual tag)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Game_Tags (
                app_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (app_id, tag_id),
                FOREIGN KEY (app_id) REFERENCES Games (app_id),
                FOREIGN KEY (tag_id) REFERENCES Tags (tag_id)
            )
        ''')
        
        # Cria um índice para acelerar a busca por tags no futuro
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_tag_name ON Tags(tag_name)')
        
        self.conn.commit()

    def fetch_game_info(self, app_id):
        """
        Busca os dados do jogo usando a API pública do SteamSpy.
        """
        url = f"https://steamspy.com/api.php?request=appdetails&appid={app_id}"
        print(f"Buscando metadados do AppID {app_id} no SteamSpy...")
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # O SteamSpy retorna o próprio app_id se falhar em achar o jogo
            if not data.get('name'):
                print(f"Jogo {app_id} não encontrado ou inválido na API.")
                return None
                
            return data
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar metadados: {e}")
            return None

    def insert_game(self, app_id):
        """
        Orquestra a inserção do jogo, suas tags e os relacionamentos no banco.
        """
        game_data = self.fetch_game_info(app_id)
        
        if not game_data:
            return

        title = game_data.get('name')
        developer = game_data.get('developer')
        
        # 'tags' no SteamSpy é um dicionário: {"RPG": 1000, "Action": 500}
        # Nós só queremos os nomes das tags (as chaves)
        tags_dict = game_data.get('tags', {})
        if isinstance(tags_dict, list): # As vezes a API retorna lista vazia se não houver tags
            tags_list = []
        else:
            tags_list = list(tags_dict.keys())

        try:
            # 1. Insere o Jogo (INSERT OR IGNORE evita erro se o jogo já estiver no banco)
            self.cursor.execute('''
                INSERT OR IGNORE INTO Games (app_id, title, developer)
                VALUES (?, ?, ?)
            ''', (app_id, title, developer))

            # 2. Insere as Tags e faz a associação
            for tag in tags_list:
                # Tenta inserir a tag. Se ela já existir, o IGNORE pula silenciosamente.
                self.cursor.execute('''
                    INSERT OR IGNORE INTO Tags (tag_name)
                    VALUES (?)
                ''', (tag,))
                
                # Descobre qual é o ID numérico dessa tag
                self.cursor.execute('SELECT tag_id FROM Tags WHERE tag_name = ?', (tag,))
                tag_id = self.cursor.fetchone()[0]

                # Cria a associação Jogo <-> Tag
                self.cursor.execute('''
                    INSERT OR IGNORE INTO Game_Tags (app_id, tag_id)
                    VALUES (?, ?)
                ''', (app_id, tag_id))

            self.conn.commit()
            print(f"Sucesso! '{title}' e suas {len(tags_list)} tags foram salvas no banco.")
            
        except sqlite3.Error as e:
            print(f"Erro de banco de dados ao inserir {app_id}: {e}")
            self.conn.rollback()

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    # Lista expandida com diversos gêneros para enriquecer a semântica do RAG
    test_games = [
        367520,   # Hollow Knight (Metroidvania/Souls-like)
        292030,   # The Witcher 3 (Medieval/RPG)
        1091500,  # Cyberpunk 2077 (Sci-Fi/RPG)
        413150,   # Stardew Valley (Farming/Relaxing)
        379720,   # DOOM (FPS/Action)
        1196590,  # Resident Evil 4 (Horror/Survival)
        289070,   # Civilization VI (Strategy)
        1238840   # Battlefield 1 (FPS/Multiplayer)
    ]
    
    db = SteamMetadataDB()
    
    for app_id in test_games:
        db.insert_game(app_id)
        time.sleep(1.5) # Respeito ao limite da API do SteamSpy
        
    db.close()
    print("\nBanco de dados atualizado com sucesso. Verifique a pasta 'data/'.")