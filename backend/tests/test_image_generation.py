"""图片生成服务测试"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import tempfile

from app.database import Base
from app.models.project import Project, Script
from app.models.image import ImageTask
from app.models.provider import ProviderAccount
from app.services.image_generation import ImageGenerationService


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_data(db_session):
    """创建测试数据"""
    # 创建供应商账号
    account = ProviderAccount(
        provider_code="grsai",
        base_url="https://api.example.com",
        api_key="test-api-key",
        valid=True,
    )
    db_session.add(account)
    
    # 创建项目
    project = Project(
        name="Test Project",
        mode="manga",
        summary="Test summary",
    )
    db_session.add(project)
    db_session.flush()
    
    # 创建分镜
    script = Script(
        project_id=project.id,
        order_index=0,
        shot_index=1,
        content="Test content",
        image_prompt="Test image prompt",
        generation_enabled=True,
    )
    db_session.add(script)
    db_session.flush()
    
    return {
        "project": project,
        "script": script,
        "account": account,
    }


def test_generate_single_creates_task(db_session, sample_data):
    """测试单张图片生成创建任务"""
    service = ImageGenerationService(db_session)
    
    # Mock 适配器
    with patch("app.services.image_generation.ImageProviderAdapter") as mock_adapter_class:
        mock_adapter = MagicMock()
        mock_adapter.generate_image.return_value = {
            "image_url": "https://example.com/image.png",
            "generation_time": 5.5,
        }
        mock_adapter_class.return_value = mock_adapter
        
        result = service.generate_single(
            script_id=sample_data["script"].id,
            provider_code="grsai",
            model="nano-banana-2",
            aspect_ratio="3:4",
            resolution="2K",
        )
        
        # 验证返回结果
        assert result["status"] == "done"
        assert result["image_url"] == "https://example.com/image.png"
        
        # 验证任务创建
        tasks = db_session.query(ImageTask).filter_by(script_id=sample_data["script"].id).all()
        assert len(tasks) == 1
        assert tasks[0].status == "done"
        assert tasks[0].image_url == "https://example.com/image.png"
        
        # 验证分镜的候选图更新
        db_session.refresh(sample_data["script"])
        candidates = json.loads(sample_data["script"].candidate_images)
        assert len(candidates) == 1
        assert "candidate_1" in candidates


def test_generate_batch(db_session, sample_data):
    """测试批量生成"""
    service = ImageGenerationService(db_session)
    
    # 创建第二个分镜
    script2 = Script(
        project_id=sample_data["project"].id,
        order_index=1,
        shot_index=2,
        content="Test content 2",
        image_prompt="Test image prompt 2",
        generation_enabled=True,
    )
    db_session.add(script2)
    db_session.flush()
    
    # Mock 适配器
    with patch("app.services.image_generation.ImageProviderAdapter") as mock_adapter_class:
        mock_adapter = MagicMock()
        mock_adapter.generate_image.return_value = {
            "image_url": "https://example.com/image.png",
            "generation_time": 5.5,
        }
        mock_adapter_class.return_value = mock_adapter
        
        results = service.generate_batch(
            script_ids=[sample_data["script"].id, script2.id],
            provider_code="grsai",
        )
        
        # 验证两个任务都成功
        assert len(results) == 2
        assert all(r["status"] == "success" for r in results)
        
        # 验证任务创建
        tasks = db_session.query(ImageTask).all()
        assert len(tasks) == 2


def test_select_main_image(db_session, sample_data):
    """测试选择主图"""
    service = ImageGenerationService(db_session)
    
    # 先生成一张图片
    with patch("app.services.image_generation.ImageProviderAdapter") as mock_adapter_class:
        mock_adapter = MagicMock()
        mock_adapter.generate_image.return_value = {
            "image_url": "https://example.com/image1.png",
            "generation_time": 5.5,
        }
        mock_adapter_class.return_value = mock_adapter
        
        result1 = service.generate_single(
            script_id=sample_data["script"].id,
        )
        task1_id = result1["task_id"]
        
        # 再生成一张图片
        mock_adapter.generate_image.return_value = {
            "image_url": "https://example.com/image2.png",
            "generation_time": 6.0,
        }
        
        result2 = service.generate_single(
            script_id=sample_data["script"].id,
        )
        task2_id = result2["task_id"]
        
        # 选择第二张为主图
        selection_result = service.select_main_image(
            script_id=sample_data["script"].id,
            task_id=task2_id,
        )
        
        # 验证主图更新
        assert selection_result["main_image"] == "https://example.com/image2.png"
        
        # 验证分镜的 main_image 更新
        db_session.refresh(sample_data["script"])
        assert sample_data["script"].main_image == "https://example.com/image2.png"
        
        # 验证任务的 is_main 标记
        task1 = db_session.query(ImageTask).filter_by(id=task1_id).first()
        task2 = db_session.query(ImageTask).filter_by(id=task2_id).first()
        assert task1.is_main == False
        assert task2.is_main == True


def test_get_candidates(db_session, sample_data):
    """测试获取候选图"""
    service = ImageGenerationService(db_session)
    
    # 生成两张图片
    with patch("app.services.image_generation.ImageProviderAdapter") as mock_adapter_class:
        mock_adapter = MagicMock()
        mock_adapter.generate_image.side_effect = [
            {
                "image_url": "https://example.com/image1.png",
                "generation_time": 5.5,
            },
            {
                "image_url": "https://example.com/image2.png",
                "generation_time": 6.0,
            },
        ]
        mock_adapter_class.return_value = mock_adapter
        
        service.generate_single(script_id=sample_data["script"].id)
        service.generate_single(script_id=sample_data["script"].id)
        
        # 获取候选图
        candidates = service.get_candidates(script_id=sample_data["script"].id)
        
        # 验证返回两张候选图
        assert len(candidates) == 2
        assert candidates[0]["image_url"] in [
            "https://example.com/image1.png",
            "https://example.com/image2.png",
        ]
        assert candidates[1]["image_url"] in [
            "https://example.com/image1.png",
            "https://example.com/image2.png",
        ]


def test_generate_failed_updates_task_status(db_session, sample_data):
    """测试生成失败时更新任务状态"""
    service = ImageGenerationService(db_session)
    
    # Mock 适配器抛出异常
    with patch("app.services.image_generation.ImageProviderAdapter") as mock_adapter_class:
        mock_adapter = MagicMock()
        mock_adapter.generate_image.side_effect = Exception("API error")
        mock_adapter_class.return_value = mock_adapter
        
        with pytest.raises(Exception, match="API error"):
            service.generate_single(script_id=sample_data["script"].id)
        
        # 验证任务状态为失败
        tasks = db_session.query(ImageTask).filter_by(script_id=sample_data["script"].id).all()
        assert len(tasks) == 1
        assert tasks[0].status == "failed"
        assert tasks[0].error_message == "API error"
