"""
增强素材库
支持角色/场景/道具/音乐分类，标签搜索，素材复用
"""

import os
import json
import uuid
import shutil
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict
from datetime import datetime


class AssetCategory(str, Enum):
    CHARACTER = "character"   # 角色
    SCENE = "scene"           # 场景
    PROP = "prop"             # 道具
    MUSIC = "music"           # 音乐
    EFFECT = "effect"         # 特效/音效
    OTHER = "other"


class AssetType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


ASSET_EXTENSIONS = {
    AssetType.IMAGE: {".jpg", ".jpeg", ".png", ".webp", ".gif"},
    AssetType.VIDEO: {".mp4", ".mov", ".avi", ".mkv", ".webm"},
    AssetType.AUDIO: {".mp3", ".wav", ".aac", ".m4a", ".ogg"},
}

# 分类 → 默认素材类型
CATEGORY_DEFAULT_TYPE = {
    AssetCategory.CHARACTER: AssetType.IMAGE,
    AssetCategory.SCENE: AssetType.IMAGE,
    AssetCategory.PROP: AssetType.IMAGE,
    AssetCategory.MUSIC: AssetType.AUDIO,
    AssetCategory.EFFECT: AssetType.AUDIO,
    AssetCategory.OTHER: AssetType.IMAGE,
}


@dataclass
class Asset:
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    asset_type: AssetType = AssetType.IMAGE
    category: AssetCategory = AssetCategory.OTHER
    file_path: str = ""
    file_size: int = 0
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    description: str = ""
    style: str = ""             # 关联风格（古装/现代/科幻等）
    drama_id: str = ""          # 关联剧集 ID，便于复用
    use_count: int = 0          # 使用次数
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "uploaded"    # ai_generated / uploaded / downloaded


class AssetLibrary:
    """增强素材库"""

    SUBDIRS = {
        AssetCategory.CHARACTER: "characters",
        AssetCategory.SCENE: "scenes",
        AssetCategory.PROP: "props",
        AssetCategory.MUSIC: "music",
        AssetCategory.EFFECT: "effects",
        AssetCategory.OTHER: "other",
    }

    def __init__(self, storage_dir: str = "data/assets"):
        self.storage_dir = storage_dir
        self.db_path = os.path.join(storage_dir, "library.json")
        self._assets: Dict[str, Asset] = {}

        for subdir in self.SUBDIRS.values():
            os.makedirs(os.path.join(storage_dir, subdir), exist_ok=True)

        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                # 兼容枚举字段
                v["asset_type"] = AssetType(v.get("asset_type", "image"))
                v["category"] = AssetCategory(v.get("category", "other"))
                self._assets[k] = Asset(**v)

    def _save(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump({k: asdict(v) for k, v in self._assets.items()},
                      f, ensure_ascii=False, indent=2)

    # ── Import / Register ────────────────────────────────────────────────────

    def import_file(self, src_path: str, category: AssetCategory = AssetCategory.OTHER,
                    tags: List[str] = None, description: str = "",
                    style: str = "", drama_id: str = "",
                    source: str = "uploaded") -> Asset:
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"文件不存在: {src_path}")

        ext = os.path.splitext(src_path)[1].lower()
        asset_type = self._detect_type(ext)
        subdir = self.SUBDIRS[category]

        asset_id = str(uuid.uuid4())[:8]
        dest = os.path.join(self.storage_dir, subdir, f"{asset_id}{ext}")
        shutil.copy2(src_path, dest)

        asset = Asset(
            asset_id=asset_id,
            name=os.path.basename(src_path),
            asset_type=asset_type,
            category=category,
            file_path=dest,
            file_size=os.path.getsize(dest),
            tags=tags or [],
            description=description,
            style=style,
            drama_id=drama_id,
            source=source,
        )
        self._assets[asset_id] = asset
        self._save()
        return asset

    def register_generated(self, file_path: str,
                            category: AssetCategory = AssetCategory.OTHER,
                            tags: List[str] = None, description: str = "",
                            style: str = "", drama_id: str = "") -> Asset:
        """注册 AI 生成的素材（文件已在目标位置）"""
        ext = os.path.splitext(file_path)[1].lower()
        asset_type = self._detect_type(ext)
        asset_id = str(uuid.uuid4())[:8]
        asset = Asset(
            asset_id=asset_id,
            name=os.path.basename(file_path),
            asset_type=asset_type,
            category=category,
            file_path=file_path,
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            tags=tags or [],
            description=description,
            style=style,
            drama_id=drama_id,
            source="ai_generated",
        )
        self._assets[asset_id] = asset
        self._save()
        return asset

    # ── Query ────────────────────────────────────────────────────────────────

    def get(self, asset_id: str) -> Optional[Asset]:
        return self._assets.get(asset_id)

    def list_all(self) -> List[Asset]:
        return list(self._assets.values())

    def by_category(self, category: AssetCategory) -> List[Asset]:
        return [a for a in self._assets.values() if a.category == category]

    def by_style(self, style: str) -> List[Asset]:
        return [a for a in self._assets.values() if a.style == style]

    def by_drama(self, drama_id: str) -> List[Asset]:
        return [a for a in self._assets.values() if a.drama_id == drama_id]

    def search(self, keyword: str) -> List[Asset]:
        kw = keyword.lower()
        return [
            a for a in self._assets.values()
            if kw in a.name.lower()
            or kw in a.description.lower()
            or kw in a.style.lower()
            or any(kw in t.lower() for t in a.tags)
        ]

    def filter(self, asset_type: AssetType = None, category: AssetCategory = None,
               tags: List[str] = None, style: str = None) -> List[Asset]:
        results = list(self._assets.values())
        if asset_type:
            results = [a for a in results if a.asset_type == asset_type]
        if category:
            results = [a for a in results if a.category == category]
        if style:
            results = [a for a in results if a.style == style]
        if tags:
            results = [a for a in results if any(t in a.tags for t in tags)]
        return results

    def most_used(self, limit: int = 10) -> List[Asset]:
        return sorted(self._assets.values(), key=lambda a: a.use_count, reverse=True)[:limit]

    # ── Reuse ────────────────────────────────────────────────────────────────

    def mark_used(self, asset_id: str):
        """记录素材使用，便于统计复用率"""
        a = self._assets.get(asset_id)
        if a:
            a.use_count += 1
            self._save()

    def find_reusable(self, style: str, category: AssetCategory,
                      tags: List[str] = None) -> List[Asset]:
        """查找可复用的素材"""
        results = self.filter(category=category, style=style, tags=tags)
        return sorted(results, key=lambda a: a.use_count, reverse=True)

    # ── Manage ───────────────────────────────────────────────────────────────

    def add_tags(self, asset_id: str, tags: List[str]):
        a = self._assets.get(asset_id)
        if a:
            a.tags = list(set(a.tags + tags))
            self._save()

    def set_style(self, asset_id: str, style: str):
        a = self._assets.get(asset_id)
        if a:
            a.style = style
            self._save()

    def delete(self, asset_id: str, remove_file: bool = False) -> bool:
        a = self._assets.pop(asset_id, None)
        if a:
            if remove_file and os.path.exists(a.file_path):
                os.remove(a.file_path)
            self._save()
            return True
        return False

    # ── Stats ────────────────────────────────────────────────────────────────

    def stats(self) -> Dict:
        assets = list(self._assets.values())
        by_cat = {}
        for cat in AssetCategory:
            by_cat[cat.value] = sum(1 for a in assets if a.category == cat)
        return {
            "total": len(assets),
            "by_category": by_cat,
            "by_type": {
                "image": sum(1 for a in assets if a.asset_type == AssetType.IMAGE),
                "video": sum(1 for a in assets if a.asset_type == AssetType.VIDEO),
                "audio": sum(1 for a in assets if a.asset_type == AssetType.AUDIO),
            },
            "total_size_mb": round(sum(a.file_size for a in assets) / 1024 / 1024, 2),
            "most_used": [
                {"id": a.asset_id, "name": a.name, "use_count": a.use_count}
                for a in self.most_used(5)
            ],
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _detect_type(self, ext: str) -> AssetType:
        for t, exts in ASSET_EXTENSIONS.items():
            if ext in exts:
                return t
        raise ValueError(f"不支持的文件类型: {ext}")
