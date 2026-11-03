# DeskMate 成员 B 交付入口

本目录覆盖 B-00 的作业文档、图表和技术页素材，并记录 B-01～B-07 的验证证据。工程代码在 `../../backend/`，部署配置在 `../../deploy/`。C 的任务卡、前端、wellbeing 算法与报告代码均未修改。

| 材料 | 用途 |
| --- | --- |
| [B-00 作业素材包](DeskMate_B00_materials.zip) | SRS、图表、讲稿、验证记录及导出工具源码，不含运行环境和凭据 |
| [需求规格 PDF](DeskMate_SRS_B.pdf) | 17 页正式结构评审草稿，含六张图和附录 A 十组验收用例 |
| [SRS 源稿](SRS.md) | 可在仓库评审和继续修订的需求文本 |
| [浏览器版本](SRS.html) | 本地直接打开的排版版，配合 figures 目录使用 |
| [答辩技术页](DEFENSE_TECH_PAGES.md) | B 的两页正文、七十秒讲稿和备查问答，供 C 合稿 |
| [验证记录](VALIDATION.md) | 测试、覆盖率、localhost、容器和文档检查的实际状态 |
| [图表目录](figures/) | 六张 mmd 源、矢量 SVG 和高清 PNG |

## 重新导出图表和 PDF

需要 Node.js、Chrome 和网络安装文档开发依赖。运行时不会读取后端 .env，也不会连接任何模型。

```bash
cd deskmate/docs/assignment_b/tools
PUPPETEER_SKIP_DOWNLOAD=true npm ci --no-audit --no-fund
node export.mjs
```

默认使用 macOS 的 Google Chrome；其他环境通过 `CHROME_PATH` 指定浏览器。字体默认 PingFang SC，Linux 应安装 Noto Sans CJK SC。脚本顺序渲染 Mermaid、输出 SVG 与 2700 像素宽 PNG，再用浏览器排版导出 PDF。修改图表或文本后需要重新导出并查看每一页。

本轮未修改共同 CONTRACTS，SRS 第 5 章逐项列出源文档中的冲突和待确认项。所有真机性能与问卷结果保留待验，不把本地测试数当作课程最终端到端成功率。
