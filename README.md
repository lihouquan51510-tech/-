# AI 选房智能体（MVP Demo）

本仓库提供一个可运行的 MVP 闭环示例：

- 城市限定：**济南市**
- 数据源限定：**贝壳租房 `https://jn.ke.com/zufang/`**
- 闭环流程：用户输入自然语言 → 需求解析 → 抓取房源（失败回退样例）→ 硬筛选 → 过滤打分 → 可解释推荐展示

## 目录

- `app.py`：Streamlit 页面入口（含智能体执行日志）
- `src/pipeline.py`：抓取、解析、硬筛、打分、推荐主流程
- `scripts/run_next_step.py`：基于 20 条样本的下一步验证脚本
- `data/test_cases_jinan_beike.json`：20 条用户需求样本
- `data/sample_listings_jn.json`：抓取失败时回退的本地样例房源
- `data/next_step_report.json`：脚本输出的阶段报告（运行后生成）
- `AI_选房智能体_MVP需求说明书.md`：需求说明书文档

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

打开浏览器访问 `http://localhost:8501`。

## 下一步工作（已落地）

根据需求说明书，本阶段已补齐“智能体开发流程”的执行与验证：

1. **Parse**：自然语言需求结构化（预算/户型/区域/偏好/避让项）
2. **Crawl**：抓取贝壳济南租房列表，失败时回退样例
3. **Filter**：硬筛选（预算上浮阈值、最少居室数、行政区）
4. **Rank**：可解释打分排序（预算、户型、区域、偏好、避让项、紧急程度）
5. **Evaluate**：使用 `scripts/run_next_step.py` 批量跑 20 条样本并输出报告

运行：

```bash
python scripts/run_next_step.py
```

## 说明

1. 线上抓取使用 `urllib` 访问贝壳济南租房列表页，并用轻量正则抽取字段。  
2. 若遇到反爬/网络限制，自动回退 `data/sample_listings_jn.json`，确保演示闭环可跑通。  
3. 推荐结果给出匹配分与命中理由，便于 PM/运营调参。

## 可扩展项

- 替换需求解析器为 LLM API（结构化 JSON 输出）
- 增加向量召回与多维权重学习
- 接入 PostgreSQL + 定时任务（APScheduler/Celery）
