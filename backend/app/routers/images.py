"""图片生成 API 路由"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.image_generation import ImageGenerationService

router = APIRouter(prefix="/images", tags=["images"])


class GenerateSingleRequest(BaseModel):
    provider_code: str = "grsai"
    model: str = "nano-banana-2"
    aspect_ratio: str = "3:4"
    resolution: str = "2K"


class GenerateBatchRequest(BaseModel):
    script_ids: list[int]
    provider_code: str = "grsai"
    model: str = "nano-banana-2"
    aspect_ratio: str = "3:4"
    resolution: str = "2K"


class SelectMainRequest(BaseModel):
    task_id: int


@router.post("/scripts/{script_id}/generate")
def generate_single(
    script_id: int,
    request: GenerateSingleRequest,
    db: Session = Depends(get_db)
):
    """为单个分镜生成图片"""
    try:
        service = ImageGenerationService(db)
        result = service.generate_single(
            script_id=script_id,
            provider_code=request.provider_code,
            model=request.model,
            aspect_ratio=request.aspect_ratio,
            resolution=request.resolution,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


@router.post("/batch-generate")
def generate_batch(
    request: GenerateBatchRequest,
    db: Session = Depends(get_db)
):
    """批量生成图片"""
    try:
        service = ImageGenerationService(db)
        results = service.generate_batch(
            script_ids=request.script_ids,
            provider_code=request.provider_code,
            model=request.model,
            aspect_ratio=request.aspect_ratio,
            resolution=request.resolution,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {str(e)}")


@router.post("/scripts/{script_id}/select-main")
def select_main_image(
    script_id: int,
    request: SelectMainRequest,
    db: Session = Depends(get_db)
):
    """选择候选图作为主图"""
    try:
        service = ImageGenerationService(db)
        result = service.select_main_image(
            script_id=script_id,
            task_id=request.task_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/scripts/{script_id}/candidates")
def get_candidates(
    script_id: int,
    db: Session = Depends(get_db)
):
    """获取分镜的所有候选图"""
    try:
        service = ImageGenerationService(db)
        candidates = service.get_candidates(script_id=script_id)
        return candidates
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
