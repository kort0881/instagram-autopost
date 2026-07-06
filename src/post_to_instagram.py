#!/usr/bin/env python3
"""Instagram Auto-Post — основной скрипт публикации.

Pipeline: generate → validate → upload → publish → verify
"""
import os
import sys
import json
import random
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone
from io import BytesIO

from config import Config
from content_generator import ContentGenerator
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
                    # 4xx — не retry, 5xx — retry
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
    CATEGORY_IMAGES = {
        "historical": "ancient+history+archaeology",
        "science": "science+technology+discovery",
        "mystery": "mysterious+dark+paranormal",
        "archaeology": "excavation+ruins+artifacts",
        "psychology": "brain+mind+consciousness",
        "anatomy": "human+body+anatomy",
    }

    def __init__(self, dry_run=False):
        Config.validate()
        self.generator = ContentGenerator()
        self.agnes = AgnesClient()
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

    def _already_published(self, title):
        return any(item["title"] == title for item in self.published["items"])

    def _mark_published(self, title, post_id=None, media_type=None, status="published", permalink=None):
        self.published["items"].append({
            "title": title,
            "post_id": post_id,
            "media_type": media_type,
            "status": status,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "permalink": permalink,
        })
        self._save_published()

    # ── stage 1: generate ────────────────────────────────────────────

    def _pick_fact(self):
        exclude = [item["title"] for item in self.published["items"]
                   if item["status"] in ("published",)]
        fact = self.generator.get_random_fact(exclude)
        if not fact:
            log.info("📭 Все факты опубликованы. На сегодня всё.")
            return None
        return fact

    # ── stage 2: validate ────────────────────────────────────────────

    def _validate_fact(self, fact):
        errors = []
        if not fact.get("title") or len(fact["title"].strip()) < 3:
            errors.append("title missing or too short")
        if not fact.get("text") or len(fact["text"].strip()) < 10:
            errors.append("text missing or too short")
        if errors:
            raise ValueError(f"Fact validation failed: {', '.join(errors)}")
        return True

    # ── stage 3: generate media (reel video or post image) ───────────

    def _generate_reel(self, fact):
        log.info("  → Generating Reels video via Agnes...")
        video_url = self.agnes.generate_video(
            f"{fact['title']}. {fact['text']}",
            fact["title"],
        )
        log.info("  ✅ Video URL: %s", video_url)
        return video_url

    def _generate_post_image(self, fact):
        from PIL import Image, ImageDraw, ImageFont  # noqa: lazy import
        import textwrap

        colors = {
            "historical": (45, 55, 72),
            "science": (30, 60, 80),
            "mystery": (25, 20, 35),
            "archaeology": (55, 45, 30),
            "psychology": (40, 35, 55),
            "anatomy": (50, 30, 35),
        }
        category = "historical"
        for cat_key in colors:
            if any(tag in fact.get("tags", []) for tag in [f"#{cat_key}", f"#{cat_key[:4]}"]):
                category = cat_key
                break

        bg_color = colors.get(category, (30, 30, 40))
        img = Image.new("RGB", (1080, 1080), bg_color)
        draw = ImageDraw.Draw(img)

        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font = None
        for fp in font_paths:
            if Path(fp).exists():
                font = ImageFont.truetype(fp, 42)
                break
        if not font:
            font = ImageFont.load_default()

        # title
        title = fact["title"][:120]
        lines = textwrap.wrap(title, width=25)
        y = 150
        for line in lines[:4]:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(((1080 - tw) // 2, y), line, fill=(255, 255, 255), font=font)
            y += 55

        # body
        y += 40
        body_font = font
        if Path(font_paths[1]).exists():
            body_font = ImageFont.truetype(font_paths[1], 32)
        text_lines = textwrap.wrap(fact["text"], width=35)
        for line in text_lines[:12]:
            bbox = draw.textbbox((0, 0), line, font=body_font)
            tw = bbox[2] - bbox[0]
            draw.text(((1080 - tw) // 2, y), line, fill=(220, 220, 220), font=body_font)
            y += 40

        output_path = (
            Path(Config.DATA_DIR) / "posts" / f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, quality=95)
        return str(output_path)

    # ── stage 3b: upload image to hosting ────────────────────────────

    def _upload_to_cloudinary(self, image_path):
        if not Config.CLOUDINARY_CLOUD_NAME:
            return None
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(
                cloud_name=Config.CLOUDINARY_CLOUD_NAME,
                api_key=Config.CLOUDINARY_API_KEY,
                api_secret=Config.CLOUDINARY_API_SECRET,
            )
            result = cloudinary.uploader.upload(
                image_path, folder="instagram_autopost", resource_type="image"
            )
            url = result.get("secure_url")
            log.info("  ☁️ Cloudinary: %s", url)
            return url
        except Exception as e:
            log.warning("  ⚠️ Cloudinary error: %s", e)
            return None

    def _get_public_url(self, image_path):
        if Config.CLOUDINARY_CLOUD_NAME:
            return self._upload_to_cloudinary(image_path)
        return None

    # ── stage 4: publish to Instagram API ────────────────────────────

    @retry(max_retries=3, delay=3, backoff=2.0)
    def _publish_media(self, media_url, caption, media_type="REELS"):
        is_video = media_type in ("VIDEO", "REELS")
        payload = {
            "media_type": media_type,
            "caption": caption,
            "access_token": Config.INSTAGRAM_ACCESS_TOKEN,
        }
        payload["video_url" if is_video else "image_url"] = media_url

        log.info("  → Creating %s container...", media_type)
        resp = requests.post(
            f"{self.base_url}/{Config.INSTAGRAM_USER_ID}/media",
            data=payload,
            timeout=60,
        )
        resp.raise_for_status()
        creation_id = resp.json().get("id")
        if not creation_id:
            raise RuntimeError(f"No container id: {resp.json()}")
        log.info("  ✅ Container created: %s", creation_id)

        # video: wait for processing
        if is_video:
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

        # 1. choose post type
        post_type = random.choices(["reel", "post"], weights=[0.9, 0.1])[0]

        # 2. generate
        fact = self._pick_fact()
        if not fact:
            return

        # 3. validate
        self._validate_fact(fact)
        log.info("📄 Fact: %s", fact["title"])

        # 4. caption
        caption = self.generator.generate_caption(fact, post_type)

        # 5. media generation + publish
        if post_type == "reel":
            log.info("🎬 Reels pipeline")
            try:
                video_url = self._generate_reel(fact)
                if self.dry_run:
                    log.info("🔍 [DRY-RUN] Would publish REELS")
                    log.info("   caption: %s...", caption[:200])
                    log.info("   video: %s", video_url)
                    self._mark_published(fact["title"], media_type="REELS", status="dry_run")
                    return

                result = self._publish_media(video_url, caption, "REELS")
                media_id = result.get("id")
                permalink = self._verify_post(media_id)
                self._mark_published(fact["title"], media_id, "REELS", "published", permalink)
                log.info("✅ Done: %s", fact["title"])

            except Exception as e:
                log.error("❌ Reels pipeline failed: %s", e)
                self._mark_published(fact["title"], media_type="REELS", status=f"error: {e}")
                raise

        else:
            log.info("📸 Image post pipeline")
            try:
                image_path = self._generate_post_image(fact)
                if not image_path:
                    log.warning("⚠️ Image not generated, skipping")
                    return

                public_url = self._get_public_url(image_path)
                if not public_url:
                    log.warning("⚠️ No image hosting configured, skipping post")
                    log.info("📝 Set Cloudinary secrets for image upload")
                    return

                if self.dry_run:
                    log.info("🔍 [DRY-RUN] Would publish IMAGE")
                    log.info("   caption: %s...", caption[:200])
                    log.info("   image: %s", public_url)
                    self._mark_published(fact["title"], media_type="IMAGE", status="dry_run")
                    return

                result = self._publish_media(public_url, caption, "IMAGE")
                media_id = result.get("id")
                permalink = self._verify_post(media_id)
                self._mark_published(fact["title"], media_id, "IMAGE", "published", permalink)
                log.info("✅ Done: %s", fact["title"])

            except Exception as e:
                log.error("❌ Image pipeline failed: %s", e)
                self._mark_published(fact["title"], media_type="IMAGE", status=f"error: {e}")
                raise


# ── entry point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or os.getenv("DRY_RUN", "false").lower() == "true"
    poster = InstagramPoster(dry_run=dry_run)
    if dry_run:
        log.info("🔍 DRY-RUN mode — no real publishing")
    poster.run()
