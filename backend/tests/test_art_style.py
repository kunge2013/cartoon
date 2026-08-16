"""画风库单元测试"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.art_style import ArtStyle
from app.services.art_style import ArtStyleService


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_art_style(db_session):
    """测试创建画风"""
    service = ArtStyleService(db_session)
    
    style = service.create_art_style(
        code="korean_manga",
        name="韩漫画风",
        category="韩漫",
        prefix="韩漫画风，精致线稿",
        suffix="高品质",
        negative_prompt="低质量，模糊",
        recommended_model="nano-banana-2",
        recommended_aspect_ratio="3:4",
        recommended_resolution="2K",
    )
    
    assert style.id is not None
    assert style.code == "korean_manga"
    assert style.name == "韩漫画风"
    assert style.category == "韩漫"
    assert style.is_active is True


def test_get_art_style(db_session):
    """测试获取画风"""
    service = ArtStyleService(db_session)
    
    # 创建画风
    created = service.create_art_style(
        code="test_style",
        name="测试画风",
    )
    
    # 获取画风
    retrieved = service.get_art_style(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.code == "test_style"


def test_get_art_style_by_code(db_session):
    """测试根据代码获取画风"""
    service = ArtStyleService(db_session)
    
    # 创建画风
    service.create_art_style(
        code="unique_code",
        name="唯一代码画风",
    )
    
    # 根据代码获取
    retrieved = service.get_art_style_by_code("unique_code")
    assert retrieved is not None
    assert retrieved.code == "unique_code"
    
    # 不存在的代码
    not_found = service.get_art_style_by_code("nonexistent")
    assert not_found is None


def test_list_art_styles(db_session):
    """测试列出画风"""
    service = ArtStyleService(db_session)
    
    # 创建多个画风
    service.create_art_style(code="style1", name="画风1", category="韩漫", is_active=True)
    service.create_art_style(code="style2", name="画风2", category="韩漫", is_active=True)
    service.create_art_style(code="style3", name="画风3", category="日漫", is_active=False)
    
    # 列出所有
    all_styles = service.list_art_styles()
    assert len(all_styles) == 3
    
    # 按分类过滤
    korean_styles = service.list_art_styles(category="韩漫")
    assert len(korean_styles) == 2
    
    # 按启用状态过滤
    active_styles = service.list_art_styles(is_active=True)
    assert len(active_styles) == 2


def test_update_art_style(db_session):
    """测试更新画风"""
    service = ArtStyleService(db_session)
    
    # 创建画风
    style = service.create_art_style(
        code="update_test",
        name="原始名称",
        category="原始分类",
    )
    
    # 更新画风
    updated = service.update_art_style(
        style.id,
        name="新名称",
        category="新分类",
        prefix="新的前缀",
    )
    
    assert updated is not None
    assert updated.name == "新名称"
    assert updated.category == "新分类"
    assert updated.prefix == "新的前缀"
    assert updated.code == "update_test"  # 代码不应改变


def test_delete_art_style(db_session):
    """测试删除画风"""
    service = ArtStyleService(db_session)
    
    # 创建画风
    style = service.create_art_style(code="delete_test", name="删除测试")
    
    # 删除画风
    success = service.delete_art_style(style.id)
    assert success is True
    
    # 验证已删除
    deleted = service.get_art_style(style.id)
    assert deleted is None
    
    # 删除不存在的画风
    not_found = service.delete_art_style(9999)
    assert not_found is False


def test_get_categories(db_session):
    """测试获取分类"""
    service = ArtStyleService(db_session)
    
    # 创建不同分类的画风
    service.create_art_style(code="s1", name="画风1", category="韩漫")
    service.create_art_style(code="s2", name="画风2", category="韩漫")
    service.create_art_style(code="s3", name="画风3", category="日漫")
    service.create_art_style(code="s4", name="画风4", category="写实")
    
    # 获取分类
    categories = service.get_categories()
    assert len(categories) == 3
    assert "韩漫" in categories
    assert "日漫" in categories
    assert "写实" in categories
