# Claude Code 与 MAS 功能重叠分析

## Claude Code 原生能力

| 能力 | 工具/参数 | 说明 |
|------|----------|------|
| 文件操作 | Read, Glob, Grep, Edit, Write | 完整文件系统访问 |
| 日志输出 | console, --verbose | 内置控制台 + 调试模式 |
| 子 Agent 调度 | Task 工具 | 多 Agent 协作 |
| 会话记忆 | --session-id | 跨对话上下文保持 |
| Skills 系统 | CLI Skills | 技能热插拔 |
| 搜索能力 | WebSearch, WebFetch | 网络搜索 |
| MCP 支持 | --mcp-config | 外部工具集成 |

## MAS 设计功能

| 功能 | 与 Claude Code 关系 | 建议 |
|------|-------------------|------|
| FilesTab 文件浏览器 | 冗余 - Claude Code 已有 | 简化 |
| LogsTab 日志查看 | 部分冗余 - Claude Code 有更完整日志 | 简化 |
| Task API | 冗余 - Task 工具已实现 | 标记废弃 |
| Files API | 冗余 - Claude Code 已有 | 标记废弃 |
| Session 持久化 | 互补 - 需要前端配合 | 保持 |
| Skills 选择 | 互补 - 需要前端配合 | 保持 |
| ResearchState | 独有 - 科学流程管理 | 保持 |
| 多 Agent 可视化 | 独有 - UI 展示 | 保持 |
