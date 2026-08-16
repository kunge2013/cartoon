# -*- coding: utf-8 -*-
"""图片生成供应商适配器（OpenAI 兼容协议）。"""
import base64
import time
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models.provider import ProviderAccount


class ImageProviderAdapter:
    """图片生成供应商适配器（OpenAI 兼容协议）。"""
    
    def __init__(self, db: Session, provider_code: str = "grsai"):
        self.db = db
        self.provider_code = provider_code
        self.account = self._get_account()
    
    def _get_account(self) -> Optional[ProviderAccount]:
        """获取供应商账号配置。"""
        return self.db.query(ProviderAccount).filter(
            ProviderAccount.provider_code == self.provider_code,
            ProviderAccount.valid == True
        ).first()
    
    def generate_image(
        self,
        prompt: str,
        model: str = "nano-banana-2",
        aspect_ratio: str = "3:4",
        resolution: str = "2K",
        output_dir: Optional[Path] = None,
    ) -> dict:
        """
        生成单张图片。
        
        Args:
            prompt: 图片提示词
            model: 模型名称
            aspect_ratio: 宽高比（如 "3:4"）
            resolution: 分辨率（如 "2K"）
            output_dir: 输出目录（可选，不指定则返回 URL）
        
        Returns:
            {
                "image_url": str,  # 图片 URL 或本地路径
                "generation_time": float,  # 生成耗时（秒）
            }
        """
        if not self.account:
            raise ValueError(f"Provider account not found: {self.provider_code}")
        
        base_url = self.account.base_url.rstrip("/")
        api_key = self.account.api_key
        
        # 构建请求
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        
        start_time = time.time()
        
        # 调用 API
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{base_url}/images/generations",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        
        generation_time = time.time() - start_time
        
        result = response.json()
        
        # 解析响应（OpenAI 兼容格式）
        if "data" in result and len(result["data"]) > 0:
            image_data = result["data"][0]
            
            # 如果返回 base64，保存到本地
            if "b64_json" in image_data and output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = int(time.time() * 1000)
                filename = f"image_{timestamp}.png"
                filepath = output_dir / filename
                
                image_bytes = base64.b64decode(image_data["b64_json"])
                filepath.write_bytes(image_bytes)
                
                return {
                    "image_url": str(filepath),
                    "generation_time": generation_time,
                }
            
            # 如果返回 URL，直接返回
            elif "url" in image_data:
                return {
                    "image_url": image_data["url"],
                    "generation_time": generation_time,
                }
        
        raise ValueError("Invalid response format from image provider")
    
    def generate_batch(
        self,
        prompts: list[str],
        model: str = "nano-banana-2",
        aspect_ratio: str = "3:4",
        resolution: str = "2K",
        output_dir: Optional[Path] = None,
        concurrency: int = 5,
    ) -> list[dict]:
        """
        批量生成图片。
        
        Args:
            prompts: 提示词列表
            model: 模型名称
            aspect_ratio: 宽高比
            resolution: 分辨率
            output_dir: 输出目录
            concurrency: 并发数
        
        Returns:
            结果列表，每个元素包含 image_url 和 generation_time
        """
        # 简单实现：串行调用（实际应该用异步或线程池实现并发）
        results = []
        for prompt in prompts:
            try:
                result = self.generate_image(
                    prompt=prompt,
                    model=model,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                    output_dir=output_dir,
                )
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        
        return results
