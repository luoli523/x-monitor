# Changelog

## 2026-02-09 - 报告重新生成功能

### 新功能：从数据库重新生成报告

新增 `x-monitor regenerate` 命令，可以直接从本地数据库中的推文重新生成 LLM 分析报告，无需调用 X API。

### 使用场景

- **优化提示词后重新分析** - 修改了 LLM prompt 后，可以用历史数据重新生成报告查看效果
- **节省 API 调用** - 不消耗 X API 配额，适合测试和调试
- **生成历史报告** - 为之前抓取的数据生成新的分析报告
- **修复错误分析** - 如果某次分析出现问题，可以重新生成

### 命令示例

```bash
# 重新生成今天的报告
x-monitor regenerate

# 重新生成指定日期的报告
x-monitor regenerate --date 2026-02-08

# 重新生成并发送通知
x-monitor regenerate --notify
```

### 功能特性

- ✅ **零 API 调用** - 完全从本地数据库读取推文
- ✅ **智能日期范围** - 自动查询指定日期的所有推文
- ✅ **完整输出** - 更新数据库 summary 记录并生成 Markdown 报告
- ✅ **可选通知** - 支持重新发送 Email 和 Telegram 通知
- ✅ **保留历史** - 使用 `INSERT OR REPLACE`，保留原记录的同时更新分析

### 修改的文件

1. **src/agent.py**
   - 新增 `regenerate_report_from_db()` 方法
   - 实现数据库推文查询、LLM 分析和报告保存的完整流程

2. **src/storage.py**
   - 新增 `get_tweets_between()` 方法
   - 支持按日期范围查询推文（支持可选的用户名过滤）

3. **src/main.py**
   - 新增 `regenerate` CLI 命令
   - 支持 `--date` 和 `--notify` 选项
   - 提供清晰的成功/失败反馈

4. **README.md**
   - 在 Usage 部分添加 `regenerate` 命令文档
   - 说明使用场景和示例

### 测试结果

✅ **成功测试** - 2026-02-09
- 从数据库读取 147 条推文
- 生成 6,598 字符的分析报告
- 保存到 `output/report_2026-02-09.md`（13KB）
- 更新数据库 summary 记录
- 命令执行时间：约 2 分钟（主要是 LLM 调用）

---

## 2026-02-04 - Rate Limit 处理策略优化

### 变更：跳过限流请求而非等待重试

**之前：** 遇到 Rate limit 时会进行指数退避重试（最多 5 次，每次等待时间翻倍）
**现在：** 遇到 Rate limit 时立即跳过该请求，继续处理下一个账号

### 修改的文件

1. **src/scrapers/x_scraper.py**
   - 修改 `_execute_with_retry()` 方法：遇到限流直接返回 None
   - 更新 `get_user_info()` 和 `get_recent_tweets()` 处理 None 返回值
   - 修改 `tweepy.Client` 配置：`wait_on_rate_limit=False`
   - 标记重试相关参数为废弃（保留向后兼容）

2. **.env.example** 和 **.env**
   - 更新注释说明新的限流处理策略
   - 标记 `RATE_LIMIT_MAX_RETRIES` 和 `RATE_LIMIT_RETRY_BASE_DELAY` 为废弃

### 优势

- ✅ **更快** - 不再等待重试，立即继续处理
- ✅ **更稳定** - 避免长时间阻塞在单个账号上
- ✅ **更可控** - 明确知道哪些账号因限流被跳过
- ✅ **更适合批量处理** - 20 个账号中即使几个被限流也能快速完成其他账号

### 日志示例

遇到限流时会输出：
```
⚠️  Rate limit hit! Skipping this request to continue processing. Error: ...
Skipped fetching tweets from @username due to rate limit
```

### 向后兼容性

- 保留了重试相关的配置参数（但不再使用）
- 不影响现有的 `.env` 配置文件
- CLI 命令继续正常工作

---

## 2026-02-04 - 配置方式重构

### 重大变更：账号列表管理方式改变

**之前：** 账号列表存储在 SQLite 数据库中
**现在：** 账号列表从 `config/accounts.json` 配置文件读取

### 修改的文件

1. **src/storage.py**
   - 移除了数据库中的 `accounts` 表
   - 添加了 JSON 配置文件读写方法
   - `get_accounts()` - 从 JSON 文件读取
   - `add_account()` - 写入 JSON 文件
   - `remove_account()` - 从 JSON 文件删除
   - `get_account()` - 从 JSON 文件查询

2. **README.md**
   - 更新了配置说明
   - 添加了 `config/accounts.json` 的使用方法

### 优势

- ✅ **更直观** - 可以直接编辑 JSON 文件批量管理账号
- ✅ **版本控制友好** - JSON 文件可以纳入 Git 管理
- ✅ **易于迁移** - 直接复制配置文件到新环境
- ✅ **备份简单** - 只需备份一个 JSON 文件

### 配置格式

```json
{
  "accounts": [
    {
      "username": "karpathy",
      "note": "LLM之王（从零教你造大模型）"
    }
  ]
}
```

### 兼容性

- SQLite 数据库仍然用于存储每日分析报告（summaries 表）
- CLI 命令（add/remove/list）继续可用，会自动操作 JSON 文件
- 现有的 `.env` 配置无需修改

### 测试结果

✅ `x-monitor list` - 成功读取 20 个账号
✅ `x-monitor add testuser` - 成功添加账号到 JSON
✅ `x-monitor remove testuser` - 成功从 JSON 删除账号
