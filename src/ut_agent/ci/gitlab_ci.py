"""GitLab CI 集成.

提供 GitLab CI 配置生成、MR 评论和流水线触发功能。
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GitLabCIJob:
    """GitLab CI 任务.
    
    Attributes:
        name: 任务名称
        stage: 阶段
        script: 脚本命令
        image: Docker 镜像
        variables: 变量
        artifacts: 制品
        coverage: 覆盖率正则
    """
    name: str
    script: List[str]
    stage: str = "test"
    image: str = "python:3.12"
    variables: Dict[str, str] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    coverage: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        data = {
            "script": self.script,
            "stage": self.stage,
            "image": self.image,
        }
        if self.variables:
            data["variables"] = self.variables
        if self.artifacts:
            data["artifacts"] = self.artifacts
        if self.coverage:
            data["coverage"] = self.coverage
        return data


@dataclass
class GitLabCIStage:
    """GitLab CI 阶段.
    
    Attributes:
        name: 阶段名称
        jobs: 任务列表
    """
    name: str
    jobs: List[GitLabCIJob] = field(default_factory=list)
    
    def add_job(self, job: GitLabCIJob) -> None:
        """添加任务."""
        self.jobs.append(job)


class GitLabCIConfig:
    """GitLab CI 配置.
    
    表示一个完整的 GitLab CI 配置。
    """
    
    def __init__(self):
        """初始化配置."""
        self.stages: List[str] = []
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.variables: Dict[str, str] = {}
        
    def add_stage(self, stage: GitLabCIStage) -> None:
        """添加阶段."""
        if stage.name not in self.stages:
            self.stages.append(stage.name)
            
    def add_job(self, job: GitLabCIJob) -> None:
        """添加任务."""
        self.jobs[job.name] = job.to_dict()
        
    def to_yaml(self) -> str:
        """生成 YAML 内容."""
        lines = []
        
        # stages
        if self.stages:
            lines.append("stages:")
            for stage in self.stages:
                lines.append(f"  - {stage}")
            lines.append("")
        
        # variables
        if self.variables:
            lines.append("variables:")
            for key, value in self.variables.items():
                lines.append(f"  {key}: {value}")
            lines.append("")
        
        # jobs
        for job_name, job_data in self.jobs.items():
            lines.append(f"{job_name}:")
            
            if "stage" in job_data:
                lines.append(f"  stage: {job_data['stage']}")
            if "image" in job_data:
                lines.append(f"  image: {job_data['image']}")
            if "variables" in job_data:
                lines.append("  variables:")
                for key, value in job_data["variables"].items():
                    lines.append(f"    {key}: {value}")
            
            lines.append("  script:")
            for script in job_data.get("script", []):
                lines.append(f"    - {script}")
            
            if "artifacts" in job_data:
                lines.append("  artifacts:")
                for key, value in job_data["artifacts"].items():
                    if isinstance(value, list):
                        lines.append(f"    {key}:")
                        for item in value:
                            lines.append(f"      - {item}")
                    else:
                        lines.append(f"    {key}: {value}")
            
            if "coverage" in job_data:
                lines.append(f"  coverage: '{job_data['coverage']}'")
            
            lines.append("")
        
        return "\n".join(lines)


class GitLabCIGenerator:
    """GitLab CI 配置生成器."""
    
    def __init__(self):
        """初始化生成器."""
        self.logger = logging.getLogger(__name__)
        
    def generate_python_test_config(
        self,
        python_versions: Optional[List[str]] = None,
    ) -> GitLabCIConfig:
        """生成 Python 测试配置."""
        python_versions = python_versions or ["3.10", "3.11", "3.12"]
        
        config = GitLabCIConfig()
        config.stages = ["test", "coverage"]
        
        # Test job
        test_job = GitLabCIJob(
            name="pytest",
            stage="test",
            script=[
                "pip install -r requirements.txt -r requirements-dev.txt",
                "pytest tests/ -v --junitxml=report.xml",
            ],
            artifacts={
                "reports": {
                    "junit": "report.xml",
                },
            },
        )
        config.add_job(test_job)
        
        # Coverage job
        coverage_job = GitLabCIJob(
            name="coverage",
            stage="coverage",
            script=[
                "pip install pytest-cov",
                "pytest --cov=src --cov-report=xml",
            ],
            coverage="/TOTAL.+ ([0-9]{1,3}%)/",
        )
        config.add_job(coverage_job)
        
        return config
        
    def generate_coverage_config(self, min_coverage: int = 80) -> GitLabCIConfig:
        """生成覆盖率配置."""
        config = GitLabCIConfig()
        config.stages = ["coverage"]
        
        job = GitLabCIJob(
            name="coverage",
            stage="coverage",
            script=[
                f"pip install pytest-cov",
                f"pytest --cov=src --cov-fail-under={min_coverage}",
            ],
        )
        config.add_job(job)
        
        return config
        
    def save_config(self, config: GitLabCIConfig, output_path: str) -> bool:
        """保存配置到文件."""
        try:
            path = Path(output_path)
            path.write_text(config.to_yaml())
            self.logger.info(f"Saved GitLab CI config to {path}")
            return True
        except Exception as e:
            self.logger.exception(f"Failed to save config: {e}")
            return False


class GitLabMRReporter:
    """GitLab MR 报告器."""
    
    def __init__(self, token: str, project_id: str):
        """初始化报告器."""
        self.token = token
        self.project_id = project_id
        self.logger = logging.getLogger(__name__)
        
    def format_test_report(self, results: Dict[str, Any]) -> str:
        """格式化测试报告."""
        lines = [
            "## 🧪 Test Results",
            "",
            f"- **Passed**: {results.get('passed', 0)}",
            f"- **Failed**: {results.get('failed', 0)}",
            f"- **Total**: {results.get('total', 0)}",
            "",
        ]
        return "\n".join(lines)
        
    def post_mr_comment(self, mr_iid: int, body: str) -> bool:
        """发布 MR 评论."""
        try:
            import requests
            
            url = f"https://gitlab.com/api/v4/projects/{self.project_id}/merge_requests/{mr_iid}/notes"
            headers = {"PRIVATE-TOKEN": self.token}
            data = {"body": body}
            
            response = requests.post(url, headers=headers, data=data)
            
            return response.status_code == 201
        except Exception as e:
            self.logger.exception(f"Failed to post MR comment: {e}")
            return False


class GitLabPipelineTrigger:
    """GitLab 流水线触发器."""
    
    def __init__(self, token: str, project_id: str):
        """初始化触发器."""
        self.token = token
        self.project_id = project_id
        self.logger = logging.getLogger(__name__)
        
    def trigger_pipeline(self, ref: str = "main") -> Optional[Dict[str, Any]]:
        """触发流水线."""
        try:
            import requests
            
            url = f"https://gitlab.com/api/v4/projects/{self.project_id}/trigger/pipeline"
            data = {
                "token": self.token,
                "ref": ref,
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 201:
                return response.json()
            return None
        except Exception as e:
            self.logger.exception(f"Failed to trigger pipeline: {e}")
            return None
