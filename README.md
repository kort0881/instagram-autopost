# Instagram Auto-Post

Автоматическая публикация исторических и научных Reels в Instagram.

**Архитектура:** `fact → DeepSeek LLM → Agnes AI video → Instagram`

DeepSeek — "мозг" системы: генерирует hook, script, caption, hashtags.
Instagram API — публикует готовый контент.

## Pipeline

```
fact selector → DeepSeek LLM → Agnes video → Instagram publish → verify
                     │
                     └→ structured JSON: {topic, hook, script, caption,
                                           hashtags, visual_prompt, category}
```

1. **Выбор факта** — случайный факт из `data/facts.json` (с защитой от дублей)
2. **DeepSeek LLM** — генерирует Reels-пакет (structured JSON):
   - `hook` — цепляющий хук для первых секунд видео
   - `script` — сценарий Reels
   - `caption` — готовая подпись к посту
   - `hashtags` — релевантные хэштеги
   - `visual_prompt` — описание визуального ряда для генерации видео
   - `category` — категория факта
3. **Agnes AI** — генерация вертикального видео по visual_prompt
4. **Instagram API** — публикация Reels через Meta Graph API
5. **Verify** — проверка статуса опубликованного поста

## Структура

```
instagram-autopost/
├── src/
│   ├── config.py                  # Конфигурация (env vars)
│   ├── content_generator.py       # Выбор факта из facts.json
│   ├── llm_client.py              # DeepSeek LLM клиент (OpenAI-compatible)
│   ├── agnes_client.py            # Генерация видео через Agnes AI
│   └── post_to_instagram.py       # Основной пайплайн публикации
├── data/
│   ├── facts.json                 # База фактов по категориям
│   └── published_log.json         # Лог опубликованных фактов
├── .github/workflows/
│   └── publish.yml                # GitHub Actions (ежедневный запуск)
├── .env.example
└── requirements.txt
```

## Установка

```bash
pip install -r requirements.txt
cp .env.example .env
# заполнить .env
```

## Secrets (GitHub Actions)

| Secret | Обязательный | Описание |
|--------|-------------|----------|
| `INSTAGRAM_ACCESS_TOKEN` | Да (для публикации) | Long-lived токен Meta Graph API (60 дней) |
| `INSTAGRAM_USER_ID` | Да | Instagram Business/Creator Account ID |
| `AGNES_API_KEY` | Да | API-ключ Agnes AI для генерации видео |
| `DEEPSEEK_API_KEY` | Нет (mock-mode) | API-ключ DeepSeek для LLM генерации контента |

Если `DEEPSEEK_API_KEY` не задан — LLM работает в mock-режиме (шаблонный вывод).
Также можно явно установить `SOCIALPOSTER` как fallback для `INSTAGRAM_ACCESS_TOKEN`.

## Режимы запуска

### 1. Подготовка без публикации (prepare-only)

```bash
PREPARE_ONLY=true python src/post_to_instagram.py
```
- DeepSeek (или mock) генерирует Reels-пакет
- Agnes и Instagram **не вызываются**
- Результат логируется в `published_log.json` со статусом `prepared`

### 2. Dry-run

```bash
python src/post_to_instagram.py --dry-run
# или
DRY_RUN=true python src/post_to_instagram.py
```
- Всё кроме Instagram API: DeepSeek + Agnes видео
- В лог пишется со статусом `dry_run`

### 3. Полный запуск

```bash
python src/post_to_instagram.py
```

## Защита от дублей

Каждый факт логируется в `data/published_log.json`:
```json
{
  "items": [
    {
      "title": "Исчезновение Девятого легиона",
      "post_id": "178956...",
      "media_type": "REELS",
      "status": "published",
      "published_at": "2026-07-06T10:00:00+00:00",
      "permalink": "...",
      "llm": {
        "hook": "Целый легион исчез!",
        "script": "117 год...",
        "hashtags": ["#история", "#рим"],
        "visual_prompt": "Туманный лес, римские доспехи",
        "category": "historical"
      }
    }
  ]
}
```

Факт не будет выбран повторно, пока лог не очищен.

## Image-посты

По умолчанию **отключены**. Система публикует только Reels.
Чтобы включить: `ENABLE_IMAGE_POSTS=true` + настроить Cloudinary secrets.

## Модели DeepSeek

| Модель | Переменная | Назначение |
|--------|-----------|------------|
| `deepseek-v4-flash` | `DEEPSEEK_MODEL` (default) | Быстрый и дешёвый |
| `deepseek-v4-pro` | `DEEPSEEK_MODEL=deepseek-v4-pro` | Более качественный |

DeepSeek API совместим с OpenAI SDK:

```python
from openai import OpenAI
client = OpenAI(
    api_key="sk-...",
    base_url="https://api.deepseek.com/v1",
)
resp = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "..."}],
    response_format={"type": "json_object"},
)
```

## Типовые ошибки

| Проблема | Что делать |
|----------|------------|
| `Missing: INSTAGRAM_ACCESS_TOKEN` | Добавить секрет в GitHub |
| `DEEPSEEK_API_KEY not set` | Не критично — LLM работает в mock |
| Reels не генерируется | Проверить `AGNES_API_KEY` и баланс |
| Факты кончились | Добавить в `data/facts.json` или очистить `published_log.json` |

## Что остаётся сделать вручную

1. Добавить `DEEPSEEK_API_KEY` в GitHub Secrets (для реального LLM, не mock)
2. Обновлять `INSTAGRAM_ACCESS_TOKEN` раз в 60 дней (токен протухает)
3. Наполнять `data/facts.json` новыми фактами
