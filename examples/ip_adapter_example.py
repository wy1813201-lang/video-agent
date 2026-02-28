"""
角色一致性图像生成示例
展示如何使用 IP-Adapter + 角色特征库
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.character_consistency import CharacterTrait, PromptEnhancer
from src.ip_adapter_generator import IPAdapterGenerator, generate_character_image


def example_single_character():
    """示例1: 单角色图像生成"""
    print("=" * 50)
    print("示例1: 单角色图像生成 (IP-Adapter)")
    print("=" * 50)
    
    # 定义角色
    character = CharacterTrait(
        name="女主",
        appearance="beautiful young woman, long flowing hair, expressive eyes",
        outfit="elegant blue dress",
        age_range="early 20s",
        gender="female",
        role="protagonist",
        reference_images=["data/characters/heroine_ref.jpg"],
        ip_adapter_scale=0.8,
    )
    
    # 如果有参考图，使用 IP-Adapter
    if character.reference_images and os.path.exists(character.reference_images[0]):
        try:
            result = generate_character_image(
                prompt=f"{character.appearance}, {character.outfit}, high quality, detailed face",
                character_ref=character.reference_images[0],
                output_path="output/character_heroine.jpg",
                ip_adapter_scale=character.ip_adapter_scale,
                seed=character.seed_value or 42,
            )
            print(f"✅ 角色图像已生成: output/character_heroine.jpg")
            return result
        except Exception as e:
            print(f"⚠️ IP-Adapter 生成失败: {e}")
            print("将使用普通 SDXL 生成...")
    
    # 否则使用普通提示词
    print("❌ 未找到参考图像，请放置角色图片到 data/characters/")
    return None


def example_batch_scenes():
    """示例2: 多场景角色一致性生成"""
    print("=" * 50)
    print("示例2: 多场景角色一致性 (IP-Adapter)")
    print("=" * 50)
    
    # 角色定义
    character = CharacterTrait(
        name="男主",
        appearance="handsome young man, short dark hair, strong jawline",
        outfit="smart casual",
        reference_images=["data/characters/hero_ref.jpg"],
    )
    
    # 多个场景提示词
    scenes = [
        "standing in rain, city background, dramatic lighting",
        "sitting in coffee shop, reading book, warm atmosphere",
        "walking on beach at sunset, romantic mood",
    ]
    
    if not character.reference_images or not os.path.exists(character.reference_images[0]):
        print("❌ 请先准备参考图像: data/characters/hero_ref.jpg")
        return
    
    try:
        generator = IPAdapterGenerator()
        
        # 批量生成
        results = generator.generate_batch(
            prompts=scenes,
            reference_images=character.reference_images[0],
            ip_adapter_scale=0.75,
            seed=42002,
        )
        
        # 保存结果
        os.makedirs("output", exist_ok=True)
        for i, img in enumerate(results):
            img.save(f"output/scene_{i+1}.jpg")
            
        print(f"✅ 批量生成完成: 生成了 {len(results)} 张图像")
        
    except Exception as e:
        print(f"❌ 生成失败: {e}")


def example_with_enhancer():
    """示例3: 使用 PromptEnhancer 增强提示词"""
    print("=" * 50)
    print("示例3: 使用 PromptEnhancer")
    print("=" * 50)
    
    # 角色库
    characters = {
        "女主": CharacterTrait(
            name="女主",
            appearance="beautiful young woman, long black hair",
            outfit="red dress",
            reference_images=["data/characters/heroine.jpg"],
            seed_value=42001,
        ),
    }
    
    enhancer = PromptEnhancer(characters)
    
    # 原始提示词
    base_prompt = "in a dark forest, mysterious atmosphere"
    scene_text = "女主独自走在黑暗的森林中"
    
    # 增强后的提示词
    enhanced = enhancer.enhance(
        base_prompt=base_prompt,
        scene_text=scene_text,
        use_ip_adapter=True,
    )
    
    print(f"原始提示词: {base_prompt}")
    print(f"场景描述: {scene_text}")
    print(f"增强后: {enhanced}")
    
    return enhanced


if __name__ == "__main__":
    print("🎬 角色一致性图像生成示例")
    print()
    
    # 确保输出目录存在
    os.makedirs("output", exist_ok=True)
    os.makedirs("data/characters", exist_ok=True)
    
    # 运行示例
    example_with_enhancer()
    print()
    
    # 需要参考图像的示例
    print("💡 要运行完整示例，请:")
    print("   1. pip install diffusers torch pillow")
    print("   2. 下载 IP-Adapter 模型到 ~/.cache/huggingface/")
    print("   3. 准备角色参考图到 data/characters/")
