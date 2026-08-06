import requests
import time
import re
import urllib.parse
import pandas as pd
import shutil
import os

class SteamReviewScraper:
    def __init__(self, app_id, language='brazilian', max_reviews=1000):
        """
        Inicializa o scraper para um jogo específico.
        
        :param app_id: ID do jogo na Steam (ex: 374320 para Dark Souls III)
        :param language: Idioma das reviews ('brazilian', 'english', 'all')
        :param max_reviews: Quantidade máxima de reviews para baixar
        """
        self.app_id = app_id
        self.language = language
        self.max_reviews = max_reviews
        self.base_url = f"https://store.steampowered.com/appreviews/{self.app_id}?json=1"
        
    def clean_text_for_embeddings(self, text):
        """
        Limpa o texto para garantir que o modelo de embeddings (LLM) 
        receba apenas semântica útil, removendo ruídos da Steam.
        """
        if not text:
            return None
            
        # 1. Remove marcações BBCode comuns na Steam (ex: [b]texto[/b], [h1]título[/h1])
        text = re.sub(r'\[/?.*?\]', '', text)
        
        # 2. Remove URLs
        text = re.sub(r'http\S+|www\.\S+', '', text)
        
        # 3. Remove múltiplos espaços, quebras de linha e tabulações
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 4. Filtro Anti-ASCII Art e Spam de pontuação
        # Se mais de 30% do texto for composto por símbolos não-alfanuméricos, provavelmente é ASCII art ou spam.
        alfanum_count = sum(c.isalnum() for c in text)
        if len(text) > 0 and (alfanum_count / len(text)) < 0.7:
            return None
            
        # 5. Filtro de Tamanho (Remover reviews muito curtas ou irrelevantes)
        # Reviews com menos de 10 palavras raramente têm valor semântico para RAG
        word_count = len(text.split())
        if word_count < 10 or word_count > 500: # Limitamos a 500 para evitar estourar o limite de tokens de modelos menores
            return None
            
        return text

    def fetch_reviews(self):
        """
        Faz a paginação na API da Steam usando cursores e retorna as reviews limpas.
        """
        reviews_data = []
        cursor = '*' # O cursor inicial na API da Steam é sempre '*'
        
        print(f"Iniciando download de reviews para o AppID {self.app_id}...")
        
        while len(reviews_data) < self.max_reviews:
            # Parametros da requisição
            params = {
                'filter': 'updated', # Traz as mais recentes/atualizadas
                'language': self.language,
                'day_range': '9223372036854775807', # Hack da API para ignorar limite de dias
                'cursor': cursor,
                'review_type': 'all',
                'purchase_type': 'all',
                'num_per_page': 100 # Máximo permitido por página
            }
            
            try:
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                print(f"Erro na requisição: {e}")
                break
                
            if data.get('success') != 1:
                print("A API retornou um erro de sucesso=0.")
                break
                
            batch_reviews = data.get('reviews', [])
            if not batch_reviews:
                print("Não há mais reviews disponíveis.")
                break # Fim das reviews
                
            for review in batch_reviews:
                raw_text = review.get('review', '')
                clean_text = self.clean_text_for_embeddings(raw_text)
                
                # Só salvamos se passou nos nossos filtros de qualidade
                if clean_text:
                    reviews_data.append({
                        'review_id': review.get('recommendationid'),
                        'author_playtime_forever': review.get('author', {}).get('playtime_forever', 0) / 60, # Em horas
                        'voted_up': review.get('voted_up'),
                        'votes_up': review.get('votes_up'),
                        'clean_text': clean_text
                    })
                    
                if len(reviews_data) >= self.max_reviews:
                    break
            
            # Atualiza o cursor para a próxima página
            new_cursor = data.get('cursor')
            if not new_cursor or new_cursor == cursor:
                break # Cursor parou de mudar, fim da lista
            
            cursor = new_cursor
            
            print(f"Baixadas e limpas {len(reviews_data)}/{self.max_reviews} reviews...")
            time.sleep(1) # Respeita o rate limit da Valve
            
        return reviews_data

class reviewFile:
    def __init__(self, dataFrame, review_path=None):
        self.dataFrame = dataFrame
        self.review_path = review_path

        
    def moveReviews(dataFrame, review_path=None):
        if review_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            review_path = os.path.join(current_dir,"..","data","reviews_raw")

        # Garante que a pasta 'data' exista
        os.makedirs(os.path.dirname(review_path), exist_ok=True)

        origem = current_dir
        destino = review_path

        dataFrame.shutil.move(current_dir, review_path)
        

if __name__ == "__main__":
    # Exemplo de uso: Hollow Knight (AppID 367520)
    APP_ID = 1196590
    scraper = SteamReviewScraper(app_id=APP_ID, language='brazilian', max_reviews=500)
    
    # Executa a coleta
    dados = scraper.fetch_reviews()
    
    # Converte para DataFrame do Pandas para facilitar manipulação
    df = pd.DataFrame(dados)
    
    print("\nColeta finalizada!")
    print(f"Total de reviews processadas com sucesso: {len(df)}")
    
    if not df.empty:
        # Salva em CSV
        df.to_csv(f'steam_reviews_{APP_ID}_clean.csv', index=False)
        print("Amostra dos dados limpos:")
        print(df[['voted_up', 'clean_text']].head())

    review_path = None

    if review_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            review_path = os.path.join(current_dir,"..","data","reviews_raw")

    # Garante que a pasta 'data' exista
    os.makedirs(os.path.dirname(review_path), exist_ok=True)

    shutil.move(f'steam_reviews_{APP_ID}_clean.csv', review_path)


