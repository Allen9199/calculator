# Memory 自动保存配置

## 问题
OpenClaw 的 session-memory hook 没有启用，导致 bootstrap 对话没有自动保存到 memory 文件。

## 解决方案
1. 重启 gateway
2. 启用 hooks: `openclaw hooks enable session-memory`
3. 之后每次用 /new 开始对话会自动保存

## 临时解决方案
重要对话手动保存到此文件。

---

## 重要信息

### 身份
- 名称: Moss
- 类型: AI 数字助手
- Emoji: 🌿
- 性格: 实用、略有趣、无废话

### 用户
- 姓名: Allen
- 职业: 软件工程师
- 关系: 协作伙伴

### 沟通规则
- 有结论或处理结果后，**主动回复**，不要等用户追问
- **自动保存记忆**：每个话题讨论结束后，自动把要点保存到 MEMORY.md

---

### 2026-03-05 讨论记录

#### 股票监控优化
- **问题**：Yahoo Finance API 限流，导致数据获取失败
- **解决方案**：主备模式
  - 优先使用 Yahoo Finance
  - 限流时自动切换到 Twelvedata API
  - 每次请求延迟 5 秒，避免触发限流
- **脚本位置**：`/root/.openclaw/workspace/stock_monitor.py`
- **消息格式优化**：
  - 顶部显示涨跌概览（📈 上涨/📉 下跌）
  - 每个股票单独显示（名称、价格、涨跌幅、成交量）
  - 缩进区分标题和数据
- **飞书消息类型**：text（不支持 markdown）
- **数据源**：Twelvedata (API Key: 785bfc4b878c4bc9a5cc517262c26f25)
- **已推送到 GitHub**

### GitHub 同步
- Token 存储在环境变量 `GITHUB_TOKEN`
- 同步命令：`git remote set-url origin https://Allen9199:${GITHUB_TOKEN}@github.com/Allen9199/calculator.git && git push origin main`

### Git 操作规范
- **必须先拉取远程代码**: `git pull <remote> <branch> --rebase` 或 `git merge`
- **禁止直接 --force**: 除非明确知道远程版本可以丢弃
- **解决冲突后再推送**: 确保本地和远程合并后无冲突
- **先检查远程状态**: 用 `git fetch` 和 `git log` 查看远程版本
