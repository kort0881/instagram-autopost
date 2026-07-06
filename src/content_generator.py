import json
import random
from pathlib import Path
from config import Config


class ContentGenerator:
    def __init__(self):
        self.facts_file = Path(Config.DATA_DIR) / "facts.json"
        self.facts = self._load_facts()

    def _load_facts(self):
        if not self.facts_file.exists():
            raise FileNotFoundError(
                f"facts.json not found at {self.facts_file}. "
                "Create it with categories and facts."
            )
        with open(self.facts_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_random_fact(self, exclude_list=None):
        exclude_list = exclude_list or []
        all_facts = [f for cat in self.facts.values() for f in cat]
        available = [f for f in all_facts if f["title"] not in exclude_list]
        return random.choice(available) if available else None
