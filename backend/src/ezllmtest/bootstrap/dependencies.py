"""具体依赖的唯一装配位置；绑定不连接数据库，也不初始化 schema。"""
def bind_persistence():
    """将当前进程的项目和产物仓储接到模块端口。"""
    from ezllmtest.modules.projects.ports import repository as project_port
    from ezllmtest.modules.projects.infrastructure import repository
    from ezllmtest.modules.projects.infrastructure.models import TestProjectInfo
    from ezllmtest.modules.generation.infrastructure.models import TestProjectWorkflowArtifact
    repository.bind_workflow_model(TestProjectWorkflowArtifact)
    project_port.bind(repository)
    from ezllmtest.modules.knowledge.ports import retrieval, documents, indexes, splitters
    from ezllmtest.modules.knowledge.infrastructure import retrievers, loaders, index, splitters as concrete_splitters
    retrieval.bind(retrievers)
    documents.bind(loaders)
    indexes.bind(index)
    splitters.bind({name: getattr(concrete_splitters, name) for name in ['design_child_text_splitter', 'design_parent_text_splitter', 'knowledge_text_splitter', 'require_child_text_splitter', 'require_parent_text_splitter', 'testdoc_text_splitter_for_acceptance', 'testdoc_text_splitter_for_api', 'testdoc_text_splitter_for_db', 'testdoc_text_splitter_for_integration', 'testdoc_text_splitter_for_menu', 'testdoc_text_splitter_for_nfunctional', 'testdoc_text_splitter_for_ui', 'testdoc_text_splitter_for_unit', 'testdoc_text_splitter_for_use_case']})
    from ezllmtest.modules.generation.ports import artifact_store, artifacts
    from ezllmtest.modules.generation.infrastructure import artifact_repository, workflow_artifacts
    artifact_repository.bind_model(TestProjectWorkflowArtifact)
    workflow_artifacts.bind_models(TestProjectInfo, TestProjectWorkflowArtifact)
    artifact_store.bind(artifact_repository)
    artifacts.bind(workflow_artifacts)
