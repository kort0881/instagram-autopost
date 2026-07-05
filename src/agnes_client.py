#!/usr/bin/env python3
import requests
import time
import os
from config import Config


class AgnesClient:
    BASE_URL = "https://apihub.agnes-ai.com"

    def __init__(self):
        self.api_key = Config.AGNES_API_KEY
        if not self.api_key:
            raise ValueError("AGNES_API_KEY не задан в конфиге")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate_video(self, text, title=None, voice=None, mode="manuscript"):
        """
        Генерация короткого вертикального видео (Reels) через Agnes AI API.
        Использует официальный эндпоинт /v1/videos и корректный polling.
        Возвращает URL готового видео.
        """
        # Формируем промпт из заголовка и текста
        prompt = f"{title or 'Исторический факт'}. {text}"

        # Параметры для Reels (вертикальное видео 9:16)
        payload = {
            "model": "agnes-video-v2.0",
            "prompt": prompt,
            "height": 768,          # 768x1152 — стандарт для коротких вертикальных видео
            "width": 1152,
            "num_frames": 241,      # ~10 секунд при 24 fps (8*30+1 = 241)
            "frame_rate": 24,
            # Дополнительные параметры (опционально):
            # "cfg_scale": 7,
            # "seed": 42,
        }

        print(f"  → Отправка запроса на генерацию видео...")
        try:
            response = requests.post(
                f"{self.BASE_URL}/v1/videos",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка при создании задачи: {e}")

        data = response.json()

        # Извлекаем video_id (в ответе может быть поле "id" или "video_id")
        video_id = data.get("video_id") or data.get("id")
        if not video_id:
            raise Exception(f"Не удалось получить video_id из ответа: {data}")

        print(f"  → Задача создана, video_id: {video_id}. Ожидание завершения...")

        # Polling статуса через правильный эндпоинт
        max_attempts = 60           # 60 попыток по 5 секунд = 5 минут
        for attempt in range(max_attempts):
            time.sleep(5)

            status_data = None
            try:
                status_resp = requests.get(
                    f"{self.BASE_URL}/agnesapi",
                    params={"video_id": video_id},
                    headers=self.headers,
                    timeout=30
                )
                if not status_resp.ok:
                    print(f"  ⚠️ Статус {status_resp.status_code}, повторная попытка...")
                    continue
                status_data = status_resp.json()
            except requests.exceptions.Timeout:
                print(f"  ⏳ Таймаут при проверке статуса, попытка {attempt+1}/{max_attempts}")
                continue
            except Exception as e:
                print(f"  ⚠️ Ошибка HTTP/JSON: {e}, повторная попытка...")
                continue

            status = status_data.get("status", "unknown")
            progress = status_data.get("progress", 0)
            print(f"  ⏳ Статус: {status}, прогресс: {progress}%")

            # Успешные статусы
            if status.lower() in ("succeeded", "success", "completed", "done"):
                video_url = (
                    status_data.get("url")
                    or status_data.get("video_url")
                    or status_data.get("remixed_from_video_id")
                    or (status_data.get("output") or {}).get("video_url")
                    or (status_data.get("data") or {}).get("url")
                )
                if video_url:
                    print(f"  ✅ Видео готово: {video_url}")
                    return video_url
                else:
                    print(f"  ❌ Видео готово, но URL не найден: {status_data}")
                    raise Exception(f"Видео готово, но URL не найден")

            # Статусы ошибок
            if status.lower() in ("failed", "error", "cancelled"):
                error_msg = status_data.get("error") or status_data.get("message") or "Неизвестная ошибка"
                raise Exception(f"Генерация видео не удалась: {error_msg}")

            # Иначе статус "queued" или "in_progress" — продолжаем ждать

        raise Exception(f"Видео не сгенерировалось за {max_attempts * 5} секунд (video_id={video_id})")


# Блок для локального тестирования (запустите с реальным API-ключом)
if __name__ == "__main__":
    # Для теста установите переменную окружения AGNES_API_KEY или пропишите в .env
    from dotenv import load_dotenv
    load_dotenv()

    try:
        client = AgnesClient()
        # Тестовый запрос с коротким текстом
        video_url = client.generate_video(
            text="В Древнем Египте кошек бальзамировали и хоронили с почестями.",
            title="Кошки в Египте"
        )
        print(f"🎬 Видео получено: {video_url}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
