# Skill Dojo Report Templates

> 技能评测报告的统一模板系统。将报告风格从SKILL.md和脚本中抽离，便于维护和复用。

## 目录结构

```
templates/
├── README.md                 # 本文件：使用说明
├── report-styles.css         # 统一CSS变量和基础样式
├── benchmark-report.html     # 方式B评测报告模板
├── improvement-report.html   # 方式A改进报告模板
└── components/               # 可复用HTML组件
    ├── header.html           # 页头组件
    ├── stats-cards.html      # 统计卡片组件
    ├── skill-chips.html      # 技能芯片组件
    └── result-table.html     # 结果表格组件
```

## 设计理念

### 1. 统一视觉语言
- 使用 GitHub 深色主题作为基础
- 渐变色系：蓝紫为主调，绿/红/黄为状态色
- 圆角卡片 + 微妙阴影 + 适度动效

### 2. 组件化
- 每个报告由多个可复用组件组成
- 组件使用模板变量 `{{variable}}` 占位
- Python 脚本负责填充数据

### 3. 三种报告类型

| 类型 | 文件 | 用途 |
|:-----|:-----|:-----|
| 评测报告 | `benchmark-report.html` | 方式B自动化评测结果 |
| 改进报告 | `improvement-report.html` | 方式A轻量评测 + 修复记录 |
| 对话复盘 | `transcript-report.html` | 单场景对话详情 |

## 使用方式

### Python 脚本调用

```python
from pathlib import Path

def load_template(name: str) -> str:
    template_dir = Path(__file__).parent.parent / "templates"
    return (template_dir / name).read_text(encoding="utf-8")

# 加载CSS
css = load_template("report-styles.css")

# 加载报告模板
template = load_template("benchmark-report.html")

# 替换变量
html = template.replace("{{CSS}}", css)
html = html.replace("{{TITLE}}", "技能评测报告")
# ...
```

### Agent 直接使用

当需要手动生成报告时，可以：
1. 读取对应模板文件
2. 按模板结构填充数据
3. 写入 `reports/` 目录

## 模板变量说明

### 通用变量

| 变量 | 说明 | 示例 |
|:-----|:-----|:-----|
| `{{CSS}}` | 内联CSS样式 | 从 report-styles.css 读取 |
| `{{TITLE}}` | 页面标题 | "技能评测报告 · 2026-03-21" |
| `{{TIMESTAMP}}` | 生成时间 | "2026-03-21 06:20" |
| `{{TOTAL}}` | 总测试数 | 10 |
| `{{PASSED}}` | 通过数 | 8 |
| `{{FAILED}}` | 失败数 | 2 |
| `{{PASS_RATE}}` | 通过率 | "80%" |

### 评测报告专用

| 变量 | 说明 |
|:-----|:-----|
| `{{SKILL_CHIPS}}` | 技能芯片HTML列表 |
| `{{TABLE_ROWS}}` | 评测结果表格行 |
| `{{DURATION}}` | 总耗时（秒） |

### 改进报告专用

| 变量 | 说明 |
|:-----|:-----|
| `{{TOP_SKILLS}}` | Top N 高频技能芯片 |
| `{{FIXES_APPLIED}}` | 已执行修复项 |
| `{{PENDING_ACTIONS}}` | 待处理项 |
| `{{RECOMMENDATIONS}}` | 建议卡片 |

## 版本历史

| 版本 | 日期 | 变更 |
|:-----|:-----|:-----|
| v1.1 | 2026-03-21 | **链接协议修复**：`report_generator.py` 中的链接从 `file://` 改为相对路径 `../transcripts/xxx`，解决浏览器安全策略阻止点击跳转的问题 |
| v1.0 | 2026-03-21 | 初始版本，从 SKILL.md 和脚本中抽离报告样式 |

## 注意事项

> ⚠️ **链接协议规范（踩坑沉淀）**
> 
> 报告中的交付物和会话记录链接**必须使用相对路径**，禁止使用 `file://` 协议。
> 
> | 协议 | 示例 | 能否点击 |
> |:-----|:-----|:---------|
> | ❌ `file://` | `file:///Users/.../transcripts/xxx.html` | 浏览器安全策略阻止 |
> | ✅ 相对路径 | `../transcripts/xxx.html` | 正常跳转 |
> 
> **验证方法**：`grep "file://" reports/*.html` — 如果有匹配则链接不可点击
> 
> **技术原因**：浏览器禁止从 HTTP 页面跳转到本地 `file://` 资源（跨协议安全限制）
