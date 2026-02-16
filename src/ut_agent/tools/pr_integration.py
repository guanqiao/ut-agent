"""PR 工作流集成模块.

与 Git 平台集成，在 PR 中自动生成测试建议和覆盖率报告。
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from abc import ABC, abstractmethod


class PRStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"
    DRAFT = "draft"


class CommentType(Enum):
    REVIEW = "review"
    SUGGESTION = "suggestion"
    COVERAGE = "coverage"
    TEST_GENERATION = "test_generation"
    QUALITY = "quality"


@dataclass
class FileChange:
    file_path: str
    change_type: str
    additions: int
    deletions: int
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "change_type": self.change_type,
            "additions": self.additions,
            "deletions": self.deletions,
        }


@dataclass
class PRInfo:
    pr_number: int
    title: str
    description: str
    status: PRStatus
    author: str
    source_branch: str
    target_branch: str
    files_changed: List[FileChange]
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pr_number": self.pr_number,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "author": self.author,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "files_changed": [f.to_dict() for f in self.files_changed],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class PRComment:
    comment_type: CommentType
    file_path: Optional[str]
    line_number: Optional[int]
    content: str
    severity: str = "info"
    suggestions: List[str] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        if self.comment_type == CommentType.COVERAGE:
            return self._format_coverage_comment()
        elif self.comment_type == CommentType.TEST_GENERATION:
            return self._format_test_generation_comment()
        elif self.comment_type == CommentType.SUGGESTION:
            return self._format_suggestion_comment()
        else:
            return self.content
    
    def _format_coverage_comment(self) -> str:
        icon = "📊"
        if self.severity == "warning":
            icon = "⚠️"
        elif self.severity == "error":
            icon = "❌"
        
        return f"""### {icon} Coverage Report

{self.content}

{chr(10).join(f'- {s}' for s in self.suggestions) if self.suggestions else ''}"""
    
    def _format_test_generation_comment(self) -> str:
        return f"""### 🧪 Test Generation Suggestions

{self.content}

{chr(10).join(f'- {s}' for s in self.suggestions) if self.suggestions else ''}"""
    
    def _format_suggestion_comment(self) -> str:
        icon = "💡"
        if self.severity == "warning":
            icon = "⚠️"
        elif self.severity == "error":
            icon = "🚨"
        
        location = ""
        if self.file_path:
            location = f"\n**File:** `{self.file_path}`"
            if self.line_number:
                location += f" (Line {self.line_number})"
        
        return f"""{icon} **Suggestion**

{location}

{self.content}

{chr(10).join(f'- {s}' for s in self.suggestions) if self.suggestions else ''}"""


@dataclass
class PRReviewResult:
    pr_number: int
    overall_status: str
    coverage_change: float
    quality_score: float
    test_suggestions: List[PRComment]
    coverage_report: Optional[PRComment] = None
    quality_report: Optional[PRComment] = None
    summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pr_number": self.pr_number,
            "overall_status": self.overall_status,
            "coverage_change": round(self.coverage_change, 2),
            "quality_score": round(self.quality_score, 2),
            "test_suggestions": [s.__dict__ for s in self.test_suggestions],
            "summary": self.summary,
        }


class GitPlatformClient(ABC):
    
    @abstractmethod
    def get_pr_info(self, pr_number: int) -> PRInfo:
        pass
    
    @abstractmethod
    def post_comment(self, pr_number: int, comment: PRComment) -> bool:
        pass
    
    @abstractmethod
    def post_review(self, pr_number: int, comments: List[PRComment], summary: str) -> bool:
        pass
    
    @abstractmethod
    def get_file_content(self, file_path: str, ref: str) -> Optional[str]:
        pass
    
    @abstractmethod
    def set_status(self, pr_number: int, status: str, description: str) -> bool:
        pass


class GitHubClient(GitPlatformClient):
    
    def __init__(
        self,
        repo_owner: str,
        repo_name: str,
        token: Optional[str] = None,
        api_url: str = "https://api.github.com",
    ):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.token = token
        self.api_url = api_url.rstrip('/')
        self._session = None
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers
    
    def get_pr_info(self, pr_number: int) -> PRInfo:
        import httpx
        
        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"
        
        response = httpx.get(url, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()
        
        files_response = httpx.get(
            f"{url}/files",
            headers=self._get_headers(),
        )
        files_response.raise_for_status()
        files_data = files_response.json()
        
        files_changed = [
            FileChange(
                file_path=f["filename"],
                change_type=f["status"],
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
            )
            for f in files_data
        ]
        
        return PRInfo(
            pr_number=pr_number,
            title=data["title"],
            description=data.get("body", ""),
            status=PRStatus(data["state"]),
            author=data["user"]["login"],
            source_branch=data["head"]["ref"],
            target_branch=data["base"]["ref"],
            files_changed=files_changed,
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
        )
    
    def post_comment(self, pr_number: int, comment: PRComment) -> bool:
        import httpx
        
        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/issues/{pr_number}/comments"
        
        body = comment.to_markdown()
        
        response = httpx.post(
            url,
            headers=self._get_headers(),
            json={"body": body},
        )
        
        return response.status_code == 201
    
    def post_review(
        self,
        pr_number: int,
        comments: List[PRComment],
        summary: str,
    ) -> bool:
        import httpx
        
        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}/reviews"
        
        review_comments = []
        for comment in comments:
            if comment.file_path and comment.line_number:
                review_comments.append({
                    "path": comment.file_path,
                    "line": comment.line_number,
                    "body": comment.content,
                })
        
        payload = {
            "body": summary,
            "event": "COMMENT",
            "comments": review_comments,
        }
        
        response = httpx.post(
            url,
            headers=self._get_headers(),
            json=payload,
        )
        
        return response.status_code == 200
    
    def get_file_content(self, file_path: str, ref: str) -> Optional[str]:
        import httpx
        import base64
        
        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}?ref={ref}"
        
        response = httpx.get(url, headers=self._get_headers())
        
        if response.status_code == 200:
            data = response.json()
            if data.get("encoding") == "base64":
                return base64.b64decode(data["content"]).decode("utf-8")
            return data.get("content")
        
        return None
    
    def set_status(self, pr_number: int, status: str, description: str) -> bool:
        import httpx
        
        pr_url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"
        pr_response = httpx.get(pr_url, headers=self._get_headers())
        pr_data = pr_response.json()
        sha = pr_data["head"]["sha"]
        
        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/statuses/{sha}"
        
        response = httpx.post(
            url,
            headers=self._get_headers(),
            json={
                "state": status,
                "description": description,
                "context": "ut-agent/test-coverage",
            },
        )
        
        return response.status_code == 201


class PRTestAnalyzer:
    
    SOURCE_FILE_PATTERNS = [
        re.compile(r'src/main/java/.*\.java$'),
        re.compile(r'src/main/(typescript|ts)/.*\.ts$'),
        re.compile(r'src/main/(javascript|js)/.*\.js$'),
        re.compile(r'src/.*\.vue$'),
        re.compile(r'src/.*\.tsx?$'),
    ]
    
    TEST_FILE_PATTERNS = [
        re.compile(r'src/test/java/.*Test\.java$'),
        re.compile(r'src/test/java/.*Tests\.java$'),
        re.compile(r'.*\.spec\.ts$'),
        re.compile(r'.*\.test\.ts$'),
        re.compile(r'.*\.spec\.js$'),
        re.compile(r'.*\.test\.js$'),
    ]
    
    def __init__(self, git_client: GitPlatformClient):
        self.git_client = git_client
    
    def analyze_pr(self, pr_number: int) -> PRReviewResult:
        pr_info = self.git_client.get_pr_info(pr_number)
        
        source_files = self._filter_source_files(pr_info.files_changed)
        test_files = self._filter_test_files(pr_info.files_changed)
        
        test_suggestions = self._generate_test_suggestions(
            source_files,
            pr_info.source_branch,
        )
        
        coverage_report = self._generate_coverage_report(
            source_files,
            test_files,
        )
        
        quality_report = self._generate_quality_report(source_files)
        
        overall_status = self._determine_overall_status(
            test_suggestions,
            coverage_report,
        )
        
        summary = self._generate_summary(
            pr_info,
            source_files,
            test_files,
            test_suggestions,
        )
        
        return PRReviewResult(
            pr_number=pr_number,
            overall_status=overall_status,
            coverage_change=coverage_report.coverage_change if coverage_report else 0,
            quality_score=quality_report.quality_score if quality_report else 0,
            test_suggestions=test_suggestions,
            coverage_report=coverage_report,
            quality_report=quality_report,
            summary=summary,
        )
    
    def _filter_source_files(self, files: List[FileChange]) -> List[FileChange]:
        return [
            f for f in files
            if any(pattern.match(f.file_path) for pattern in self.SOURCE_FILE_PATTERNS)
        ]
    
    def _filter_test_files(self, files: List[FileChange]) -> List[FileChange]:
        return [
            f for f in files
            if any(pattern.match(f.file_path) for pattern in self.TEST_FILE_PATTERNS)
        ]
    
    def _generate_test_suggestions(
        self,
        source_files: List[FileChange],
        branch: str,
    ) -> List[PRComment]:
        suggestions = []
        
        for file in source_files:
            if file.change_type == "deleted":
                continue
            
            content = self.git_client.get_file_content(file.file_path, branch)
            if not content:
                continue
            
            test_needed = self._analyze_test_needs(file.file_path, content)
            
            if test_needed:
                suggestions.append(PRComment(
                    comment_type=CommentType.TEST_GENERATION,
                    file_path=file.file_path,
                    line_number=None,
                    content=f"New source file detected that may need tests.",
                    severity="warning",
                    suggestions=test_needed,
                ))
        
        return suggestions
    
    def _analyze_test_needs(self, file_path: str, content: str) -> List[str]:
        suggestions = []
        
        if file_path.endswith('.java'):
            class_match = re.search(r'public\s+class\s+(\w+)', content)
            if class_match:
                class_name = class_match.group(1)
                suggestions.append(f"Generate unit tests for `{class_name}`")
            
            method_matches = re.findall(
                r'public\s+\w+\s+(\w+)\s*\([^)]*\)',
                content
            )
            if method_matches:
                suggestions.append(f"Test public methods: {', '.join(method_matches[:5])}")
        
        elif file_path.endswith(('.ts', '.vue', '.tsx')):
            function_matches = re.findall(
                r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',
                content
            )
            if function_matches:
                suggestions.append(f"Test exported functions: {', '.join(function_matches[:5])}")
        
        return suggestions
    
    def _generate_coverage_report(
        self,
        source_files: List[FileChange],
        test_files: List[FileChange],
    ) -> Optional[PRComment]:
        if not source_files:
            return None
        
        source_count = len(source_files)
        test_count = len(test_files)
        
        test_ratio = test_count / source_count if source_count > 0 else 0
        
        content = f"""**Files Changed Analysis**
- Source files: {source_count}
- Test files: {test_count}
- Test-to-source ratio: {test_ratio:.2f}"""
        
        suggestions = []
        if test_ratio < 0.5:
            suggestions.append("Consider adding tests for new source files")
        if test_ratio < 0.2:
            suggestions.append("⚠️ Low test coverage for this PR")
        
        severity = "info"
        if test_ratio < 0.3:
            severity = "warning"
        if test_ratio < 0.1:
            severity = "error"
        
        return PRComment(
            comment_type=CommentType.COVERAGE,
            file_path=None,
            line_number=None,
            content=content,
            severity=severity,
            suggestions=suggestions,
            coverage_change=test_ratio,
        )
    
    def _generate_quality_report(
        self,
        source_files: List[FileChange],
    ) -> Optional[PRComment]:
        if not source_files:
            return None
        
        total_additions = sum(f.additions for f in source_files)
        total_deletions = sum(f.deletions for f in source_files)
        
        quality_score = min(100, (total_additions / 100) * 10)
        
        content = f"""**Code Quality Metrics**
- Lines added: {total_additions}
- Lines deleted: {total_deletions}
- Quality score: {quality_score:.1f}"""
        
        return PRComment(
            comment_type=CommentType.QUALITY,
            file_path=None,
            line_number=None,
            content=content,
            severity="info",
            quality_score=quality_score,
        )
    
    def _determine_overall_status(
        self,
        suggestions: List[PRComment],
        coverage_report: Optional[PRComment],
    ) -> str:
        if not suggestions:
            return "approved"
        
        critical_count = sum(1 for s in suggestions if s.severity == "error")
        warning_count = sum(1 for s in suggestions if s.severity == "warning")
        
        if critical_count > 0:
            return "changes_requested"
        elif warning_count > 2:
            return "comment"
        else:
            return "approved"
    
    def _generate_summary(
        self,
        pr_info: PRInfo,
        source_files: List[FileChange],
        test_files: List[FileChange],
        suggestions: List[PRComment],
    ) -> str:
        summary_parts = [
            f"## 🤖 UT-Agent PR Analysis\n",
            f"**PR #{pr_info.pr_number}**: {pr_info.title}\n",
            f"**Author**: @{pr_info.author}\n",
            f"**Branch**: `{pr_info.source_branch}` → `{pr_info.target_branch}`\n",
        ]
        
        summary_parts.append("\n### 📊 Summary\n")
        summary_parts.append(f"- {len(source_files)} source file(s) changed\n")
        summary_parts.append(f"- {len(test_files)} test file(s) changed\n")
        
        if suggestions:
            summary_parts.append(f"- {len(suggestions)} suggestion(s) for improvement\n")
        
        summary_parts.append("\n### ✅ Status\n")
        if not suggestions:
            summary_parts.append("All checks passed! No additional tests needed.\n")
        else:
            summary_parts.append(f"Found {len(suggestions)} area(s) that may need attention.\n")
        
        return "".join(summary_parts)


class PRAutomationBot:
    
    def __init__(
        self,
        git_client: GitPlatformClient,
        test_generator=None,
        coverage_analyzer=None,
    ):
        self.git_client = git_client
        self.test_generator = test_generator
        self.coverage_analyzer = coverage_analyzer
        self.analyzer = PRTestAnalyzer(git_client)
    
    def process_pr(self, pr_number: int) -> PRReviewResult:
        result = self.analyzer.analyze_pr(pr_number)
        
        if result.test_suggestions:
            self._post_test_suggestions(pr_number, result.test_suggestions)
        
        if result.coverage_report:
            self.git_client.post_comment(pr_number, result.coverage_report)
        
        status = "success" if result.overall_status == "approved" else "pending"
        description = f"Coverage analysis: {result.overall_status}"
        self.git_client.set_status(pr_number, status, description)
        
        return result
    
    def _post_test_suggestions(
        self,
        pr_number: int,
        suggestions: List[PRComment],
    ) -> None:
        for suggestion in suggestions[:5]:
            self.git_client.post_comment(pr_number, suggestion)
    
    def generate_tests_for_pr(
        self,
        pr_number: int,
        output_dir: str,
    ) -> Dict[str, str]:
        pr_info = self.git_client.get_pr_info(pr_number)
        
        source_files = [
            f for f in pr_info.files_changed
            if f.change_type != "deleted"
        ]
        
        generated_tests = {}
        
        for file in source_files:
            content = self.git_client.get_file_content(
                file.file_path,
                pr_info.source_branch,
            )
            
            if content and self.test_generator:
                test_code = self._generate_test_for_file(
                    file.file_path,
                    content,
                )
                
                if test_code:
                    generated_tests[file.file_path] = test_code
        
        return generated_tests
    
    def _generate_test_for_file(
        self,
        file_path: str,
        content: str,
    ) -> Optional[str]:
        if not self.test_generator:
            return None
        
        return f"// Generated test for {file_path}\n// TODO: Implement with actual test generator"


class PRWebhookHandler:
    
    def __init__(self, bot: PRAutomationBot):
        self.bot = bot
        self._handlers = {
            "opened": self._handle_pr_opened,
            "synchronize": self._handle_pr_synchronize,
            "closed": self._handle_pr_closed,
        }
    
    def handle_webhook(
        self,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        handler = self._handlers.get(event_type)
        
        if handler:
            return handler(payload)
        
        return {"status": "ignored", "reason": f"Unhandled event type: {event_type}"}
    
    def _handle_pr_opened(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        pr_number = payload.get("number", 0)
        
        result = self.bot.process_pr(pr_number)
        
        return {
            "status": "processed",
            "pr_number": pr_number,
            "action": "opened",
            "result": result.to_dict(),
        }
    
    def _handle_pr_synchronize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        pr_number = payload.get("number", 0)
        
        result = self.bot.process_pr(pr_number)
        
        return {
            "status": "processed",
            "pr_number": pr_number,
            "action": "synchronized",
            "result": result.to_dict(),
        }
    
    def _handle_pr_closed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        pr_number = payload.get("number", 0)
        merged = payload.get("merged", False)
        
        return {
            "status": "processed",
            "pr_number": pr_number,
            "action": "merged" if merged else "closed",
        }
