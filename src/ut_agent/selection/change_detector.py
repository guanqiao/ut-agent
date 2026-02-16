"""变更检测器."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

try:
    import git
except ImportError:
    git = None


class ChangeType(Enum):
    """变更类型."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class MethodChange:
    """方法变更信息."""
    name: str
    signature: str
    change_type: ChangeType
    line_start: int = 0
    line_end: int = 0
    old_content: str = ""
    new_content: str = ""


@dataclass
class FileChange:
    """文件变更信息."""
    path: str
    change_type: ChangeType
    old_path: Optional[str] = None
    old_content: str = ""
    new_content: str = ""
    method_changes: List[MethodChange] = field(default_factory=list)
    added_lines: List[int] = field(default_factory=list)
    deleted_lines: List[int] = field(default_factory=list)


@dataclass
class ChangeSet:
    """变更集合."""
    changes: List[FileChange] = field(default_factory=list)
    base_ref: str = ""
    head_ref: str = ""
    
    def add(self, change: FileChange) -> None:
        self.changes.append(change)
    
    def get_by_type(self, change_type: ChangeType) -> List[FileChange]:
        return [c for c in self.changes if c.change_type == change_type]
    
    def get_file_paths(self) -> List[str]:
        return [c.path for c in self.changes]


class ChangeDetector:
    """变更检测器 - 检测代码变更并识别变更的方法."""
    
    SOURCE_EXTENSIONS = {".java", ".ts", ".tsx", ".js", ".jsx", ".vue", ".py"}
    
    def __init__(self, repo_path: str):
        self._repo_path = Path(repo_path)
        self._repo = None
        
        try:
            if git is not None:
                self._repo = git.Repo(repo_path)
        except Exception:
            pass
    
    def detect_changes(
        self,
        base_ref: str = "HEAD~1",
        head_ref: str = "HEAD",
    ) -> ChangeSet:
        change_set = ChangeSet(
            base_ref=base_ref,
            head_ref=head_ref,
        )
        
        if self._repo is None:
            return change_set
        
        try:
            base_commit = self._repo.commit(base_ref)
            head_commit = self._repo.commit(head_ref)
            
            diff_index = base_commit.diff(head_commit)
            
            for diff in diff_index:
                if not self._is_source_file(diff.a_path or diff.b_path):
                    continue
                
                change = self._create_file_change(diff)
                if change:
                    change_set.add(change)
        
        except Exception:
            pass
        
        return change_set
    
    def detect_staged_changes(self) -> ChangeSet:
        change_set = ChangeSet(
            base_ref="HEAD",
            head_ref="INDEX",
        )
        
        if self._repo is None:
            return change_set
        
        try:
            diff_index = self._repo.index.diff("HEAD")
            
            for diff in diff_index:
                if not self._is_source_file(diff.a_path or diff.b_path):
                    continue
                
                change = self._create_file_change(diff)
                if change:
                    change_set.add(change)
        
        except Exception:
            pass
        
        return change_set
    
    def detect_unstaged_changes(self) -> ChangeSet:
        change_set = ChangeSet(
            base_ref="INDEX",
            head_ref="WORKING",
        )
        
        if self._repo is None:
            return change_set
        
        try:
            if self._repo.is_dirty():
                for item in self._repo.index.diff(None):
                    if not self._is_source_file(item.a_path):
                        continue
                    
                    change = FileChange(
                        path=item.a_path,
                        change_type=ChangeType.MODIFIED,
                    )
                    change_set.add(change)
        
        except Exception:
            pass
        
        return change_set
    
    def detect_method_changes(self, file_change: FileChange) -> List[MethodChange]:
        method_changes = []
        
        old_methods = self._parse_methods(file_change.old_content, file_change.path)
        new_methods = self._parse_methods(file_change.new_content, file_change.path)
        
        old_sigs = {m.signature: m for m in old_methods}
        new_sigs = {m.signature: m for m in new_methods}
        
        for sig, method in new_sigs.items():
            if sig not in old_sigs:
                method_changes.append(MethodChange(
                    name=method.name,
                    signature=method.signature,
                    change_type=ChangeType.ADDED,
                    line_start=method.line_start,
                    line_end=method.line_end,
                    new_content=method.content,
                ))
        
        for sig, old_method in old_sigs.items():
            if sig not in new_sigs:
                method_changes.append(MethodChange(
                    name=old_method.name,
                    signature=old_method.signature,
                    change_type=ChangeType.DELETED,
                    line_start=old_method.line_start,
                    line_end=old_method.line_end,
                    old_content=old_method.content,
                ))
        
        for sig, new_method in new_sigs.items():
            if sig in old_sigs:
                old_method = old_sigs[sig]
                if old_method.content != new_method.content:
                    method_changes.append(MethodChange(
                        name=new_method.name,
                        signature=new_method.signature,
                        change_type=ChangeType.MODIFIED,
                        line_start=old_method.line_start,
                        line_end=new_method.line_end,
                        old_content=old_method.content,
                        new_content=new_method.content,
                    ))
        
        return method_changes
    
    def _create_file_change(self, diff) -> Optional[FileChange]:
        change_type = self._get_change_type(diff)
        
        old_content = ""
        new_content = ""
        
        try:
            if diff.a_blob:
                old_content = diff.a_blob.data_stream.read().decode("utf-8", errors="ignore")
            if diff.b_blob:
                new_content = diff.b_blob.data_stream.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        
        change = FileChange(
            path=diff.b_path or diff.a_path,
            change_type=change_type,
            old_path=diff.a_path if diff.renamed else None,
            old_content=old_content,
            new_content=new_content,
        )
        
        change.method_changes = self.detect_method_changes(change)
        
        return change
    
    def _get_change_type(self, diff) -> ChangeType:
        if diff.new_file:
            return ChangeType.ADDED
        elif diff.deleted_file:
            return ChangeType.DELETED
        elif diff.renamed:
            return ChangeType.RENAMED
        else:
            return ChangeType.MODIFIED
    
    def _is_source_file(self, path: str) -> bool:
        if not path:
            return False
        
        ext = Path(path).suffix.lower()
        return ext in self.SOURCE_EXTENSIONS
    
    def _parse_methods(self, content: str, file_path: str) -> List[Any]:
        if not content:
            return []
        
        ext = Path(file_path).suffix.lower()
        
        if ext == ".java":
            return self._parse_java_methods(content)
        elif ext in [".ts", ".tsx", ".js", ".jsx"]:
            return self._parse_ts_methods(content)
        elif ext == ".py":
            return self._parse_python_methods(content)
        else:
            return []
    
    def _parse_java_methods(self, content: str) -> List[Any]:
        methods = []
        
        pattern = r'(?:public|private|protected)?\s+(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\s*\{'
        
        for match in re.finditer(pattern, content):
            name = match.group(1)
            params = match.group(2)
            
            start = match.start()
            line_start = content[:start].count("\n") + 1
            
            brace_count = 0
            end = start
            for i, char in enumerate(content[start:], start):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            
            line_end = content[:end].count("\n") + 1
            method_content = content[start:end]
            
            from dataclasses import dataclass
            @dataclass
            class MethodInfo:
                name: str
                signature: str
                content: str
                line_start: int
                line_end: int
            
            methods.append(MethodInfo(
                name=name,
                signature=f"{name}({params})",
                content=method_content,
                line_start=line_start,
                line_end=line_end,
            ))
        
        return methods
    
    def _parse_ts_methods(self, content: str) -> List[Any]:
        methods = []
        
        patterns = [
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
            r'(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*[^=]+)?\s*=>',
            r'(?:public|private)?\s*(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*\w+)?\s*\{',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                params = match.group(2)
                
                start = match.start()
                line_start = content[:start].count("\n") + 1
                
                from dataclasses import dataclass
                @dataclass
                class MethodInfo:
                    name: str
                    signature: str
                    content: str
                    line_start: int
                    line_end: int
                
                methods.append(MethodInfo(
                    name=name,
                    signature=f"{name}({params})",
                    content=match.group(0),
                    line_start=line_start,
                    line_end=line_start + 5,
                ))
        
        return methods
    
    def _parse_python_methods(self, content: str) -> List[Any]:
        methods = []
        
        pattern = r'def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*\w+)?\s*:'
        
        for match in re.finditer(pattern, content):
            name = match.group(1)
            params = match.group(2)
            
            start = match.start()
            line_start = content[:start].count("\n") + 1
            
            lines = content[start:].split("\n")
            method_lines = [lines[0]]
            
            if len(lines) > 1:
                base_indent = len(lines[0]) - len(lines[0].lstrip())
                for line in lines[1:]:
                    if line.strip() and not line.startswith(" " * (base_indent + 1)):
                        break
                    method_lines.append(line)
            
            from dataclasses import dataclass
            @dataclass
            class MethodInfo:
                name: str
                signature: str
                content: str
                line_start: int
                line_end: int
            
            methods.append(MethodInfo(
                name=name,
                signature=f"{name}({params})",
                content="\n".join(method_lines),
                line_start=line_start,
                line_end=line_start + len(method_lines),
            ))
        
        return methods
