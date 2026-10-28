"""Tree-sitter Java extraction and lightweight Spring configuration parsing."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import tree_sitter_java
from tree_sitter import Language, Parser


@dataclass
class MethodInfo:
    name: str
    class_name: str
    file: str
    start_line: int
    end_line: int
    calls: list[str] = field(default_factory=list)
    config_keys: list[str] = field(default_factory=list)
    endpoints: list[tuple[str, str]] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.class_name}.{self.name}()"


@dataclass
class ClassInfo:
    name: str
    file: str
    start_line: int
    end_line: int
    methods: list[MethodInfo] = field(default_factory=list)
    config_keys: list[str] = field(default_factory=list)
    endpoints: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class JavaProject:
    classes: list[ClassInfo]
    config_keys: dict[str, list[str]]


_PARSER = Parser(Language(tree_sitter_java.language()))
_ENDPOINT_ANNOTATIONS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}
_CLASS_NODE_TYPES = {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"}
_SKIP_DIRECTORIES = {".git", ".venv", "venv", "target"}


def _text(source: bytes, node: object) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(node: object):
    yield node
    for child in node.children:
        yield from _walk(child)


def _annotations(node: object, source: bytes) -> list[str]:
    result: list[str] = []
    for child in node.children:
        if child.type in {"modifiers", "annotation", "marker_annotation"}:
            result.extend(_text(source, item) for item in _walk(child) if item.type in {"annotation", "marker_annotation"})
    return result


def _endpoint(annotation: str) -> tuple[str, str] | None:
    match = re.match(r"@(?:[\w$.]+\.)?(\w+)\s*(?:\((.*)\))?", annotation, re.DOTALL)
    if not match:
        return None
    name, args = match.group(1), match.group(2) or ""
    if name in _ENDPOINT_ANNOTATIONS:
        method = _ENDPOINT_ANNOTATIONS[name]
    elif name == "RequestMapping":
        method_match = re.search(r"\b(?:RequestMethod\.)?(GET|POST|PUT|DELETE|PATCH)\b", args)
        method = method_match.group(1) if method_match else "ANY"
    else:
        return None
    path_match = re.search(r"\b(?:path|value)\s*=\s*(?:\{\s*)?\"([^\"]*)\"", args)
    if path_match is None:
        path_match = re.match(r'\s*(?:\{\s*)?"([^"]*)"', args)
    return method, path_match.group(1) if path_match else "/"


def _config_from_source(source: str) -> list[str]:
    keys: set[str] = set()
    keys.update(re.findall(r'\$\{([^}:]+)', source))
    for line in source.splitlines():
        property_match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*[:=]\s*.*$", line)
        if property_match and not line.lstrip().startswith("#"):
            keys.add(property_match.group(1))
    return sorted(keys)


def _application_config_keys(path: Path, source: str) -> list[str]:
    if path.suffix == ".properties":
        return _config_from_source(source)
    parents: list[tuple[int, str]] = []
    keys: set[str] = set()
    for line in source.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\s*)([A-Za-z0-9_.-]+)\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        indent = len(match.group(1).expandtabs(2))
        name, value = match.group(2), match.group(3)
        while parents and parents[-1][0] >= indent:
            parents.pop()
        if value:
            keys.add(".".join([part for _, part in parents] + [name]))
        else:
            parents.append((indent, name))
    return sorted(keys)


def _project_files(root: Path, predicate: Callable[[str], bool]) -> list[Path]:
    matches: list[Path] = []
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name not in _SKIP_DIRECTORIES]
        matches.extend(Path(directory) / name for name in filenames if predicate(name))
    return sorted(matches)


def parse_java_file(path: str | Path, root: str | Path | None = None) -> list[ClassInfo]:
    """Parse Java declarations, calls, Spring endpoints, and @Value properties."""
    file_path = Path(path)
    source = file_path.read_bytes()
    tree = _PARSER.parse(source)
    relative = file_path.relative_to(root).as_posix() if root else str(file_path)
    classes: list[ClassInfo] = []

    for class_node in (item for item in _walk(tree.root_node) if item.type in {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"}):
        name_node = next((child for child in class_node.children if child.type == "identifier"), None)
        if name_node is None:
            continue
        class_name = _text(source, name_node)
        class_info = ClassInfo(class_name, relative, class_node.start_point.row + 1, class_node.end_point.row + 1)
        class_annotations = _annotations(class_node, source)
        class_endpoint = next((_endpoint(annotation) for annotation in class_annotations if _endpoint(annotation)), None)
        for annotation in class_annotations:
            if re.search(r"@(?:[\w$]+\.)*Value\b", annotation):
                class_info.config_keys.extend(re.findall(r'\$\{([^}:]+)', annotation))

        for member in class_node.children:
            if member.type != "class_body":
                continue
            for field_node in member.children:
                if field_node.type != "field_declaration":
                    continue
                for annotation in _annotations(field_node, source):
                    if re.search(r"@(?:[\w$]+\.)*Value\b", annotation):
                        class_info.config_keys.extend(re.findall(r'\$\{([^}:]+)', annotation))

        for method_node in (item for item in _walk(class_node) if item.type in {"method_declaration", "constructor_declaration"}):
            parent = method_node.parent
            nested_class = False
            while parent is not None and parent.id != class_node.id:
                if parent.type in _CLASS_NODE_TYPES:
                    nested_class = True
                    break
                parent = parent.parent
            if nested_class:
                continue
            method_name_node = method_node.child_by_field_name("name")
            if method_name_node is None:
                continue
            method_name = _text(source, method_name_node)
            method = MethodInfo(method_name, class_name, relative, method_node.start_point.row + 1, method_node.end_point.row + 1)
            for call in _walk(method_node):
                if call.type == "method_invocation":
                    name = call.child_by_field_name("name")
                    if name is not None:
                        method.calls.append(_text(source, name))
            for annotation in _annotations(method_node, source):
                if re.search(r"@(?:[\w$]+\.)*Value\b", annotation):
                    method.config_keys.extend(re.findall(r'\$\{([^}:]+)', annotation))
                endpoint = _endpoint(annotation)
                if endpoint:
                    method.endpoints.append(endpoint)
            if class_endpoint and method.endpoints:
                method.endpoints = [
                    (verb if verb != "ANY" else class_endpoint[0], (class_endpoint[1].rstrip("/") + "/" + path.lstrip("/")).rstrip("/") or "/")
                    for verb, path in method.endpoints
                ]
            class_info.methods.append(method)
        classes.append(class_info)
    return classes


def parse_project(root: str | Path) -> JavaProject:
    """Parse all Java sources and application YAML/properties keys below root."""
    project_root = Path(root).resolve()
    classes: list[ClassInfo] = []
    for path in _project_files(project_root, lambda name: name.endswith(".java")):
        classes.extend(parse_java_file(path, project_root))

    config_keys: dict[str, list[str]] = {}
    for path in _project_files(
        project_root,
        lambda name: name.startswith("application") and Path(name).suffix in {".yml", ".yaml", ".properties"},
    ):
        relative = path.relative_to(project_root).as_posix()
        content = path.read_text(encoding="utf-8")
        for key in _application_config_keys(path, content):
            config_keys.setdefault(key, []).append(relative)
    return JavaProject(classes, config_keys)
