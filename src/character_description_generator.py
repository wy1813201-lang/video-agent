#!/usr/bin/env python3
"""
角色描述生成器
支持 Opus → MiniMax 自动 fallback

用于从剧本生成结构化角色描述，然后转换为 CharacterMaster
"""

import json
import re
import asyncio
from typing import Optional, Dict, Any, List

# LLM 可用性检测
OPENAI_AVAILABLE = False
ANTHROPIC_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    pass

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    pass


SYSTEM_PROMPT = """你是一个专业的AI短剧角色设计师。
你的任务是从剧本中提取角色，并生成结构化的外貌描述。

【核心原则】
1. 禁止使用模糊词：帅气、漂亮、美丽、好看、英俊、可爱、迷人、性感
2. 必须使用结构化、可测量的描述语言
3. 每个描述字段都要有具体数值或形态

【输出格式】
请返回严格JSON格式（包裹在```json ... ```中）：

{
  "character_name": "角色名",
  "gender": "male / female",
  "age_range": "如 early 20s / mid 30s",
  "hair_color": "如 jet black / platinum blonde",
  "hair_style": "如 waist-length straight / short layered bob",
  "face_structure": "如 oval face, high cheekbones, defined chin",
  "skin_tone": "如 fair porcelain skin / medium olive",
  "eye_description": "如 large almond-shaped dark brown eyes",
  "nose_description": "如 straight nose, refined tip",
  "lip_description": "如 full lips, natural rose pink",
  "height_proportion": "如 168cm, long leg-to-torso ratio 0.55",
  "body_type": "如 slender athletic build / curvy figure",
  "outfit_primary": "主服装如 white chiffon A-line dress",
  "outfit_collar": "领口如 V-neck, 8cm depth",
  "outfit_sleeve": "袖型如 cap sleeve / long sleeve",
  "outfit_texture": "面料如 semi-transparent chiffon with floral embroidery",
  "outfit_accessories": ["配饰列表"],
  "personality": "性格描述（可选）",
  "role_in_story": "protagonist / antagonist / supporting"
}

请为剧本中每个出现的角色生成描述。"""


class CharacterDescriptionGenerator:
    """角色描述生成器，支持 LLM fallback"""
    
    def __init__(self, api_config: dict):
        self.api_config = api_config
        self.client_type = None
        self.custom_opus = None
        self.minimax_config = None
        self._client = None  # anthropic client
        self._init_client()
    
    def _init_client(self):
        """初始化 LLM 客户端，优先级: custom_opus > minimax"""
        import requests
        
        self._requests = requests

        # 1. 尝试 custom_opus
        custom_opus = self.api_config.get("script", {}).get("custom_opus", {})
        if custom_opus.get("enabled") and custom_opus.get("api_key"):
            self.custom_opus = {
                "api_key": custom_opus["api_key"],
                "base_url": custom_opus.get("base_url", "http://47.253.7.24:3000"),
                "model": custom_opus.get("model", "claude-opus-4-6")
            }
            self.client_type = "custom_opus"
            print("[CharacterDescriptionGenerator] 使用 custom_opus")
            return
        
        # 2. Fallback: minimax
        minimax_cfg = self.api_config.get("script", {}).get("minimax", {})
        if minimax_cfg.get("enabled") and minimax_cfg.get("api_key"):
            self.minimax_config = {
                "api_key": minimax_cfg["api_key"],
                "group_id": minimax_cfg.get("group_id", ""),
                "model": minimax_cfg.get("model", "MiniMax-M2.1")
            }
            self.client_type = "minimax"
            print("[CharacterDescriptionGenerator] 使用 minimax (fallback)")
            return
        
        # 3. Fallback: openai
        openai_cfg = self.api_config.get("script", {}).get("openai", {})
        if openai_cfg.get("api_key") and OPENAI_AVAILABLE:
            openai.api_key = openai_cfg["api_key"]
            self.client_type = "openai"
            print("[CharacterDescriptionGenerator] 使用 openai (fallback)")
            return
        
        # 4. Fallback: anthropic
        anthropic_cfg = self.api_config.get("script", {}).get("anthropic", {})
        if anthropic_cfg.get("api_key") and ANTHROPIC_AVAILABLE:
            self._client = anthropic.Anthropic(api_key=anthropic_cfg["api_key"])
            self.client_type = "anthropic"
            print("[CharacterDescriptionGenerator] 使用 anthropic (fallback)")
            return
        
        raise RuntimeError("没有可用的 LLM 客户端")
    
    async def generate_descriptions(self, script: str) -> List[Dict]:
        """
        从剧本生成所有角色的结构化描述
        
        Args:
            script: 剧本文本
            
        Returns:
            角色描述列表
        """
        # 提取角色列表
        characters = self._extract_characters(script)
        
        if not characters:
            print("[CharacterDescriptionGenerator] 未找到角色，跳过")
            return []
        
        print(f"[CharacterDescriptionGenerator] 找到角色: {characters}")
        
        # 为每个角色生成描述
        results = []
        for char_name in characters:
            try:
                desc = await self._generate_single(char_name, script)
                if desc:
                    results.append(desc)
            except Exception as e:
                print(f"[CharacterDescriptionGenerator] 角色 {char_name} 生成失败: {e}")
                continue
        
        return results
    
    def _extract_characters(self, script: str) -> List[str]:
        """从剧本提取角色名列表"""
        characters = []
        seen = set()
        
        for line in script.split('\n'):
            match = re.match(r'^([^：:\n]+)[:：]', line.strip())
            if match:
                name = match.group(1).strip()
                # 过滤场景标记等
                if name and len(name) < 10 and name not in seen:
                    if not re.match(r'^场景\d+$', name):
                        if name not in {"对话", "台词", "旁白", "字幕", "内容"}:
                            seen.add(name)
                            characters.append(name)
        
        return characters
    
    async def _generate_single(self, character_name: str, script: str) -> Optional[Dict]:
        """生成单个角色的结构化描述"""
        prompt = f"""请从以下剧本中提取角色"{character_name}"的详细外貌描述。

要求：
1. 禁止模糊词（帅气、漂亮、可爱等）
2. 必须结构化描述
3. 参考角色在剧本中的服装、行为推断

剧本：
{script[:3000]}

请只返回这个角色的描述 JSON。"""
        
        try:
            # 优先尝试 custom_opus
            if self.client_type == "custom_opus":
                return await self._call_custom_opus(prompt)
            elif self.client_type == "minimax":
                return await self._call_minimax(prompt)
            elif self.client_type == "openai":
                return await self._call_openai(prompt)
            elif self.client_type == "anthropic":
                return await self._call_anthropic(prompt)
        except Exception as e:
            print(f"[CharacterDescriptionGenerator] {self.client_type} 调用失败: {e}")
            # 尝试 fallback 到 minimax
            if self.client_type != "minimax":
                try:
                    print("[CharacterDescriptionGenerator] 尝试 fallback 到 minimax...")
                    self.client_type = "minimax"
                    return await self._call_minimax(prompt)
                except Exception as e2:
                    print(f"[CharacterDescriptionGenerator] minimax fallback 也失败: {e2}")
            raise
    
    async def _call_custom_opus(self, prompt: str) -> Dict:
        """调用 custom_opus API"""
        url = f"{self.custom_opus['base_url']}/v1/messages"
        headers = {
            "Authorization": f"Bearer {self.custom_opus['api_key']}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        data = {
            "model": self.custom_opus['model'],
            "max_tokens": 2000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        def _sync_call():
            response = self._requests.post(url, headers=headers, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"]
        
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _sync_call)
        return self._parse_json_response(text)
    
    async def _call_minimax(self, prompt: str) -> Dict:
        """调用 MiniMax API"""
        url = "https://api.minimax.chat/v1/text/chatcompletion_pro"
        headers = {
            "Authorization": f"Bearer {self.minimax_config['api_key']}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.minimax_config["model"],
            "group_id": self.minimax_config["group_id"],
            "max_tokens": 2000,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        }
        
        def _sync_call():
            response = self._requests.post(url, headers=headers, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _sync_call)
        return self._parse_json_response(text)
    
    async def _call_openai(self, prompt: str) -> Dict:
        """调用 OpenAI API"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        text = response.choices[0].message.content
        return self._parse_json_response(text)
    
    async def _call_anthropic(self, prompt: str) -> Dict:
        """调用 Anthropic API"""
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            system=SYSTEM_PROMPT,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        text = response.content[0].text
        return self._parse_json_response(text)
    
    def _parse_json_response(self, text: str) -> Dict:
        """解析 JSON 响应，提取 JSON 部分"""
        # 尝试提取 ```json ... ``` 块
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # 尝试直接解析
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_str = match.group(0)
            else:
                raise ValueError(f"无法从响应中提取 JSON: {text[:200]}")
        
        return json.loads(json_str)


# 便捷函数
async def create_character_masters_from_script(script: str, api_config: dict, output_dir: str = "data/character_masters") -> 'CharacterMasterRegistry':
    """
    从剧本创建角色母版
    
    Args:
        script: 剧本文本
        api_config: API 配置
        output_dir: 角色母版输出目录
        
    Returns:
        CharacterMasterRegistry 注册表
    """
    from src.character_master import CharacterMaster, CharacterMasterRegistry
    
    # 生成角色描述
    generator = CharacterDescriptionGenerator(api_config)
    character_descs = await generator.generate_descriptions(script)
    
    if not character_descs:
        print("[create_character_masters] 未生成任何角色描述")
        return CharacterMasterRegistry(output_dir)
    
    # 创建注册表
    registry = CharacterMasterRegistry(output_dir)
    
    # 转换为 CharacterMaster 并注册
    for i, desc in enumerate(character_descs):
        try:
            master = CharacterMaster(
                character_id=f"char_{i+1:03d}",
                name=desc.get("character_name", desc.get("name", f"角色{i+1}")),
                gender=desc.get("gender", "female"),
                age_range=desc.get("age_range", "early 20s"),
                hair_color=desc.get("hair_color", "jet black"),
                hair_style=desc.get("hair_style", "waist-length straight"),
                face_structure=desc.get("face_structure", "oval face"),
                skin_tone=desc.get("skin_tone", "fair skin"),
                eye_description=desc.get("eye_description", "dark brown eyes"),
                nose_description=desc.get("nose_description", ""),
                lip_description=desc.get("lip_description", ""),
                height_proportion=desc.get("height_proportion", ""),
                body_type=desc.get("body_type", ""),
                outfit_primary=desc.get("outfit_primary", ""),
                outfit_collar=desc.get("outfit_collar", ""),
                outfit_sleeve=desc.get("outfit_sleeve", ""),
                outfit_texture=desc.get("outfit_texture", ""),
                outfit_accessories=desc.get("outfit_accessories", []),
                personality=desc.get("personality", ""),
                role_in_story=desc.get("role_in_story", "supporting"),
            )
            registry.register(master)
            print(f"   ✓ 角色母版已创建: {master.name}")
        except Exception as e:
            print(f"   ⚠️ 角色 {desc.get('character_name', i)} 创建失败: {e}")
            continue
    
    return registry


if __name__ == "__main__":
    # 测试
    test_script = """
场景1: [公司大厅]
保安: 哎，站住。你不能进去。
林晚: 我来面试的，让开。
保安: 没有预约不能进。
林晚: 我是林氏集团的千金！

场景2: [会议室]
林晚: 这笔并购案的问题在于股权结构。
陈总: 你怎么知道？
    """
    
    import os
    config_path = "/Users/you/.openclaw/workspace/ai-short-drama-automator/config/api_keys.json"
    if os.path.exists(config_path):
        with open(config_path) as f:
            api_config = json.load(f)
    else:
        api_config = {}
    
    async def test():
        registry = await create_character_masters_from_script(test_script, api_config)
        print(f"\n已创建 {len(registry.list_all())} 个角色母版")
        for m in registry.list_all():
            print(f"  - {m.name}: {m.to_anchor_fragment()[:100]}...")
    
    asyncio.run(test())
