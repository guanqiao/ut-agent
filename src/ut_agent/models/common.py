"""公共数据模型定义."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class ChangeType(Enum):
    """变更类型."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class CodeChange:
    """代码变更信息."""

    file_path: str
    change_type: ChangeType
    old_path: Optional[str] = None
    line_range: Tuple[int, int] = field(default_factory=lambda: (0, 0))
    diff_content: str = ""
    added_lines: List[int] = field(default_factory=list)
    deleted_lines: List[int] = field(default_factory=list)


@dataclass
class MethodInfo:
    """方法信息."""

    name: str
    signature: str
    line_start: int
    line_end: int
    content: str = ""
    modifiers: List[str] = field(default_factory=list)
    return_type: str = ""
    parameters: List[str] = field(default_factory=list)
    is_public: bool = True
    is_static: bool = False
    annotations: List[str] = field(default_factory=list)


@dataclass
class MethodChange:
    """方法级变更信息."""

    file_path: str
    method_name: str
    change_type: ChangeType
    signature: str = ""
    line_start: int = 0
    line_end: int = 0
