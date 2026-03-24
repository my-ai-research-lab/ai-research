"""
Transcript Renderer v1.0

把 link-agent-session-controller 保存的 JSON 对话记录
渲染成可读的 HTML 复盘页面。

支持的消息类型：
  text           → 用户输入 / AI 回复
  thinking       → AI 内部思考（可折叠）
  tool           → 工具调用（useSkill / executeCommand / 其他）
  command_output → 命令执行输出
  ask            → AI 等待用户确认
  completion_result → 任务结束
  api_req_started   → API 请求（忽略）
  checkpoint_created → 内部快照（忽略）
"""

import json
import re
import html as _html
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    """HTML 转义"""
    return _html.escape(str(s), quote=False)

def _ts(ts_ms: int) -> str:
    """毫秒时间戳 → HH:MM:SS"""
    try:
        return datetime.fromtimestamp(ts_ms / 1000).strftime("%H:%M:%S")
    except Exception:
        return ""

def _md_light(text: str) -> str:
    """极简 Markdown → HTML（只处理代码块、行内代码、粗体）"""
    # 代码块
    text = re.sub(
        r'```(\w*)\n(.*?)```',
        lambda m: f'<pre class="code-block"><code class="lang-{m.group(1)}">{_esc(m.group(2))}</code></pre>',
        text, flags=re.DOTALL
    )
    # 行内代码
    text = re.sub(r'`([^`\n]+)`', lambda m: f'<code class="inline-code">{_esc(m.group(1))}</code>', text)
    # 粗体
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # 换行
    text = text.replace('\n', '<br>')
    return text


# ─────────────────────────────────────────────────────────────────────
# 消息渲染器
# ─────────────────────────────────────────────────────────────────────

class MessageRenderer:

    def render(self, msg: Dict, idx: int) -> str:
        say  = msg.get("say", "")
        role = msg.get("role", "assistant")
        ts   = _ts(msg.get("ts", 0))

        # 忽略纯系统消息
        if say in ("api_req_started", "checkpoint_created", "completion_result"):
            return ""

        dispatch = {
            "text":          self._text,
            "thinking":      self._thinking,
            "tool":          self._tool,
            "command_output":self._command_output,
            "ask":           self._ask,
        }
        renderer = dispatch.get(say, self._unknown)
        return renderer(msg, idx, ts, role)

    # ── 用户输入 / AI 文字回复 ────────────────────────────────────────
    def _text(self, msg, idx, ts, role) -> str:
        text = msg.get("text", "")
        if not text.strip():
            return ""
        is_user = (role == "user")
        bubble_cls = "bubble-user" if is_user else "bubble-ai"
        label      = "用户" if is_user else "AI"
        label_cls  = "label-user" if is_user else "label-ai"
        content    = _md_light(text) if not is_user else _esc(text).replace('\n','<br>')
        model      = msg.get("chatModel", "")
        model_tag  = f'<span class="model-tag">{_esc(model)}</span>' if model and not is_user else ""

        return f"""
<div class="msg-row {'row-user' if is_user else 'row-ai'}">
  <div class="msg-meta">
    <span class="msg-label {label_cls}">{label}</span>
    <span class="msg-ts">{ts}</span>
    {model_tag}
  </div>
  <div class="bubble {bubble_cls}">{content}</div>
</div>"""

    # ── AI 思考 ──────────────────────────────────────────────────────
    def _thinking(self, msg, idx, ts, role) -> str:
        text = msg.get("text", "").strip()
        if not text:
            return ""
        tc = msg.get("timeCost", "")
        cost_tag = f'<span class="think-cost">⏱ {tc}s</span>' if tc else ""
        return f"""
<div class="msg-row row-think">
  <details class="think-details">
    <summary class="think-summary">
      <span class="think-icon">🧠</span>
      <span class="think-label">思考过程</span>
      {cost_tag}
      <span class="msg-ts">{ts}</span>
    </summary>
    <div class="think-body">{_esc(text).replace(chr(10),'<br>')}</div>
  </details>
</div>"""

    # ── 工具调用 ─────────────────────────────────────────────────────
    def _tool(self, msg, idx, ts, role) -> str:
        raw = msg.get("text", "")
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {"tool": "unknown", "raw": raw}

        tool_name = obj.get("tool", "unknown")

        # 特化展示不同工具
        if tool_name == "useSkill":
            return self._tool_use_skill(obj, ts)
        elif tool_name == "executeCommand":
            return self._tool_exec_cmd(obj, ts)
        elif tool_name == "writeToFile":
            return self._tool_write_file(obj, ts)
        elif tool_name == "readFile":
            return self._tool_read_file(obj, ts)
        else:
            return self._tool_generic(obj, ts)

    def _tool_use_skill(self, obj, ts) -> str:
        name   = obj.get("skillName", "")
        reason = obj.get("reason", "")
        return f"""
<div class="msg-row row-tool">
  <div class="tool-chip chip-skill">
    <span class="tool-icon">🔧</span>
    <div class="tool-body">
      <span class="tool-name">useSkill</span>
      <span class="tool-detail">→ <strong>{_esc(name)}</strong></span>
    </div>
    <span class="msg-ts">{ts}</span>
  </div>
  {f'<div class="tool-reason">{_esc(reason)}</div>' if reason else ''}
</div>"""

    def _tool_exec_cmd(self, obj, ts) -> str:
        cmd = obj.get("command", "")
        short = cmd.split('\n')[0][:80] + ("…" if len(cmd) > 80 or '\n' in cmd else "")
        return f"""
<div class="msg-row row-tool">
  <div class="tool-chip chip-cmd">
    <span class="tool-icon">⚡</span>
    <div class="tool-body">
      <span class="tool-name">executeCommand</span>
      <code class="tool-cmd-short">{_esc(short)}</code>
    </div>
    <span class="msg-ts">{ts}</span>
  </div>
</div>"""

    def _tool_write_file(self, obj, ts) -> str:
        path = obj.get("path", obj.get("relativePath", ""))
        return f"""
<div class="msg-row row-tool">
  <div class="tool-chip chip-file">
    <span class="tool-icon">📝</span>
    <div class="tool-body">
      <span class="tool-name">writeToFile</span>
      <code class="tool-cmd-short">{_esc(path)}</code>
    </div>
    <span class="msg-ts">{ts}</span>
  </div>
</div>"""

    def _tool_read_file(self, obj, ts) -> str:
        path = obj.get("path", obj.get("relativePath", ""))
        return f"""
<div class="msg-row row-tool">
  <div class="tool-chip chip-file">
    <span class="tool-icon">📖</span>
    <div class="tool-body">
      <span class="tool-name">readFile</span>
      <code class="tool-cmd-short">{_esc(path)}</code>
    </div>
    <span class="msg-ts">{ts}</span>
  </div>
</div>"""

    def _tool_generic(self, obj, ts) -> str:
        name = obj.get("tool", "unknown")
        keys = [k for k in obj if k != "tool"]
        detail = ", ".join(f"{k}={str(obj[k])[:40]}" for k in keys[:3])
        return f"""
<div class="msg-row row-tool">
  <div class="tool-chip chip-generic">
    <span class="tool-icon">🔩</span>
    <div class="tool-body">
      <span class="tool-name">{_esc(name)}</span>
      <span class="tool-detail">{_esc(detail)}</span>
    </div>
    <span class="msg-ts">{ts}</span>
  </div>
</div>"""

    # ── 命令输出 ─────────────────────────────────────────────────────
    def _command_output(self, msg, idx, ts, role) -> str:
        text = msg.get("text", "").strip()
        if not text:
            return ""
        # 截断超长输出
        lines = text.split('\n')
        truncated = False
        if len(lines) > 30:
            lines = lines[:30]
            truncated = True
        display = _esc('\n'.join(lines))
        if truncated:
            display += '\n<span class="truncate-note">… (输出已截断)</span>'
        return f"""
<div class="msg-row row-output">
  <div class="output-header">
    <span class="output-icon">📤</span>
    <span class="output-label">命令输出</span>
    <span class="msg-ts">{ts}</span>
  </div>
  <pre class="output-pre">{display}</pre>
</div>"""

    # ── 等待确认 ─────────────────────────────────────────────────────
    def _ask(self, msg, idx, ts, role) -> str:
        ask_type = msg.get("askType", msg.get("ask", ""))
        text     = msg.get("text", "")
        try:
            obj = json.loads(text)
            cmd = obj.get("command", text)[:120]
        except Exception:
            cmd = text[:120]
        return f"""
<div class="msg-row row-ask">
  <div class="ask-chip">
    <span class="ask-icon">⏸️</span>
    <div class="ask-body">
      <span class="ask-label">等待用户确认</span>
      <code class="ask-cmd">{_esc(cmd)}</code>
    </div>
    <span class="msg-ts">{ts}</span>
  </div>
</div>"""

    # ── 未知类型 ─────────────────────────────────────────────────────
    def _unknown(self, msg, idx, ts, role) -> str:
        say  = msg.get("say", "?")
        text = msg.get("text", "")[:80]
        if not text:
            return ""
        return f"""
<div class="msg-row row-unknown">
  <span class="msg-ts">{ts}</span>
  <span style="color:var(--muted);font-size:0.78rem">[{_esc(say)}] {_esc(text)}</span>
</div>"""


# ─────────────────────────────────────────────────────────────────────
# 主渲染器
# ─────────────────────────────────────────────────────────────────────

class TranscriptRenderer:

    def __init__(self):
        self.msg_renderer = MessageRenderer()

    def render_file(self, json_path: Path, out_path: Optional[Path] = None) -> Path:
        """
        读取 JSON transcript 文件，生成 HTML 文件。
        返回生成的 HTML 文件路径。
        """
        msgs = json.loads(json_path.read_text(encoding="utf-8"))
        name = json_path.stem
        html = self.render(msgs, title=name)

        if out_path is None:
            out_path = json_path.with_suffix(".html")
        out_path.write_text(html, encoding="utf-8")
        return out_path

    def render(self, msgs: List[Dict], title: str = "对话记录") -> str:
        """把消息列表渲染成完整 HTML 字符串"""
        # 基础统计
        total   = len(msgs)
        user_c  = sum(1 for m in msgs if m.get("role") == "user" and m.get("say") == "text")
        tool_c  = sum(1 for m in msgs if m.get("say") == "tool")
        think_c = sum(1 for m in msgs if m.get("say") == "thinking")
        model   = next((m.get("chatModel","") for m in msgs if m.get("chatModel")), "")

        # 时间范围
        tss = [m.get("ts", 0) for m in msgs if m.get("ts")]
        time_range = ""
        if tss:
            t0 = datetime.fromtimestamp(min(tss)/1000).strftime("%H:%M:%S")
            t1 = datetime.fromtimestamp(max(tss)/1000).strftime("%H:%M:%S")
            dur = (max(tss) - min(tss)) / 1000
            time_range = f"{t0} → {t1}（{dur:.0f}s）"

        # 渲染所有消息
        body = ""
        for idx, m in enumerate(msgs):
            body += self.msg_renderer.render(m, idx)

        return self._page(title, body, total, user_c, tool_c, think_c, model, time_range)

    def _page(self, title, body, total, user_c, tool_c, think_c, model, time_range) -> str:
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{_esc(title)} · 对话复盘</title>
<style>
/* ── Reset ─── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0d1117;--sur:#161b22;--sur2:#1f2937;
  --bd:rgba(255,255,255,0.07);
  --tx:#c9d1d9;--muted:#6e7681;
  --green:#3fb950;--red:#f85149;--yellow:#d29922;
  --cyan:#39c5cf;--purple:#bc8cff;--blue:#58a6ff;
  --user-bg:rgba(56,139,253,0.08);--user-bd:rgba(56,139,253,0.2);
  --ai-bg:rgba(255,255,255,0.03);--ai-bd:rgba(255,255,255,0.06);
}}
html{{font-size:14px;line-height:1.6}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--tx);
  min-height:100vh;padding:28px 20px 60px;
}}
a{{color:var(--blue);text-decoration:none}}
code{{font-family:"SF Mono","Fira Code","Cascadia Code",monospace}}

/* ── Layout ─── */
.wrap{{max-width:860px;margin:0 auto}}

/* ── Header ─── */
.header{{margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid var(--bd)}}
.header-top{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px}}
.title{{font-size:1.15rem;font-weight:700;letter-spacing:-0.01em}}
.title em{{color:var(--blue);font-style:normal}}
.back-btn{{
  font-size:0.78rem;color:var(--muted);border:1px solid var(--bd);
  border-radius:6px;padding:4px 10px;cursor:pointer;
  transition:color 0.15s,border-color 0.15s;
}}
.back-btn:hover{{color:var(--tx);border-color:rgba(255,255,255,0.2)}}
.stats-row{{display:flex;gap:18px;flex-wrap:wrap}}
.stat-item{{font-size:0.78rem;color:var(--muted)}}
.stat-item em{{color:var(--tx);font-style:normal;font-weight:600}}

/* ── 消息通用 ─── */
.msg-row{{margin-bottom:14px}}
.msg-meta{{
  display:flex;align-items:center;gap:8px;
  margin-bottom:5px;font-size:0.72rem;
}}
.msg-label{{
  font-weight:700;font-size:0.7rem;padding:1px 7px;border-radius:4px;
  text-transform:uppercase;letter-spacing:0.04em;
}}
.label-user{{background:rgba(56,139,253,0.15);color:var(--blue)}}
.label-ai  {{background:rgba(188,140,255,0.15);color:var(--purple)}}
.msg-ts{{color:var(--muted);font-size:0.68rem}}
.model-tag{{
  font-size:0.65rem;color:var(--muted);
  border:1px solid var(--bd);border-radius:3px;padding:0 4px;
}}

/* ── 气泡 ─── */
.bubble{{
  padding:12px 16px;border-radius:8px;
  font-size:0.85rem;line-height:1.7;
  border:1px solid;
}}
.bubble-user{{
  background:var(--user-bg);border-color:var(--user-bd);
  color:var(--tx);
}}
.bubble-ai{{
  background:var(--ai-bg);border-color:var(--ai-bd);
  color:var(--tx);
}}
.row-user .bubble{{margin-left:20px}}
.row-ai  .bubble{{margin-right:20px}}

/* 代码块 */
.code-block{{
  margin:10px 0;padding:10px 14px;
  background:rgba(0,0,0,0.35);border-radius:6px;
  font-size:0.8rem;overflow-x:auto;
  border:1px solid rgba(255,255,255,0.06);
  white-space:pre;
}}
.inline-code{{
  background:rgba(255,255,255,0.08);
  padding:1px 5px;border-radius:3px;
  font-size:0.82em;color:#e6c07b;
}}

/* ── 思考 ─── */
.think-details{{
  border:1px solid rgba(210,153,34,0.2);
  border-radius:8px;overflow:hidden;
}}
.think-summary{{
  display:flex;align-items:center;gap:8px;
  padding:8px 12px;cursor:pointer;
  background:rgba(210,153,34,0.06);
  font-size:0.78rem;list-style:none;
  user-select:none;
}}
.think-summary::-webkit-details-marker{{display:none}}
.think-summary:hover{{background:rgba(210,153,34,0.1)}}
.think-icon{{font-size:0.9rem}}
.think-label{{color:var(--yellow);font-weight:600}}
.think-cost{{font-size:0.68rem;color:var(--muted);border:1px solid var(--bd);border-radius:3px;padding:0 4px}}
.think-body{{
  padding:10px 14px;font-size:0.78rem;color:var(--muted);
  line-height:1.7;border-top:1px solid rgba(210,153,34,0.12);
}}

/* ── 工具调用 ─── */
.tool-chip{{
  display:inline-flex;align-items:center;gap:8px;
  padding:7px 12px;border-radius:6px;
  border:1px solid;font-size:0.78rem;
}}
.chip-skill{{
  background:rgba(63,185,80,0.06);border-color:rgba(63,185,80,0.2);
}}
.chip-cmd{{
  background:rgba(57,197,207,0.06);border-color:rgba(57,197,207,0.2);
}}
.chip-file{{
  background:rgba(88,166,255,0.06);border-color:rgba(88,166,255,0.18);
}}
.chip-generic{{
  background:rgba(255,255,255,0.03);border-color:var(--bd);
}}
.tool-icon{{font-size:1rem;flex-shrink:0}}
.tool-body{{flex:1;display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0}}
.tool-name{{font-weight:600;color:var(--tx)}}
.tool-detail{{color:var(--muted);font-size:0.75rem}}
.tool-cmd-short{{
  font-size:0.75rem;color:var(--cyan);
  background:rgba(57,197,207,0.08);
  padding:1px 6px;border-radius:3px;
  max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  display:inline-block;
}}
.tool-reason{{
  margin-top:4px;margin-left:4px;
  font-size:0.75rem;color:var(--muted);
  padding-left:12px;border-left:2px solid rgba(63,185,80,0.2);
}}

/* ── 命令输出 ─── */
.output-header{{
  display:flex;align-items:center;gap:8px;
  margin-bottom:6px;font-size:0.75rem;color:var(--muted);
}}
.output-icon{{font-size:0.9rem}}
.output-label{{font-weight:600}}
.output-pre{{
  background:rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.05);
  border-radius:6px;padding:10px 14px;
  font-size:0.75rem;color:#8b949e;
  overflow-x:auto;white-space:pre-wrap;word-break:break-all;
  max-height:250px;overflow-y:auto;
}}
.truncate-note{{color:var(--muted);font-style:italic}}

/* ── 等待确认 ─── */
.ask-chip{{
  display:inline-flex;align-items:center;gap:8px;
  padding:7px 12px;border-radius:6px;
  background:rgba(248,81,73,0.06);border:1px solid rgba(248,81,73,0.2);
  font-size:0.78rem;
}}
.ask-icon{{font-size:0.9rem}}
.ask-body{{flex:1;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.ask-label{{font-weight:600;color:var(--red)}}
.ask-cmd{{
  font-size:0.73rem;color:var(--muted);
  max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  display:inline-block;
}}

/* ── 未知 ─── */
.row-unknown{{font-size:0.75rem;color:var(--muted);padding:2px 0}}

/* ── 滚动条 ─── */
::-webkit-scrollbar{{width:4px;height:4px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:rgba(255,255,255,0.12);border-radius:2px}}
</style>
</head>
<body>
<div class="wrap">

  <div class="header">
    <div class="header-top">
      <div class="title">💬 <em>{_esc(title)}</em> · 对话复盘</div>
      <button class="back-btn" onclick="history.back()">← 返回报告</button>
    </div>
    <div class="stats-row">
      <div class="stat-item">消息总数 <em>{total}</em></div>
      <div class="stat-item">用户输入 <em>{user_c}</em> 条</div>
      <div class="stat-item">工具调用 <em>{tool_c}</em> 次</div>
      <div class="stat-item">思考步骤 <em>{think_c}</em> 步</div>
      {'<div class="stat-item">模型 <em>' + _esc(model) + '</em></div>' if model else ''}
      {'<div class="stat-item">时间 <em>' + _esc(time_range) + '</em></div>' if time_range else ''}
    </div>
  </div>

  <div class="messages">
{body}
  </div>

</div>
<div style="margin-top:40px;text-align:center;font-size:0.72rem;color:var(--muted)">
  Generated by Transcript Renderer · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
</div>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="把 transcript JSON 转成 HTML 复盘页面")
    parser.add_argument("input",  help="输入 JSON 文件路径（或目录批量处理）")
    parser.add_argument("--out",  help="输出 HTML 文件路径（可选）")
    args = parser.parse_args()

    renderer = TranscriptRenderer()
    inp = Path(args.input)

    if inp.is_dir():
        files = list(inp.glob("*.json"))
        print(f"批量处理 {len(files)} 个文件...")
        for f in files:
            out = renderer.render_file(f)
            print(f"  ✓ {out.name}")
    else:
        out = renderer.render_file(inp, Path(args.out) if args.out else None)
        print(f"✓ {out}")
