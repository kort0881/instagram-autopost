#!/usr/bin/env python3
import requests
import time
from config import Config


class AgnesClient:
    BASE_URL = "https://apihub.agnes-ai.com/v1"

    def __init__(self):
        self.api_key = Config.AGNES_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate_video(self, text, title=None, voice=None, mode="manuscript"):
        """
        Генерация видео через Agnes AI API.
        Agnes использует асинхронную генерацию:
        1. POST /video/generations → получаем task_id
        2. GET /video/generations/{task_id} → ждём status=completed
        3. Возвращаем URL готового видео
        """
        payload = {
            "model": "agnes-video-v2.0",
            "prompt": f"{title or 'Исторический факт'}. {text}",
            "duration": 30,
            "style": "mystery",
            "size": "1080x1920"
        }

        print(f"  → Отправка запроса на генерацию видео...")
        response = requests.post(
            f"{self.BASE_URL}/video/generations",
            headers=self.headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()

        task_id = data.get('task_id') or data.get('id')
        if not task_id:
            raise Exception(f"Нет task_id в ответе: {data}")

        print(f"  → Задача создана: {task_id}. Ожидание завершения...")

        # Polling статуса
        max_attempts = 30
        for attempt in range(max_attempts):
            time.sleep(5)
            try:
                status_resp = requests.get(
                    f"{self.BASE_URL}/video/generations/{task_id}",
                    headers=self.headers,
                    timeout=30
                )
                if not status_resp.ok:
                    print(f"  ⚠️ Статус {status_resp.status_code}, продолжаем ожидание...")
                    continue

                status_data = status_resp.json()
                status = status_data.get('status', 'unknown')
                progress = status_data.get('progress', 0)

                print(f"  ⏳ Статус: {status}, прогресс: {progress}%")

                if status == 'completed':
                    # Ищем URL видео
                    video_url = (
                        status_data.get('url')
                        or status_data.get('video_url')
                        or (status_data.get('data') or [{}])[0].get('url')
                        or (status_data.get('output') or {}).get('video_url')
                    )
                    if video_url:
                        print(f"  ✅ Видео готово: {video_url}")
                        return video_url
                    else:
                        raise Exception(f"Видео готово, но URL не найден: {status_data}")

                elif status in ('failed', 'error'):
                    raise Exception(f"Генерация видео не удалась: {status_data.get('error', status_data)}")

            except requests.Timeout:
                print(f"  ⏳ Таймаут при проверке статуса, попытка {attempt+1}/{max_attempts}")
                continue

        raise Exception(f"Видео не сгенерировалось за {max_attempts * 5} секунд")


if __name__ == "__main__":
    import os
    os.environ["AGNES_API_KEY"] = "test"
    print(AgnesClient().generate_video("Тест"))
