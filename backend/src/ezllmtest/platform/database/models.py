"""仅共享 SQLAlchemy metadata；不创建 engine、连接或数据库 schema。"""
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """业务所有者的 ORM 映射共用同一个 metadata。"""
    pass
