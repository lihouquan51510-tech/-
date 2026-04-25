# AI 选房智能体（MVP Demo）

本仓库提供一个可运行的 MVP 闭环示例：

- 城市限定：**济南市**
- 数据源限定：**贝壳租房 `https://jn.ke.com/zufang/`**
- 闭环流程：用户输入自然语言 → 需求解析 → 抓取房源（失败回退样例）→ 硬筛选 → 过滤打分 → 可解释推荐展示

## 目录

- `app.py`：Streamlit 页面入口（含智能体执行日志）
- `src/pipeline.py`：抓取、解析、硬筛、打分、推荐主流程
- `src/llm_parser.py`：下一里程碑实验能力（LLM 结构化解析，失败回退规则）
- `scripts/run_next_step.py`：基于 20 条样本的下一步验证脚本
- `scripts/stage_gate_runner.py`：阶段闸门执行器（每阶段自动测试 + 下一阶段提示）
- `docs/agent_development_stages.md`：完整智能体开发阶段与 Gate 规则
- `data/test_cases_jinan_beike.json`：20 条用户需求样本
- `data/sample_listings_jn.json`：抓取失败时回退的本地样例房源
- `data/next_step_report.json`：解析与推荐基线报告
- `data/stage_gate_report.json`：阶段闸门执行报告（运行后生成）

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

打开浏览器访问 `http://localhost:8501`。

## 阶段化开发

根据需求说明书，已落地 Stage-Gate 流程：

1. Stage 0 范围冻结
2. Stage 1 数据采集
3. Stage 2 需求解析
4. Stage 3 匹配推荐
5. Stage 4 交互展示
6. Stage 5 验收迭代

执行方式：

```bash
python scripts/stage_gate_runner.py
```

## 下一里程碑（已启动）

已新增 **LLM + Rule 融合投票解析能力**：
- UI 勾选“启用 LLM 结构化解析”后，会先执行 LLM 解析，再与规则解析做融合投票。
- 一致字段直接采用；冲突字段按稳定性启发式处理（如预算冲突大时优先规则、卧室数取更保守值）。
- 如 LLM 调用失败，会自动回退规则解析，保证流程不中断。

环境变量：

```bash
export OPENAI_API_KEY=your_key
export OPENAI_BASE_URL=https://api.openai.com/v1    # 可选
export OPENAI_MODEL=gpt-4.1-mini                    # 可选
```

## 截图工具接口说明

- Stage 4 需要通过浏览器截图工具接口完成页面截图留档。
- 若当前环境无可用浏览器截图能力，请在报告中标记 `pending_or_blocked_by_environment`。

## 说明

1. 线上抓取使用 `urllib` 访问贝壳济南租房列表页，并用轻量正则抽取字段。  
2. 若遇到反爬/网络限制，自动回退 `data/sample_listings_jn.json`，确保演示闭环可跑通。  
3. 推荐结果给出匹配分与命中理由，便于 PM/运营调参。

## 可扩展项

- 持续优化融合投票策略（置信度学习/字段级权重）
- 增加向量召回与多维权重学习
- 接入 PostgreSQL + 定时任务（APScheduler/Celery）
