-- Iteration 2 Task 1: additive, revision-aware workflow artifact storage.
CREATE TABLE IF NOT EXISTS tb_project_workflow_artifact (
  project_id VARCHAR(21) NOT NULL,
  artifact_key VARCHAR(80) NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_revision CHAR(64) NOT NULL,
  prompt_version VARCHAR(32) NOT NULL,
  model_label VARCHAR(32) NOT NULL,
  content LONGTEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (
    project_id,
    artifact_key,
    input_hash,
    source_revision,
    prompt_version,
    model_label
  ),
  INDEX idx_workflow_artifact_project_key (project_id, artifact_key),
  CONSTRAINT fk_workflow_artifact_project
    FOREIGN KEY (project_id) REFERENCES tb_test_project(id)
);
