import requests
import time
from config import Config

class AgnesClient:
    BASE_URL = "https://api.agnes-ai.com/v1"

    def __init__(self):
        self.api_key = Config.AGNES_API_KEY
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def generate_video(self, text, title=None, voice="ru-RU-SvetlanaNeural", mode="manuscript"):
        payload = {
            "mode": mode,
            "text": text,
            "title": title or "Исторический факт",
            "voice": voice,
            "subtitle": True,
            "style": "mystery"
        }
        response = requests.post(f"{self.BASE_URL}/generate", headers=self.headers, json=payload, timeout=60)
        response.raise_for_status()
        task_id = response.json().get('task_id')
        while True:
            status = requests.get(f"{self.BASE_URL}/status/{task_id}", headers=self.headers).json()
            if status.get('state') == 'completed':
                return status.get('video_url')
            if status.get('state') == 'failed':
                raise Exception("Agnes generation failed")
            time.sleep(5)
