import json
import re
import struct
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_ROOT = PROJECT_ROOT / "docs" / "images" / "readme"
MANIFEST_PATH = IMAGE_ROOT / "manifest.json"

EXPECTED_IMAGES = {
    "01-login.png": (1440, 900, "/", "none"),
    "02-project-setup.png": (1440, 900, "/create", "project_setup"),
    "03-plan-running.png": (1440, 900, "/plan", "project_analysis"),
    "04-plan-saved.png": (1440, 900, "/plan", "project_analysis"),
    "05-test-menu.png": (1440, 900, "/menu", "project_analysis"),
    "06-unit-analysis.png": (1440, 900, "/unit", "unit_info"),
    "07-unit-cases.png": (1440, 900, "/unit", "unit_case"),
    "08-api-session-only.png": (1440, 900, "/api", "api_case"),
    "09-ui-persisted.png": (1440, 900, "/ui", "ui_case"),
    "10-mobile-navigation.png": (390, 844, "/ui", "ui_case"),
}


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def png_header(path: Path) -> tuple[int, int, int, set[bytes]]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    width = height = colour_type = 0
    chunks: set[bytes] = set()
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        chunks.add(chunk_type)
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, _depth, colour_type, *_rest = struct.unpack(
                ">IIBBBBB", payload
            )
        if chunk_type == b"IEND":
            break
    return width, height, colour_type, chunks


def test_readme_is_a_complete_private_repository_showcase_and_runbook():
    readme = read("README.md")
    for heading in (
        "项目背景",
        "适用场景",
        "核心能力",
        "技术栈",
        "系统架构",
        "关键界面",
        "仓库结构",
        "本地运行",
        "配置变量",
        "测试与质量门禁",
        "安全与费用",
        "迭代文档",
    ):
        assert heading in readme

    for fragment in (
        "19 个可恢复流式工作流",
        "revision-aware",
        "session-only",
        "Vue 3",
        "FastAPI",
        "MySQL",
        "Element Plus",
        "LangChain Core",
        "SSE",
        "RAG",
        "git clone git@github.com:Jaily16/EzllmTest.git",
        "conda create --name ezllmtest python=3.11 -y",
        "mysql -u root -p ezllmtest_dev < ezllmtest.sql",
        "npm ci",
        "python .\\serve.py",
        "npm run serve",
        "python -m pytest .\\tests -q",
        "npm run lint",
        "scan_credentials.py",
        "smoke_llm.py --provider zhipu --confirm-cost --with-embedding",
        "ez_front_dev/",
        "ez_back_dev/",
        "docs/",
        "scripts/",
        "ezllmtest.sql",
        "唯一的数据库结构文件",
        "DROP TABLE",
    ):
        assert fragment in readme

    assert "```mermaid" in readme
    assert "<details>" in readme
    for image_name in EXPECTED_IMAGES:
        assert f"](docs/images/readme/{image_name})" in readme


def test_release_text_contains_no_project_identifier_machine_path_or_secret():
    release_text = read("README.md") + MANIFEST_PATH.read_text(encoding="utf-8")
    assert re.search(r"Ez\d{19}", release_text) is None
    assert re.search(r"\b[A-Za-z]:\\", release_text) is None
    assert re.search(r"\b(?:gho|github_pat|sk)-[A-Za-z0-9_-]{16,}", release_text) is None
    assert "BEGIN PRIVATE KEY" not in release_text


def test_readme_screenshot_manifest_matches_safe_bounded_png_assets():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["source"] == "real-model representative journey"
    entries = manifest["screenshots"]
    assert {entry["file"] for entry in entries} == set(EXPECTED_IMAGES)

    total_size = 0
    for entry in entries:
        image_name = entry["file"]
        expected_width, expected_height, route, operation = EXPECTED_IMAGES[
            image_name
        ]
        assert entry["route"] == route
        assert entry["viewport"] == {
            "width": expected_width,
            "height": expected_height,
        }
        assert entry["operation"] == operation
        assert entry["model"] in {"none", "GLM-4.7"}
        assert entry["captured_at"].endswith("+08:00")
        assert entry["redaction"] in {
            "none",
            "project ID masked",
            "project ID outside viewport",
        }
        assert set(entry) == {
            "file",
            "route",
            "viewport",
            "operation",
            "model",
            "captured_at",
            "redaction",
        }

        path = IMAGE_ROOT / image_name
        width, height, colour_type, chunks = png_header(path)
        assert (width, height) == (expected_width, expected_height)
        assert colour_type == 6
        assert chunks.isdisjoint({b"tEXt", b"zTXt", b"iTXt", b"eXIf"})
        assert path.stat().st_size <= 1_200 * 1024
        total_size += path.stat().st_size
    assert total_size <= 8 * 1024 * 1024

    assert {path.name for path in IMAGE_ROOT.iterdir()} == {
        *EXPECTED_IMAGES,
        "manifest.json",
    }


def test_iteration3_release_docs_record_real_journey_without_overwriting_history():
    closeout = read("docs/iteration-3-closeout.md")
    log = read("docs/iteration-3-development-log.md")
    for fragment in (
        "Aurora 任务协作平台",
        "GLM-4.7",
        "embedding-3",
        "project_analysis",
        "unit_menu",
        "unit_info",
        "unit_case",
        "api_info",
        "api_case",
        "ui_info",
        "ui_case",
        "docs/images/readme/",
        "PRIVATE",
        "main",
    ):
        assert fragment in closeout
        assert fragment in log
    assert "355 passed" in closeout
    assert "未提交、未推送、未发布" in closeout
