# -*- coding: utf-8 -*-
"""图片生成 API 路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.image_generation import ImageGenerationService


router = APIRouter(prefix="/image-generation", tags=["image-generation"])


class GenerateSingleRequest(BaseModel):
    """单镜生成请求。"""
    script_id: int
    provider_code: str = "grsai"
    model: str = "nano-banana-2"
    aspect_ratio: str = "3:4"
    resolution: str = "2K"


class GenerateBatchRequest(BaseModel):
    """批量生成请求。"""
    script_ids: list[int]
    provider_code: str = "grsai"
    model: str = "nano-banana-2"
    aspect_ratio: str = "3:4"
    resolution: str = "2K"


class SelectMainImageRequest(BaseModel):
    """选择主图请求。"""
    script_id: int
    task_id: int


class GenerateSingleResponse(BaseModel):
    """单镜生成响应。"""
    task_id: int
    status: str
    image_url: str


class GenerateBatchResponse(BaseModel):
    """批量生成响应。"""
    total: int
    success: int
    failed: int
    results: list[dict]


class SelectMainImageResponse(BaseModel):
    """选择主图响应。"""
    script_id: int
    main_image: str


class CandidateImageResponse(BaseModel):
    """候选图响应。"""
    task_id: int
    image_url: str
    generation_time: Optional[float] = None
    is_main: bool
    created_at: Optional[str] = None


@router.post("/generate", response_model=GenerateSingleResponse)
def generate_single(
    request: GenerateSingleRequest,
    db: Session = Depends(get_db),
):
    """
    为单个分镜生成图片。
    
    - **script_id**: 分镜 ID
    - **provider_code**: 供应商代码（默认 grsai）
    - **model**: 模型名称（默认 nano-banana-2）
    - **aspect_ratio**: 宽高比（默认 3:4）
    - **resolution**: 分辨率（默认 2K）
    
    返回任务信息和生成的图片 URL。
    """
    try:
        service = ImageGenerationService(db)
        result = service.generate_single(
            script_id=request.script_id,
            provider_code=request.provider_code,
            model=request.model,
            aspect_ratio=request.aspect_ratio,
            resolution=request.resolution,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image generation failed: {str(e)}",
        )


@router.post("/batch", response_model=GenerateBatchResponse)
def generate_batch(
    request: GenerateBatchRequest,
    db: Session = Depends(get_db),
):
    """
    批量生成分镜图片。
    
    - **script_ids**: 分镜 ID 列表
    - **provider_code**: 供应商代码
    - **model**: 模型名称
    - **aspect_ratio**: 宽高比
    - **resolution**: 分辨率
    
    返回批量生成统计。
    """
    try:
        service = ImageGenerationService(db)
        results = service.generate_batch(
            script_ids=request.script_ids,
            provider_code=request.provider_code,
            model=request.model,
            aspect_ratio=request.aspect_ratio,
            resolution=request.resolution,
        )
        
        success_count = sum(1 for r in results if r["status"] == "success")
        failed_count = len(results) - success_count
        
        return {
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch generation failed: {str(e)}",
        )


@router.post("/select-main", response_model=SelectMainImageResponse)
def select_main_image(
    request: SelectMainImageRequest,
    db: Session = Depends(get_db),
):
    """
    选择候选图作为主图。
    
    - **script_id**: 分镜 ID
    - **task_id**: 任务 ID
    
    返回更新后的主图 URL。
    """
    try:
        service = ImageGenerationService(db)
        result = service.select_main_image(
            script_id=request.script_id,
            task_id=request.task_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Select main image failed: {str(e)}",
        )


@router.get("/candidates/{script_id}", response_model=list[CandidateImageResponse])
def get_candidates(
    script_id: int,
    db: Session = Depends(get_db),
):
    """
    获取分镜的所有候选图。
    
    - **script_id**: 分镜 ID
    
    返回候选图列表。
    """
    try:
        service = ImageGenerationService(db)
        candidates = service.get_candidates(script_id)
        return candidates
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Get candidates failed: {str(e)}",
        )


@router.get("/tasks/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """
    获取任务详情。
    
    - **task_id**: 任务 ID
    
    返回任务详细信息。
    """
    service = ImageGenerationService(db)
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    return {
        "id": task.id,
        "script_id": task.script_id,
        "project_id": task.project_id,
        "status": task.status,
        "image_prompt": task.image_prompt,
        "provider_code": task.provider_code,
        "model": task.model,
        "aspect_ratio": task.aspect_ratio,
        "resolution": task.resolution,
        "image_url": task.image_url,
        "candidate_index": task.candidate_index,
        "is_main": task.is_main,
        "error_message": task.error_message,
        "retry_count": task.retry_count,
        "generation_time": task.generation_time,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.get("/tasks")
def list_tasks(
    script_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    列出任务。
    
    - **script_id**: 分镜 ID（可选）
    - **status**: 任务状态（可选：pending/running/done/failed）
    
    返回任务列表。
    """
    service = ImageGenerationService(db)
    tasks = service.list_tasks(script_id=script_id, status=status)
    
    return [
        {
            "id": task.id,
            "script_id": task.script_id,
            "project_id": task.project_id,
            "status": task.status,
            "image_url": task.image_url,
            "is_main": task.is_main,
            "generation_time": task.generation_time,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        }
        for task in tasks
    ]
