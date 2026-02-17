"""GitHub Actions 集成.

提供 GitHub Actions 工作流生成、PR 评论和状态报告功能。
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowTrigger:
    """工作流触发器.
    
    Attributes:
        event: 触发事件 (push, pull_request, etc.)
        branches: 分支列表
        paths: 路径模式列表
    """
    event: str
    branches: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        data = {"event": self.event}
        if self.branches:
            data["branches"] = self.branches
        if self.paths:
            data["paths"] = self.paths
        return data


@dataclass
class WorkflowStep:
    """工作流步骤.
    
    Attributes:
        name: 步骤名称
        uses: 使用的 action
        run: 运行命令
        env: 环境变量
        with_: action 参数
    """
    name: str
    uses: Optional[str] = None
    run: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    with_: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        data = {"name": self.name}
        if self.uses:
            data["uses"] = self.uses
        if self.run:
            data["run"] = self.run
        if self.env:
            data["env"] = self.env
        if self.with_:
            data["with"] = self.with_
        return data


@dataclass
class WorkflowJob:
    """工作流任务.
    
    Attributes:
        name: 任务名称
        runs_on: 运行环境
        steps: 步骤列表
        needs: 依赖任务
        strategy: 矩阵策略
    """
    name: str
    runs_on: str = "ubuntu-latest"
    steps: List[WorkflowStep] = field(default_factory=list)
    needs: List[str] = field(default_factory=list)
    strategy: Dict[str, Any] = field(default_factory=dict)
    
    def add_step(self, step: WorkflowStep) -> None:
        """添加步骤."""
        self.steps.append(step)
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        data = {
            "name": self.name,
            "runs-on": self.runs_on,
            "steps": [step.to_dict() for step in self.steps],
        }
        if self.needs:
            data["needs"] = self.needs
        if self.strategy:
            data["strategy"] = self.strategy
        return data


class GitHubActionsWorkflow:
    """GitHub Actions 工作流.
    
    表示一个完整的 GitHub Actions 工作流。
    """
    
    def __init__(
        self,
        name: str,
        on_events: Optional[List[str]] = None,
    ):
        """初始化工作流.
        
        Args:
            name: 工作流名称
            on_events: 触发事件列表
        """
        self.name = name
        self.on_events = on_events or ["push", "pull_request"]
        self.jobs: Dict[str, WorkflowJob] = {}
        
    def add_job(self, job_id: str, job: WorkflowJob) -> None:
        """添加任务.
        
        Args:
            job_id: 任务 ID
            job: 任务对象
        """
        self.jobs[job_id] = job
        
    def to_yaml(self) -> str:
        """生成 YAML 内容.
        
        Returns:
            str: YAML 内容
        """
        lines = [f"name: {self.name}", ""]
        
        # on 部分
        lines.append("on:")
        for event in self.on_events:
            lines.append(f"  {event}:")
            lines.append("    branches:")
            lines.append("      - main")
            lines.append("      - develop")
        lines.append("")
        
        # jobs 部分
        lines.append("jobs:")
        for job_id, job in self.jobs.items():
            lines.append(f"  {job_id}:")
            job_dict = job.to_dict()
            
            # name
            lines.append(f"    name: {job_dict['name']}")
            
            # runs-on
            lines.append(f"    runs-on: {job_dict['runs-on']}")
            
            # strategy (matrix)
            if "strategy" in job_dict and "matrix" in job_dict["strategy"]:
                lines.append("    strategy:")
                lines.append("      matrix:")
                for key, values in job_dict["strategy"]["matrix"].items():
                    lines.append(f"        {key}: {values}")
                lines.append("      fail-fast: false")
            
            # steps
            lines.append("    steps:")
            for step in job_dict["steps"]:
                lines.append(f"      - name: {step['name']}")
                
                if "uses" in step:
                    lines.append(f"        uses: {step['uses']}")
                if "with" in step:
                    for key, value in step["with"].items():
                        lines.append(f"        with:")
                        lines.append(f"          {key}: {value}")
                if "run" in step:
                    lines.append(f"        run: {step['run']}")
                if "env" in step:
                    lines.append(f"        env:")
                    for key, value in step["env"].items():
                        lines.append(f"          {key}: {value}")
                        
        return "\n".join(lines)


class GitHubActionsGenerator:
    """GitHub Actions 工作流生成器.
    
    生成各种 CI/CD 工作流。
    """
    
    def __init__(self):
        """初始化生成器."""
        self.logger = logging.getLogger(__name__)
        
    def generate_python_test_workflow(
        self,
        python_versions: Optional[List[str]] = None,
        test_command: str = "pytest tests/",
        os_versions: Optional[List[str]] = None,
    ) -> GitHubActionsWorkflow:
        """生成 Python 测试工作流.
        
        Args:
            python_versions: Python 版本列表
            test_command: 测试命令
            os_versions: 操作系统版本列表
            
        Returns:
            GitHubActionsWorkflow: 工作流对象
        """
        python_versions = python_versions or ["3.10", "3.11", "3.12"]
        os_versions = os_versions or ["ubuntu-latest"]
        
        workflow = GitHubActionsWorkflow(
            name="Python Tests",
            on_events=["push", "pull_request"],
        )
        
        job = WorkflowJob(name="test")
        
        # 矩阵策略
        if len(python_versions) > 1 or len(os_versions) > 1:
            job.strategy = {
                "matrix": {
                    "python-version": python_versions,
                    "os": os_versions,
                },
            }
        
        # Checkout
        job.add_step(WorkflowStep(
            name="Checkout code",
            uses="actions/checkout@v4",
        ))
        
        # Setup Python
        if job.strategy:
            job.add_step(WorkflowStep(
                name="Setup Python ${{ matrix.python-version }}",
                uses="actions/setup-python@v5",
                with_={"python-version": "${{ matrix.python-version }}"},
            ))
        else:
            job.add_step(WorkflowStep(
                name="Setup Python",
                uses="actions/setup-python@v5",
                with_={"python-version": python_versions[0]},
            ))
        
        # Install dependencies
        job.add_step(WorkflowStep(
            name="Install dependencies",
            run="pip install -r requirements.txt -r requirements-dev.txt",
        ))
        
        # Run tests
        job.add_step(WorkflowStep(
            name="Run tests",
            run=test_command,
        ))
        
        workflow.add_job("test", job)
        return workflow
        
    def generate_coverage_workflow(
        self,
        coverage_tool: str = "pytest-cov",
        min_coverage: int = 80,
    ) -> GitHubActionsWorkflow:
        """生成覆盖率工作流.
        
        Args:
            coverage_tool: 覆盖率工具
            min_coverage: 最小覆盖率
            
        Returns:
            GitHubActionsWorkflow: 工作流对象
        """
        workflow = GitHubActionsWorkflow(
            name="Coverage",
            on_events=["push", "pull_request"],
        )
        
        job = WorkflowJob(name="coverage")
        
        job.add_step(WorkflowStep(
            name="Checkout code",
            uses="actions/checkout@v4",
        ))
        
        job.add_step(WorkflowStep(
            name="Setup Python",
            uses="actions/setup-python@v5",
            with_={"python-version": "3.12"},
        ))
        
        job.add_step(WorkflowStep(
            name="Install dependencies",
            run=f"pip install -r requirements.txt {coverage_tool}",
        ))
        
        job.add_step(WorkflowStep(
            name="Run tests with coverage",
            run=f"pytest --cov=src --cov-report=xml --cov-fail-under={min_coverage}",
        ))
        
        job.add_step(WorkflowStep(
            name="Upload coverage to Codecov",
            uses="codecov/codecov-action@v3",
            with_={"file": "./coverage.xml"},
        ))
        
        workflow.add_job("coverage", job)
        return workflow
        
    def generate_lint_workflow(
        self,
        linters: Optional[List[str]] = None,
    ) -> GitHubActionsWorkflow:
        """生成代码检查工作流.
        
        Args:
            linters: 代码检查工具列表
            
        Returns:
            GitHubActionsWorkflow: 工作流对象
        """
        linters = linters or ["flake8", "black", "mypy"]
        
        workflow = GitHubActionsWorkflow(
            name="Lint",
            on_events=["push", "pull_request"],
        )
        
        job = WorkflowJob(name="lint")
        
        job.add_step(WorkflowStep(
            name="Checkout code",
            uses="actions/checkout@v4",
        ))
        
        job.add_step(WorkflowStep(
            name="Setup Python",
            uses="actions/setup-python@v5",
            with_={"python-version": "3.12"},
        ))
        
        job.add_step(WorkflowStep(
            name="Install linting tools",
            run=f"pip install {' '.join(linters)}",
        ))
        
        # Run each linter
        for linter in linters:
            if linter == "flake8":
                job.add_step(WorkflowStep(
                    name="Run flake8",
                    run="flake8 src/ tests/",
                ))
            elif linter == "black":
                job.add_step(WorkflowStep(
                    name="Run black",
                    run="black --check src/ tests/",
                ))
            elif linter == "mypy":
                job.add_step(WorkflowStep(
                    name="Run mypy",
                    run="mypy src/",
                ))
        
        workflow.add_job("lint", job)
        return workflow
        
    def generate_ut_agent_workflow(
        self,
        generate_tests: bool = True,
        analyze_quality: bool = True,
    ) -> GitHubActionsWorkflow:
        """生成 UT-Agent 专用工作流.
        
        Args:
            generate_tests: 是否生成测试
            analyze_quality: 是否分析质量
            
        Returns:
            GitHubActionsWorkflow: 工作流对象
        """
        workflow = GitHubActionsWorkflow(
            name="UT Agent CI",
            on_events=["push", "pull_request"],
        )
        
        job = WorkflowJob(name="ut-agent")
        
        job.add_step(WorkflowStep(
            name="Checkout code",
            uses="actions/checkout@v4",
        ))
        
        job.add_step(WorkflowStep(
            name="Setup Python",
            uses="actions/setup-python@v5",
            with_={"python-version": "3.12"},
        ))
        
        job.add_step(WorkflowStep(
            name="Install UT Agent",
            run="pip install ut-agent",
        ))
        
        if generate_tests:
            job.add_step(WorkflowStep(
                name="Generate tests",
                run="ut-agent generate --all",
            ))
        
        job.add_step(WorkflowStep(
            name="Run tests",
            run="pytest tests/ -v",
        ))
        
        if analyze_quality:
            job.add_step(WorkflowStep(
                name="Analyze test quality",
                run="ut-agent analyze tests/",
            ))
        
        workflow.add_job("ut-agent", job)
        return workflow
        
    def save_workflow(
        self,
        workflow: GitHubActionsWorkflow,
        filename: str,
        output_path: str,
    ) -> bool:
        """保存工作流到文件.
        
        Args:
            workflow: 工作流对象
            filename: 文件名
            output_path: 输出路径
            
        Returns:
            bool: 是否成功
        """
        try:
            path = Path(output_path)
            path.mkdir(parents=True, exist_ok=True)
            
            file_path = path / filename
            file_path.write_text(workflow.to_yaml())
            
            self.logger.info(f"Saved workflow to {file_path}")
            return True
        except Exception as e:
            self.logger.exception(f"Failed to save workflow: {e}")
            return False
            
    def validate_workflow(self, workflow: GitHubActionsWorkflow) -> bool:
        """验证工作流.
        
        Args:
            workflow: 工作流对象
            
        Returns:
            bool: 是否有效
        """
        if not workflow.name:
            return False
        if not workflow.on_events:
            return False
        if not workflow.jobs:
            return False
        return True


class GitHubCommentReporter:
    """GitHub 评论报告器.
    
    在 PR 中发布测试和覆盖率报告。
    """
    
    def __init__(self, token: str, repository: str):
        """初始化报告器.
        
        Args:
            token: GitHub Token
            repository: 仓库名 (owner/repo)
        """
        self.token = token
        self.repository = repository
        self.logger = logging.getLogger(__name__)
        
    def format_test_report(self, results: Dict[str, Any]) -> str:
        """格式化测试报告.
        
        Args:
            results: 测试结果
            
        Returns:
            str: 报告内容
        """
        lines = [
            "## 🧪 Test Results",
            "",
            f"- **Passed**: {results.get('passed', 0)}",
            f"- **Failed**: {results.get('failed', 0)}",
            f"- **Skipped**: {results.get('skipped', 0)}",
            f"- **Total**: {results.get('total', 0)}",
            f"- **Duration**: {results.get('duration', 0):.2f}s",
            "",
        ]
        
        if results.get('failed', 0) > 0:
            lines.append("❌ Some tests failed. Please check the logs.")
        else:
            lines.append("✅ All tests passed!")
            
        return "\n".join(lines)
        
    def format_coverage_report(self, coverage: Dict[str, Any]) -> str:
        """格式化覆盖率报告.
        
        Args:
            coverage: 覆盖率数据
            
        Returns:
            str: 报告内容
        """
        total = coverage.get('total', 0)
        
        lines = [
            "## 📊 Coverage Report",
            "",
            f"**Total Coverage**: {total:.1f}%",
            "",
        ]
        
        if total >= 80:
            lines.append("✅ Coverage looks good!")
        elif total >= 60:
            lines.append("⚠️ Coverage could be improved.")
        else:
            lines.append("❌ Coverage is too low. Please add more tests.")
            
        return "\n".join(lines)
        
    def post_comment(self, pr_number: int, body: str) -> bool:
        """发布评论.
        
        Args:
            pr_number: PR 编号
            body: 评论内容
            
        Returns:
            bool: 是否成功
        """
        try:
            import requests
            
            url = f"https://api.github.com/repos/{self.repository}/issues/{pr_number}/comments"
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
            }
            data = {"body": body}
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 201:
                self.logger.info(f"Posted comment to PR #{pr_number}")
                return True
            else:
                self.logger.error(f"Failed to post comment: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.exception(f"Failed to post comment: {e}")
            return False


class GitHubStatusReporter:
    """GitHub 状态报告器.
    
    设置提交状态检查。
    """
    
    def __init__(self, token: str, repository: str):
        """初始化报告器.
        
        Args:
            token: GitHub Token
            repository: 仓库名 (owner/repo)
        """
        self.token = token
        self.repository = repository
        self.logger = logging.getLogger(__name__)
        
    def _format_context(self, check_name: str, suffix: str = "") -> str:
        """格式化状态上下文.
        
        Args:
            check_name: 检查名称
            suffix: 后缀
            
        Returns:
            str: 上下文
        """
        if suffix:
            return f"ci/{check_name}/{suffix}"
        return f"ci/{check_name}"
        
    def set_status(
        self,
        sha: str,
        state: str,
        context: str,
        description: str,
        target_url: Optional[str] = None,
    ) -> bool:
        """设置状态.
        
        Args:
            sha: 提交 SHA
            state: 状态 (success, failure, error, pending)
            context: 上下文
            description: 描述
            target_url: 目标 URL
            
        Returns:
            bool: 是否成功
        """
        try:
            import requests
            
            url = f"https://api.github.com/repos/{self.repository}/statuses/{sha}"
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
            }
            data = {
                "state": state,
                "context": context,
                "description": description,
            }
            if target_url:
                data["target_url"] = target_url
                
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 201:
                self.logger.info(f"Set status {state} for {context}")
                return True
            else:
                self.logger.error(f"Failed to set status: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.exception(f"Failed to set status: {e}")
            return False
