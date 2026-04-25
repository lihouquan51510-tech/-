import json
from dataclasses import asdict

import streamlit as st

from src.pipeline import JN_BEIKE_URL, recommend

st.set_page_config(page_title="AI 选房智能体（济南·贝壳）", page_icon="🏠", layout="wide")

st.title("🏠 AI 选房智能体 MVP")
st.caption("限定范围：济南市 + 贝壳租房（jn.ke.com）")

with st.expander("系统范围说明", expanded=False):
    st.markdown(
        f"""
- 城市：**济南市**
- 站点：**贝壳租房**（{JN_BEIKE_URL}）
- 功能：需求解析 → 抓取/回退样例 → 过滤打分 → 可解释推荐
        """
    )

sample_query = "预算 5000，历下区，两居，地铁近一点，最好有电梯。"
user_text = st.text_area("请输入你的找房需求（自然语言）", value=sample_query, height=120)

col1, col2 = st.columns([1, 3])
with col1:
    top_k = st.slider("返回推荐数量", min_value=3, max_value=10, value=5)
with col2:
    run = st.button("开始推荐", type="primary")

if run:
    result = recommend(user_text, top_k=top_k)

    st.subheader("1) 结构化需求（解析结果）")
    st.json(asdict(result["query"]))

    st.subheader("2) 推荐结果（可解释）")
    st.write(f"候选房源总数：{result['total_candidates']}")

    for idx, item in enumerate(result["recommendations"], start=1):
        with st.container(border=True):
            st.markdown(f"### {idx}. {item['title']}")
            st.markdown(
                f"- 价格：**{item.get('price', '-') } 元/月**  \n"
                f"- 户型：{item.get('layout', '-') }  \n"
                f"- 区域：{item.get('district', '-') }  \n"
                f"- 匹配分：**{item.get('score', 0)}**"
            )
            st.markdown(f"- 链接：{item.get('url', '-')}")
            st.markdown("**推荐理由**")
            if item.get("reasons"):
                for r in item["reasons"]:
                    st.write(f"✅ {r}")
            else:
                st.write("⚠️ 当前未命中显式偏好，按基础条件排序")

    st.subheader("3) 原始结果 JSON（调试）")
    st.code(json.dumps(result, ensure_ascii=False, indent=2, default=str), language="json")
else:
    st.info("输入需求并点击“开始推荐”查看结果。")
