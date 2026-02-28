"""
IP-Adapter 图像生成器
基于 diffusers 实现 IP-Adapter 角色一致性图像生成
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    from diffusers import StableDiffusionXLAdapterPipeline, StableDiffusionXLInpaintPipeline
    from diffusers.utils import load_image
    import torch
    from PIL import Image
    HAS_DIFFUSERS = True
except ImportError:
    HAS_DIFFUSERS = False


class IPAdapterGenerator:
    """
    IP-Adapter 图像生成器
    使用参考图像保持角色一致性
    """

    def __init__(
        self,
        model_path: str = "stabilityai/stable-diffusion-xl-base-1.0",
        ip_adapter_path: str = "h94/IP-Adapter",
        device: str = "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu",
    ):
        """
        初始化 IP-Adapter 生成器
        
        Args:
            model_path: Stable Diffusion XL 模型路径
            ip_adapter_path: IP-Adapter 模型路径
            device: 生成设备 (cuda/cpu)
        """
        if not HAS_DIFFUSERS:
            raise ImportError("需要安装 diffusers: pip install diffusers")
        
        self.device = device
        self.model_path = model_path
        self.ip_adapter_path = ip_adapter_path
        self.pipeline = None
        
    def load_pipeline(self):
        """加载 IP-Adapter Pipeline"""
        if self.pipeline is not None:
            return
            
        print(f"正在加载 IP-Adapter pipeline from {self.model_path}...")
        
        # 加载 SDXL + IP-Adapter pipeline
        self.pipeline = StableDiffusionXLAdapterPipeline.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            variant="fp16",
        )
        
        # 加载 IP-Adapter 权重
        self.pipeline.load_ip_adapter(
            self.ip_adapter_path,
            subfolder="sdxl_models",
            weight_name="ip-adapter_sdxl.bin"
        )
        
        # 设置 LoRA 权重（可选）
        # self.pipeline.load_lora_weights(lora_path, weight_name="pytorch_lora_weights.bin")
        
        if self.device == "cuda":
            self.pipeline = self.pipeline.to("cuda")
        
        print("IP-Adapter pipeline 加载完成!")
        
    def unload(self):
        """卸载 pipeline 释放内存"""
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
            if self.device == "cuda":
                import torch
                torch.cuda.empty_cache()
            print("IP-Adapter pipeline 已卸载")
        
    def generate_with_reference(
        self,
        prompt: str,
        reference_images: List[Union[str, Image.Image]],
        negative_prompt: str = "",
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        ip_adapter_scale: float = 0.7,
    ) -> Image.Image:
        """
        使用参考图像生成保持角色一致性的图像
        
        Args:
            prompt: 图像描述提示词
            reference_images: 参考图像列表 (路径或 PIL Image)
            negative_prompt: 负面提示词
            num_inference_steps: 推理步数
            guidance_scale: 引导系数
            seed: 随机种子
            ip_adapter_scale: IP-Adapter 强度 (0-1)
            
        Returns:
            生成的 PIL Image
        """
        if self.pipeline is None:
            self.load_pipeline()
            
        # 加载参考图像
        ref_imgs = []
        for img in reference_images:
            if isinstance(img, str):
                ref_imgs.append(load_image(img))
            else:
                ref_imgs.append(img)
        
        # 设置种子
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        else:
            generator = None
        
        # 生成图像
        try:
            images = self.pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                ip_adapter_image=ref_imgs,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
                ip_adapter_scale=ip_adapter_scale,
            ).images
        except Exception as e:
            raise RuntimeError(f"图像生成失败: {e}") from e
        
        return images[0]
    
    def generate_batch(
        self,
        prompts: List[str],
        reference_images: Union[List[Union[str, Image.Image]], str, Image.Image],
        **kwargs
    ) -> List[Image.Image]:
        """
        批量生成保持角色一致性的图像
        
        Args:
            prompts: 提示词列表
            reference_images: 参考图像 (单个或列表)
            
        Returns:
            生成的图像列表
        """
        if self.pipeline is None:
            self.load_pipeline()
            
        # 确保参考图像是列表
        if not isinstance(reference_images, list):
            ref_imgs = [reference_images]
        else:
            ref_imgs = reference_images
            
        # 加载参考图像
        loaded_refs = []
        for img in ref_imgs:
            if isinstance(img, str):
                loaded_refs.append(load_image(img))
            else:
                loaded_refs.append(img)
        
        results = []
        for prompt in prompts:
            img = self.generate_with_reference(
                prompt=prompt,
                reference_images=loaded_refs,
                **kwargs
            )
            results.append(img)
            
        return results


class LoRALoader:
    """
    LoRA 加载器管理
    """
    
    def __init__(self, pipeline):
        self.pipeline = pipeline
        
    def load_lora(
        self,
        lora_path: str,
        lora_name: str = "pytorch_lora_weights.bin",
        alpha: float = 0.75,
    ):
        """
        加载 LoRA 权重
        
        Args:
            lora_path: LoRA 文件路径
            lora_name: LoRA 文件名
            alpha: LoRA 权重混合比例
        """
        self.pipeline.load_lora_weights(
            lora_path,
            weight_name=lora_name,
        )
        self.pipeline.fuse_lora(lora_alpha=alpha)
        print(f"LoRA 权重已加载: {lora_path}")
        
    def unload_lora(self):
        """卸载 LoRA"""
        self.pipeline.unfuse_lora()
        print("LoRA 已卸载")


# === 便捷函数 ===

def generate_character_image(
    prompt: str,
    character_ref: Union[str, Image.Image, List[Union[str, Image.Image]]],
    output_path: Optional[str] = None,
    ip_adapter_scale: float = 0.7,
    **kwargs
) -> Image.Image:
    """
    使用参考图像生成角色图像的便捷函数
    
    Args:
        prompt: 图像描述
        character_ref: 参考图像路径或 PIL Image 或其列表
        output_path: 输出路径 (可选)
        ip_adapter_scale: IP-Adapter 强度
        
    Returns:
        生成的 PIL Image
    """
    generator = IPAdapterGenerator()
    
    # 确保是列表
    refs = character_ref if isinstance(character_ref, list) else [character_ref]
    
    result = generator.generate_with_reference(
        prompt=prompt,
        reference_images=refs,
        ip_adapter_scale=ip_adapter_scale,
        **kwargs
    )
    
    if output_path:
        result.save(output_path)
        print(f"图像已保存: {output_path}")
        
    return result


# === 使用示例 ===
if __name__ == "__main__":
    # 示例 1: 单图生成
    # result = generate_character_image(
    #     prompt="beautiful young woman, elegant dress, standing in garden",
    #     character_ref="/path/to/reference_face.jpg",
    #     output_path="output_character.jpg",
    #     seed=42
    # )
    
    # 示例 2: 批量生成
    # generator = IPAdapterGenerator()
    # results = generator.generate_batch(
    #     prompts=[
    #         "woman in red dress, walking on beach",
    #         "woman in blue jeans, sitting in cafe",
    #         "woman in formal suit, in office"
    #     ],
    #     reference_images="/path/to/reference_face.jpg",
    #     ip_adapter_scale=0.8
    # )
    
    print("IP-Adapter 生成器已就绪!")
    print("需要先安装依赖: pip install diffusers torch pillow")
    print("并下载 IP-Adapter 模型权重")
