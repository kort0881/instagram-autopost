#!/usr/bin/env python3
import sys
import json
import random
import requests
from pathlib import Path
from datetime import datetime
from config import Config
from content_generator import ContentGenerator
from agnes_client import AgnesClient


class InstagramPoster:
    def __init__(self):
        Config.validate()
        self.config = Config()
        self.generator = ContentGenerator()
        self.agnes = AgnesClient()
        self.base_url = "https://graph.facebook.com/v18.0"
        self.log_file = Path(Config.DATA_DIR) / 'published_log.json'
        self.published = self._load_log()

    def _load_log(self):
        if self.log_file.exists():
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"reels": [], "posts": []}

    def _save_log(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.published, f, ensure_ascii=False, indent=2)

    def _upload_to_cloudinary(self, image_path):
        if not Config.CLOUDINARY_CLOUD_NAME:
            print("⚠️ Cloudinary не настроен — пропускаем загрузку")
            return None
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(
                cloud_name=Config.CLOUDINARY_CLOUD_NAME,
                api_key=Config.CLOUDINARY_API_KEY,
                api_secret=Config.CLOUDINARY_API_SECRET
            )
            result = cloudinary.uploader.upload(
                image_path,
                folder="instagram_autopost",
                resource_type="image"
            )
            url = result.get('secure_url')
            print(f"☁️ Загружено на Cloudinary: {url}")
            return url
        except Exception as e:
            print(f"⚠️ Cloudinary error: {e}")
            return None

    def _fetch_pinterest_image(self, query):
        """Попытка достать картинку из Pinterest по теме факта"""
        try:
            from pinterest_parser import PinterestParser
            parser = PinterestParser(cache_dir=str(Config.CACHE_DIR))
            images = parser.search_pins(query, limit=3)
            if images:
                local_path = parser.download_image(images[0])
                if local_path:
                    return local_path
            return None
        except Exception as e:
            print(f"⚠️ Pinterest error: {e}")
            return None

    def _publish_media(self, media_url, caption, media_type='VIDEO'):
        params = {
            "media_type": media_type,
            "caption": caption,
            "access_token": Config.INSTAGRAM_ACCESS_TOKEN
        }
        params["video_url" if media_type == 'VIDEO' else "image_url"] = media_url

        container = requests.post(
            f"{self.base_url}/{Config.INSTAGRAM_USER_ID}/media",
            params=params,
            timeout=30
        )
        container.raise_for_status()
        creation_id = container.json()['id']

        publish = requests.post(
            f"{self.base_url}/{Config.INSTAGRAM_USER_ID}/media_publish",
            params={"creation_id": creation_id, "access_token": Config.INSTAGRAM_ACCESS_TOKEN},
            timeout=30
        )
        publish.raise_for_status()
        return publish.json()

    def run(self):
        print(f"🚀 Запуск {datetime.now()}")

        # Чередование: 60% reels, 40% posts
        post_type = random.choices(['reel', 'post'], weights=[0.6, 0.4])[0]

        exclude = self.published.get('reels', []) + self.published.get('posts', [])
        fact = self.generator.get_random_fact(exclude)
        if not fact:
            print("❌ Нет новых неопубликованных фактов. Сброс лога.")
            self.published = {"reels": [], "posts": []}
            self._save_log()
            fact = self.generator.get_random_fact()

        caption = self.generator.generate_caption(fact, post_type)

        if post_type == 'reel':
            print("🎬 Генерация Reels...")
            try:
                video_url = self.agnes.generate_video(
                    f"{fact['title']}. {fact['text']}",
                    fact['title']
                )
                print(f"📹 Видео сгенерировано: {video_url}")
                self._publish_media(video_url, caption, 'VIDEO')
            except Exception as e:
                print(f"❌ Ошибка генерации Reels: {e}")
                return
        else:
            print("📸 Публикация поста с изображением...")

            # Пытаемся достать картинку: Pinterest -> Cloudinary -> заглушка
            image_url = None

            # 1. Пробуем Pinterest
            pinterest_image = self._fetch_pinterest_image(fact['title'])
            if pinterest_image:
                print(f"🖼️ Изображение найдено на Pinterest: {pinterest_image}")
                # 2. Загружаем на Cloudinary если настроен
                if Config.CLOUDINARY_CLOUD_NAME:
                    cloud_url = self._upload_to_cloudinary(pinterest_image)
                    if cloud_url:
                        image_url = cloud_url
                else:
                    image_url = pinterest_image

            if image_url:
                try:
                    self._publish_media(image_url, caption, 'IMAGE')
                    print(f"✅ Пост опубликован с изображением")
                except Exception as e:
                    print(f"❌ Ошибка публикации поста: {e}")
                    return
            else:
                print("⚠️ Нет изображения для поста. Публикация отложена.")
                print("📝 Совет: настрой Cloudinary или Pinterest токен в Secrets")

        self.published.setdefault(post_type + 's', []).append(fact['title'])
        self._save_log()
        print(f"✅ Готово: {fact['title']}")


if __name__ == "__main__":
    InstagramPoster().run()
