import asyncio
import base64
import hashlib
import json
import logging
import os
import time

import aiofiles
import aiohttp
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("humor-vision")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

SAVE_DIR = "server/detected_images"
os.makedirs(SAVE_DIR, exist_ok=True)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

log.info("model=%s api_key=%s", OPENROUTER_MODEL, "set" if OPENROUTER_API_KEY else "MISSING")

EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}

PROMPT = (
    "You are analyzing an image. Decide if it is a meme "
    "(humorous image, often with overlaid text, reaction image, or "
    "internet culture reference). Respond with ONLY a JSON object matching "
    'this exact shape: {"is_meme": boolean, "confidence": number between 0 and 1, '
    '"description": string}. The description should be a detailed, vivid description '
    "of the image contents — if it is a meme, explain the joke and any text overlay; "
    "if not, describe what is shown. No prose outside the JSON."
)

analysis_cache: dict[str, dict] = {}


class ImageBatch(BaseModel):
    urls: list[str]


def guess_ext(url: str, content_type: str | None) -> str:
    if content_type:
        mime = content_type.split(";")[0].strip().lower()
        if mime in EXT_BY_MIME:
            return EXT_BY_MIME[mime]
    ext = url.split("?")[0].split("#")[0].split(".")[-1].lower()[:4]
    if ext in ["jpg", "jpeg", "png", "gif", "webp", "svg"]:
        return ext
    return "jpg"


async def analyze_image(content: bytes, mime: str, url: str) -> dict:
    if not OPENROUTER_API_KEY:
        log.warning("skipping analysis, no api key url=%s", url)
        return {
            "is_meme": False,
            "confidence": 0.0,
            "description": "OPENROUTER_API_KEY not set on server.",
        }

    b64 = base64.b64encode(content).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    start = time.monotonic()
    log.info("analyze start url=%s bytes=%d mime=%s", url, len(content), mime)
    try:
        completion = await client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=600,
        )
        raw = completion.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        elapsed = time.monotonic() - start
        result = {
            "is_meme": bool(parsed.get("is_meme", False)),
            "confidence": float(parsed.get("confidence", 0.0)),
            "description": str(parsed.get("description", "")),
        }
        log.info(
            "analyze ok url=%s meme=%s conf=%.2f t=%.2fs",
            url, result["is_meme"], result["confidence"], elapsed,
        )
        return result
    except json.JSONDecodeError:
        log.warning("analyze bad-json url=%s raw=%r", url, (raw or "")[:200])
        return {
            "is_meme": False,
            "confidence": 0.0,
            "description": (raw or "")[:500],
        }
    except Exception as e:
        log.exception("analyze failed url=%s err=%s", url, e)
        return {
            "is_meme": False,
            "confidence": 0.0,
            "description": f"analysis failed: {e}",
        }


async def fetch_and_analyze(session: aiohttp.ClientSession, url: str) -> dict:
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]

    if url_hash in analysis_cache:
        cached = analysis_cache[url_hash]
        log.info("cache hit url=%s", url)
        return {"url": url, "status": "cached", **cached}

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                log.warning("fetch failed url=%s http=%d", url, resp.status)
                return {
                    "url": url,
                    "status": "failed",
                    "reason": f"http {resp.status}",
                    "is_meme": False,
                    "confidence": 0.0,
                    "description": f"Could not fetch image (HTTP {resp.status}).",
                }

            content = await resp.read()
            mime = (resp.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
            ext = guess_ext(url, mime)

        filename = url_hash + "." + ext
        filepath = os.path.join(SAVE_DIR, filename)
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(content)
        log.info("fetched url=%s bytes=%d saved=%s", url, len(content), filename)

        if mime not in EXT_BY_MIME:
            mime = "image/jpeg"
        analysis = await analyze_image(content, mime, url)

        record = {"file": filename, **analysis}
        analysis_cache[url_hash] = record

        return {"url": url, "status": "saved", **record}
    except Exception as e:
        log.exception("fetch_and_analyze error url=%s err=%s", url, e)
        return {
            "url": url,
            "status": "failed",
            "reason": str(e),
            "is_meme": False,
            "confidence": 0.0,
            "description": f"error: {e}",
        }


@app.post("/detect")
async def detect_images(batch: ImageBatch):
    if not batch.urls:
        raise HTTPException(400, "no urls provided")

    start = time.monotonic()
    log.info("/detect received n=%d", len(batch.urls))
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_and_analyze(session, url) for url in batch.urls]
        results = await asyncio.gather(*tasks)

    saved = sum(1 for r in results if r["status"] in ("saved", "cached"))
    memes = sum(1 for r in results if r.get("is_meme"))
    elapsed = time.monotonic() - start
    log.info(
        "/detect done n=%d saved=%d memes=%d t=%.2fs",
        len(batch.urls), saved, memes, elapsed,
    )
    return {
        "total": len(batch.urls),
        "saved": saved,
        "memes": memes,
        "model": OPENROUTER_MODEL,
        "results": results,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
