5. 重跑评测 → 确认评分回升 → 更新基线

### 场景 4: 自动修复（定时任务）

**周检发现 web-dev-workflow 版本号过时**:
1. 检测问题：SKILL.md 第5行 version: 1.5.0，但实际已有 v1.6 改动
2. 判断类型：文档过时 → 可自动修复类
3. 检查条件：修改1行 ✓ 有明确证据 ✓ 在git控制下 ✓
4. 直接执行：`replace_in_file` 更新版本号
5. 输出：`🔧 自动修复执行 | 技能: web-dev-workflow | 类型: 文档过时 | 修改: version 1.5.0→1.6.0 | 行数: 1行 | 状态: ✅ 已修复`

---

## 踩坑经验

> 完整踩坑经验见 `references/lessons-learned.md`

---

> 📚 **更多详细内容**: [references/overflow.md](references/overflow.md)


---
> - §1 一步到位原则：诊断后必须立即修复，不能只输出清单；报告必须用 HTTP URL（非 file://）
> - §2 方式B必须独立会话（三代踩坑）：含续跑场景不能复用旧 evidence.json

## 注意事项

1. **自动修复有边界**：定时任务中满足自动修复条件的问题会直接修复，但逻辑变更/新增功能仍需用户确认
2. **场景库质量 > 数量**：每个技能 5-10 个高质量场景足够，不需要追求数量
3. **避免过拟合**：场景要覆盖典型用例和边界用例，不要只测"容易通过"的场景
4. **基线是累积最高分**：基线只升不降，除非用户手动重置
5. **轻量优先**：日常使用方式A（走读评测），只在周/月度使用方式B（spawn subagent）

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.1.0 | 2026-03-22 | **周检规则优化**：将「Top 5/Top 10 高频技能」改为「本周调用 ≥1次的所有技能」全量评测，提升周检覆盖率 |
| v2.0 | 2026-03-21 | **报告模板系统重构 + 链接协议修复**：新增 `templates/` 子目录，将报告样式从SKILL.md和脚本中抽离为独立模块；统一CSS设计Token（`report-styles.css`）；新增两个HTML模板（`benchmark-report.html` + `improvement-report.html`）；`report_generator.py` 重构支持模板加载；**修复链接不可点击问题**：将 `file://` 协议改为相对路径 `../transcripts/xxx`，浏览器安全策略阻止HTTP页面中的file://跳转 |
| v1.9 | 2026-03-20 | **方式B强制规则（P0级踩坑沉淀）**：新增方式B执行前强制检查点（必须用skill-test-runner或agent-session-controller启动独立会话）；明确正确/错误会话角色分工；禁止在当前会话逐个手动测试。来源：执行层技能评测踩坑（偷换概念反模式）|
| v1.8 | 2026-03-19 | **benchmark.json 数据格式规范（v5.1）**：新增 artifacts 字段规范（必须用 `value` 而非 `path`）；禁止 `file://` 协议链接（浏览器安全限制无法点击）；transcript 字段配置规范；方式A人工走读完整流程（创建transcript JSON → 生成HTML复盘页 → 配置artifacts和transcript → 生成报告 → 修复链接）|
| v1.7 | 2026-03-19 | **报告格式标准化（v5.0）+ task-wait 防抖修复**：报告新增「会话记录 & 交付件」必须列（完整/截断/交付件/未运行四态）；HTTP 服务器根目录规范（必须设为 link-skill-dojo/）；task-wait.sh 修复竞态：grace period 8s→30s，新增防抖机制（连续3次 isRunning=false 才确认完成） |
| v1.6 | 2026-03-19 | **执行层评测实战经验沉淀**：场景格式新增必填字段规范（`display_name`/`priority`/`timeout`/`artifact_extractors`）和编写规范（中文引号陷阱/assertions用name不用target/干跑验证）；skill-test-runner.py 新增 `--file/-f` 参数支持自定义场景文件；方式A新增A/B混用补全策略（应对竞态截断场景）；方式B新增竞态陷阱警告（工具调用间隙假完成，task-wait grace period 建议>=30s）；修复 BenchmarkReport dataclass 缺少默认值问题 |
| v1.5 | 2026-03-19 | **自动化评测引擎落地**：方式B深度评测从概念落地为完整脚本体系（skill-test-runner + graders + report_generator + transcript_renderer）。新增 HTML 评测报告（v4.0：统计卡片+技能芯片+可折叠评测项+交付物预览）和 HTML 对话复盘页（思考折叠+工具高亮+终端输出）。评测报告中「对话记录」链接直接打开 HTML 复盘页，点击可复盘完整执行过程 |
| v1.4 | 2026-03-19 | **吸收万擎skill-creator评估框架**：能力2新增"方式C对照评测"（subagent并行执行with-skill vs baseline）；新增benchmark.json量化指标（pass_rate/time_ms/tokens/delta）；新增grading.json断言格式规范。来源：万擎技能广场skill-creator(新版) |
| v1.3 | 2026-03-17 | **新增自动修复模式**。能力5改进闭环升级：定时任务（周检/月检/每日修炼）中发现的明确问题可自动修复，无需用户确认。定义四类可自动修复问题（文档过时/触发词缺失/格式问题/冗余内容）和四项安全条件。手动触发仍保持交互模式 |
| v1.2 | 2026-03-16 | **新增能力6: 社区对标**。技能修炼不再只做内部评测，新增外部对标能力：调用 link-find-skills 主动巡检已有技能的外部更新，调用 ks-clawbook 浏览社区最佳实践，产出社区对标报告并汇入改进闭环。技能生命周期从线性链正式成环（skill-dojo → link-find-skills 反馈路径）。明确与吸星大法的分工边界：社区对标管「已有技能升级」，吸星大法管「全新技能吸收」|
| v1.0 | 2026-03-14 | 创建技能。五大能力：场景库管理、自动化评测、退化检测、弱点发现、改进闭环。从 ks-kim-docs-shuttle 升级实践中提炼出持续精进的系统化方法 |
