"""
结构化剧本 Schema 校验（轻量内置版）
不依赖 jsonschema 第三方库，避免部署阻塞。
"""

from typing import Any, Dict, List, Tuple


REQUIRED_ROOT_KEYS = [
    "title",
    "episode",
    "style",
    "summary",
    "character_count",
    "conflict_structure",
    "emotion_nodes",
    "scenes",
]

REQUIRED_SCENE_KEYS = [
    "scene_id",
    "location",
    "time_of_day",
    "characters",
    "emotion",
    "action_summary",
    "description",
    "dialogues",
]


def validate_structured_script(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    if not isinstance(data, dict):
        return False, ["root must be object"]

    for key in REQUIRED_ROOT_KEYS:
        if key not in data:
            issues.append(f"missing root key: {key}")

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        issues.append("scenes must be non-empty array")
        return False, issues

    for idx, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            issues.append(f"scene[{idx}] must be object")
            continue
        for key in REQUIRED_SCENE_KEYS:
            if key not in scene:
                issues.append(f"scene[{idx}] missing key: {key}")
        dialogues = scene.get("dialogues", [])
        if not isinstance(dialogues, list):
            issues.append(f"scene[{idx}].dialogues must be array")
            continue
        for didx, item in enumerate(dialogues):
            if not isinstance(item, dict):
                issues.append(f"scene[{idx}].dialogues[{didx}] must be object")
                continue
            if "speaker" not in item or "line" not in item:
                issues.append(f"scene[{idx}].dialogues[{didx}] missing speaker/line")

    return len(issues) == 0, issues

