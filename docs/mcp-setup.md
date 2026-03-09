# MCP 服务器配置

## Tavily Search

### 获取 API Key
1. 访问 https://tavily.com/
2. 注册免费账号
3. 在 Dashboard 获取 API Key

### 免费配额
- 1000 次搜索/月
- 足够个人研究使用

### 故障排除
- 检查 API Key 是否正确配置
- 查看后端日志中的 MCP 相关错误
- 确认 npx 可用

## 当前状态

### 已完成
- [x] MCP 配置类添加到 config.py
- [x] ClaudeCodeService 支持 MCP
- [x] 系统提示词包含 MCP 工具信息
- [x] local.yaml 配置完成

### 已知问题
- MCP 配置会导致 CLI 挂起（超时）
- 可能原因：与第三方 API (minimax) 组合使用时的兼容性问题

### 建议解决方案
1. 使用官方 Anthropic API 而不是第三方 API
2. 或使用不同的 MCP 服务器配置方式
3. 或使用本地运行的 MCP 服务器
