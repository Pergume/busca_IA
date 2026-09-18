import sqlite3
import requests
import time
import os
import re

class SteamMetadataDB:
    def __init__(self, db_path=None):
        if db_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, '..', 'data', 'games_metadata.db')

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # ATUALIZAÇÃO: Adicionada a coluna "synopsis" na tabela Games
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Games (
                app_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                synopsis TEXT,
                developer TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT UNIQUE NOT NULL
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Game_Tags (
                app_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (app_id, tag_id),
                FOREIGN KEY (app_id) REFERENCES Games (app_id),
                FOREIGN KEY (tag_id) REFERENCES Tags (tag_id)
            )
        ''')
        
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_tag_name ON Tags(tag_name)')
        self.conn.commit()

    def fetch_game_info(self, app_id):
        """
        Agora fazemos DUAS buscas: Uma no SteamSpy (para as tags da comunidade)
        e uma na Steam Oficial (para a Sinopse do jogo).
        """
        print(f"Buscando metadados do AppID {app_id}...")
        
        # 1. Busca no SteamSpy
        spy_url = f"https://steamspy.com/api.php?request=appdetails&appid={app_id}"
        game_data = None
        try:
            response = requests.get(spy_url, timeout=10)
            response.raise_for_status()
            game_data = response.json()
            if not game_data.get('name'):
                print(f"Jogo {app_id} não encontrado no SteamSpy.")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar no SteamSpy: {e}")
            return None

        # 2. Busca na API Oficial da Steam (Para pegar a sinopse em PT-BR)
        steam_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=brazilian"
        synopsis = "Sinopse não disponível."
        try:
            steam_response = requests.get(steam_url, timeout=10)
            steam_response.raise_for_status()
            steam_json = steam_response.json()
            
            # A API da steam retorna os dados dentro da chave do proprio ID
            if steam_json and str(app_id) in steam_json and steam_json[str(app_id)]['success']:
                raw_synopsis = steam_json[str(app_id)]['data'].get('short_description', synopsis)
                # Limpa marcações HTML (como <br>, <i>) que a Steam às vezes manda
                synopsis = re.sub(r'<[^>]+>', '', raw_synopsis)
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar sinopse na Steam Oficial: {e}")

        # Guarda a sinopse limpa dentro dos nossos dados
        game_data['synopsis'] = synopsis
        return game_data

    def insert_game(self, app_id):
        game_data = self.fetch_game_info(app_id)
        if not game_data:
            return

        title = game_data.get('name')
        developer = game_data.get('developer')
        synopsis = game_data.get('synopsis')
        
        tags_dict = game_data.get('tags', {})
        tags_list = [] if isinstance(tags_dict, list) else list(tags_dict.keys())

        try:
            # Inserindo o jogo agora com a coluna synopsis
            self.cursor.execute('''
                INSERT OR IGNORE INTO Games (app_id, title, synopsis, developer)
                VALUES (?, ?, ?, ?)
            ''', (app_id, title, synopsis, developer))

            for tag in tags_list:
                self.cursor.execute('''
                    INSERT OR IGNORE INTO Tags (tag_name)
                    VALUES (?)
                ''', (tag,))
                
                self.cursor.execute('SELECT tag_id FROM Tags WHERE tag_name = ?', (tag,))
                tag_id = self.cursor.fetchone()[0]

                self.cursor.execute('''
                    INSERT OR IGNORE INTO Game_Tags (app_id, tag_id)
                    VALUES (?, ?)
                ''', (app_id, tag_id))

            self.conn.commit()
            print(f"Sucesso! '{title}' salvo com sinopse e {len(tags_list)} tags.")
            
        except sqlite3.Error as e:
            print(f"Erro de banco de dados ao inserir {app_id}: {e}")
            self.conn.rollback()

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    # Testando com os jogos que você já raspou: Hollow Knight, Witcher 3, Cyberpunk, Stardew Valley, DOOM (2016), Resident Evil 4, Civilization 6, Battlefield 1
    test_games = [367520, 292030, 1091500, 413150, 379720, 1196590, 289070, 1238840 ]
    
    db = SteamMetadataDB()
    for app_id in test_games:
        db.insert_game(app_id)
        time.sleep(1.5) 
        
    db.close()
    print("\nBanco de dados atualizado com sucesso!")