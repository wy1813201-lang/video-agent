"""
素材管理系统
支持图像、视频、音频的本地存储、标签和分类管理
"""

import os
import json
import uuid
import shutil
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict
from datetime import datetime


class AssetType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


ASSET_EXTENSIONS = {
    AssetType.IMAGE: {".jpg", ".jpeg", ".png", ".webp", ".gif"},
    AssetType.VIDEO: {".mp4", ".mov", ".avi", ".mkv", ".webm"},
    AssetType.AUDIO: {".mp3", ".wav", ".aac", ".m4a", ".ogg"},
}


@dataclass
class Asset:
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    asset_type: AssetType = AssetType.IMAGE
    file_path: str = ""
    file_size: int = 0          # bytes
    duration: Optional[float] = None   # 视频/音频时长(秒)
    width: Optional[int] = None
    height: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    category: str = "uncategorized"
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = ""            # 来源：ai_generated / uploaded / downloaded


class AssetManager:
    """素材库管理器"""

    def __init__(self, storage_dir: str = "data/storage"):
        self.storage_dir = storage_dir
        self.db_path = os.path.join(storage_dir, "assets.json")
        self._assets: Dict[str, Asset] = {}

        for sub in ["images", "videos", "audios"]:
            os.makedirs(os.path.join(storage_dir, sub), exist_ok=True)

        self._load_db()

    # ── DB ──────────────────────────────────────────────────────────────────

    def _load_db(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._assets = {k: Asset(**v) for k, v in raw.items()}

    def _save_db(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump({k: asdict(v) for k, v in self._assets.items()}, f, ensure_ascii=False, indent=2)

    # ── Import ───────────────────────────────────────────────────────────────

    def import_file(self, src_path: str, tags: List[str] = None,
                    category: str = "uncategorized", description: str = "",
                    source: str = "uploaded") -> Asset:
        """导入文件到素材库"""
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"文件不存在: {src_path}")

        ext = os.path.splitext(src_path)[1].lower()
        asset_type = self._detect_type(ext)
        sub = {"image": "images", "video": "videos", "audio": "audios"}[asset_type.value]

        asset_id = str(uuid.uuid4())[:8]
        filename = f"{asset_id}{ext}"
        dest = os.path.join(self.storage_dir, sub, filename)
        shutil.copy2(src_path, dest)

        asset = Asset(
            asset_id=asset_id,
            name=os.path.basename(src_path),
            asset_type=asset_type,
            file_path=dest,
            file_size=os.path.getsize(dest),
            tags=tags or [],
            category=category,
            description=description,
            source=source,
        )
        self._assets[asset_id] = asset
        self._save_db()
        return asset

    def register_generated(self, file_path: str, asset_type: AssetType,
                            tags: List[str] = None, category: str = "generated",
                            description: str = "") -> Asset:
        """注册AI生成的素材（文件已在目标位置）"""
        asset_id = str(uuid.uuid4())[:8]
        asset = Asset(
            asset_id=asset_id,
            name=os.path.basename(file_path),
            asset_type=asset_type,
            file_path=file_path,
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            tags=tags or [],
            category=category,
            description=description,
            source="ai_generated",
        )
        self._assets[asset_id] = asset
        self._save_db()
        return asset

    # ── Query ────────────────────────────────────────────────────────────────

    def get(self, asset_id: str) -> Optional[Asset]:
        return self._assets.get(asset_id)

    def list_all(self) -> List[Asset]:
        return list(self._assets.values())

    def filter(self, asset_type: AssetType = None, category: str = None,
               tags: List[str] = None) -> List[Asset]:
        results = list(self._assets.values())
        if asset_type:
            results = [a for a in results if a.asset_type == asset_type]
        if category:
            results = [a for a in results if a.category == category]
        if tags:
            results = [a for a in results if any(t in a.tags for t in tags)]
        return results

    def search(self, keyword: str) -> List[Asset]:
        kw = keyword.lower()
        return [a for a in self._assets.values()
                if kw in a.name.lower() or kw in a.description.lower()
                or any(kw in t.lower() for t in a.tags)]

    # ── Manage ───────────────────────────────────────────────────────────────

    def add_tags(self, asset_id: str, tags: List[str]):
        a = self._assets.get(asset_id)
        if a:
            a.tags = list(set(a.tags + tags))
            self._save_db()

    def set_category(self, asset_id: str, category: str):
        a = self._assets.get(asset_id)
        if a:
            a.category = category
            self._save_db()

    def delete(self, asset_id: str, remove_file: bool = False) -> bool:
        a = self._assets.pop(asset_id, None)
        if a:
            if remove_file and os.path.exists(a.file_path):
                os.remove(a.file_path)
            self._save_db()
            return True
        return False

    def export_manifest(self, dest_path: str):
        """导出素材清单 JSON"""
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump([asdict(a) for a in self._assets.values()], f, ensure_ascii=False, indent=2)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _detect_type(self, ext: str) -> AssetType:
        for t, exts in ASSET_EXTENSIONS.items():
            if ext in exts:
                return t
        raise ValueError(f"不支持的文件类型: {ext}")

    def stats(self) -> Dict:
        assets = list(self._assets.values())
        return {
            "total": len(assets),
            "images": sum(1 for a in assets if a.asset_type == AssetType.IMAGE),
            "videos": sum(1 for a in assets if a.asset_type == AssetType.VIDEO),
            "audios": sum(1 for a in assets if a.asset_type == AssetType.AUDIO),
            "total_size_mb": round(sum(a.file_size for a in assets) / 1024 / 1024, 2),
        }
