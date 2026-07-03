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
        Использует эндпоинт /v1/video/generations (OpenAI-совместимый).
        """
        # Пробуем стандартный OpenAI-совместимый эндпоинт для генерации
        # Agnes поддерживает text-to-video через model: agnes-video-*
        payload = {
            "model": "agnes-video-1",
            "prompt": f"{title or 'Исторический факт'}. {text}",
            "duration": 30,
            "style": "mystery"
        }

        if voice:
            payload["voice"] = voice

        # Пробуем разные возможные эндпоинты
        endpoints = [
            f"{self.BASE_URL}/video/generations",
            f"{self.BASE_URL}/images/generations",
            f"{self.BASE_URL}/chat/completions",
        ]

        last_error = None
        for endpoint in endpoints:
            try:
                print(f"  → {endpoint}")
                response = requests.post(
                    endpoint,
                    headers=self.headers,
                    json=payload if "completions" not in endpoint else {
                        "model": "agnes-video-1",
                        "messages": [{"role": "user", "content": f"Создай короткое видео для Instagram Reels на тему: {payload['prompt']}"}]
                    },
                    timeout=30
                )
                if response.ok:
                    data = response.json()
                    # OpenAI-формат: choices[0].message.content или data[0].url
                    if "choices" in data:
                        return data["choices"][0].get("message", {}).get("content", str(data))
                    if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                        return data["data"][0].get("url", str(data))
                    return str(data)
                else:
                    last_error = f"{response.status_code}: {response.text[:200]}"
            except Exception as e:
                last_error = str(e)

        raise Exception(f"Agnes API error: {last_error}")


if __name__ == "__main__":
    # Тест
    import os
    os.environ["AGNES_API_KEY"] = "test"
    print(AgnesClient().generate_video("Тестовый факт"))
