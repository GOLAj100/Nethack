"""Ищет локальные переменные, перекрывающие имена импортированных модулей.

Пример бага, который это ловит:
    from .lang import t          # функция перевода
    def check_tile(self, x, y):
        t = lv.at(x, y)          # локальное t - тип тайла
        self.msg(t("m.fountain"))  # TypeError: 'int' object is not callable
"""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def module_imports(tree: ast.Module) -> dict[str, str]:
    out = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    continue
                out[a.asname or a.name] = node.module or ""
        elif isinstance(node, ast.Import):
            for a in node.names:
                out[(a.asname or a.name).split(".")[0]] = a.name
    return out


def local_names(fn) -> set[str]:
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            tgt = node.target
            for n in ast.walk(tgt):
                if isinstance(n, ast.Name):
                    names.add(n.id)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name):
                    names.add(n.id)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                names.add(node.name)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars:
                    for n in ast.walk(item.optional_vars):
                        if isinstance(n, ast.Name):
                            names.add(n.id)
        elif isinstance(node, ast.comprehension):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name):
                    names.add(n.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node is not fn:
                names.add(node.name)
    return names


def check(path: str) -> list[str]:
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src, filename=path)
    imports = module_imports(tree)
    problems = []
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        clash = local_names(fn) & set(imports)
        if clash:
            problems.append(f"{os.path.relpath(path, ROOT)}:{fn.lineno} "
                            f"{fn.name}(): локальные {sorted(clash)} "
                            f"перекрывают импорт из {sorted({imports[c] for c in clash})}")
    return problems


def main() -> int:
    targets = sys.argv[1:] or ["game", "engine"]
    found = []
    for target in targets:
        full = os.path.join(ROOT, target)
        files = []
        if os.path.isfile(full):
            files = [full]
        else:
            for root, _, names in os.walk(full):
                if "__pycache__" in root:
                    continue
                files += [os.path.join(root, n) for n in names if n.endswith(".py")]
        for f in sorted(files):
            found += check(f)
    for line in found:
        print(line)
    print()
    print(f"конфликтов имён: {len(found)}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
