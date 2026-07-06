# Instagram Auto-Post

Автоматическая публикация исторических и научных фактов в Instagram.
Генерация Reels через Agnes AI API, публикация через Meta Graph API.

## Структура проекта

```
instagram-autopost/
├── src/
│   ├── config.py                  # Конфигурация (env vars)
│   ├── content_generator.py       # Факты, captions, генерация контента
│   ├── agnes_client.py            # Клиент Agnes AI API (генерация видео)
│   └── post_to_instagram.py       # Основной скрипт публикации
├── data/
│   └── facts.json                 # База фактов по категориям
├── .github/workflows/
│   └── publish.yml                # GitHub Actions (ежедневный запуск)
├── .env.example                   # Шаблон переменных окружения
└── requirements.txt               # Python-зависимости
```

## Pipeline (generate → validate → upload → publish → verify)

1. **generate** — выбор случайного факта из `data/facts.json` (с защитой от дублей)
2. **validate** — проверка полей факта (title, text) перед отправкой
3. **upload** — генерация медиа:
   - Reels (90%): видео через Agnes AI API
   - Image posts (10%): генерация картинки через Pillow + загрузка на Cloudinary
4. **publish** — отправка в Instagram через Meta Graph API
5. **verify** — проверка статуса опубликованного поста

## Установка

```bash
pip install -r requirements.txt
cp .env.example .env
# заполнить .env реальными ключами
```

## Secrets (GitHub Actions)

Обязательные:

| Secret | Описание |
|--------|----------|
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived токен Meta Graph API (60 дней) |
| `INSTAGRAM_USER_ID` | Instagram Business/Creator Account ID |
| `AGNES_API_KEY` | API-ключ Agnes AI для генерации видео |

Опциональные:

| Secret | Описание |
|--------|----------|
| `CLOUDINARY_API_KEY` | Cloudinary API ключ (нужен для image-постов) |
| `CLOUDINARY_API_SECRET` | Cloudinary API секрет |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `PINTEREST_ACCESS_TOKEN` | Pinterest API токен |

**Важно:** `INSTAGRAM_ACCESS_TOKEN` живёт 60 дней. Нужно обновлять вручную или настроить refresh через Meta API.

## Запуск

```bash
# Реальный запуск
python src/post_to_instagram.py

# Dry-run (без публикации в Instagram)
python src/post_to_instagram.py --dry-run

# Через env
DRY_RUN=true python src/post_to_instagram.py
```

## Режим dry-run

Не отправляет данные в Instagram API. Показывает:
- какой факт выбран
- caption
- URL сгенерированного видео/изображения
- логирует факт как `dry_run` в published_log.json

## Защита от дублей

После успешной публикации факт записывается в `data/published_log.json`:
```json
{
  "items": [
    {
      "title": "Исчезновение Девятого легиона",
      "post_id": "178956...",
      "media_type": "REELS",
      "status": "published",
      "published_at": "2026-07-06T10:00:00+00:00",
      "permalink": "https://instagram.com/p/..."
    }
  ]
}
```

Факт не будет выбран повторно, пока не будет очищен лог.

## Типовые ошибки и отладка

| Проблема | Что проверять |
|----------|---------------|
| `Missing: INSTAGRAM_ACCESS_TOKEN` | Не задан токен в .env или GitHub Secrets |
| `Instagram API 400` | Проверить токен (не истёк ли 60 дней), формат caption |
| `Instagram API 401` | Токен отозван или невалиден |
| `Instagram API 403` | Нет прав на media публикацию |
| Reels не генерируется | Проверить `AGNES_API_KEY` и баланс Agnes |
| Image post пропущен | Cloudinary secrets не настроены (нормально, если только Reels) |
| Факты кончились | Добавить новые в `data/facts.json` или очистить `published_log.json` |

## Расширение

Архитектура подготовлена для:
- **Reels**: отдельный путь — `src/post_to_instagram.py:run()` → post_type == 'reel'
- **Image posts**: отдельный путь — post_type == 'post'
- **SEO-капшены**: расширить `ContentGenerator.generate_caption()` под ключи/хэштеги
- **Caption AI**: добавить провайдер в `generate_caption()` без изменения пайплайна
