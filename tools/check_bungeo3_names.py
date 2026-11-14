#!/usr/bin/env python3
"""bake_sequence_node.py 가 쓰는 P.*(positions.py) / G.*(grip_params.py) 이름이 모두 정의돼 있는지 정적 검사.

로봇을 돌려 보기 전에, 공정 도중(예: 8단계)에 AttributeError 로 죽을 이름 누락을 미리 찾는다.

  python3 tools/check_bungeo3_names.py ~/bungeoppang3_ws/src/bungeoppang2/bungeoppang2_yammy
"""
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser()


def defined(path):
    names = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
    return names


def used(path, alias):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # hasattr(G, "NAME") 로 이미 보호된 이름은 없어도 죽지 않으므로 제외
    guarded = {c.args[1].value for c in ast.walk(tree)
               if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "hasattr"
               and len(c.args) == 2 and isinstance(c.args[0], ast.Name) and c.args[0].id == alias
               and isinstance(c.args[1], ast.Constant) and isinstance(c.args[1].value, str)}
    return {n.attr for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == alias} - guarded


node = root / "bake_sequence_node.py"
bad = False
for alias, mod in (("P", "positions.py"), ("G", "grip_params.py")):
    missing = sorted(used(node, alias) - defined(root / mod))
    print(f"{alias}.* ({mod}): {'OK — 누락 없음' if not missing else '누락 ' + str(len(missing)) + '개 → ' + ', '.join(missing)}")
    bad = bad or bool(missing)
lines = len(node.read_text(encoding="utf-8").splitlines())
has_main = "def main" in node.read_text(encoding="utf-8")
print(f"bake_sequence_node.py: {lines}줄, main {'있음' if has_main else '없음 ← 실행 코드가 아님'}")
sys.exit(1 if bad or not has_main else 0)
