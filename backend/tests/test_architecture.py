"""可执行依赖边界：阻止旧 facade、跨域深层导入及平台反向依赖重新出现。"""
import ast
import importlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"src"/"ezllmtest"

# 静态拒绝旧 facade、跨域深层导入和 platform 反向依赖，检查不导入业务服务。
def test_module_import_boundaries():
    violations=[]
    for path in ROOT.rglob("*.py"):
        tree=ast.parse(path.read_text(encoding="utf-8"))
        parts=path.relative_to(ROOT).parts
        for node in ast.walk(tree):
            imports=[]
            if isinstance(node,ast.Import): imports=[x.name for x in node.names]
            elif isinstance(node,ast.ImportFrom) and node.module: imports=[node.module]
            for target in imports:
                if target.startswith(("service.","model.","app.","infrastructure.","dao.","chain.","prompt.")):
                    violations.append((str(path),target))
                if parts[0] in {"platform","shared"} and target.startswith(("ezllmtest.modules.","ezllmtest.bootstrap.")):
                    violations.append((str(path),target))
                if parts[0]=="modules" and target.startswith("ezllmtest.modules."):
                    owner=target.split(".")[2]
                    if owner!=parts[1] and target!="ezllmtest.modules."+owner+".public":
                        violations.append((str(path),target))
                if parts[0]=="modules" and ("application" in parts or "runtime" in parts) and ".infrastructure" in target:
                    violations.append((str(path),target))
                if parts[0]=="modules" and target.startswith("ezllmtest.bootstrap."):
                    violations.append((str(path),target))
            if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and (node.value.id,node.attr) in {("sys","path"),("sys","modules")}:
                violations.append((str(path),"import alias injection"))
    assert violations==[]

# 在网络和资料保护钩子下导入产品模块，证明导入不启动服务或连接外部依赖。
def test_all_modules_import_without_external_connections():
    for path in ROOT.rglob("*.py"):
        if "entrypoints" in path.parts: continue
        name="ezllmtest."+ ".".join(path.relative_to(ROOT).with_suffix("").parts)
        if name.endswith(".__init__"): name=name[:-9]
        importlib.import_module(name)

# 核对 editable 包实际解析到当前 V6 源码，防止测试意外覆盖另一份安装副本。
def test_editable_package_resolves_here():
    import ezllmtest
    assert Path(ezllmtest.__file__).resolve().parent==ROOT
