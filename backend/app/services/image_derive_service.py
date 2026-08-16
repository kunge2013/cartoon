# -*- coding: utf-8 -*-
"""图片提示词推导服务（Phase 5）

核心流程：
1. 收集上下文：角色卡、前情分镜、项目摘要、画风前缀、项目前后缀
2. 通过拼装引擎组装 LLM 输入
3. 调用 LLM 生成三段式 image_prompt
4. 解析并存储结果
5. 记录渲染日志（由 Assembler 自动完成）
"""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models.project import Project, Script
from app.models.novel import Novel
from app.models.role import Role
from app.adapters.llm import chat
from app.prompt_engine import Assembler, AssemblyContext


class ImageDeriveService:
    """图片提示词推导服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def derive_script_prompt(
        self,
        script_id: int,
        preset_id: Optional[str] = None,
        provider_code: Optional[str] = None,
        model: Optional[str] = None
    ) -> dict:
        """
        推导单个分镜的 image_prompt
        
        Args:
            script_id: 分镜ID
            preset_id: 预设ID，默认使用 plot_manga_fusion_bw
            provider_code: LLM供应商代码
            model: 模型名称
        
        Returns:
            {
                "script_id": int,
                "image_prompt": str,
                "render_log_id": int
            }
        """
        # 1. 获取分镜
        script = self.db.get(Script, script_id)
        if not script:
            raise ValueError(f"Script {script_id} not found")
        
        project = self.db.get(Project, script.project_id)
        if not project:
            raise ValueError(f"Project {script.project_id} not found")
        
        novel = self.db.get(Novel, project.novel_id) if project.novel_id else None
        
        # 2. 选择预设
        if not preset_id:
            preset_id = "plot_manga_fusion_bw"
        
        # 3. 收集上下文变量
        variables = self._build_variables(script, project, novel)
        
        # 4. 通过拼装引擎组装 LLM 输入（会自动记录渲染日志）
        assembler = Assembler(self.db)
        assembly_result = assembler.assemble(
            AssemblyContext(
                stage="image_derive",
                preset_id=preset_id,
                variables=variables,
                target_table="scripts",
                target_id=script.id,
                persist_log=True
            )
        )
        
        # 5. 调用 LLM（拼装结果是 LLM 的输入 prompt）
        llm_output = chat(
            db=self.db,
            prompt=assembly_result.rendered,
            provider_code=provider_code,
            model=model
        )
        
        # 6. 解析三段式输出
        image_prompt = self._parse_three_part_output(llm_output)
        
        # 7. 更新分镜的 image_prompt
        script.image_prompt = image_prompt
        script.updated_at = datetime.now()
        self.db.commit()
        
        return {
            "script_id": script.id,
            "image_prompt": image_prompt,
            "render_log_id": assembly_result.log_id
        }
    
    def batch_derive(
        self,
        project_id: int,
        script_ids: Optional[list[int]] = None,
        preset_id: Optional[str] = None,
        provider_code: Optional[str] = None,
        model: Optional[str] = None
    ) -> dict:
        """
        批量推导分镜的 image_prompt
        
        Args:
            project_id: 项目ID
            script_ids: 分镜ID列表，None表示全部
            preset_id: 预设ID
            provider_code: LLM供应商代码
            model: 模型名称
        
        Returns:
            {
                "total": int,
                "success": int,
                "failed": int,
                "results": [...]
            }
        """
        # 获取分镜列表
        query = self.db.query(Script).filter(Script.project_id == project_id)
        if script_ids:
            query = query.filter(Script.id.in_(script_ids))
        scripts = query.order_by(Script.order_index).all()
        
        results = []
        success_count = 0
        failed_count = 0
        
        for script in scripts:
            try:
                result = self.derive_script_prompt(
                    script_id=script.id,
                    preset_id=preset_id,
                    provider_code=provider_code,
                    model=model
                )
                results.append({
                    "script_id": script.id,
                    "status": "success",
                    "render_log_id": result["render_log_id"]
                })
                success_count += 1
            except Exception as e:
                results.append({
                    "script_id": script.id,
                    "status": "failed",
                    "error": str(e)
                })
                failed_count += 1
        
        return {
            "total": len(scripts),
            "success": success_count,
            "failed": failed_count,
            "results": results
        }
    
    def _build_variables(self, script: Script, project: Project, novel: Optional[Novel]) -> dict:
        """构建推导上下文变量"""
        variables = {
            "shot_content": script.content or "",
            "project_summary": project.summary or "",
            "project_img_prefix": project.img_prompt_prefix or "",
            "project_img_suffix": project.img_prompt_suffix or "",
        }
        
        # 1. 获取角色卡（序列化为 JSON 字符串供 Jinja2 使用）
        if novel and novel.id:
            roles = self.db.query(Role).filter(
                (Role.novel_id == novel.id) | (Role.project_id == project.id)
            ).all()
            roles_data = [
                {
                    "name": role.name,
                    "alias": role.alias,
                    "content": role.content,
                    "content_word2": role.content_word2
                }
                for role in roles
            ]
        else:
            roles_data = []
        
        variables["roles"] = roles_data if roles_data else []
        
        # 2. 获取前情分镜（当前分镜之前的所有分镜）
        prev_scripts = self.db.query(Script).filter(
            Script.project_id == project.id,
            Script.order_index < script.order_index
        ).order_by(Script.order_index.desc()).limit(3).all()  # 取前3个分镜作为参考
        
        prev_shots_data = [
            {
                "index": s.order_index,
                "content": s.content,
                "image_prompt": s.image_prompt
            }
            for s in reversed(prev_scripts)  # 按顺序排列
        ]
        
        variables["prev_shots"] = prev_shots_data if prev_shots_data else []
        
        return variables
    
    def _parse_three_part_output(self, llm_output: str) -> str:
        """
        解析三段式输出
        
        三段式结构：
        1. 画风总述（如"韩系商业条漫画风..."）
        2. 版式逻辑详解（如"本镜采用三格横条版式..."）
        3. 固定负面后缀（如"禁止..."）
        
        Returns:
            拼接后的完整 image_prompt
        """
        # 简单处理：直接使用 LLM 输出（已经是三段式）
        # 如果需要更精细的解析，可以在这里添加正则匹配
        return llm_output.strip()
