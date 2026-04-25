# AI 选房智能体（MVP Demo）

本仓库提供一个可运行的 MVP 闭环示例：

- 城市限定：**济南市**
- 数据源限定：**贝壳租房 `https://jn.ke.com/zufang/`**
- 闭环流程：用户输入自然语言 → 需求解析 → 抓取房源（失败回退样例）→ 过滤打分 → 可解释推荐展示

## 目录

- `app.py`：Streamlit 页面入口
- `src/pipeline.py`：抓取、解析、打分、推荐主流程
- `data/test_cases_jinan_beike.json`：20 条用户需求样本
- `data/sample_listings_jn.json`：抓取失败时回退的本地样例房源
- `AI_选房智能体_MVP需求说明书.md`：需求说明书文档

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

打开浏览器访问 `http://localhost:8501`。

## 说明

1. 线上抓取使用 `requests + BeautifulSoup` 访问贝壳济南租房列表页。  
2. 若遇到反爬/网络限制，自动回退 `data/sample_listings_jn.json`，确保演示闭环可跑通。  
3. 推荐结果给出匹配分与命中理由，便于 PM/运营调参。

## 可扩展项

- 替换需求解析器为 LLM API（结构化 JSON 输出）
- 增加向量召回与多维权重学习
- 接入 PostgreSQL + 定时任务（APScheduler/Celery）
