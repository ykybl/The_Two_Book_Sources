# The Two Book Sources

Legado 阅读书源合集，多仓库采集、URL 可达性校验后去重保存。

## 维护规则

- 每个批次的书源单独保存为一个 JSON 文件，不合并到旧文件
- 新书源入库前与所有已有文件整体去重，**重复的从新书源中删除**，已有文件不动
- 定期重新校验全部书源，**失效的从原文件中直接删除**
- 每个文件不超过 10MB，超过则拆分

## 书源文件

| 文件 | 书源数 | 大小 | 说明 |
|------|--------|------|------|
| `book_sources.json` | 1678 | 8.53MB | 第 1 批：XIU2/Yuedu + aoaostar/legado + tickmao/Novel 合并去重校验 |

## 校验工具

使用 [xin-verify-book-source](https://github.com/CalmXin/xin-verify-book-source) 校验书源 URL 可达性（GET 请求首页，状态码 200 视为有效）。
