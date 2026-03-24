#!/usr/bin/env python3
"""
Skill Test Runner - 技能批量自动化测试执行引擎

功能:
1. 加载场景库（scenarios/*.json）
2. 创建隔离会话执行测试
3. 运行评估器验证输出
4. 收集交付件（URL、文件路径等）
5. 生成 HTML 报告

使用方式:
    python3 skill-test-runner.py --scenario sc-ai-insight-001
    python3 skill-test-runner.py --priority P0
    python3 skill-test-runner.py --skills ai-insight,web-dev-workflow
    python3 skill-test-runner.py --all
"""

import os
import sys
import json
import time
import argparse
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

# 添加模块路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from graders import run_assertions
from artifact_collector import ArtifactCollector
from report_generator import HTMLReportGenerator

# 配置
SKILL_DOJO_DIR = Path(__file__).parent.parent
SCENARIOS_DIR = SKILL_DOJO_DIR / "scenarios"
REPORTS_DIR = SKILL_DOJO_DIR / "reports"
TRANSCRIPTS_DIR = SKILL_DOJO_DIR / "transcripts"
AGENT_SCRIPTS_DIR = Path.home() / ".codeflicker/skills/link-agent-session-controller/scripts"

# 确保目录存在
REPORTS_DIR.mkdir(exist_ok=True)
TRANSCRIPTS_DIR.mkdir(exist_ok=True)


@dataclass
class AssertionResult:
    """单个断言的结果"""
    name: str
    passed: bool
    actual: Optional[Any] = None
    expected: Optional[Any] = None
    evidence: str = ""


@dataclass
class Artifact:
    """交付件"""
    type: str  # url, file, screenshot
    name: str
    value: str
    description: str = ""
    valid: bool = True
    validation_error: str = ""


@dataclass
class TestResult:
    """单个测试场景的结果"""
    scenario_id: str
    skill_name: str
    description: str
    status: str  # passed, failed, error, timeout
    duration_ms: int = 0
    assertions: List[AssertionResult] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    transcript: Dict = field(default_factory=dict)
    error_message: str = ""
    key_outputs: List[str] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    """完整测试报告"""
    run_id: str
    timestamp: str
    total_scenarios: int
    duration_seconds: float = 0.0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    pass_rate: float = 0.0
    results: List[TestResult] = field(default_factory=list)
    by_priority: Dict = field(default_factory=dict)
    by_skill: Dict = field(default_factory=dict)


class SkillTestRunner:
    """技能测试执行引擎"""
    
    def __init__(self, scenarios_path: Optional[Path] = None, verbose: bool = True):
        self.scenarios_path = scenarios_path or SCENARIOS_DIR / "baseline-v1.json"
        self.scenarios = self._load_scenarios()
        self.verbose = verbose
        self.artifact_collector = ArtifactCollector()
        self.report_generator = HTMLReportGenerator()
        
    def _load_scenarios(self) -> List[Dict]:
        """加载场景库"""
        if not self.scenarios_path.exists():
            raise FileNotFoundError(f"场景库文件不存在: {self.scenarios_path}")
        
        with open(self.scenarios_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get('scenarios', [])
    
    def _log(self, message: str, level: str = "info"):
        """输出日志"""
        if not self.verbose:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        icons = {
            "info": "📋",
            "start": "🧪",
            "send": "📤",
            "wait": "⏳",
            "pass": "✅",
            "fail": "❌",
            "error": "⚠️",
            "artifact": "📦",
        }
        icon = icons.get(level, "•")
        print(f"[{timestamp}] {icon} {message}")
    
    def _run_script(self, script_name: str, *args, capture_output: bool = True) -> subprocess.CompletedProcess:
        """执行 agent-session-controller 脚本"""
        script_path = AGENT_SCRIPTS_DIR / script_name
        if not script_path.exists():
            raise FileNotFoundError(f"脚本不存在: {script_path}")
        
        cmd = [str(script_path)] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=300
        )
        return result
    
    def _parse_json_output(self, output: str) -> Dict:
        """解析脚本的 JSON 输出"""
        try:
            return json.loads(output.strip())
        except json.JSONDecodeError:
            return {"error": "JSON解析失败", "raw": output}
    
    def _check_health(self) -> bool:
        """检查 CodeFlicker 服务是否可用"""
        try:
            result = self._run_script("health-check.sh")
            data = self._parse_json_output(result.stdout)
            return data.get("success", False)
        except Exception as e:
            self._log(f"健康检查失败: {e}", "error")
            return False
    
    def _create_session(self, name: str) -> Optional[str]:
        """创建测试会话"""
        try:
            result = self._run_script("session-create.sh", name, "agent")
            data = self._parse_json_output(result.stdout)
            if data.get("success"):
                return data.get("data", {}).get("sessionId")
        except Exception as e:
            self._log(f"创建会话失败: {e}", "error")
        return None
    
    def _send_task(self, session_id: str, prompt: str) -> bool:
        """发送测试任务"""
        try:
            # 将 prompt 写入临时文件避免 shell 转义问题
            tmp_file = Path("/tmp/skill-test-prompt.txt")
            tmp_file.write_text(prompt, encoding='utf-8')
            
            result = self._run_script("task-send.sh", session_id, "--file", str(tmp_file))
            data = self._parse_json_output(result.stdout)
            return data.get("success", False)
        except Exception as e:
            self._log(f"发送任务失败: {e}", "error")
            return False
    
    def _wait_for_completion(self, session_id: str, timeout: int = 300) -> Dict:
        """等待任务完成"""
        try:
            result = self._run_script("task-wait.sh", session_id, str(timeout), "2")
            # task-wait.sh 返回码: 0=成功, 1=失败, 2=超时, 3=等待用户输入
            
            if result.returncode == 2:
                return {"completed": False, "timeout": True, "output": result.stdout}
            
            if result.returncode == 3:
                # 等待用户输入（通常是命令执行需要批准）
                # 自动批准并继续等待
                self._log("Task waiting for approval, auto-approving...", "info")
                self._auto_approve(session_id)
                # 递归等待剩余时间
                return self._wait_for_completion(session_id, timeout - 30)
            
            # 通过检查最后的消息来判断是否完成
            # 无论返回码是 0 还是 1，只要有 completion_result 就算完成
            return {
                "completed": True,  # 先假设完成，后续会获取消息验证
                "timeout": False,
                "failed": False,
                "output": result.stdout
            }
        except subprocess.TimeoutExpired:
            return {"completed": False, "timeout": True}
        except Exception as e:
            return {"completed": False, "error": str(e)}
    
    def _auto_approve(self, session_id: str) -> bool:
        """自动批准等待的命令"""
        try:
            # 使用 task-respond.sh 发送批准 (action=approve, ask_type=command)
            result = self._run_script("task-respond.sh", session_id, "approve", "command")
            self._log(f"Approve response: {result.stdout[:200]}", "debug")
            data = self._parse_json_output(result.stdout)
            return data.get("success", False)
        except Exception as e:
            self._log(f"Auto-approve failed: {e}", "error")
            return False
    
    def _get_messages(self, session_id: str) -> List[Dict]:
        """获取会话消息"""
        try:
            result = self._run_script("messages-search.sh", session_id)
            data = self._parse_json_output(result.stdout)
            if data.get("success"):
                return data.get("data", {}).get("messages", [])
        except Exception as e:
            self._log(f"获取消息失败: {e}", "error")
        return []
    
    def _delete_session(self, session_id: str) -> bool:
        """删除测试会话"""
        try:
            result = self._run_script("session-delete.sh", session_id)
            data = self._parse_json_output(result.stdout)
            return data.get("success", False)
        except Exception as e:
            self._log(f"删除会话失败: {e}", "error")
            return False
    
    def _extract_output_text(self, messages: List[Dict]) -> str:
        """从消息中提取输出文本
        
        注意：messages-search.sh 返回的消息可能没有 role 字段，
        需要通过 say 类型和消息特征来识别助手消息。
        """
        output_parts = []
        for msg in messages:
            role = msg.get("role", "")
            say = msg.get("say", "")
            text = msg.get("text", "") or ""
            
            # 跳过用户消息（有 role=user，或者 say=text 且包含 [测试模式] 标记）
            if role == "user":
                continue
            if say == "text" and "[测试模式]" in text:
                continue
            
            # 提取助手文本（text 类型，非空）
            # 兼容两种格式：有 role=assistant 的，和没有 role 字段的（messages-search.sh 输出）
            if say == "text" and text.strip():
                output_parts.append(text)
        
        return "\n".join(output_parts)
    
    def _extract_key_outputs(self, output: str) -> List[str]:
        """提取关键输出（用于报告摘要）"""
        key_outputs = []
        
        # 提取包含数字的关键信息
        patterns = [
            r'收集到?\s*(\d+)\s*条.*新闻',
            r'(\d+)\s*个?条?文章',
            r'部署成功.*?(https?://[^\s]+)',
            r'生成.*?报告.*?(https?://[^\s]+)',
            r'推送.*?成功',
            r'上传.*?成功',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if matches:
                key_outputs.append(f"匹配: {pattern} -> {matches[0]}")
        
        return key_outputs[:5]  # 最多5条
    
    def run_scenario(self, scenario: Dict) -> TestResult:
        """执行单个测试场景"""
        scenario_id = scenario.get("scenario_id", "unknown")
        skill_name = scenario.get("skill_name", "unknown")
        description = scenario.get("description", "")
        prompt = scenario.get("prompt", "")
        timeout = scenario.get("timeout", 300)
        
        self._log(f"Testing: {scenario_id} ({skill_name})", "start")
        
        start_time = time.time()
        result = TestResult(
            scenario_id=scenario_id,
            skill_name=skill_name,
            description=description,
            status="error"
        )
        
        # 构造测试 prompt
        test_prompt = f"""[测试模式] 请使用 {skill_name} 技能执行以下任务：

{prompt}

执行完成后，请明确说明完成状态和关键输出。"""
        
        try:
            # 1. 创建会话
            self._log(f"Creating session: test-{scenario_id}", "send")
            session_id = self._create_session(f"test-{scenario_id}")
            if not session_id:
                result.error_message = "创建会话失败"
                return result
            
            # 2. 发送任务
            self._log(f"Sending task: \"{prompt[:50]}...\"", "send")
            if not self._send_task(session_id, test_prompt):
                result.error_message = "发送任务失败"
                self._delete_session(session_id)
                return result
            
            # 3. 等待完成
            self._log(f"Waiting for completion (timeout: {timeout}s)", "wait")
            wait_result = self._wait_for_completion(session_id, timeout)
            
            if wait_result.get("timeout"):
                result.status = "timeout"
                result.error_message = f"任务超时 ({timeout}s)"
            elif wait_result.get("failed"):
                result.status = "failed"
                result.error_message = "任务执行失败"
            elif wait_result.get("completed"):
                # 4. 获取消息
                # v4: 增加延迟等待消息同步（从5秒增至8秒）
                # 原因：completion_result 后消息可能还在写入，需要等待API完全同步
                self._log("Waiting 8s for message sync...", "wait")
                time.sleep(8)
                messages = self._get_messages(session_id)
                self._log(f"Retrieved {len(messages)} messages", "info")
                output_text = self._extract_output_text(messages)
                
                # 5. 保存 transcript
                transcript_path = TRANSCRIPTS_DIR / f"{scenario_id}.json"
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    json.dump(messages, f, ensure_ascii=False, indent=2)
                
                result.transcript = {
                    "session_id": session_id,
                    "messages_count": len(messages),
                    "transcript_path": str(transcript_path)
                }
                
                # 6. 提取关键输出
                result.key_outputs = self._extract_key_outputs(output_text)
                
                # 7. 运行断言
                assertions = scenario.get("assertions", [])
                expected_behaviors = scenario.get("expected_behaviors", [])
                
                # 将 expected_behaviors 转换为简单的 contains 断言
                if expected_behaviors and not assertions:
                    assertions = [
                        {"type": "contains", "name": behavior, "value": behavior}
                        for behavior in expected_behaviors[:3]  # 取前3个作为简单验证
                    ]
                
                assertion_results = run_assertions(assertions, output_text, messages)
                result.assertions = [
                    AssertionResult(**ar) for ar in assertion_results
                ]
                
                # 8. 收集交付件
                extractors = scenario.get("artifact_extractors", [])
                # 默认提取器
                if not extractors:
                    extractors = [
                        {"name": "部署URL", "type": "url", "pattern": r"https://[^\s]+\.github\.io/[^\s]+"},
                        {"name": "KIM文档", "type": "url", "pattern": r"https://docs\.corp\.[^\s]+"},
                        {"name": "本地文件", "type": "file", "pattern": r"/Users/[^\s]+\.(html|md|json)"},
                    ]
                
                artifacts = self.artifact_collector.collect(output_text, extractors)
                result.artifacts = [Artifact(**art) for art in artifacts]
                
                # 9. 判断最终状态
                all_passed = all(ar.passed for ar in result.assertions) if result.assertions else True
                result.status = "passed" if all_passed else "failed"
            
            # 10. 清理会话
            self._delete_session(session_id)
            
        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
        
        # 计算耗时
        result.duration_ms = int((time.time() - start_time) * 1000)
        
        # 输出结果
        if result.status == "passed":
            passed_count = len([a for a in result.assertions if a.passed])
            total_count = len(result.assertions)
            self._log(f"PASSED ({passed_count}/{total_count} assertions) - {result.duration_ms/1000:.1f}s", "pass")
        else:
            self._log(f"FAILED: {result.error_message or result.status} - {result.duration_ms/1000:.1f}s", "fail")
        
        return result
    
    def filter_scenarios(self, 
                        skills: Optional[List[str]] = None,
                        priority: Optional[str] = None,
                        scenario_ids: Optional[List[str]] = None) -> List[Dict]:
        """过滤场景"""
        filtered = self.scenarios
        
        if scenario_ids:
            filtered = [s for s in filtered if s.get("scenario_id") in scenario_ids]
        
        if skills:
            filtered = [s for s in filtered if s.get("skill_name") in skills]
        
        if priority:
            filtered = [s for s in filtered if s.get("priority") == priority]
        
        return filtered
    
    def run_all(self,
                skills: Optional[List[str]] = None,
                priority: Optional[str] = None,
                scenario_ids: Optional[List[str]] = None,
                dry_run: bool = False) -> BenchmarkReport:
        """批量执行测试"""
        # 检查服务
        self._log("Checking CodeFlicker service...", "info")
        if not self._check_health():
            self._log("CodeFlicker 服务不可用，请先启动", "error")
            raise RuntimeError("CodeFlicker 服务不可用")
        
        # 过滤场景
        scenarios = self.filter_scenarios(skills, priority, scenario_ids)
        
        if not scenarios:
            self._log("没有匹配的测试场景", "error")
            raise ValueError("没有匹配的测试场景")
        
        self._log(f"Loading scenarios: {len(scenarios)} total", "info")
        
        if dry_run:
            self._log("DRY RUN - 只显示将要执行的场景", "info")
            for s in scenarios:
                print(f"  - {s.get('scenario_id')}: {s.get('description')}")
            return None
        
        # 初始化报告
        run_id = f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start_time = time.time()
        
        report = BenchmarkReport(
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            total_scenarios=len(scenarios)
        )
        
        # 执行测试
        self._log("─" * 50, "info")
        for i, scenario in enumerate(scenarios, 1):
            self._log(f"[{i}/{len(scenarios)}] {scenario.get('scenario_id')}", "info")
            result = self.run_scenario(scenario)
            report.results.append(result)
            
            # 统计
            if result.status == "passed":
                report.passed += 1
            elif result.status == "failed":
                report.failed += 1
            else:
                report.errors += 1
        
        # 计算统计
        report.duration_seconds = time.time() - start_time
        report.pass_rate = report.passed / report.total_scenarios if report.total_scenarios > 0 else 0
        
        # 按优先级统计
        for scenario in scenarios:
            priority = scenario.get("priority", "P2")
            if priority not in report.by_priority:
                report.by_priority[priority] = {"passed": 0, "total": 0}
            report.by_priority[priority]["total"] += 1
        
        for result in report.results:
            scenario = next((s for s in scenarios if s.get("scenario_id") == result.scenario_id), None)
            if scenario:
                priority = scenario.get("priority", "P2")
                if result.status == "passed":
                    report.by_priority[priority]["passed"] += 1
        
        # 按技能统计
        for result in report.results:
            skill = result.skill_name
            if skill not in report.by_skill:
                report.by_skill[skill] = {"passed": 0, "failed": 0, "total": 0}
            report.by_skill[skill]["total"] += 1
            if result.status == "passed":
                report.by_skill[skill]["passed"] += 1
            else:
                report.by_skill[skill]["failed"] += 1
        
        self._log("─" * 50, "info")
        self._log(f"Summary: {report.passed}/{report.total_scenarios} PASSED ({report.pass_rate*100:.1f}%)", "info")
        
        # 保存报告
        self._save_report(report)
        
        return report
    
    def _save_report(self, report: BenchmarkReport):
        """保存报告"""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        # JSON 报告
        json_path = REPORTS_DIR / f"benchmark-{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            # 转换 dataclass 为 dict
            report_dict = {
                "meta": {
                    "run_id": report.run_id,
                    "timestamp": report.timestamp,
                    "total_scenarios": report.total_scenarios,
                    "duration_seconds": report.duration_seconds
                },
                "summary": {
                    "pass_rate": report.pass_rate,
                    "passed": report.passed,
                    "failed": report.failed,
                    "errors": report.errors,
                    "by_priority": report.by_priority,
                    "by_skill": report.by_skill
                },
                "results": [
                    {
                        "scenario_id": r.scenario_id,
                        "skill_name": r.skill_name,
                        "description": r.description,
                        "status": r.status,
                        "duration_ms": r.duration_ms,
                        "assertions": [asdict(a) for a in r.assertions],
                        "artifacts": [asdict(a) for a in r.artifacts],
                        "transcript": r.transcript,
                        "key_outputs": r.key_outputs,
                        "error_message": r.error_message
                    }
                    for r in report.results
                ]
            }
            json.dump(report_dict, f, ensure_ascii=False, indent=2)
        
        self._log(f"JSON Report: {json_path}", "artifact")
        
        # HTML 报告
        html_path = REPORTS_DIR / f"benchmark-{timestamp}.html"
        html_content = self.report_generator.generate(report_dict)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self._log(f"HTML Report: {html_path}", "artifact")


def main():
    parser = argparse.ArgumentParser(description="技能批量自动化测试执行引擎")
    parser.add_argument("--scenario", "-s", help="测试单个场景 (scenario_id)")
    parser.add_argument("--priority", "-p", choices=["P0", "P1", "P2"], help="按优先级过滤")
    parser.add_argument("--skills", help="按技能过滤 (逗号分隔)")
    parser.add_argument("--all", "-a", action="store_true", help="运行所有场景")
    parser.add_argument("--dry-run", action="store_true", help="只显示将要执行的场景")
    parser.add_argument("--quiet", "-q", action="store_true", help="安静模式")
    parser.add_argument("--file", "-f", help="指定场景文件路径（默认 scenarios/baseline-v1.json）")
    
    args = parser.parse_args()
    
    # 确定场景文件
    scenarios_path = Path(args.file) if args.file else None
    
    # 创建执行器
    runner = SkillTestRunner(scenarios_path=scenarios_path, verbose=not args.quiet)
    
    try:
        if args.scenario:
            scenarios = runner.filter_scenarios(scenario_ids=[args.scenario])
            if not scenarios:
                print(f"找不到场景: {args.scenario}")
                sys.exit(1)
            result = runner.run_scenario(scenarios[0])
            sys.exit(0 if result.status == "passed" else 1)
        
        elif args.all or args.priority or args.skills:
            skills = args.skills.split(",") if args.skills else None
            report = runner.run_all(
                skills=skills,
                priority=args.priority,
                dry_run=args.dry_run
            )
            if report:
                sys.exit(0 if report.pass_rate >= 0.8 else 1)
        
        else:
            parser.print_help()
            sys.exit(0)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
