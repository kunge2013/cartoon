# -*- coding: utf-8 -*-
"""图片提示词推导 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.image_derive_service import ImageDeriveService


router = APIRouter(prefix="/image-derive", tags=["image-derive"])


class DeriveRequest(BaseModel):
    """单镜推导请求"""
    preset_id: Optional[str] = None
    provider_code: Optional[str] = None
    model: Optional[str] = None


class BatchDeriveRequest(BaseModel):
    """批量推导请求"""
    script_ids: Optional[List[int]] = None  # None 表示全部
    preset_id: Optional[str] = None
    provider_code: Optional[str] = None
    model: Optional[str] = None


class DeriveResponse(BaseModel):
    """推导响应"""
    script_id: int
    image_prompt: str
    render_log_id: Optional[int] = None


class BatchDeriveResponse(BaseModel):
    """批量推导响应"""
    total: int
    success: int
    failed: int
    results: List[dict]


@router.post("/scripts/{script_id}", response_model=DeriveResponse)
def derive_script_prompt(
    script_id: int,
    request: DeriveRequest = DeriveRequest(),
    db: Session = Depends(get_db)
):
    """
    推导单个分镜的 image_prompt

    - **script_id**: 分镜ID
    - **preset_id**: 预设ID，默认使用 plot_manga_fusion_bw
    - **provider_code**: LLM供应商代码（deepseek/grsai/volcengine）
    - **model**: 模型名称

    返回推导结果和渲染日志ID
    """
    try:
        service = ImageDeriveService(db)
        result = service.derive_script_prompt(
            script_id=script_id,
            preset_id=request.preset_id,
            provider_code=request.provider_code,
            model=request.model
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推导失败: {str(e)}")


@router.post("/projects/{project_id}/batch", response_model=BatchDeriveResponse)
def batch_derive(
    project_id: int,
    request: BatchDeriveRequest = BatchDeriveRequest(),
    db: Session = Depends(get_db)
):
    """
    批量推导项目下分镜的 image_prompt

    - **project_id**: 项目ID
    - **script_ids**: 分镜ID列表，None表示全部
    - **preset_id**: 预设ID
    - **provider_code**: LLM供应商代码
    - **model**: 模型名称

    返回批量推导结果统计
    """
    try:
        service = ImageDeriveService(db)
        result = service.batch_derive(
            project_id=project_id,
            script_ids=request.script_ids,
            preset_id=request.preset_id,
            provider_code=request.provider_code,
            model=request.model
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量推导失败: {str(e)}")


@router.get("/presets")
def list_presets(db: Session = Depends(get_db)):
    """
    获取可用的图片推导预设列表
    """
    from app.models.prompt import PromptPreset

    presets = db.query(PromptPreset).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category
        }
        for p in presets
    ]
