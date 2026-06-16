# AI-Novels - VibeCoding 项目契约

## 项目身份

| 属性 | 值 |
|------|-----|
| 名称 | AI-Novels |
| 技术栈 | Python |
| 框架 | - |
| 包名 | - |
| 端口号段 | 33xxx |
| 描述 | AI小说生成系统 |
| Git: Y | Docker: Y | 测试: Y |

## 编程契约

继承自主契约的通用规则:
- 结论优先: 先给方案再解释
- 最小改动: 只改必须改的代码
- 可验证: 每个任务有明确完成标准
- 先问后做: 复杂改动先出方案
- 错误不吞: 所有代码必须有错误处理
- 可追溯: 所有改动在 MEMORY.md 中记录

### Python 规则
- 命名: snake_case / PascalCase
- 类型: 强制 type hints
- 异常: 使用日志记录，禁止 except: pass
- 资源: 使用 with 语句
- 测试: pytest

## 记忆体系

- 短期: 本项目的 MEMORY.md
- 长期: E:\\Typora(Note)\\ 知识库
- 主契约: C:\\Users\\Ryan\\.codex\\AGENTS.md

## VibeCoding 工作流

1. 需求澄清 -> 2. 方案输出 -> 3. 确认执行 -> 4. 代码生成
5. 编译检查 -> 6. 测试验证 -> 7. 代码审查 -> 8. 文档归档
9. Git 提交 -> 10. 推送远程

## Git 规范

```
git add . && git commit -m "type: 中文说明"
git push origin <当前分支>
```
