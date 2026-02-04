# Changelog

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
