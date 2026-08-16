# -*- coding: utf-8 -*-
"""图片导出服务：长图拼接 + ZIP 打包。"""
import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.config import OUTPUT_DIR
from app.models.export import ExportTask
from app.models.project import Project, Script


class ExportService:
    """图片导出服务。"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_export_task(
        self,
        project_id: int,
        export_style: str = "vertical",
        page_numbers: bool = False,
        titles: bool = False,
        quality: int = 90,
    ) -> ExportTask:
        """
        创建导出任务。
        
        Args:
            project_id: 项目 ID
            export_style: 导出样式（vertical/horizontal）
            page_numbers: 是否添加页码
            titles: 是否添加标题
            quality: JPEG 质量 (1-100)
        
        Returns:
            ExportTask 实例
        """
        task = ExportTask(
            project_id=project_id,
            status="pending",
            export_style=export_style,
            page_numbers=page_numbers,
            titles=titles,
            quality=quality,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def execute_export(self, task_id: int) -> ExportTask:
        """
        执行导出任务。
        
        Args:
            task_id: 任务 ID
        
        Returns:
            更新后的 ExportTask
        """
        task = self.db.get(ExportTask, task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        task.status = "running"
        task.started_at = datetime.now()
        self.db.commit()
        
        try:
            project = self.db.get(Project, task.project_id)
            if not project:
                raise ValueError(f"Project not found: {task.project_id}")
            
            # 获取所有有主图的分镜
            scripts = self.db.query(Script).filter(
                Script.project_id == project.id,
                Script.main_image != "",
            ).order_by(Script.order_index).all()
            
            if not scripts:
                raise ValueError(f"No scripts with main_image found in project {project.id}")
            
            # 创建输出目录
            output_dir = OUTPUT_DIR / str(project.id) / "export"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 根据导出样式生成长图
            if task.export_style == "vertical":
                output_path = self._create_vertical_stitch(
                    scripts=scripts,
                    output_dir=output_dir,
                    task_id=task.id,
                    page_numbers=task.page_numbers,
                    titles=task.titles,
                    quality=task.quality,
                )
            else:
                raise ValueError(f"Unsupported export style: {task.export_style}")
            
            # 更新任务状态
            task.status = "done"
            task.output_path = str(output_path.relative_to(OUTPUT_DIR))
            task.file_size = output_path.stat().st_size
            task.completed_at = datetime.now()
            self.db.commit()
            
            return task
        
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            self.db.commit()
            raise
    
    def _create_vertical_stitch(
        self,
        scripts: list[Script],
        output_dir: Path,
        task_id: int,
        page_numbers: bool = False,
        titles: bool = False,
        quality: int = 90,
    ) -> Path:
        """
        创建垂直拼接长图。
        
        Args:
            scripts: 分镜列表
            output_dir: 输出目录
            task_id: 任务 ID
            page_numbers: 是否添加页码
            titles: 是否添加标题
            quality: JPEG 质量
        
        Returns:
            输出文件路径
        """
        # 加载所有图片
        images = []
        for script in scripts:
            img_path = Path(script.main_image)
            if img_path.exists():
                images.append((script, Image.open(img_path)))
        
        if not images:
            raise ValueError("No valid images found")
        
        # 计算总尺寸
        max_width = max(img.width for _, img in images)
        total_height = sum(img.height for _, img in images)
        
        # 如果需要页码或标题，增加额外空间
        extra_height = 0
        if page_numbers or titles:
            extra_height = 50 * len(images)  # 每个分镜增加 50px 空间
            total_height += extra_height
        
        # 创建画布
        canvas = Image.new("RGB", (max_width, total_height), "white")
        draw = ImageDraw.Draw(canvas)
        
        # 尝试加载字体（如果失败则使用默认字体）
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        # 拼接图片
        current_y = 0
        for idx, (script, img) in enumerate(images, 1):
            # 添加页码/标题
            if page_numbers or titles:
                text_parts = []
                if page_numbers:
                    text_parts.append(f"第 {idx} 页")
                if titles and script.content:
                    text_parts.append(script.content[:30])  # 限制长度
                
                if text_parts:
                    text = " | ".join(text_parts)
                    draw.text((10, current_y + 10), text, fill="black", font=font)
                    current_y += 50
            
            # 粘贴图片
            canvas.paste(img, (0, current_y))
            current_y += img.height
            img.close()
        
        # 保存为 JPEG
        output_path = output_dir / f"export_{task_id}.jpg"
        canvas.save(output_path, "JPEG", quality=quality)
        canvas.close()
        
        return output_path
    
    def create_zip_package(self, project_id: int) -> Path:
        """
        创建 ZIP 打包。
        
        Args:
            project_id: 项目 ID
        
        Returns:
            ZIP 文件路径
        """
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        # 获取所有有主图的分镜
        scripts = self.db.query(Script).filter(
            Script.project_id == project_id,
            Script.main_image != "",
        ).order_by(Script.order_index).all()
        
        if not scripts:
            raise ValueError(f"No scripts with main_image found in project {project_id}")
        
        # 创建 ZIP 文件
        output_dir = OUTPUT_DIR / str(project_id) / "export"
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / f"{project.name}_export.zip"
        
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for idx, script in enumerate(scripts, 1):
                img_path = Path(script.main_image)
                if img_path.exists():
                    # 在 ZIP 中使用序号命名
                    arcname = f"{idx:03d}_{img_path.name}"
                    zipf.write(img_path, arcname)
        
        return zip_path
    
    def get_task(self, task_id: int) -> Optional[ExportTask]:
        """获取任务详情。"""
        return self.db.get(ExportTask, task_id)
    
    def list_tasks(self, project_id: Optional[int] = None) -> list[ExportTask]:
        """列出任务。"""
        query = self.db.query(ExportTask)
        if project_id:
            query = query.filter(ExportTask.project_id == project_id)
        return query.order_by(ExportTask.created_at.desc()).all()
