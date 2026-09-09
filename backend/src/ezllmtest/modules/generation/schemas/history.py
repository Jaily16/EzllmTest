"""产物历史只读快照；跨域消费者看不到 ORM/session。"""
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ArtifactHistoryRow:
    artifact_key: str
    input_hash: str
    source_revision: str
    prompt_version: str
    model_label: str
    content: str
    metadata_json: str
    updated_at: datetime
