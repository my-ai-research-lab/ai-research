"""
Report Generator - HTML 报告生成器 v5.0

重构版：使用统一模板系统生成报告。

模板文件位于 templates/ 目录：
- report-styles.css: 统一CSS样式
- benchmark-report.html: 评测报告模板
- improvement-report.html: 改进报告模板
"""

import os
import json
import html as _html_mod
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

# 模板目录路径
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _esc(s: str) -> str:
    """HTML 转义"""
    return _html_mod.escape(str(s), quote=False)


def _load_template(name: str) -> str:
    """加载模板文件"""
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"模板文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def _load_css() -> str:
    """加载统一CSS样式"""
    return _load_template("report-styles.css")


class HTMLReportGenerator:
    """评测报告生成器 (方式B: 自动化评测结果)"""
    
    VERSION = "1.9.0"
    
    def __init__(self):
        self.css = _load_css()
        try:
            self.template = _load_template("benchmark-report.html")
        except FileNotFoundError:
            # 回退到内联模板
            self.template = None
    
    def generate(self, report_data: Dict) -> str:
        """生成评测报告HTML"""
        meta = report_data.get("meta", {})
        summary = report_data.get("summary", {})
        results = report_data.get("results", [])
        
        # 如果有模板文件，使用模板
        if self.template:
            return self._generate_from_template(meta, summary, results)
        
        # 否则使用内联生成（向后兼容）
        return self._generate_inline(meta, summary, results)
    
    def _generate_from_template(self, meta: Dict, summary: Dict, results: List[Dict]) -> str:
        """使用模板生成报告"""
        ts = meta.get("timestamp", "")
        try:
            ts_formatted = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            ts_formatted = ts
        
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        errors = summary.get("errors", 0)
        total = passed + failed + errors
        rate = summary.get("pass_rate", 0) * 100
        
        # 替换模板变量
        html = self.template.replace("{{CSS}}", self.css)
        html = html.replace("{{TITLE}}", f"技能评测报告 · {ts_formatted}")
        html = html.replace("{{TIMESTAMP}}", ts_formatted)
        html = html.replace("{{MODE}}", meta.get("mode", "方式B (深度评测)"))
        html = html.replace("{{PASS_RATE}}", f"{rate:.0f}%")
        html = html.replace("{{PASSED}}", str(passed))
        html = html.replace("{{FAILED}}", str(failed))
        html = html.replace("{{ERRORS}}", str(errors))
        html = html.replace("{{TOTAL}}", str(total))
        html = html.replace("{{VERSION}}", self.VERSION)
        html = html.replace("{{GENERATED_AT}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # 生成技能芯片
        skill_chips = self._generate_skill_chips(results)
        html = html.replace("{{SKILL_CHIPS}}", skill_chips)
        
        # 生成表格行
        table_rows = "".join(self._generate_table_row(r, i) for i, r in enumerate(results))
        html = html.replace("{{TABLE_ROWS}}", table_rows)
        
        return html
    
    def _generate_skill_chips(self, results: List[Dict]) -> str:
        """生成技能芯片HTML"""
        chips = ""
        for i, r in enumerate(results):
            status = r.get("status", "error")
            skill = r.get("skill_name", "?")
            dur_ms = r.get("duration_ms", 0)
            
            chip_class = {
                "passed": "chip-pass",
                "failed": "chip-fail"
            }.get(status, "chip-warn")
            
            chips += f'''<div class="skill-chip {chip_class}" onclick="jumpToRow('{i}')">
              <span class="dot"></span>
              {_esc(skill)}
              <span class="duration">{dur_ms/1000:.0f}s</span>
            </div>'''
        
        return chips
    
    def _generate_table_row(self, r: Dict, idx: int) -> str:
        """生成单行表格HTML"""
        status = r.get("status", "error")
        skill = r.get("skill_name", "")
        sid = r.get("scenario_id", "")
        desc = r.get("description", "")
        assertions = r.get("assertions", [])
        artifacts = r.get("artifacts", [])
        dur_ms = r.get("duration_ms", 0)
        transcript = r.get("transcript", {})
        
        # 状态徽章
        badge_class = {
            "passed": "badge-pass",
            "failed": "badge-fail"
        }.get(status, "badge-warn")
        badge_symbol = {
            "passed": "✓",
            "failed": "✗",
            "error": "!",
            "timeout": "⏱"
        }.get(status, "?")
        badge_html = f'<span class="badge badge-circle {badge_class}">{badge_symbol}</span>'
        
        # 评测项
        assertions_html = self._render_assertions(assertions, idx)
        
        # 交付物
        artifacts_html = self._render_artifacts(artifacts, transcript)
        
        return f'''
        <tr class="row-anchor" id="row-{idx}">
          <td style="text-align:center;color:var(--text-muted)">{idx + 1}</td>
          <td style="text-align:center">{badge_html}</td>
          <td>
            <div class="skill-name">{_esc(skill)}</div>
            <div class="skill-id">{_esc(sid)}</div>
          </td>
          <td><div class="skill-desc">{_esc(desc)}</div></td>
          <td>{assertions_html}</td>
          <td>{artifacts_html}</td>
          <td style="text-align:right;color:var(--text-muted)">{dur_ms/1000:.1f}s</td>
        </tr>'''
    
    def _render_assertions(self, assertions: List[Dict], idx: int) -> str:
        """渲染评测项列表（带折叠）"""
        if not assertions:
            return '<span class="empty">—</span>'
        
        passed = sum(1 for a in assertions if a.get("passed"))
        total = len(assertions)
        all_ok = passed == total
        
        # 摘要行
        pill_pass = f'<span class="pill pill-pass">✓ {passed}</span>'
        pill_fail = f'<span class="pill pill-fail">✗ {total - passed}</span>' if passed < total else ""
        toggle_btn = f'<span class="pill-toggle" onclick="toggleAssertions({idx})">▼ 展开</span>'
        
        summary_html = f'''<div class="assertion-summary" onclick="toggleAssertions({idx})">
          <div class="assertion-pills">{pill_pass}{pill_fail}</div>
          <span style="font-size:0.72rem">{total} 项</span>
          {toggle_btn}
        </div>'''
        
        # 详情行
        detail_class = "assertion-detail" + ("" if all_ok else " open")
        detail_rows = ""
        for a in assertions:
            ok = a.get("passed", False)
            icon_class = "c-green" if ok else "c-red"
            symbol = "✓" if ok else "✗"
            evidence = f'<div class="assertion-evidence">{_esc(a.get("evidence", ""))}</div>' if a.get("evidence") else ""
            detail_rows += f'''<li class="assertion-item">
              <span class="assertion-icon {icon_class}">{symbol}</span>
              <div>
                <span class="assertion-text">{_esc(a.get("name", ""))}</span>
                {evidence}
              </div>
            </li>'''
        
        display_style = 'style="display:block"' if not all_ok else ''
        return f'''<div>
          {summary_html}
          <ul class="assertion-list assertion-detail" id="assertions-{idx}" {display_style}>
            {detail_rows}
          </ul>
        </div>'''
    
    def _render_artifacts(self, artifacts: List[Dict], transcript: Dict) -> str:
        """渲染交付物列表"""
        items = []
        
        # 真实交付物（排除对话相关）
        real = [a for a in artifacts if "对话" not in a.get("name", "")]
        for a in real:
            items.append(self._artifact_card(a))
        
        # 对话记录
        if transcript:
            t_path = transcript.get("transcript_path", "")
            t_count = transcript.get("messages_count", 0)
            if t_path:
                html_path = str(Path(t_path).with_suffix(".html"))
                # 使用相对路径（相对于 reports/ 目录）
                filename = Path(t_path).stem
                if os.path.exists(html_path):
                    url = f"../transcripts/{filename}.html"
                    tag = "对话复盘 · HTML"
                else:
                    url = f"../transcripts/{filename}.json"
                    tag = "对话记录 · JSON"
                items.append(f'''<a class="artifact-card" href="{url}" target="_blank">
                  <span class="artifact-icon">💬</span>
                  <div class="artifact-body">
                    <div class="artifact-name">{tag}</div>
                    <div class="artifact-desc">{t_count} 条消息</div>
                  </div>
                  <span class="artifact-arrow">↗</span>
                </a>''')
        
        if not items:
            return '<span class="empty">文本输出</span>'
        
        return f'<div class="artifact-list">{"".join(items)}</div>'
    
    def _artifact_card(self, a: Dict) -> str:
        """生成单个交付物卡片"""
        a_type = a.get("type", "file")
        a_name = a.get("name", "")
        a_value = a.get("value", "")
        a_valid = a.get("valid", True)
        a_desc = a.get("description", "")
        
        # URL处理
        filename = a_value.rsplit("/", 1)[-1] if "/" in a_value else a_value
        if a_type == "url":
            url = a_value
        elif a_value.startswith("http"):
            url = a_value
        else:
            # 使用相对路径（相对于 reports/ 目录）
            # 假设文件在 transcripts/ 目录下
            url = f"../transcripts/{filename}"
        
        # 无效文件
        if not a_valid:
            return f'''<div class="artifact-card invalid">
              <span class="artifact-icon">⚠️</span>
              <div class="artifact-body">
                <div class="artifact-name">{_esc(a_name)}</div>
                <div class="artifact-desc">文件不存在</div>
              </div>
            </div>'''
        
        # 图片类
        if a_value.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")):
            return f'''<a class="artifact-card" href="{url}" target="_blank">
              <img class="artifact-thumb" src="{url}" alt="{_esc(a_name)}" loading="lazy"/>
              <div class="artifact-body">
                <div class="artifact-name">{_esc(a_name)}</div>
                <div class="artifact-desc">{_esc(a_desc or filename)}</div>
              </div>
              <span class="artifact-arrow">↗</span>
            </a>'''
        
        # HTML类
        if a_value.lower().endswith((".html", ".htm")):
            return f'''<a class="artifact-card" href="{url}" target="_blank">
              <span class="artifact-icon">🌐</span>
              <div class="artifact-body">
                <div class="artifact-name">{_esc(a_name)}</div>
                <div class="artifact-desc">{_esc(a_desc or filename)}</div>
              </div>
              <span class="artifact-arrow">↗</span>
            </a>'''
        
        # URL类型
        if a_type == "url":
            return f'''<a class="artifact-card" href="{url}" target="_blank">
              <span class="artifact-icon">🔗</span>
              <div class="artifact-body">
                <div class="artifact-name">{_esc(a_name)}</div>
                <div class="artifact-desc">{_esc(a_desc or url[:50])}</div>
              </div>
              <span class="artifact-arrow">↗</span>
            </a>'''
        
        # 通用文件
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        icon = {
            "json": "📋", "txt": "📄", "md": "📝",
            "pdf": "📕", "csv": "📊", "py": "🐍"
        }.get(ext, "📄")
        
        return f'''<a class="artifact-card" href="{url}" target="_blank">
          <span class="artifact-icon">{icon}</span>
          <div class="artifact-body">
            <div class="artifact-name">{_esc(a_name)}</div>
            <div class="artifact-desc">{_esc(a_desc or filename)}</div>
          </div>
          <span class="artifact-arrow">↗</span>
        </a>'''
    
    def _generate_inline(self, meta: Dict, summary: Dict, results: List[Dict]) -> str:
        """内联生成报告（向后兼容，无模板时使用）"""
        # 保留原有的内联实现作为 fallback
        return self._generate_from_template(meta, summary, results)


class ImprovementReportGenerator:
    """改进报告生成器 (方式A: 轻量评测 + 自动修复)"""
    
    VERSION = "1.9.0"
    
    def __init__(self):
        self.css = _load_css()
        try:
            self.template = _load_template("improvement-report.html")
        except FileNotFoundError:
            self.template = None
    
    def generate(self, report_data: Dict) -> str:
        """生成改进报告HTML"""
        meta = report_data.get("meta", {})
        top_skills = report_data.get("top_skills", [])
        results = report_data.get("results", [])
        fixes = report_data.get("fixes", [])
        pending = report_data.get("pending_actions", [])
        recommendations = report_data.get("recommendations", {})
        
        ts = meta.get("timestamp", datetime.now().isoformat())
        try:
            ts_formatted = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
        except:
            ts_formatted = ts
        
        # 统计
        passed_count = sum(1 for r in results if r.get("status") == "passed")
        failed_count = sum(1 for r in results if r.get("status") == "failed")
        fixed_count = sum(1 for r in results if r.get("status") == "fixed")
        pending_count = sum(1 for r in results if r.get("status") == "pending")
        
        if not self.template:
            return self._generate_fallback(meta, top_skills, results, fixes, pending, recommendations)
        
        html = self.template.replace("{{CSS}}", self.css)
        html = html.replace("{{TITLE}}", f"技能持续精进报告 · {ts_formatted}")
        html = html.replace("{{TIMESTAMP}}", ts_formatted)
        html = html.replace("{{MODE}}", meta.get("mode", "方式A (轻量评测 + 自动修复)"))
        html = html.replace("{{TOP_N}}", str(len(top_skills)))
        html = html.replace("{{PASSED}}", str(passed_count))
        html = html.replace("{{FIXED}}", str(fixed_count))
        html = html.replace("{{FAILED}}", str(failed_count))
        html = html.replace("{{PENDING}}", str(pending_count))
        html = html.replace("{{VERSION}}", self.VERSION)
        html = html.replace("{{GENERATED_AT}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # Top N 技能芯片
        top_chips = self._generate_top_skill_chips(top_skills, results)
        html = html.replace("{{TOP_SKILL_CHIPS}}", top_chips)
        
        # 评测详情表格
        detail_rows = self._generate_detail_rows(results)
        html = html.replace("{{DETAIL_ROWS}}", detail_rows)
        
        # 已执行修复
        fixes_html = self._generate_fixes_html(fixes) if fixes else ""
        html = html.replace("{{#if FIXES_APPLIED}}", "" if fixes else "<!--")
        html = html.replace("{{/if}}", "" if fixes else "-->")
        html = html.replace("{{FIXES_APPLIED}}", fixes_html)
        
        # 待处理项
        pending_html = self._generate_pending_html(pending) if pending else ""
        # 简单处理条件渲染
        if not pending:
            # 移除整个 pending section
            import re
            html = re.sub(r'\{\{#if PENDING_ACTIONS\}\}.*?\{\{/if\}\}', '', html, flags=re.DOTALL)
        else:
            html = html.replace("{{#if PENDING_ACTIONS}}", "")
            html = html.replace("{{/if}}", "")
        html = html.replace("{{PENDING_ACTIONS}}", pending_html)
        
        # 建议
        html = html.replace("{{RECOMMENDATIONS_IMMEDIATE}}", 
                           self._list_items(recommendations.get("immediate", [])))
        html = html.replace("{{RECOMMENDATIONS_WEEKLY}}", 
                           self._list_items(recommendations.get("weekly", [])))
        html = html.replace("{{RECOMMENDATIONS_MONTHLY}}", 
                           self._list_items(recommendations.get("monthly", [])))
        
        return html
    
    def _generate_top_skill_chips(self, top_skills: List[Dict], results: List[Dict]) -> str:
        """生成Top N技能芯片"""
        # 创建结果状态映射
        status_map = {r.get("skill_name"): r.get("status") for r in results}
        
        chips = ""
        for i, skill in enumerate(top_skills):
            name = skill.get("name", "")
            status = status_map.get(name, "pending")
            chip_class = {
                "passed": "chip-pass",
                "failed": "chip-fail",
                "fixed": "chip-fixed",
                "pending": "chip-pending"
            }.get(status, "chip-pending")
            
            chips += f'<span class="skill-chip {chip_class}">#{i+1} {_esc(name)}</span>\n'
        
        return chips
    
    def _generate_detail_rows(self, results: List[Dict]) -> str:
        """生成评测详情表格行"""
        rows = ""
        for r in results:
            skill = r.get("skill_name", "")
            skill_desc = r.get("description", "")
            status = r.get("status", "pending")
            issue_type = r.get("issue_type", "—")
            root_cause = r.get("root_cause", "—")
            fix_suggestion = r.get("fix_suggestion", "—")
            
            badge_class = {
                "passed": "badge-pass",
                "failed": "badge-fail",
                "fixed": "badge-fixed",
                "pending": "badge-pending"
            }.get(status, "badge-pending")
            
            badge_text = {
                "passed": "✅ 通过",
                "failed": "❌ 失败",
                "fixed": "✅ 已修复",
                "pending": "⏳ 待验证"
            }.get(status, "❓")
            
            rows += f'''<tr>
              <td><strong>{_esc(skill)}</strong><br><small class="skill-desc">{_esc(skill_desc)}</small></td>
              <td><span class="badge {badge_class}">{badge_text}</span></td>
              <td>{_esc(issue_type)}</td>
              <td>{_esc(root_cause)}</td>
              <td>{_esc(fix_suggestion)}</td>
            </tr>'''
        
        return rows
    
    def _generate_fixes_html(self, fixes: List[Dict]) -> str:
        """生成已执行修复HTML"""
        html = ""
        for fix in fixes:
            html += f'''<div class="fix-item">
              <div class="skill-name">{_esc(fix.get("skill_name", ""))}</div>
              <div class="action">{_esc(fix.get("action", ""))}</div>
              <div class="status" style="color:var(--green)">✅ {_esc(fix.get("result", "完成"))}</div>
            </div>'''
        return html
    
    def _generate_pending_html(self, pending: List[Dict]) -> str:
        """生成待处理项HTML"""
        html = ""
        for item in pending:
            priority = item.get("priority", "P2")
            priority_class = f"priority-{priority.lower()}"
            html += f'''<div class="action-item">
              <span class="priority {priority_class}">{priority}</span>
              <div class="content">
                <div class="title">{_esc(item.get("title", ""))}</div>
                <div class="desc">{_esc(item.get("description", ""))}</div>
              </div>
            </div>'''
        return html
    
    def _list_items(self, items: List[str]) -> str:
        """生成列表项HTML"""
        return "".join(f"<li>{_esc(item)}</li>" for item in items) if items else "<li>无</li>"
    
    def _generate_fallback(self, meta, top_skills, results, fixes, pending, recommendations) -> str:
        """无模板时的后备生成方法"""
        # 简化的HTML生成
        return f'''<!DOCTYPE html>
<html><head><title>改进报告</title><style>{self.css}</style></head>
<body><div class="page">
<h1>技能持续精进报告</h1>
<p>评测了 {len(results)} 个技能</p>
</div></body></html>'''


def generate_html_report(report_data: Dict) -> str:
    """生成评测报告（向后兼容接口）"""
    return HTMLReportGenerator().generate(report_data)


def generate_improvement_report(report_data: Dict) -> str:
    """生成改进报告"""
    return ImprovementReportGenerator().generate(report_data)
