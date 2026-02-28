"""
IP-Adapter 图像生成器
基于 diffusers 实现 IP-Adapter 角色一致性图像生成
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple, Union

try:
    from diffusers import StableDiffusionXLAdapterPipeline
    from diffusers.utils import load_image
    import torch
    from PIL import Image
    HAS_DIFFUSERS = True
except ImportError:
    HAS_DIFFUSERS = False


logger = logging.getLogger(__name__)


class IPAdapterGenerator:
    """
    IP-Adapter 图像生成器
    使用参考图像保持角色一致性
    """

    _PIPELINE_CACHE: Dict[Tuple[str, str, str], StableDiffusionXLAdapterPipeline] = {}
    _PIPELINE_REF_COUNTS: Dict[Tuple[str, str, str], int] = {}

    def __init__(
        self,
        model_path: str = "stabilityai/stable-diffusion-xl-base-1.0",
        ip_adapter_path: str = "h94/IP-Adapter",
        device: Optional[str] = None,
        attention_backend: str = "auto",
    ):
        """
        初始化 IP-Adapter 生成器

        Args:
            model_path: Stable Diffusion XL 模型路径
            ip_adapter_path: IP-Adapter 模型路径
            device: 生成设备 (cuda/cpu)
            attention_backend: 注意力后端 (auto/xformers/sdpa/none)
        """
        if not HAS_DIFFUSERS:
            raise ImportError("需要安装 diffusers: pip install diffusers")

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.device = device
        self.model_path = model_path
        self.ip_adapter_path = ip_adapter_path
        self.attention_backend = attention_backend.lower()
        self.pipeline: Optional[StableDiffusionXLAdapterPipeline] = None
        self._cache_key: Optional[Tuple[str, str, str]] = None

    @staticmethod
    def _build_cache_key(model_path: str, ip_adapter_path: str, device: str) -> Tuple[str, str, str]:
        return (model_path, ip_adapter_path, device)

    def _configure_attention_backend(self, pipeline: StableDiffusionXLAdapterPipeline):
        """启用 xFormers / SDPA 注意力优化。"""
        if self.device != "cuda":
            logger.debug("非 CUDA 设备，跳过 xFormers/SDPA 配置")
            return

        backend = self.attention_backend
        if backend in ("auto", "xformers"):
            try:
                pipeline.enable_xformers_memory_efficient_attention()
                logger.info("已启用 xFormers memory efficient attention")
                return
            except Exception as exc:
                if backend == "xformers":
                    logger.warning("xFormers 启用失败，将继续使用默认注意力: %s", exc)
                    return
                logger.debug("xFormers 不可用，尝试 SDPA: %s", exc)

        if backend in ("auto", "sdpa"):
            try:
                from diffusers.models.attention_processor import AttnProcessor2_0

                if hasattr(pipeline, "unet") and pipeline.unet is not None:
                    pipeline.unet.set_attn_processor(AttnProcessor2_0())
                if hasattr(pipeline, "vae") and pipeline.vae is not None:
                    pipeline.vae.set_attn_processor(AttnProcessor2_0())
                logger.info("已启用 PyTorch SDPA (AttnProcessor2_0)")
                return
            except Exception as exc:
                logger.warning("SDPA 启用失败，将继续使用默认注意力: %s", exc)

        logger.info("注意力后端设置为 %s，使用默认实现", backend)

    def load_pipeline(self):
        """加载 IP-Adapter Pipeline（支持类级缓存复用）。"""
        if self.pipeline is not None:
            return

        cache_key = self._build_cache_key(self.model_path, self.ip_adapter_path, self.device)
        self._cache_key = cache_key

        if cache_key in self._PIPELINE_CACHE:
            self.pipeline = self._PIPELINE_CACHE[cache_key]
            self._PIPELINE_REF_COUNTS[cache_key] = self._PIPELINE_REF_COUNTS.get(cache_key, 0) + 1
            logger.info(
                "复用已缓存 IP-Adapter pipeline: model=%s, device=%s, refs=%d",
                self.model_path,
                self.device,
                self._PIPELINE_REF_COUNTS[cache_key],
            )
            return

        start = time.perf_counter()
        logger.info("正在加载 IP-Adapter pipeline: %s", self.model_path)

        pipeline_kwargs = {
            "torch_dtype": torch.float16 if self.device == "cuda" else torch.float32,
        }
        if self.device == "cuda":
            pipeline_kwargs["variant"] = "fp16"

        pipeline = StableDiffusionXLAdapterPipeline.from_pretrained(
            self.model_path,
            **pipeline_kwargs,
        )

        pipeline.load_ip_adapter(
            self.ip_adapter_path,
            subfolder="sdxl_models",
            weight_name="ip-adapter_sdxl.bin"
        )

        if self.device == "cuda":
            pipeline = pipeline.to("cuda")

        self._configure_attention_backend(pipeline)

        self.pipeline = pipeline
        self._PIPELINE_CACHE[cache_key] = pipeline
        self._PIPELINE_REF_COUNTS[cache_key] = self._PIPELINE_REF_COUNTS.get(cache_key, 0) + 1

        elapsed = time.perf_counter() - start
        logger.info("IP-Adapter pipeline 加载完成，耗时 %.2fs", elapsed)

    def unload(self):
        """减少 pipeline 引用并在无引用时释放显存。"""
        if self.pipeline is None:
            return

        cache_key = self._cache_key
        self.pipeline = None

        if cache_key is None:
            return

        ref_count = self._PIPELINE_REF_COUNTS.get(cache_key, 0) - 1
        if ref_count > 0:
            self._PIPELINE_REF_COUNTS[cache_key] = ref_count
            logger.info("pipeline 引用减少: key=%s, refs=%d", cache_key, ref_count)
            return

        pipeline = self._PIPELINE_CACHE.pop(cache_key, None)
        self._PIPELINE_REF_COUNTS.pop(cache_key, None)
        if pipeline is not None:
            del pipeline

        if self.device == "cuda":
            torch.cuda.empty_cache()

        logger.info("IP-Adapter pipeline 已卸载: key=%s", cache_key)

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

        ref_imgs = []
        for img in reference_images:
            if isinstance(img, str):
                ref_imgs.append(load_image(img))
            else:
                ref_imgs.append(img)

        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        else:
            generator = None

        start = time.perf_counter()
        try:
            self.pipeline.set_ip_adapter_scale(ip_adapter_scale)
            with torch.inference_mode():
                images = self.pipeline(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    ip_adapter_image=ref_imgs,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    generator=generator,
                ).images
        except Exception as e:
            raise RuntimeError(f"图像生成失败: {e}") from e

        elapsed = time.perf_counter() - start
        logger.info("单图生成完成，耗时 %.2fs，steps=%d", elapsed, num_inference_steps)
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

        if not isinstance(reference_images, list):
            ref_imgs = [reference_images]
        else:
            ref_imgs = reference_images

        loaded_refs = []
        for img in ref_imgs:
            if isinstance(img, str):
                loaded_refs.append(load_image(img))
            else:
                loaded_refs.append(img)

        batch_start = time.perf_counter()
        results = []
        for prompt in prompts:
            img = self.generate_with_reference(
                prompt=prompt,
                reference_images=loaded_refs,
                **kwargs
            )
            results.append(img)

        elapsed = time.perf_counter() - batch_start
        if prompts:
            logger.info(
                "批量生成完成，数量=%d，总耗时 %.2fs，平均 %.2fs/张",
                len(prompts),
                elapsed,
                elapsed / len(prompts),
            )
        else:
            logger.info("批量生成完成，数量=0")

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
        logger.info("LoRA 权重已加载: %s", lora_path)

    def unload_lora(self):
        """卸载 LoRA"""
        self.pipeline.unfuse_lora()
        logger.info("LoRA 已卸载")


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

    refs = character_ref if isinstance(character_ref, list) else [character_ref]

    result = generator.generate_with_reference(
        prompt=prompt,
        reference_images=refs,
        ip_adapter_scale=ip_adapter_scale,
        **kwargs
    )

    if output_path:
        result.save(output_path)
        logger.info("图像已保存: %s", output_path)

    return result


# === 使用示例 ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

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

    logger.info("IP-Adapter 生成器已就绪!")
    logger.info("需要先安装依赖: pip install diffusers torch pillow")
    logger.info("并下载 IP-Adapter 模型权重")
