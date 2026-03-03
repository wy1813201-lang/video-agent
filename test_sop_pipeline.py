"""
SOP 流水线单元测试
验证 SOP 规范的核心约束：
1. CharacterMaster 锚点文本不含模糊词
2. KeyframeGenerator 拦截模糊词
3. WorkflowManager.generate_video 无图片时抛出 ValueError
4. QualityAuditor 对含模糊词 prompt 返回 overall_pass=False
5. FilmDirectorAgent 相关 SOP 格式校验
"""

import sys
import os
import asyncio
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# 确保 src 可导入
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.character_master import CharacterMaster, CharacterMasterRegistry, VAGUE_TERMS_BLACKLIST
from src.keyframe_generator import KeyframeGenerator
from src.quality_auditor import QualityAuditor, SOP_THRESHOLDS


# ────────────────────────────────────────────────────────────────────────────
#  1. CharacterMaster 测试
# ────────────────────────────────────────────────────────────────────────────

class TestCharacterMaster(unittest.TestCase):

    def setUp(self):
        self.cm = CharacterMaster.example()

    def test_anchor_fragment_not_empty(self):
        """to_anchor_fragment() 必须输出非空文本"""
        anchor = self.cm.to_anchor_fragment()
        self.assertGreater(len(anchor), 20, "锚点文本太短")

    def test_anchor_no_vague_terms(self):
        """内置示例角色的锚点文本不得包含模糊词"""
        anchor = self.cm.to_anchor_fragment().lower()
        for term in VAGUE_TERMS_BLACKLIST:
            self.assertNotIn(
                term.lower(), anchor,
                f"锚点中含模糊词: '{term}'"
            )

    def test_validate_passes_for_example(self):
        """内置示例角色应通过 SOP 校验"""
        issues = self.cm.validate()
        self.assertEqual([], issues, f"示例角色 SOP 校验失败: {issues}")

    def test_json_roundtrip(self):
        """保存再加载，数据应完全一致"""
        import tempfile, json
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name
        try:
            self.cm.save_to_json(tmp_path)
            loaded = CharacterMaster.load_from_json(tmp_path)
            self.assertEqual(self.cm.character_id, loaded.character_id)
            self.assertEqual(self.cm.name, loaded.name)
            self.assertEqual(self.cm.hair_color, loaded.hair_color)
            self.assertEqual(self.cm.outfit_primary, loaded.outfit_primary)
        finally:
            os.unlink(tmp_path)

    def test_vague_character_fails_validation(self):
        """含模糊词的角色描述应被 validate() 拦截"""
        bad_cm = CharacterMaster(
            character_id="char_bad",
            name="坏的角色",
            gender="female",
            age_range="20s",
            hair_color="black",
            hair_style="natural",
            face_structure="漂亮 oval face",   # 含模糊词
            skin_tone="fair",
            eye_description="expressive eyes",
        )
        issues = bad_cm.validate()
        self.assertTrue(
            any("漂亮" in i for i in issues),
            "应检测到模糊词 '漂亮'"
        )

    def test_build_view_prompts_all_keys(self):
        """三视图 prompts 应包含所有必要的视角"""
        prompts = self.cm.build_view_prompts()
        for key in ["front", "side", "back", "half_body", "full_body_proportion"]:
            self.assertIn(key, prompts, f"缺少视角: {key}")
            self.assertGreater(len(prompts[key]), 30)

    def test_build_expression_prompts(self):
        """表情 prompts 应包含 ≥ 3 种"""
        prompts = self.cm.build_expression_prompts()
        self.assertGreaterEqual(len(prompts), 3, "表情种类不足 3 种")


# ────────────────────────────────────────────────────────────────────────────
#  2. KeyframeGenerator 测试
# ────────────────────────────────────────────────────────────────────────────

class TestKeyframeGenerator(unittest.TestCase):

    def setUp(self):
        self.cm = CharacterMaster.example()
        self.kfg = KeyframeGenerator()
        self.sample_shot = {
            "shot_id": "s1",
            "location": "café interior",
            "time_of_day": "golden hour afternoon",
            "weather": "clear",
            "emotion": "calm",
            "action": "reading a book",
            "shot_type": "中景",
            "angle": "平视",
            "subject_position": "左三分之一",
        }

    def test_build_prompt_contains_anchor(self):
        """生成的 prompt 必须包含角色锚点关键词"""
        prompt = self.kfg.build_keyframe_prompt_text(self.sample_shot, self.cm)
        anchor_kws = [self.cm.hair_color, self.cm.hair_style.split()[0]]
        for kw in anchor_kws:
            self.assertIn(
                kw.lower(), prompt.lower(),
                f"prompt 中缺少锚点关键词: '{kw}'"
            )

    def test_validate_no_vague_terms_clean(self):
        """干净 prompt 应通过校验"""
        clean_prompt = (
            "jet black waist-length straight hair, oval face, fair skin, "
            "white chiffon dress, reading a book, café interior, golden hour"
        )
        result = self.kfg._validate_no_vague_terms(clean_prompt)
        self.assertTrue(result, "干净 prompt 应通过模糊词检测")

    def test_validate_no_vague_terms_catches_bad(self):
        """含模糊描述词的 prompt 应被拦截"""
        bad_prompt = "beautiful woman, gorgeous eyes, handsome man"
        result = self.kfg._validate_no_vague_terms(bad_prompt)
        self.assertFalse(result, "含模糊词 prompt 应被拦截")

    def test_validate_prompt_returns_issues(self):
        """validate_prompt 应返回含模糊词的问题列表"""
        bad_prompt = "pretty girl, cute face"
        issues = self.kfg.validate_prompt(bad_prompt)
        self.assertTrue(len(issues) > 0, "应检测到模糊词问题")

    def test_build_nine_grid_prompt(self):
        """九宫格应生成一个包含 9 panel 描述的单一 prompt"""
        spec = self.kfg.build_nine_grid_prompt(self.sample_shot, [self.cm])
        self.assertIn("A 3x3 9-panel storyboard grid.", spec.compiled_prompt)
        self.assertIn("Panel 1:", spec.compiled_prompt)
        self.assertIn("Panel 9:", spec.compiled_prompt)

    def test_prompt_includes_composition(self):
        """生成 prompt 应包含景别和镜头角度词"""
        prompt = self.kfg.build_keyframe_prompt_text(self.sample_shot, self.cm)
        # 中景 -> medium shot
        self.assertIn("medium", prompt.lower(), "prompt 应包含景别描述")


# ────────────────────────────────────────────────────────────────────────────
#  3. WorkflowManager i2v 强制检查
# ────────────────────────────────────────────────────────────────────────────

class TestWorkflowManagerI2V(unittest.TestCase):

    def _make_manager(self):
        """返回一个不需要真实 API config 的轻量管理器"""
        from src.workflow_manager import WorkflowManager
        with patch.object(WorkflowManager, "_load_config", return_value={}):
            mgr = WorkflowManager(notify_callback=lambda x: None)
        return mgr

    def _run_async(self, coro):
        """Python 3.14 兼容的异步运行器"""
        return asyncio.run(coro)

    def test_generate_video_raises_on_empty_image_path(self):
        """无 image_path 时应抛出 ValueError（SOP 强制 i2v）"""
        mgr = self._make_manager()
        with self.assertRaises(ValueError) as ctx:
            self._run_async(mgr.generate_video(""))
        self.assertIn("SOP", str(ctx.exception))

    def test_generate_video_raises_on_nonexistent_file(self):
        """指向不存在文件的 image_path 应抛出 ValueError"""
        mgr = self._make_manager()
        with self.assertRaises(ValueError) as ctx:
            self._run_async(mgr.generate_video("/tmp/nonexistent_keyframe_xyz123.png"))
        self.assertIn("SOP", str(ctx.exception))



# ────────────────────────────────────────────────────────────────────────────
#  4. QualityAuditor 测试
# ────────────────────────────────────────────────────────────────────────────

class TestQualityAuditor(unittest.TestCase):

    def setUp(self):
        self.auditor = QualityAuditor()
        self.cm = CharacterMaster.example()

    def test_prompt_quality_with_vague_terms_fails(self):
        """含模糊词的 prompt 列表应使 overall_pass=False"""
        bad_prompts = [
            "beautiful woman standing in the park, gorgeous smile",
            "handsome man looking into the distance",
        ]
        report = self.auditor.audit_prompt_quality(bad_prompts)
        self.assertFalse(report.overall_pass, "含模糊词应导致审核不通过")

    def test_prompt_quality_clean_passes(self):
        """结构化描述的 prompt 列表应通过"""
        good_prompts = [
            (
                "early 20s female, jet black waist-length straight hair, oval face, "
                "fair porcelain skin, large almond-shaped dark brown eyes, "
                "wearing white chiffon A-line dress, sitting in café, "
                "soft left-side key light, 5600K daylight, medium shot, "
                "eye level, subject on left third of frame, "
                "photorealistic, cinematic, 4K, 9:16 vertical"
            ),
        ]
        report = self.auditor.audit_prompt_quality(good_prompts)
        self.assertTrue(report.overall_pass, "结构化 prompt 应通过审核")

    def test_character_consistency_score_with_anchor(self):
        """引用完整锚点的 prompt 应得到高一致性分数"""
        anchor = self.cm.to_anchor_fragment()
        score = self.auditor.audit_character_consistency(anchor, [self.cm])
        self.assertGreaterEqual(
            score, SOP_THRESHOLDS["character_consistency"],
            f"完整锚点应达到 ≥{SOP_THRESHOLDS['character_consistency']:.0%} 一致性"
        )

    def test_character_consistency_score_mismatch(self):
        """描述不同角色的 prompt 一致性应显著低于阈值"""
        different_prompt = "tall muscular man, bald head, dark suit, aggressive stance"
        score = self.auditor.audit_character_consistency(different_prompt, [self.cm])
        self.assertLess(
            score, SOP_THRESHOLDS["character_consistency"],
            "不匹配描述的一致性分数应低于要求"
        )

    def test_camera_motion_contradiction_detected(self):
        """矛盾镜头运动应被检测"""
        bad_shot = {"camera_motion": "push-in shot dolly-in forward, pull-back retreating"}
        result = self.auditor.audit_camera_motion(bad_shot)
        self.assertFalse(result, "矛盾镜头运动（push + pull-back）应被检测")

    def test_camera_motion_valid_passes(self):
        """合理的单一镜头运动应通过"""
        good_shot = {"camera_motion": "slow push-in, camera slowly moves closer"}
        result = self.auditor.audit_camera_motion(good_shot)
        self.assertTrue(result, "单一合理镜头运动应通过")

    def test_audit_storyboard_empty(self):
        """空分镜的审核不应崩溃"""
        report = self.auditor.audit_storyboard({}, [self.cm], "ep0")
        self.assertIsNotNone(report)
        self.assertEqual(report.total_shots, 0)


# ────────────────────────────────────────────────────────────────────────────
#  5. ScriptGenerator.parse_structured_script 测试
# ────────────────────────────────────────────────────────────────────────────

class TestScriptGeneratorParsing(unittest.TestCase):

    def test_parse_valid_json_block(self):
        """应能从 ```json ... ``` 代码块中提取结构化数据"""
        from src.script_generator import ScriptGenerator

        gen = MagicMock(spec=ScriptGenerator)
        gen.parse_structured_script = ScriptGenerator.parse_structured_script.__get__(gen, ScriptGenerator)

        sample = """
以下是生成的剧本：
```json
{
  "title": "重生复仇",
  "episode": 1,
  "character_count": 2,
  "conflict_structure": "女主重生后复仇男主",
  "emotion_nodes": ["震惊", "愤怒", "决心"],
  "scenes": [
    {
      "scene_id": "s1",
      "location": "卧室·室内",
      "time_of_day": "清晨",
      "characters": ["林诗雨"],
      "emotion": "震惊",
      "action_summary": "林诗雨坐起身，望向镜子",
      "description": "白色床铺，晨光透过窗帘",
      "dialogues": [{"speaker": "林诗雨", "line": "我重生了？"}]
    }
  ]
}
```
"""
        result = gen.parse_structured_script(sample)
        self.assertIsNotNone(result, "应成功解析 JSON")
        self.assertEqual(result["title"], "重生复仇")
        self.assertIn("scenes", result)
        self.assertEqual(len(result["scenes"]), 1)
        self.assertEqual(result["scenes"][0]["action_summary"], "林诗雨坐起身，望向镜子")

    def test_parse_missing_scenes_returns_none(self):
        """缺少 scenes 字段应返回 None"""
        from src.script_generator import ScriptGenerator

        gen = MagicMock(spec=ScriptGenerator)
        gen.parse_structured_script = ScriptGenerator.parse_structured_script.__get__(gen, ScriptGenerator)

        bad_json = '```json\n{"title": "test"}\n```'
        result = gen.parse_structured_script(bad_json)
        self.assertIsNone(result, "缺少 scenes 字段应返回 None")


# ────────────────────────────────────────────────────────────────────────────
#  主入口
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
