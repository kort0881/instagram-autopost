#!/usr/bin/env python3
"""LLM Client — DeepSeek API (OpenAI-compatible).

Генерирует structured JSON для Reels-пакета:
  topic, hook, script, caption, hashtags, visual_prompt, category

Поддерживает:
  - deepseek-v4-flash (default, быстрый и дешёвый)
  - deepseek-v4-pro (optional через env)
  - Mock-режим (LLM_DISABLED=true / PREPARE_ONLY=true) — без ключа
"""
import json
import os
import logging
from typing import Optional

log = logging.getLogger("instagram")

# ── system prompt для structured JSON ───────────────────────────────
SYSTEM_PROMPT = """Ты — копирайтер для Instagram Reels по истории, науке и загадкам. Твоя задача — получить факт и превратить его в готовый Reels-пакет. Отвечай ТОЛЬКО в формате JSON, без лишнего текста.

Поля JSON:
  "topic": str — тема (заголовок факта)
  "hook": str — цепляющий хук для первых 3 секунд видео (1 предложение)
  "script": str — сценарий Reels (2-5 предложений, разговорный русский)
  "caption": str — подпись к посту (с хуком, вопросом и призывом)
  "hashtags": [str] — 5-10 хэштегов (с #, релевантные теме)
  "visual_prompt": str — описание визуального ряда для генерации видео
  "category": str — категория факта (historical|science|mystery|archaeology|psychology|anatomy)

Пример ответа:
{"topic": "Исчезновение Девятого легиона", "hook": "Целый легион Рима исчез без следа!", "script": "117 год. Девятый легион отправляется в Британию и бесследно исчезает. Ни записей, ни выживших. До сих пор это одна из главных загадок древнего мира.", "caption": "Целый легион исчез! А вы верите? Пишите в комментариях!", "hashtags": ["#история", "#рим", "#загадки", "#факты", "#археология"], "visual_prompt": "Туманный лес, римские доспехи, древняя карта Британии", "category": "historical"}"""


class LLMClient:
    """OpenAI-compatible клиент для DeepSeek API."""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "deepseek").lower()
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.disabled = os.getenv("LLM_DISABLED", "").lower() in ("true", "1", "yes")
        self.prepare_only = os.getenv("PREPARE_ONLY", "").lower() in ("true", "1", "yes")

        # Если нет ключа — работаем в mock-режиме
        self.mock = self.disabled or self.prepare_only or not self.api_key
        if self.mock:
            log.info("  🤖 LLM mock mode — DeepSeek не вызывается (нет ключа или PREPARE_ONLY)")

    def generate_reel_package(self, fact: dict) -> dict:
        """Сгенерировать Reels-пакет из факта.

        Возвращает dict с полями: topic, hook, script, caption, hashtags, visual_prompt, category.
        В mock-режиме возвращает шаблонный пакет.
        """
        if self.mock:
            return self._mock_package(fact)

        try:
            import openai
        except ImportError:
            log.warning("  ⚠️ openai не установлен, fallback на mock")
            return self._mock_package(fact)

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=f"{self.base_url}/v1",
        )

        user_prompt = (
            f"Факт:\n"
            f"- Заголовок: {fact.get('title', 'Без названия')}\n"
            f"- Текст: {fact.get('text', '')}\n"
            f"- Теги: {', '.join(fact.get('tags', []))}\n\n"
            f"Сгенерируй Reels-пакет в JSON."
        )

        log.info("  → LLM запрос (%s, model=%s)...", self.provider, self.model)
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=2000,
                timeout=60,
            )
        except Exception as e:
            log.warning("  ⚠️ LLM запрос не удался: %s, fallback на mock", e)
            return self._mock_package(fact)

        content = resp.choices[0].message.content.strip() if resp.choices else ""
        if not content:
            log.warning("  ⚠️ LLM вернул пустой ответ, fallback на mock")
            return self._mock_package(fact)

        try:
            package = json.loads(content)
        except json.JSONDecodeError:
            log.warning("  ⚠️ LLM вернул невалидный JSON, fallback на mock")
            log.debug("  Ответ LLM: %s", content[:500])
            return self._mock_package(fact)

        # гарантируем все поля
        package.setdefault("topic", fact.get("title", ""))
        package.setdefault("hook", "")
        package.setdefault("script", fact.get("text", ""))
        package.setdefault("caption", "")
        package.setdefault("hashtags", fact.get("tags", []))
        package.setdefault("visual_prompt", "")
        package.setdefault("category", "historical")

        log.info("  ✅ LLM ответ получен (topic=%s, hashtags=%d)", package["topic"], len(package["hashtags"]))
        return package

    # ── mock ─────────────────────────────────────────────────────────

    def _mock_package(self, fact: dict) -> dict:
        """Шаблонный пакет без вызова API."""
        title = fact.get("title", "")
        text = fact.get("text", "")
        tags = fact.get("tags", [])

        # категория из тегов
        categories = ["historical", "science", "mystery", "archaeology", "psychology", "anatomy"]
        category = "historical"
        for tag in tags:
            tag_clean = tag.lstrip("#").lower()
            if tag_clean in categories:
                category = tag_clean
                break
            if tag_clean in ("история", "рим", "русь", "средневековье", "викинги", "россия", "ссср", "революция"):
                category = "historical"
            elif tag_clean in ("наука", "биология", "животные", "медицина", "космос"):
                category = "science"

        package = {
            "topic": title,
            "hook": f"А вы знали? {title[:80]}..." if len(title) > 80 else f"А вы знали? {title}!",
            "script": text,
            "caption": (
                f"🔥 {title}\n\n"
                f"{text[:300]}{'...' if len(text) > 300 else ''}\n\n"
                f"👇 А вы слышали это раньше? Пишите в комментариях!\n\n"
                f"{' '.join(tags)}\n\n"
                f"#история #факты #загадки #тайны #познавательно #reels"
            ),
            "hashtags": tags if tags else ["#история", "#факты", "#загадки"],
            "visual_prompt": f"{title}. {text[:200]}",
            "category": category,
        }
        log.info("  🤖 Mock пакет (topic=%s, category=%s)", package["topic"], package["category"])
        return package
