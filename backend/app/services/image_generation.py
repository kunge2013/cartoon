# -*- coding: utf-8 -*-
"""图片生成服务层（状态机 + 任务管理）。"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.adapters.image_provider import ImageProviderAdapter
from app.config import OUTPUT_DIR
from app.models.image import ImageTask
from app.models.project import Project, Script


class ImageGenerationService:
    """图片生成服务。"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_single(
        self,
        script_id: int,
        provider_code: str = "grsai",
        model: str = "nano-banana-2",
        aspect_ratio: str = "3:4",
        resolution: str = "2K",
    ) -> dict:
        """
        为单个分镜生成图片。
        
        Args:
            script_id: 分镜 ID
            provider_code: 供应商代码
            model: 模型名称
            aspect_ratio: 宽高比
            resolution: 分辨率
        
        Returns:
            {
                "task_id": int,
                "status": str,
                "image_url": str,
            }
        """
        # 获取分镜
        script = self.db.get(Script, script_id)
        if not script:
            raise ValueError(f"Script not found: {script_id}")
        
        # 获取项目
        project = self.db.get(Project, script.project_id)
        if not project:
            raise ValueError(f"Project not found: {script.project_id}")
        
        # 构建输出目录
        output_dir = OUTPUT_DIR / str(project.id) / "1" / "image"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建任务
        task = ImageTask(
            script_id=script_id,
            project_id=project.id,
            status="running",
            image_prompt=script.image_prompt,
            provider_code=provider_code,
            model=model,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            started_at=datetime.now(),
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        try:
            # 调用适配器生成图片
            adapter = ImageProviderAdapter(self.db, provider_code)
            result = adapter.generate_image(
                prompt=script.image_prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                output_dir=output_dir,
            )
            
            # 更新任务状态
            task.status = "done"
            task.image_url = result["image_url"]
            task.generation_time = result["generation_time"]
            task.completed_at = datetime.now()
            
            # 更新分镜的候选图
            candidates = json.loads(script.candidate_images or "{}")
            candidate_key = f"candidate_{task.id}"
            candidates[candidate_key] = {
                "image_url": result["image_url"],
                "task_id": task.id,
                "generation_time": result["generation_time"],
            }
            script.candidate_images = json.dumps(candidates, ensure_ascii=False)
            
            # 如果是第一张候选图，自动设为主图
            if not script.main_image:
                script.main_image = result["image_url"]
                task.is_main = True
                script.selected_candidate = task.id
            
            self.db.commit()
            
            return {
                "task_id": task.id,
                "status": task.status,
                "image_url": task.image_url,
            }
        
        except Exception as e:
            # 更新任务状态为失败
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            self.db.commit()
            
            raise
    
    def generate_batch(
        self,
        script_ids: list[int],
        provider_code: str = "grsai",
        model: str = "nano-banana-2",
        aspect_ratio: str = "3:4",
        resolution: str = "2K",
    ) -> list[dict]:
        """
        批量生成图片。
        
        Args:
            script_ids: 分镜 ID 列表
            provider_code: 供应商代码
            model: 模型名称
            aspect_ratio: 宽高比
            resolution: 分辨率
        
        Returns:
            任务结果列表
        """
        results = []
        for script_id in script_ids:
            try:
                result = self.generate_single(
                    script_id=script_id,
                    provider_code=provider_code,
                    model=model,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                )
                results.append({
                    "script_id": script_id,
                    "status": "success",
                    "task_id": result["task_id"],
                })
            except Exception as e:
                results.append({
                    "script_id": script_id,
                    "status": "failed",
                    "error": str(e),
                })
        
        return results
    
    def select_main_image(
        self,
        script_id: int,
        task_id: int,
    ) -> dict:
        """
        选择候选图作为主图。
        
        Args:
            script_id: 分镜 ID
            task_id: 任务 ID
        
        Returns:
            {
                "script_id": int,
                "main_image": str,
            }
        """
        script = self.db.get(Script, script_id)
        if not script:
            raise ValueError(f"Script not found: {script_id}")
        
        task = self.db.get(ImageTask, task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        if task.script_id != script_id:
            raise ValueError(f"Task {task_id} does not belong to script {script_id}")
        
        if task.status != "done":
            raise ValueError(f"Task {task_id} is not completed")
        
        # 更新主图
        script.main_image = task.image_url
        script.selected_candidate = task_id
        
        # 更新任务的 is_main 标记
        self.db.query(ImageTask).filter(
            ImageTask.script_id == script_id,
            ImageTask.id != task_id,
        ).update({"is_main": False})
        task.is_main = True
        
        self.db.commit()
        
        return {
            "script_id": script_id,
            "main_image": script.main_image,
        }
    
    def get_candidates(
        self,
        script_id: int,
    ) -> list[dict]:
        """
        获取分镜的所有候选图。
        
        Args:
            script_id: 分镜 ID
        
        Returns:
            候选图列表
        """
        tasks = self.db.query(ImageTask).filter(
            ImageTask.script_id == script_id,
            ImageTask.status == "done",
        ).all()
        
        return [
            {
                "task_id": task.id,
                "image_url": task.image_url,
                "generation_time": task.generation_time,
                "is_main": task.is_main,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            }
            for task in tasks
        ]
    
    def get_task(self, task_id: int) -> ImageTask:
        """
        获取单个任务。
        
        Args:
            task_id: 任务 ID
        
        Returns:
            ImageTask 对象
        """
        return self.db.query(ImageTask).filter(ImageTask.id == task_id).first()
    
    def list_tasks(
        self,
        script_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[ImageTask]:
        """
        列出任务。
        
        Args:
            script_id: 分镜 ID（可选）
            status: 任务状态（可选：pending/running/done/failed）
        
        Returns:
            任务列表
        """
        query = self.db.query(ImageTask)
        
        if script_id is not None:
            query = query.filter(ImageTask.script_id == script_id)
        
        if status is not None:
            query = query.filter(ImageTask.status == status)
        
        return query.order_by(ImageTask.created_at.desc()).all()
    
    def get_task(self, task_id: int) -> ImageTask:
        """
        获取单个任务。
        
        Args:
            task_id: 任务 ID
        
        Returns:
            ImageTask 对象
        """
        return self.db.query(ImageTask).filter(ImageTask.id == task_id).first()
    
    def list_tasks(
        self,
        script_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[ImageTask]:
        """
        列出任务。
        
        Args:
            script_id: 分镜 ID（可选）
            status: 任务状态（可选：pending/running/done/failed）
        
        Returns:
            任务列表
        """
        query = self.db.query(ImageTask)
        
        if script_id is not None:
            query = query.filter(ImageTask.script_id == script_id)
        
        if status is not None:
            query = query.filter(ImageTask.status == status)
        
        return query.order_by(ImageTask.created_at.desc()).all()
    
    def get_task(
        self,
        task_id: int,
    ) -> Optional[ImageTask]:
        """
        获取单个任务。
        
        Args:
            task_id: 任务 ID
        
        Returns:
            ImageTask 实例或 None
        """
        return self.db.get(ImageTask, task_id)
    
    def list_tasks(
        self,
        script_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[ImageTask]:
        """
        列出任务。
        
        Args:
            script_id: 分镜 ID（可选过滤）
            status: 任务状态（可选过滤）
        
        Returns:
            任务列表
        """
        query = self.db.query(ImageTask)
        if script_id:
            query = query.filter(ImageTask.script_id == script_id)
        if status:
            query = query.filter(ImageTask.status == status)
        return query.order_by(ImageTask.created_at.desc()).all()
