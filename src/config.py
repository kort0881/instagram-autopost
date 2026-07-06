import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Instagram
    # Читаем INSTAGRAM_ACCESS_TOKEN; если пусто — fallback на SOCIALPOSTER (старое имя)
    INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN') or os.getenv('SOCIALPOSTER')
    INSTAGRAM_USER_ID = os.getenv('INSTAGRAM_USER_ID')

    # Задержка перед публикацией видео (сек) — пока Instagram обработает файл
    VIDEO_PUBLISH_DELAY = int(os.getenv('VIDEO_PUBLISH_DELAY', '30'))

    # Agnes
    AGNES_API_KEY = os.getenv('AGNES_API_KEY')

    # Pinterest (опционально)
    PINTEREST_ACCESS_TOKEN = os.getenv('PINTEREST_ACCESS_TOKEN', '')

    # Cloudinary (опционально)
    CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY', '')
    CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET', '')
    CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME', '')

    # Пути
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    POSTS_DIR = os.path.join(BASE_DIR, 'content', 'posts')
    CACHE_DIR = os.path.join(DATA_DIR, 'images_cache')

    @classmethod
    def validate(cls):
        missing = []
        if not cls.INSTAGRAM_ACCESS_TOKEN:
            missing.append('INSTAGRAM_ACCESS_TOKEN')
        if not cls.INSTAGRAM_USER_ID:
            missing.append('INSTAGRAM_USER_ID')
        if not cls.AGNES_API_KEY:
            missing.append('AGNES_API_KEY')
        if missing:
            raise ValueError(f"Missing: {', '.join(missing)}")
        return True
