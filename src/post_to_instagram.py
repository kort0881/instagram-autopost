#!/usr/bin/env python3
"""Instagram Auto-Post — основной скрипт публикации Reels.

Pipeline: fact selector → DeepSeek LLM → Agnes video → Instagram publish → verify

Режимы:
  - dry-run: всё кроме Instagram API
  - prepare-only: DeepSeek (или mock) + лог, без Agnes и Instagram
"""
import os
import sys
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone

from config import Config
from content_generator import ContentGenerator
from llm_client import LLMClient
from agnes_client import AgnesClient

# ── logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("instagram")


# ── helpers ──────────────────────────────────────────────────────────
def retry(max_retries=3, delay=2, backoff=2.0):
    """Decorator: retry on network/API errors."""
    def deco(fn):
        def wrapper(*args, **kw):
            last_err = None
            wait = delay
            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kw)
                except (requests.exceptions.Timeout,
                        requests.exceptions.ConnectionError) as e:
                    last_err = e
                    log.warning("  ⚠️ retry %d/%d (network): %s", attempt, max_retries, e)
                except requests.exceptions.HTTPError as e:
                    status = e.response.status_code if e.response is not None else 0
                    if 500 <= status < 600:
                        last_err = e
                        log.warning("  ⚠️ retry %d/%d (HTTP %d): %s", attempt, max_retries, status, e)
                    else:
                        raise
                except Exception as e:
                    last_err = e
                    log.warning("  ⚠️ retry %d/%d: %s", attempt, max_retries, e)
                if attempt < max_retries:
                    time.sleep(wait)
                    wait *= backoff
            raise RuntimeError(f"Failed after {max_retries} retries") from last_err
        return wrapper
    return deco


# ── InstagramPoster ──────────────────────────────────────────────────
class InstagramPoster:
    def __init__(self, dry_run=False):
        Config.validate()
        self.generator = ContentGenerator()
        self.llm = LLMClient()
        self.agnes = AgnesClient() if not Config.PREPARE_ONLY else None
        self.prepare_only = Config.PREPARE_ONLY
        self.base_url = "https://graph.facebook.com/v18.0"
        self.published_file = Path(Config.DATA_DIR) / "published_log.json"
        self.published = self._load_published()
        self.dry_run = dry_run

    # ── log management ───────────────────────────────────────────────

    def _load_published(self):
        if self.published_file.exists():
            with open(self.published_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"items": []}

    def _save_published(self):
        self.published_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.published_file, "w", encoding="utf-8") as f:
            json.dump(self.published, f, ensure_ascii=False, indent=2)

    def _mark_published(self, title, post_id=None, media_type="REELS", status="published",
                        permalink=None, llm_output=None):
        entry = {
            "title": title,
            "post_id": post_id,
            "media_type": media_type,
            "status": status,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "permalink": permalink,
        }
        if llm_output:
            entry["llm"] = {
                "hook": llm_output.get("hook"),
                "script": llm_output.get("script")[:200] if llm_output.get("script") else None,
                "hashtags": llm_output.get("hashtags"),
                "visual_prompt": llm_output.get("visual_prompt"),
                "category": llm_output.get("category"),
            }
        self.published["items"].append(entry)
        self._save_published()

    # ── stage 1: pick fact ───────────────────────────────────────────

    def _pick_fact(self):
        exclude = [item["title"] for item in self.published["items"]
                   if item["status"] in ("published", "dry_run")]
        fact = self.generator.get_random_fact(exclude)
        if not fact:
            log.info("📭 Все факты опубликованы. На сегодня всё.")
            return None
        return fact

    # ── stage 2: LLM → Reels package ─────────────────────────────────

    def _build_reel_package(self, fact):
        """DeepSeek генерирует hook, script, caption, hashtags, visual_prompt."""
        log.info("🧠 Reels package by %s (%s)...", self.llm.provider, self.llm.model)
        package = self.llm.generate_reel_package(fact)
        log.info("  📝 Hook: %s", package["hook"][:120])
        log.info("  🏷️  Hashtags: %s", " ".join(package["hashtags"][:5]))
        log.info("  📂 Category: %s", package["category"])
        return package

    # ── stage 3: generate video via Agnes (skip in prepare-only) ──────

    def _generate_video(self, package):
        """Генерация Reels видео через Agnes AI API."""
        if self.prepare_only:
            log.info("  ⏭️  PREPARE_ONLY — Agnes video generation skipped")
            return None

        prompt = package.get("visual_prompt") or f"{package['topic']}. {package.get('script', '')}"
        log.info("  → Generating Reels video via Agnes...")
        video_url = self.agnes.generate_video(prompt, package["topic"])
        log.info("  ✅ Video URL: %s", video_url)
        return video_url

    # ── stage 4: publish to Instagram (skip in dry-run/prepare-only) ──

    @retry(max_retries=3, delay=3, backoff=2.0)
    def _publish_media(self, media_url, caption):
        log.info("  → Creating REELS container...")
        resp = requests.post(
            f"{self.base_url}/{Config.INSTAGRAM_USER_ID}/media",
            data={
                "media_type": "REELS",
                "video_url": media_url,
                "caption": caption,
                "access_token": Config.INSTAGRAM_ACCESS_TOKEN,
            },
            timeout=60,
        )
        resp.raise_for_status()
        creation_id = resp.json().get("id")
        if not creation_id:
            raise RuntimeError(f"No container id: {resp.json()}")
        log.info("  ✅ Container created: %s", creation_id)

        # wait for video processing
        delay = Config.VIDEO_PUBLISH_DELAY
        log.info("  ⏳ Waiting %ds for Instagram processing...", delay)
        time.sleep(delay)

        log.info("  → Publishing container %s...", creation_id)
        pub = requests.post(
            f"{self.base_url}/{Config.INSTAGRAM_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": Config.INSTAGRAM_ACCESS_TOKEN},
            timeout=60,
        )
        pub.raise_for_status()
        result = pub.json()
        log.info("  ✅ Published: %s", result.get("id"))
        return result

    # ── stage 5: verify ──────────────────────────────────────────────

    def _verify_post(self, media_id):
        try:
            resp = requests.get(
                f"{self.base_url}/{media_id}",
                params={
                    "fields": "id,media_type,permalink,status",
                    "access_token": Config.INSTAGRAM_ACCESS_TOKEN,
                },
                timeout=30,
            )
            if resp.ok:
                data = resp.json()
                log.info("  🔍 Verify: id=%s type=%s permalink=%s",
                         data.get("id"), data.get("media_type"), data.get("permalink", "N/A"))
                return data.get("permalink")
        except Exception as e:
            log.warning("  ⚠️ Verify failed: %s", e)
        return None

    # ── run ──────────────────────────────────────────────────────────

    def run(self):
        log.info("🚀 Instagram Auto-Post — start")

        # 1. pick fact
        fact = self._pick_fact()
        if not fact:
            if self.prepare_only:
                log.info("📭 Все факты использованы (prepare-only — это нормально)")
            return

        log.info("📄 Fact: %s", fact["title"])

        # 2. LLM → Reels package
        try:
            package = self._build_reel_package(fact)
        except Exception as e:
            log.error("❌ LLM package failed: %s", e)
            self._mark_published(fact["title"], status=f"llm_error: {e}")
            return

        # 3. prepare-only — только лог, без Agnes и Instagram
        if self.prepare_only:
            log.info("⏸️  PREPARE_ONLY — всё готово, публикация отложена")
            log.info("   hook: %s", package["hook"])
            log.info("   caption start: %s...", package["caption"][:200])
            log.info("   hashtags: %s", " ".join(package["hashtags"]))
            log.info("   visual_prompt: %s", package["visual_prompt"][:200])
            self._mark_published(fact["title"], media_type="REELS",
                                 status="prepared", llm_output=package)
            log.info("✅ Prepared (logged, not published)")
            return

        # 4. generate video
        try:
            video_url = self._generate_video(package)
            if not video_url and not self.dry_run:
                log.error("❌ Video generation failed, no URL")
                self._mark_published(fact["title"], status="failed_generation", llm_output=package)
                return
        except Exception as e:
            log.error("❌ Video generation failed: %s", e)
            self._mark_published(fact["title"], status=f"failed_generation: {e}", llm_output=package)
            return

        # 5. publish or dry-run
        caption = package["caption"]
        if self.dry_run:
            log.info("🔍 [DRY-RUN] Would publish REELS")
            log.info("   caption: %s...", caption[:300])
            log.info("   video: %s", video_url)
            self._mark_published(fact["title"], media_type="REELS",
                                 status="dry_run", llm_output=package)
            return

        try:
            result = self._publish_media(video_url, caption)
            media_id = result.get("id")
            permalink = self._verify_post(media_id)
            self._mark_published(fact["title"], media_id, "REELS",
                                 "published", permalink, llm_output=package)
            log.info("✅ Done: %s", fact["title"])
        except Exception as e:
            log.error("❌ Publish failed: %s", e)
            self._mark_published(fact["title"], status=f"publish_error: {e}", llm_output=package)


# ── entry point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or os.getenv("DRY_RUN", "false").lower() == "true"
    prepare_only = Config.PREPARE_ONLY

    poster = InstagramPoster(dry_run=dry_run)
    if dry_run:
        log.info("🔍 DRY-RUN mode — no Instagram publishing")
    if prepare_only:
        log.info("⏸️  PREPARE-ONLY mode — no Agnes, no Instagram")
    poster.run()
