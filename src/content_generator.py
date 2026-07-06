import json
import random
import requests
import os
import re
from pathlib import Path
from config import Config


class ContentGenerator:
    def __init__(self):
        self.facts_file = Path(Config.DATA_DIR) / "facts.json"
        self.facts = self._load_facts()

    def _load_facts(self):
        if not self.facts_file.exists():
            raise FileNotFoundError(
                f"facts.json not found at {self.facts_file}. "
                "Create it with categories and facts (see .env.example for format)."
            )
        with open(self.facts_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_facts(self):
        self.facts_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.facts_file, "w", encoding="utf-8") as f:
            json.dump(self.facts, f, ensure_ascii=False, indent=2)

    def get_random_fact(self, exclude_list=None):
        exclude_list = exclude_list or []
        all_facts = [f for cat in self.facts.values() for f in cat]
        available = [f for f in all_facts if f["title"] not in exclude_list]
        return random.choice(available) if available else None

    def generate_caption(self, fact, post_type="post"):
        style = random.choice(["question", "statement", "humor", "hook"])

        hooks = {
            "question": ("❓ А вы знали?", "А вы слышали что-то подобное? Пишите в комментариях!"),
            "humor": ("😱 Вот это поворот!", "Представьте себе эту картину — напишите в комментариях, что бы вы сделали?"),
            "hook": ("🔥 Это изменит ваше представление!", "Теперь вы знаете то, что знают единицы. Делитесь с друзьями!"),
            "statement": ("📌 Малоизвестный факт", "Как вам такой факт? Ставьте 👍 если было интересно!"),
        }
        hook, question = hooks.get(style, hooks["statement"])

        tags_str = " ".join(fact.get("tags", []))

        if post_type == "reel":
            return (
                f"🔥 {fact['title']}\n\n"
                f"{fact['text']}\n\n"
                f"{question} 👇\n\n"
                f"{tags_str}\n\n"
                f"#история #факты #загадки #тайны #познавательно #reels"
            )
        else:
            return (
                f"📜 {fact['title']}\n\n"
                f"{fact['text']}\n\n"
                f"{hook}\n\n"
                f"{question}\n\n"
                f"{tags_str}\n\n"
                f"#история #интересныефакты #наука #познавательно #пост"
            )


def scrape_youtube_facts():
    """Парсинг видео автора для наполнения facts.json (опционально)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None

    channels = [
        "https://www.youtube.com/@UCBwMQht541r-bxpy-wPSLpw",
        "https://www.youtube.com/@aleks-x2y9p",
    ]

    facts = []
    for channel_url in channels:
        try:
            resp = requests.get(
                channel_url, timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            titles = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"', resp.text)
            for t in titles[:20]:
                if t and len(t) > 10:
                    facts.append(t)
        except Exception as e:
            print(f"Error scraping {channel_url}: {e}")

    return facts
