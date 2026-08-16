# -*- coding: utf-8 -*-
"""图片导出 API 路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import OUTPUT_DIR
from app.database import get_db
from app.services.export import ExportService


router = APIRouter(prefix="/export", tags=["export"])


class CreateExportRequest(BaseModel):
    """创建导出任务请求。"""
    project_id: int
    export_style: str = "vertical"
    page_numbers: bool = False
    titles: bool = False
    quality: int = 90


class ExportTaskResponse(BaseModel):
    """导出任务响应。"""
    id: int
    project_id: int
    status: str
    export_style: str
    page_numbers: bool
    titles: bool
    quality: int
    output_path: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@router.post("/create", response_model=ExportTaskResponse)
def create_export_task(
    request: CreateExportRequest,
    db: Session = Depends(get_db),
):
    """
    创建导出任务。
    
    - **project_id**: 项目 ID
    - **export_style**: 导出样式（vertical/horizontal）
    - **page_numbers**: 是否添加页码
    - **titles**: 是否添加标题
    - **quality**: JPEG 质量 (1-100)
    """
    try:
        service = ExportService(db)
        task = service.create_export_task(
            project_id=request.project_id,
            export_style=request.export_style,
            page_numbers=request.page_numbers,
            titles=request.titles,
            quality=request.quality,
        )
        
        # 立即执行任务
        task = service.execute_export(task.id)
        
        return ExportTaskResponse(
            id=task.id,
            project_id=task.project_id,
            status=task.status,
            export_style=task.export_style,
            page_numbers=task.page_numbers,
            titles=task.titles,
            quality=task.quality,
            output_path=task.output_path,
            file_size=task.file_size,
            error_message=task.error_message,
            created_at=task.created_at.isoformat(),
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )


@router.get("/download/{task_id}")
def download_export(
    task_id: int,
    db: Session = Depends(get_db),
):
    """
    下载导出文件。
    
    - **task_id**: 任务 ID
    """
    service = ExportService(db)
    task = service.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    if task.status != "done":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task {task_id} is not completed",
        )
    
    file_path = OUTPUT_DIR / task.output_path
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found",
        )
    
    return FileResponse(
        file_path,
        media_type="image/jpeg",
        filename=f"export_{task_id}.jpg",
    )


@router.post("/zip/{project_id}")
def create_zip_package(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    创建 ZIP 打包。
    
    - **project_id**: 项目 ID
    """
    try:
        service = ExportService(db)
        zip_path = service.create_zip_package(project_id)
        
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=zip_path.name,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ZIP creation failed: {str(e)}",
        )


@router.get("/tasks/{task_id}", response_model=ExportTaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """
    获取任务详情。
    
    - **task_id**: 任务 ID
    """
    service = ExportService(db)
    task = service.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    return ExportTaskResponse(
        id=task.id,
        project_id=task.project_id,
        status=task.status,
        export_style=task.export_style,
        page_numbers=task.page_numbers,
        titles=task.titles,
        quality=task.quality,
        output_path=task.output_path,
        file_size=task.file_size,
        error_message=task.error_message,
        created_at=task.created_at.isoformat(),
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )


@router.get("/tasks")
def list_tasks(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    列出任务。
    
    - **project_id**: 项目 ID（可选）
    """
    service = ExportService(db)
    tasks = service.list_tasks(project_id=project_id)
    
    return [
        ExportTaskResponse(
            id=task.id,
            project_id=task.project_id,
            status=task.status,
            export_style=task.export_style,
            page_numbers=task.page_numbers,
            titles=task.titles,
            quality=task.quality,
            output_path=task.output_path,
            file_size=task.file_size,
            error_message=task.error_message,
            created_at=task.created_at.isoformat(),
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
        )
        for task in tasks
    ]


@router.get("/info/{project_id}")
def get_export_info(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    获取项目导出信息。
    
    - **project_id**: 项目 ID
    """
    from app.models.project import Project, Script
    
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )
    
    scripts = db.query(Script).filter(Script.project_id == project_id).all()
    scripts_with_images = [s for s in scripts if s.main_image]
    
    return {
        "project_id": project_id,
        "project_name": project.name,
        "total_scripts": len(scripts),
        "scripts_with_images": len(scripts_with_images),
        "can_export": len(scripts_with_images) > 0,
    }
