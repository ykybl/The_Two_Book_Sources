# The Two Book Sources

The Two 阅读书源合集，多仓库采集、双重算法校验后按批次归档。

## 仓库结构

```
├── sources/              # 所有书源文件
│   ├── batch_001.json    # 第1批
│   ├── batch_002.json    # 第2批...
│   └── ...
├── scripts/
│   ├── check_v1.py       # 算法1：首页可达性
│   ├── check_v2.py       # 算法2：搜索链路校验
│   ├── add_manage.py     # 添加新书源（自动2→1→2三重过滤）
│   └── verify_manage.py  # 定期维护（仅算法2）
├── reports/              # 每次操作的校验报告
└── README.md
```

## 维护规则

1. **新书源单独存为新批次文件**（`batch_002.json`、`batch_003.json`...），不合并到旧文件
2. **去重方向**：新书源入库前与所有已有文件整体比对，重复的从新书源中删除，已有文件不动
3. **失效清理**：定期校验全部书源，挂掉的从原文件中直接删除
4. **大小限制**：每个文件不超过 10MB，超过则拆分
5. **添加时三重过滤**：算法2初筛 → 算法1复检 → 算法2终验
6. **维护时单重校验**：仅算法2

## 使用方法

Legado / 简听阅读 中导入书源时，复制以下链接：

- 第1批：`https://cdn.jsdelivr.net/gh/ykybl/The_Two_Book_Sources@main/sources/batch_001.json`

> 备用链接（GitHub Raw）：`https://raw.githubusercontent.com/ykybl/The_Two_Book_Sources/main/sources/batch_001.json`

## 管理命令

```bash
# 添加新书源（自动去重 + 2→1→2三重过滤）
python scripts/add_manage.py <新书源文件或URL>

# 校验全部书源，删除失效的（仅算法2）
python scripts/verify_manage.py
```

## 书源文件

| 文件 | 条数 | 大小 |
|------|------|------|
| sources/batch_001.json | 1,001 | 5.24MB |
