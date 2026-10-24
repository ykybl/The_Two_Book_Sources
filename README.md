# The Two Book Sources

Legado 阅读书源合集，多仓库采集、URL 可达性校验后按批次归档。

## 仓库结构

```
├── sources/              # 所有书源文件
│   ├── batch_001.json    # 第1批
│   ├── batch_002.json    # 第2批...
│   └── ...
├── scripts/
│   └── manage.py         # 管理脚本（添加/校验/统计）
├── reports/              # 每次操作的校验报告
├── STATS.md              # 书源统计
└── README.md
```

## 维护规则

1. **新书源单独存为新批次文件**（`batch_002.json`、`batch_003.json`...），不合并到旧文件
2. **去重方向**：新书源入库前与所有已有文件整体比对，重复的从新书源中删除，已有文件不动
3. **失效清理**：定期校验全部书源，挂掉的从原文件中直接删除
4. **大小限制**：每个文件不超过 10MB，超过则拆分

## 使用方法

Legado 中导入书源时，选择对应的 raw 文件链接：

- 第1批：`https://raw.githubusercontent.com/ykybl/The_Two_Book_Sources/main/sources/batch_001.json`

## 管理命令

```bash
# 添加新书源（自动去重+校验）
python scripts/manage.py add <新书源文件或URL>

# 校验全部书源，删除失效的
python scripts/manage.py verify

# 查看统计
python scripts/manage.py stats
```

## 书源文件

| 文件 | 条数 | 大小 |
|------|------|------|
| sources/batch_001.json | 1,678 | 8.53MB |

## 校验工具

使用 [xin-verify-book-source](https://github.com/CalmXin/xin-verify-book-source) 校验书源 URL 可达性（GET 请求首页，状态码 200 视为有效）。
