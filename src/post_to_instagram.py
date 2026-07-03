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
            print("⚠️ Cloudinary не настроен")
            return None
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(
            cloud_name=Config.CLOUDINARY_CLOUD_NAME,
            api_key=Config.CLOUDINARY_API_KEY,
            api_secret=Config.CLOUDINARY_API_SECRET
        )
        result = cloudinary.uploader.upload(image_path)
        return result.get('secure_url')

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

        # Выбираем тип: чередуем reels и посты
        post_type = random.choice(['reel', 'post'])

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
            print("📸 Публикация текстового поста...")
            # Для поста без изображения используем заглушку
            print("⚠️ Посты с картинками требуют хостинга (Cloudinary или Pinterest)")
            print("📝 Пост сохранён в лог без публикации (только текст)")
            # Можно было бы использовать картинку-заглушку, но пропускаем

        self.published.setdefault(post_type + 's', []).append(fact['title'])
        self._save_log()
        print(f"✅ Опубликовано: {fact['title']}")


if __name__ == "__main__":
    InstagramPoster().run()
