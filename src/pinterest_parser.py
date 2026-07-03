#!/usr/bin/env python3
import requests
import json
import re
import time
from pathlib import Path


class PinterestParser:
    """Парсинг изображений из Pinterest по ключевым словам."""

    BASE_URL = "https://ru.pinterest.com"

    def __init__(self, cache_dir="data/images_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def scrape_board(self, username, board_name, limit=10):
        """Парсинг изображений с доски Pinterest."""
        url = f"{self.BASE_URL}/{username}/{board_name}/"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()

            pins = []
            patterns = [
                r'pinImages\":\[([^\]]+)\]',
                r'imageLargeUrl\":\"([^\"]+)\"',
                r'originalUrl\":\"([^\"]+)\"',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, resp.text)
                for m in matches[:limit]:
                    clean_url = m.replace('\\/', '/').replace('\\', '').replace('"', '')
                    if clean_url.startswith('http') and not clean_url.endswith('.com/'):
                        pins.append(clean_url)

            return list(dict.fromkeys(pins))[:limit]

        except Exception as e:
            print(f"Pinterest error: {e}")
            return []

    def download_image(self, url, filename=None):
        """Скачать изображение в кэш"""
        if not filename:
            filename = url.split('/')[-1].split('?')[0] or f"pin_{int(time.time())}.jpg"

        filepath = self.cache_dir / filename
        if filepath.exists():
            return str(filepath)

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            filepath.write_bytes(resp.content)
            return str(filepath)
        except Exception as e:
            print(f"Download error {url[:50]}: {e}")
            return None

    def search_pins(self, query, limit=5):
        """Поиск пинов по ключевому слову (публичный поиск)"""
        url = f"{self.BASE_URL}/search/pins/?q={query}"
        try:
            resp = self.session.get(url, timeout=15)
            images = re.findall(r'https://i\.pinimg\.com/[^\s\"\'<>]+\.(?:jpg|png|webp)', resp.text)
            return list(dict.fromkeys(images))[:limit]
        except:
            return []


if __name__ == "__main__":
    parser = PinterestParser()
    images = parser.scrape_board("alexanderyurievich88", "history", limit=5)
    print(f"Found {len(images)} images")
    for img in images[:3]:
        print(f"  {img}")
