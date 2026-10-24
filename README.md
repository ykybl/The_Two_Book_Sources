# The Two Book Sources

The Two 阅读书源合集，多仓库采集、双重算法校验后智能归档。

## 仓库结构

```
├── sources/              # 所有书源文件
│   └── batch_001.json    # 当前合并后的书源
├── scripts/
│   ├── plug/              # 纯插件（只提供函数，不直接运行）
│   │   ├── check_v1.py    # 算法1：首页可达性
│   │   ├── check_v2.py    # 算法2：搜索链路校验
│   │   └── merge.py       # 智能合并插件
│   └── dispatch/          # 调度器（直接运行，调用插件）
│       ├── add.py         # 添加新书源
│       └── verify.py      # 定期维护校验
├── reports/              # 每次操作的校验报告
└── README.md
```

## 维护规则

1. **去重方向**：新书源入库前与所有已有文件整体比对，重复的从新书源中删除，已有文件不动
2. **失效清理**：定期校验全部书源，挂掉的从原文件中直接删除
3. **大小限制**：每个文件不超过 10MB
4. **智能合并**：新书源<5MB时合并到上一个文件；合并后超10MB则均匀分配到所有文件；≥5MB则新建batch文件
5. **添加时三重过滤**：算法2初筛 → 算法1复检 → 算法2终验（2→1→2）
6. **维护时单重校验**：仅算法2

## 使用方法

Legado / 简听阅读 中导入书源时，复制以下链接：

- 第1批：`https://cdn.jsdelivr.net/gh/ykybl/The_Two_Book_Sources@main/sources/batch_001.json`

> 备用链接（GitHub Raw）：
> `https://raw.githubusercontent.com/ykybl/The_Two_Book_Sources/main/sources/batch_001.json`

## 管理命令

```bash
# 添加新书源（自动去重 + 2→1→2三重过滤 + 智能合并）
python scripts/dispatch/add.py <新书源文件或URL>

# 校验全部书源，删除失效的（仅算法2）
python scripts/dispatch/verify.py
```

## 书源统计

| 文件 | 条数 | 大小 |
|------|------|------|
| sources/batch_001.json | 1,667 | 9.4MB |
| **合计** | **1,667** | **9.4MB** |
