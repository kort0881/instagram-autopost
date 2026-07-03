# Instagram Auto-Post

Автоматическая публикация исторических и научных фактов в Instagram.

## Структура

- `src/config.py` — конфигурация
- `src/content_generator.py` — генерация контента и работа с facts.json
- `src/agnes_client.py` — клиент для Agnes API (генерация видео Reels)
- `src/post_to_instagram.py` — основной скрипт публикации
- `data/facts.json` — база фактов (история, наука, загадки, археология и др.)

## Установка

```bash
pip install -r requirements.txt
cp .env.example .env
# заполнить .env
```

## Secrets (GitHub)

- `INSTAGRAM_ACCESS_TOKEN` — токен Meta (60 дней)
- `INSTAGRAM_USER_ID` — ID Instagram-аккаунта
- `AGNES_API_KEY` — ключ Agnes AI
- `PINTEREST_ACCESS_TOKEN` — (опционально)
- `CLOUDINARY_API_KEY/SECRET/CLOUD_NAME` — (опционально)

## Запуск

```bash
python src/post_to_instagram.py
```
