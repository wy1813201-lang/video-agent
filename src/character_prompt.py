"""
角色一致性Prompt优化
为视频生成提供统一的人物描述
"""

# 林夏角色统一描述
CHARACTER_PROFILE = {
    "name": "林夏",
    "gender": "女性",
    "age": "25-30岁",
    "hair": "长发披肩，黑色",
    "outfit": "莫兰迪色真丝衬衫",
    "accessories": "精致腕表",
    "makeup": "精致职场妆",
    "temperament": "冷静自信",
    "style": "职场女强人"
}

# 模板
CHARACTER_TEMPLATE = """林夏，{age}女性，长发披肩黑色头发，身穿{outfit}，佩戴{accessories}，{makeup}，{temperament}气质，{style}风格，{action}，电影质感，4K高清"""


def build_video_prompt(
    action: str,
    base_prompt: str = "",
    character: dict = None
) -> str:
    """
    构建角色一致性视频Prompt
    
    Args:
        action: 场景动作描述
        base_prompt: 基础Prompt
        character: 角色字典，默认使用林夏
        
    Returns:
        优化后的Prompt
    """
    if character is None:
        character = CHARACTER_PROFILE
    
    # 构建角色描述
    character_desc = f"""{character['name']}，{character['age']}{character['gender']}，{character['hair']}，身穿{character['outfit']}，佩戴{character['accessories']}，{character['makeup']}，{character['temperament']}，{character['style']}"""
    
    # 组合完整Prompt
    if base_prompt:
        full_prompt = f"{character_desc}，{base_prompt}，电影质感，4K高清"
    else:
        full_prompt = f"{character_desc}，{action}，电影质感，4K高清"
    
    return full_prompt


# 场景Prompt模板
SCENE_PROMPTS = {
    1: {
        "action": "在会议室发言",
        "base": "坐在会议桌主位，神态从容"
    },
    2: {
        "action": "在写字楼电梯厅",
        "base": "拦下关键客户，目光锐利"
    },
    3: {
        "action": "在公司走廊",
        "base": "边走边看平板数据"
    },
    4: {
        "action": "在办公室落地窗前",
        "base": "放下签字笔，回眸微笑"
    },
    5: {
        "action": "走出会议室",
        "base": "踩高跟鞋，背影飒爽"
    }
}


def get_scene_prompt(scene_num: int) -> str:
    """获取场景Prompt"""
    if scene_num not in SCENE_PROMPTS:
        scene_num = 1
    
    scene = SCENE_PROMPTS[scene_num]
    return build_video_prompt(
        action=scene["action"],
        base_prompt=scene["base"]
    )


if __name__ == "__main__":
    # 测试
    for i in range(1, 6):
        prompt = get_scene_prompt(i)
        print(f"场景{i}: {prompt}")
