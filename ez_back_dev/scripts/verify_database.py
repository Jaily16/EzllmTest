import sys
from pathlib import Path

from sqlalchemy import inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dao.testProjectDao import engine


EXPECTED_TABLES = {
    "tb_project_design_testdoc",
    "tb_project_info",
    "tb_project_knowledge",
    "tb_project_requirement_testdoc",
    "tb_project_type",
    "tb_test_project",
}


def main() -> None:
    tables = set(inspect(engine).get_table_names())
    missing = EXPECTED_TABLES - tables
    if missing:
        raise SystemExit(f"Missing database tables: {', '.join(sorted(missing))}")

    with engine.connect() as connection:
        project_count = connection.execute(
            text("SELECT COUNT(*) FROM tb_test_project")
        ).scalar_one()

    print(f"Database OK: 6 tables available; project rows={project_count}.")


if __name__ == "__main__":
    main()
