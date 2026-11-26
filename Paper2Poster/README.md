# Paper2Poster

## 数据集

Paper2Poster 使用[正式论文库](../data/papers/Paper2Poster/)中五个研究方向的全部 2,300 篇论文。每篇论文按一个研究方向归档。

| 目录名 | 研究方向 | 篇数 |
|---|---|---:|
| `NLP` | 自然语言处理 | 679 |
| `ML` | 机器学习与智能决策 | 556 |
| `HCI` | 人机交互与跨学科应用 | 391 |
| `CV` | 计算机视觉与多媒体 | 362 |
| `SYS` | 计算机系统与信息服务 | 312 |
| **合计** | | **2,300** |

[逐篇清单](../data/papers/collection_manifest.jsonl)中的 `research_category` 是上表所列的目录名，`directory` 是相对于 Rubrics_poster 仓库根目录的论文目录。论文原文位于每条记录的 `directory/paper.pdf`。

各类规则存放在 `Paper2Poster/rubrics/<research_category>/`，论文存放在 `data/papers/Paper2Poster/<research_category>/` 下。
