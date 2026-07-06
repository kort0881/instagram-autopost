import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Instagram / Meta Graph API ────────────────────────────────
    INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN') or os.getenv('SOCIALPOSTER')
    INSTAGRAM_USER_ID = os.getenv('INSTAGRAM_USER_ID')

    # ── DeepSeek LLM ─────────────────────────────────────────────
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'deepseek')
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-v4-flash')

    # ── Режимы ──────────────────────────────────────────────────────
    # PREPARE_ONLY — подготовить всё, но не публиковать (ни Agnes, ни Instagram)
    PREPARE_ONLY = os.getenv('PREPARE_ONLY', '').lower() in ('true', '1', 'yes')
    # LLM_DISABLED — не вызывать DeepSeek даже если ключ есть
    LLM_DISABLED = os.getenv('LLM_DISABLED', '').lower() in ('true', '1', 'yes')

    # ── Agnes AI (генерация Reels видео) ────────────────────────────
    AGNES_API_KEY = os.getenv('AGNES_API_KEY')

    # ── Cloudinary (опционально — image-posts отключены по умолчанию) ──
    ENABLE_IMAGE_POSTS = os.getenv('ENABLE_IMAGE_POSTS', 'false').lower() in ('true', '1', 'yes')
    CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY', '')
    CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET', '')
    CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME', '')

    # ── Тайминги ─────────────────────────────────────────────────
    VIDEO_PUBLISH_DELAY = int(os.getenv('VIDEO_PUBLISH_DELAY', '30'))

    # ── Пути ─────────────────────────────────────────────────────
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, 'data')

    @classmethod
    def validate(cls):
        """Проверка обязательных переменных.

        В PREPARE_ONLY режиме — только предупреждения, не ошибка.
        В обычном режиме — обязательны: INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_USER_ID, AGNES_API_KEY.
        """
        missing = []
        if not cls.INSTAGRAM_ACCESS_TOKEN:
            missing.append('INSTAGRAM_ACCESS_TOKEN')
        if not cls.INSTAGRAM_USER_ID:
            missing.append('INSTAGRAM_USER_ID')
        if not cls.AGNES_API_KEY:
            missing.append('AGNES_API_KEY')

        if not missing:
            return True

        if cls.PREPARE_ONLY:
            import logging
            log = logging.getLogger("instagram")
            log.warning("⚠️  Missing secrets (PREPARE_ONLY — ignoring): %s", ', '.join(missing))
            return False

        raise ValueError(f"Missing required env: {', '.join(missing)}")
