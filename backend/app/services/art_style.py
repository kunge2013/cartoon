# -*- coding: utf-8 -*-
"""画风库服务：画风管理 + 项目绑定。"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.art_style import ArtStyle
from app.models.project import Project


class ArtStyleService:
    """画风库服务。"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_art_style(
        self,
        code: str,
        name: str,
        category: str = "",
        prefix: str = "",
        suffix: str = "",
        negative_prompt: str = "",
        preview_image: str = "",
        reference_image: str = "",
        recommended_model: str = "",
        recommended_aspect_ratio: str = "3:4",
        recommended_resolution: str = "2K",
        is_active: bool = True,
        sort_order: int = 0,
    ) -> ArtStyle:
        """创建画风。"""
        style = ArtStyle(
            code=code,
            name=name,
            category=category,
            prefix=prefix,
            suffix=suffix,
            negative_prompt=negative_prompt,
            preview_image=preview_image,
            reference_image=reference_image,
            recommended_model=recommended_model,
            recommended_aspect_ratio=recommended_aspect_ratio,
            recommended_resolution=recommended_resolution,
            is_active=is_active,
            sort_order=sort_order,
        )
        self.db.add(style)
        self.db.commit()
        self.db.refresh(style)
        return style
    
    def get_art_style(self, style_id: int) -> Optional[ArtStyle]:
        """获取画风。"""
        return self.db.get(ArtStyle, style_id)
    
    def get_art_style_by_code(self, code: str) -> Optional[ArtStyle]:
        """通过代码获取画风。"""
        return self.db.query(ArtStyle).filter(ArtStyle.code == code).first()
    
    def list_art_styles(
        self,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[ArtStyle]:
        """列出画风。"""
        query = self.db.query(ArtStyle)
        if category:
            query = query.filter(ArtStyle.category == category)
        if is_active is not None:
            query = query.filter(ArtStyle.is_active == is_active)
        return query.order_by(ArtStyle.sort_order, ArtStyle.id).all()
    
    def update_art_style(
        self,
        style_id: int,
        **kwargs,
    ) -> Optional[ArtStyle]:
        """更新画风。"""
        style = self.db.get(ArtStyle, style_id)
        if not style:
            return None
        
        for key, value in kwargs.items():
            if hasattr(style, key):
                setattr(style, key, value)
        
        self.db.commit()
        self.db.refresh(style)
        return style
    
    def delete_art_style(self, style_id: int) -> bool:
        """删除画风。"""
        style = self.db.get(ArtStyle, style_id)
        if not style:
            return False
        
        self.db.delete(style)
        self.db.commit()
        return True
    
    def get_categories(self) -> list[str]:
        """获取所有分类。"""
        styles = self.db.query(ArtStyle.category).distinct().all()
        return [s[0] for s in styles if s[0]]
    
    def bind_art_style_to_project(
        self,
        project_id: int,
        style_id: int,
    ) -> Optional[Project]:
        """绑定画风到项目。"""
        project = self.db.get(Project, project_id)
        style = self.db.get(ArtStyle, style_id)
        
        if not project or not style:
            return None
        
        project.art_style_id = style.id
        
        # 注入画风前缀/后缀到项目配置
        if style.prefix:
            project.img_prompt_prefix = style.prefix
        if style.suffix:
            project.img_prompt_suffix = style.suffix
        
        self.db.commit()
        self.db.refresh(project)
        return project
    
    def get_project_art_style(self, project_id: int) -> Optional[ArtStyle]:
        """获取项目绑定的画风。"""
        project = self.db.get(Project, project_id)
        if not project or not project.art_style_id:
            return None
        
        return self.db.get(ArtStyle, project.art_style_id)
