"""导出功能单元测试"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import tempfile
from PIL import Image

from app.database import Base
from app.models.project import Project, Script
from app.models.export import ExportTask
from app.services.export import ExportService


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
def sample_data(db_session, tmp_path):
    """创建测试数据：3 个测试图 + 3 个分镜。

    修复原版 bug：原先用 ``with tempfile.TemporaryDirectory()`` 临时目录，
    with 退出时目录被删，但 ``main_image`` 仍指向已删的路径，导致
    ExportService 找不到图。改为用 ``tmp_path``（pytest fixture，测试结束才清）。
    """
    # 创建项目
    project = Project(
        name="Test Project",
        mode="manga",
        summary="Test summary",
    )
    db_session.add(project)
    db_session.flush()

    # 在 tmp_path 下创建 3 张测试图
    for i in range(1, 4):
        img = Image.new("RGB", (800, 1200), color=(i * 50, 100, 150))
        img_path = tmp_path / f"test_{i}.jpg"
        img.save(img_path, "JPEG")

        script = Script(
            project_id=project.id,
            order_index=i,
            shot_index=i,
            content=f"Test content {i}",
            image_prompt=f"Test prompt {i}",
            main_image=str(img_path),
            generation_enabled=True,
        )
        db_session.add(script)

    db_session.flush()
    return {"project": project, "tmpdir": tmp_path}


def test_create_export_task(db_session, sample_data):
    """测试创建导出任务"""
    service = ExportService(db_session)
    
    task = service.create_export_task(
        project_id=sample_data["project"].id,
        export_style="vertical",
        page_numbers=True,
        titles=True,
        quality=85,
    )
    
    assert task.id is not None
    assert task.status == "pending"
    assert task.export_style == "vertical"
    assert task.page_numbers is True
    assert task.titles is True
    assert task.quality == 85


def test_execute_export_creates_stitch(db_session, sample_data):
    """测试执行导出创建拼接图"""
    service = ExportService(db_session)
    
    # 创建任务
    task = service.create_export_task(
        project_id=sample_data["project"].id,
        export_style="vertical",
        page_numbers=False,
        titles=False,
        quality=90,
    )
    
    # 执行导出
    task = service.execute_export(task.id)
    
    # 验证任务状态
    assert task.status == "done"
    assert task.output_path != ""
    assert task.file_size > 0
    
    # 验证文件存在
    from app.config import OUTPUT_DIR
    output_file = OUTPUT_DIR / task.output_path
    assert output_file.exists()
    
    # 验证图片尺寸（3 张图片垂直拼接）
    from PIL import Image
    img = Image.open(output_file)
    assert img.width == 800  # 最大宽度
    assert img.height == 3600  # 3 * 1200
    img.close()


def test_execute_export_with_page_numbers(db_session, sample_data):
    """测试带页码的导出"""
    service = ExportService(db_session)
    
    task = service.create_export_task(
        project_id=sample_data["project"].id,
        export_style="vertical",
        page_numbers=True,
        titles=False,
        quality=90,
    )
    
    task = service.execute_export(task.id)
    
    # 验证任务状态
    assert task.status == "done"
    
    # 验证图片尺寸（3 张图片 + 3 个页码区域）
    from app.config import OUTPUT_DIR
    output_file = OUTPUT_DIR / task.output_path
    
    from PIL import Image
    img = Image.open(output_file)
    # 每张图 1200px + 每个页码 50px = 3 * (1200 + 50) = 3750
    assert img.height == 3750
    img.close()


def test_create_zip_package(db_session, sample_data):
    """测试创建 ZIP 打包"""
    service = ExportService(db_session)
    
    zip_path = service.create_zip_package(sample_data["project"].id)
    
    # 验证 ZIP 文件存在
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"
    
    # 验证 ZIP 内容
    import zipfile
    with zipfile.ZipFile(zip_path, "r") as zipf:
        files = zipf.namelist()
        assert len(files) == 3  # 3 个分镜
        # 验证文件名格式
        assert all(f.endswith(".jpg") for f in files)
        assert all(f.startswith(("001_", "002_", "003_")) for f in files)


def test_execute_export_failed_no_images(db_session):
    """测试导出失败 - 没有图片"""
    # 创建项目但没有分镜
    project = Project(
        name="Empty Project",
        mode="manga",
    )
    db_session.add(project)
    db_session.flush()
    
    service = ExportService(db_session)
    task = service.create_export_task(project_id=project.id)
    
    # 执行导出应该失败
    with pytest.raises(ValueError, match="No scripts with main_image found"):
        service.execute_export(task.id)
    
    # 验证任务状态为失败
    db_session.refresh(task)
    assert task.status == "failed"
    assert "No scripts with main_image found" in task.error_message


def test_get_task(db_session, sample_data):
    """测试获取任务"""
    service = ExportService(db_session)
    
    task = service.create_export_task(project_id=sample_data["project"].id)
    
    retrieved = service.get_task(task.id)
    assert retrieved is not None
    assert retrieved.id == task.id


def test_list_tasks(db_session, sample_data):
    """测试列出任务"""
    service = ExportService(db_session)
    
    # 创建多个任务
    task1 = service.create_export_task(project_id=sample_data["project"].id)
    task2 = service.create_export_task(project_id=sample_data["project"].id)
    
    # 列出任务
    tasks = service.list_tasks(project_id=sample_data["project"].id)
    assert len(tasks) == 2
    assert all(t.project_id == sample_data["project"].id for t in tasks)
