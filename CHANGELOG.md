# Changelog

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
