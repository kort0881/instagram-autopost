#!/usr/bin/env python3
import os
import sys
import json
import random
import time
import requests
from pathlib import Path
from datetime import datetime
from io import BytesIO
from config import Config
from content_generator import ContentGenerator
from agnes_client import AgnesClient


class InstagramPoster:
    CATEGORY_IMAGES = {
        "historical": "ancient+history+archaeology",
        "science": "science+technology+discovery",
        "mystery": "mysterious+dark+paranormal",
        "archaeology": "excavation+ruins+artifacts",
        "psychology": "brain+mind+consciousness",
        "anatomy": "human+body+anatomy",
    }

    def __init__(self):
        Config.validate()
        self.config = Config()
        self.generator = ContentGenerator()
        self.agnes = AgnesClient()
        self.base_url = "https://graph.facebook.com/v18.0"
        self.log_file = Path(Config.DATA_DIR) / 'published_log.json'
        self.published = self._load_log()
        self.dry_run = False

    def _load_log(self):
        if self.log_file.exists():
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"reels": [], "posts": []}

    def _save_log(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.published, f, ensure_ascii=False, indent=2)

    def _generate_post_image(self, fact):
        """Генерация изображения для поста: красим фон, накладываем текст"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import textwrap

            # Определяем цвет фона по категории
            colors = {
                "historical": (45, 55, 72),
                "science": (30, 60, 80),
                "mystery": (25, 20, 35),
                "archaeology": (55, 45, 30),
                "psychology": (40, 35, 55),
                "anatomy": (50, 30, 35),
            }
            # Определяем категорию факта
            category = "historical"
            for cat_key in colors:
                if any(tag in fact.get('tags', []) for tag in [f"#{cat_key}", f"#{cat_key[:4]}"]):
                    category = cat_key
                    break

            bg_color = colors.get(category, (30, 30, 40))
            img = Image.new('RGB', (1080, 1080), bg_color)
            draw = ImageDraw.Draw(img)

            # Пробуем шрифт
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            font = None
            for fp in font_paths:
                if Path(fp).exists():
                    font = ImageFont.truetype(fp, 42)
                    break
            if not font:
                font = ImageFont.load_default()

            # Заголовок
            title = fact['title'][:120]
            lines = textwrap.wrap(title, width=25)
            y = 150
            for line in lines[:4]:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
                draw.text(((1080 - tw) // 2, y), line, fill=(255, 255, 255), font=font)
                y += 55

            # Текст факта
            y += 40
            body_font = ImageFont.truetype(font_paths[1] if len(font_paths) > 1 and Path(font_paths[1]).exists() else font_paths[0], 32) \
                if Path(font_paths[1]).exists() else ImageFont.load_default()
            text_lines = textwrap.wrap(fact['text'], width=35)
            for line in text_lines[:12]:
                bbox = draw.textbbox((0, 0), line, font=body_font)
                tw = bbox[2] - bbox[0]
                draw.text(((1080 - tw) // 2, y), line, fill=(220, 220, 220), font=body_font)
                y += 40

            # Сохраняем
            output_path = Path(Config.POSTS_DIR) / f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, quality=95)
            return str(output_path)

        except ImportError:
            print("⚠️ Pillow не установлен. Картинка не сгенерирована.")
            return None
        except Exception as e:
            print(f"⚠️ Ошибка генерации изображения: {e}")
            return None

    def _upload_to_cloudinary(self, image_path):
        if not Config.CLOUDINARY_CLOUD_NAME:
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
            print(f"☁️ Cloudinary: {url}")
            return url
        except Exception as e:
            print(f"⚠️ Cloudinary error: {e}")
            return None

    def _upload_to_imgbb(self, image_path):
        return None

    def _get_image_url(self, image_path):
        """Получить публичный URL для изображения через доступные хостинги"""
        # 1. Cloudinary
        if Config.CLOUDINARY_CLOUD_NAME:
            url = self._upload_to_cloudinary(image_path)
            if url:
                return url
        return None

    def _publish_media(self, media_url, caption, media_type='REELS'):
        is_video = media_type in ('VIDEO', 'REELS')
        payload = {
            "media_type": media_type,
            "caption": caption,
            "access_token": Config.INSTAGRAM_ACCESS_TOKEN
        }
        payload["video_url" if is_video else "image_url"] = media_url

        print(f"  → Создание контейнера ({media_type})...")
        container = requests.post(
            f"{self.base_url}/{Config.INSTAGRAM_USER_ID}/media",
            data=payload,
            timeout=60
        )
        if not container.ok:
            print(f"  ❌ Ошибка создания контейнера: {container.status_code}")
            print(f"  🔍 Ответ: {container.text}")
            container.raise_for_status()

        creation_id = container.json().get('id')
        if not creation_id:
            raise Exception(f"Нет id в ответе на создание контейнера: {container.json()}")
        print(f"  ✅ Контейнер создан: {creation_id}")

        # Для видео — ждём обработки Instagram
        if is_video:
            wait = getattr(Config, 'VIDEO_PUBLISH_DELAY', 30)
            print(f"  ⏳ Ожидание {wait}с для обработки видео Instagram...")
            time.sleep(wait)

        print(f"  → Публикация контейнера {creation_id}...")
        publish = requests.post(
            f"{self.base_url}/{Config.INSTAGRAM_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": Config.INSTAGRAM_ACCESS_TOKEN},
            timeout=60
        )
        if not publish.ok:
            print(f"  ❌ Ошибка публикации: {publish.status_code}")
            print(f"  🔍 Ответ: {publish.text}")
            publish.raise_for_status()

        result = publish.json()
        print(f"  ✅ Опубликовано: {result.get('id')}")
        return result

    def run(self):
        print(f"🚀 Запуск {datetime.now()}")

        # Чередование: 90% reels, 10% posts (посты только если есть Cloudinary)
        post_type = random.choices(['reel', 'post'], weights=[0.9, 0.1])[0]

        exclude = self.published.get('reels', []) + self.published.get('posts', [])
        fact = self.generator.get_random_fact(exclude)
        if not fact:
            print("❌ Нет новых фактов. Сброс лога.")
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
                print(f"📹 Видео: {video_url}")
                if not self.dry_run:
                    self._publish_media(video_url, caption, 'REELS')
                else:
                    print("🔍 [Dry-run] Публикация отключена.")
                    print(f"   Caption: {caption[:300]}...")
                    print(f"   Video URL: {video_url}")
            except Exception as e:
                print(f"❌ Ошибка Reels: {e}")
                return
        else:
            print("📸 Генерация изображения для поста...")
            image_path = self._generate_post_image(fact)

            if image_path:
                public_url = self._get_image_url(image_path)

                if public_url:
                    try:
                        if not self.dry_run:
                            self._publish_media(public_url, caption, 'IMAGE')
                            print(f"✅ Пост опубликован")
                        else:
                            print("🔍 [Dry-run] Публикация отключена.")
                            print(f"   Caption: {caption[:300]}...")
                            print(f"   Image URL: {public_url}")
                    except Exception as e:
                        print(f"❌ Ошибка публикации: {e}")
                        return
                else:
                    print("⚠️ Нет хостинга для изображения. Пост пропущен.")
                    print("📝 Настрой Cloudinary Secrets для загрузки изображений")
                    return
            else:
                print("⚠️ Не удалось сгенерировать изображение. Пост пропущен.")
                return

        self.published.setdefault(post_type + 's', []).append(fact['title'])
        self._save_log()
        print(f"✅ Готово: {fact['title']}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or os.getenv('DRY_RUN', 'false').lower() == 'true'
    poster = InstagramPoster()
    poster.dry_run = dry_run
    if dry_run:
        print("🔍 Режим dry-run — публикация в Instagram отключена")
    poster.run()
