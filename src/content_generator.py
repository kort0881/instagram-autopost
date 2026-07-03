import json
import random
import requests
import os
import re
from pathlib import Path
from config import Config

class ContentGenerator:
    def __init__(self):
        self.facts_file = Path(Config.DATA_DIR) / 'facts.json'
        self.load_facts()

    def load_facts(self):
        if self.facts_file.exists():
            with open(self.facts_file, 'r', encoding='utf-8') as f:
                self.facts = json.load(f)
        else:
            self.facts = self._generate_default_facts()
            self.save_facts()

    def _generate_default_facts(self):
        """Заглушка: 30 фактов должны быть в data/facts.json.
        Если файла нет — создаём базовый набор."""
        import os
        facts_path = Path(Config.DATA_DIR) / 'facts.json'
        facts_path.parent.mkdir(parents=True, exist_ok=True)
        if facts_path.exists():
            with open(facts_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_facts(self):
        self.facts_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.facts_file, 'w', encoding='utf-8') as f:
            json.dump(self.facts, f, ensure_ascii=False, indent=2)

    def get_random_fact(self, exclude_list=[]):
        all_facts = [f for cat in self.facts.values() for f in cat]
        available = [f for f in all_facts if f['title'] not in exclude_list]
        return random.choice(available) if available else None

    def generate_caption(self, fact, post_type='post'):
        style = random.choice(['question', 'statement', 'humor', 'hook'])

        if style == 'question':
            hook = "❓ А вы знали?"
            question = "А вы слышали что-то подобное? Пишите в комментариях!"
        elif style == 'humor':
            hook = "😱 Вот это поворот!"
            question = "Представьте себе эту картину — напишите в комментариях, что бы вы сделали?"
        elif style == 'hook':
            hook = "🔥 Это изменит ваше представление!"
            question = "Теперь вы знаете то, что знают единицы. Делитесь с друзьями!"
        else:
            hook = "📌 Малоизвестный факт"
            question = "Как вам такой факт? Ставьте 👍 если было интересно!"

        if post_type == 'reel':
            return f"""🔥 {fact['title']}

{fact['text']}

{question} 👇

{' '.join(fact.get('tags', []))}

#история #факты #загадки #тайны #познавательно #reels"""
        else:
            return f"""📜 {fact['title']}

{fact['text']}

{hook}

{question}

{' '.join(fact.get('tags', []))}

#история #интересныефакты #наука #познавательно #пост"""


def scrape_youtube_facts():
    """Парсинг видео автора для наполнения facts.json"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None

    channels = [
        "https://www.youtube.com/@UCBwMQht541r-bxpy-wPSLpw",
        "https://www.youtube.com/@aleks-x2y9p"
    ]

    facts = []
    for channel_url in channels:
        try:
            resp = requests.get(channel_url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            titles = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"', resp.text)
            for t in titles[:20]:
                if t and len(t) > 10:
                    facts.append(t)
        except Exception as e:
            print(f"Error scraping {channel_url}: {e}")

    return facts
