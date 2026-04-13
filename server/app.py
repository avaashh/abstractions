import asyncio
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor

import aiofiles
import aiohttp
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

SAVE_DIR = "server/detected_images"
os.makedirs(SAVE_DIR, exist_ok=True)

executor = ThreadPoolExecutor(max_workers=20)


class ImageBatch(BaseModel):
    urls: list[str]


async def fetch_and_save(session: aiohttp.ClientSession, url: str) -> dict:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return {"url": url, "status": "failed", "reason": f"http {resp.status}"}

            content = await resp.read()
            ext = url.split("?")[0].split(".")[-1][:4]
            if ext not in ["jpg", "jpeg", "png", "gif", "webp", "svg"]:
                ext = "jpg"

            filename = hashlib.md5(url.encode()).hexdigest()[:12] + "." + ext
            filepath = os.path.join(SAVE_DIR, filename)

            async with aiofiles.open(filepath, "wb") as f:
                await f.write(content)

            return {
                "url": url,
                "status": "saved",
                "file": filename,
                "caption": "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
            }
    except Exception as e:
        return {
            "url": url,
            "status": "failed",
            "reason": str(e),
            "caption": "Lorem ipsum dolor sit amet."
        }


@app.post("/detect")
async def detect_images(batch: ImageBatch):
    if not batch.urls:
        raise HTTPException(400, "no urls provided")

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_and_save(session, url) for url in batch.urls]
        results = await asyncio.gather(*tasks)

    saved = sum(1 for r in results if r["status"] == "saved")
    return {"total": len(batch.urls), "saved": saved, "results": results}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
