import json
from pathlib import Path
from typing import Optional  # 
from httpx import AsyncClient

from .constant import IMAGE_DIR


def load_json(path: Path, default):
    if not path.exists():
        path.write_text(
            json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return default
    return json.loads(path.read_text("utf-8"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def async_fetch_pig_data(url: str):
    async with AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


def find_image_file(pig_id: str) -> Optional[Path]:
    exts = ["png", "jpg", "jpeg", "webp", "gif"]
    for ext in exts:
        file = IMAGE_DIR / f"{pig_id}.{ext}"
        if file.exists():
            return file
    return None
