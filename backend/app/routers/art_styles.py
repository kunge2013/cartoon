# -*- coding: utf-8 -*-
"""画风库 API 路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.art_style import ArtStyleService


router = APIRouter(prefix="/art-styles", tags=["art-styles"])


class ArtStyleCreateRequest(BaseModel):
    """创建画风请求。"""
    code: str
    name: str
    category: str = ""
    prefix: str = ""
    suffix: str = ""
    negative_prompt: str = ""
    preview_image: str = ""
    reference_image: str = ""
    recommended_model: str = ""
    recommended_aspect_ratio: str = "3:4"
    recommended_resolution: str = "2K"
    is_active: bool = True
    sort_order: int = 0


class ArtStyleUpdateRequest(BaseModel):
    """更新画风请求。"""
    name: Optional[str] = None
    category: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    negative_prompt: Optional[str] = None
    preview_image: Optional[str] = None
    reference_image: Optional[str] = None
    recommended_model: Optional[str] = None
    recommended_aspect_ratio: Optional[str] = None
    recommended_resolution: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ArtStyleResponse(BaseModel):
    """画风响应。"""
    id: int
    code: str
    name: str
    category: str
    prefix: str
    suffix: str
    negative_prompt: str
    preview_image: str
    reference_image: str
    recommended_model: str
    recommended_aspect_ratio: str
    recommended_resolution: str
    is_active: bool
    sort_order: int
    created_at: str
    updated_at: str


@router.post("", response_model=ArtStyleResponse, status_code=status.HTTP_201_CREATED)
def create_art_style(
    request: ArtStyleCreateRequest,
    db: Session = Depends(get_db),
):
    """
    创建画风。
    """
    service = ArtStyleService(db)
    
    # 检查代码是否已存在
    existing = service.get_art_style_by_code(request.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Art style code '{request.code}' already exists",
        )
    
    style = service.create_art_style(
        code=request.code,
        name=request.name,
        category=request.category,
        prefix=request.prefix,
        suffix=request.suffix,
        negative_prompt=request.negative_prompt,
        preview_image=request.preview_image,
        reference_image=request.reference_image,
        recommended_model=request.recommended_model,
        recommended_aspect_ratio=request.recommended_aspect_ratio,
        recommended_resolution=request.recommended_resolution,
        is_active=request.is_active,
        sort_order=request.sort_order,
    )
    
    return ArtStyleResponse(
        id=style.id,
        code=style.code,
        name=style.name,
        category=style.category,
        prefix=style.prefix,
        suffix=style.suffix,
        negative_prompt=style.negative_prompt,
        preview_image=style.preview_image,
        reference_image=style.reference_image,
        recommended_model=style.recommended_model,
        recommended_aspect_ratio=style.recommended_aspect_ratio,
        recommended_resolution=style.recommended_resolution,
        is_active=style.is_active,
        sort_order=style.sort_order,
        created_at=style.created_at.isoformat(),
        updated_at=style.updated_at.isoformat(),
    )


@router.get("", response_model=list[ArtStyleResponse])
def list_art_styles(
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """
    列出画风。
    """
    service = ArtStyleService(db)
    styles = service.list_art_styles(category=category, is_active=is_active)
    
    return [
        ArtStyleResponse(
            id=style.id,
            code=style.code,
            name=style.name,
            category=style.category,
            prefix=style.prefix,
            suffix=style.suffix,
            negative_prompt=style.negative_prompt,
            preview_image=style.preview_image,
            reference_image=style.reference_image,
            recommended_model=style.recommended_model,
            recommended_aspect_ratio=style.recommended_aspect_ratio,
            recommended_resolution=style.recommended_resolution,
            is_active=style.is_active,
            sort_order=style.sort_order,
            created_at=style.created_at.isoformat(),
            updated_at=style.updated_at.isoformat(),
        )
        for style in styles
    ]


# Bind style to project
class BindStyleRequest(BaseModel):
    """绑定画风到项目请求。"""
    project_id: int
    style_id: int


@router.post("/bind")
def bind_style_to_project(
    request: BindStyleRequest,
    db: Session = Depends(get_db),
):
    """绑定画风到项目。"""
    service = ArtStyleService(db)
    project = service.bind_art_style_to_project(
        project_id=request.project_id,
        style_id=request.style_id,
    )
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to bind style to project",
        )
    
    return {
        "project_id": project.id,
        "style_id": project.art_style_id,
        "message": "Style bound successfully",
    }


@router.get("/project/{project_id}")
def get_project_style(
    project_id: int,
    db: Session = Depends(get_db),
):
    """获取项目绑定的画风。"""
    service = ArtStyleService(db)
    style = service.get_project_art_style(project_id)
    
    if not style:
        return None
    
    return ArtStyleResponse(
        id=style.id,
        code=style.code,
        name=style.name,
        category=style.category,
        prefix=style.prefix,
        suffix=style.suffix,
        negative_prompt=style.negative_prompt,
        preview_image=style.preview_image,
        reference_image=style.reference_image,
        recommended_model=style.recommended_model,
        recommended_aspect_ratio=style.recommended_aspect_ratio,
        recommended_resolution=style.recommended_resolution,
        is_active=style.is_active,
        sort_order=style.sort_order,
        created_at=style.created_at.isoformat(),
        updated_at=style.updated_at.isoformat(),
    )


@router.get("/categories", response_model=list[str])
def get_categories(
    db: Session = Depends(get_db),
):
    """获取所有分类。"""
    service = ArtStyleService(db)
    return service.get_categories()


@router.get("/{style_id}", response_model=ArtStyleResponse)
def get_art_style(
    style_id: int,
    db: Session = Depends(get_db),
):
    """
    获取画风。
    """
    service = ArtStyleService(db)
    style = service.get_art_style(style_id)
    
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Art style {style_id} not found",
        )
    
    return ArtStyleResponse(
        id=style.id,
        code=style.code,
        name=style.name,
        category=style.category,
        prefix=style.prefix,
        suffix=style.suffix,
        negative_prompt=style.negative_prompt,
        preview_image=style.preview_image,
        reference_image=style.reference_image,
        recommended_model=style.recommended_model,
        recommended_aspect_ratio=style.recommended_aspect_ratio,
        recommended_resolution=style.recommended_resolution,
        is_active=style.is_active,
        sort_order=style.sort_order,
        created_at=style.created_at.isoformat(),
        updated_at=style.updated_at.isoformat(),
    )


@router.put("/{style_id}", response_model=ArtStyleResponse)
def update_art_style(
    style_id: int,
    request: ArtStyleUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    更新画风。
    """
    service = ArtStyleService(db)
    
    # 过滤掉 None 值
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    
    style = service.update_art_style(style_id, **update_data)
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Art style {style_id} not found",
        )
    
    return ArtStyleResponse(
        id=style.id,
        code=style.code,
        name=style.name,
        category=style.category,
        prefix=style.prefix,
        suffix=style.suffix,
        negative_prompt=style.negative_prompt,
        preview_image=style.preview_image,
        reference_image=style.reference_image,
        recommended_model=style.recommended_model,
        recommended_aspect_ratio=style.recommended_aspect_ratio,
        recommended_resolution=style.recommended_resolution,
        is_active=style.is_active,
        sort_order=style.sort_order,
        created_at=style.created_at.isoformat(),
        updated_at=style.updated_at.isoformat(),
    )


@router.delete("/{style_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_art_style(
    style_id: int,
    db: Session = Depends(get_db),
):
    """
    删除画风。
    """
    service = ArtStyleService(db)
    success = service.delete_art_style(style_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Art style {style_id} not found",
        )
