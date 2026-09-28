# -*- coding: utf-8 -*-
"""승인 화면.  `streamlit run app.py`

담당자가 **10초 안에** 판단할 수 있어야 한다. 그래서 한 건을 열면 다섯 칸만 보인다 —
요청 원문 · 핵심 정보 · AI 판정과 근거가 된 규정 · 왜 멈췄는지 · 통과시키면 무슨 일이.
마지막 칸이 승인 버튼의 무게를 정한다.
"""
import json
import os

import streamlit as st

import graph
from common import OUT, api_key, jload
from jobs import JOBS

st.set_page_config(page_title="승인 대기함", page_icon="🛑", layout="wide")

st.markdown("""<style>
.stApp{font-size:15.5px}
.칸{border:1px solid #d8dee6;border-radius:6px;padding:12px 14px;margin-bottom:9px;
    background:#fff}
.칸 b{display:block;font-size:12px;letter-spacing:.02em;color:#6b7684;margin-bottom:5px;
      font-weight:600}
.칸 .내용{white-space:pre-wrap;line-height:1.65;color:#151a1f}
.경고{border-color:#e0584a;background:#fff5f4}
.경고 b{color:#c0392b}
.무게{border-color:#d79a00;background:#fffaf0}
.무게 b{color:#9a6f00}
.무게 .내용{font-weight:600}
@media (prefers-color-scheme:dark){
 .칸{background:#151b22;border-color:#2b3640} .칸 .내용{color:#dde5ec}
 .경고{background:#2a1614;border-color:#8c3a30}
 .무게{background:#2a2312;border-color:#8a6a10}}
</style>""", unsafe_allow_html=True)


def 칸(제목, 내용, 종류=""):
    st.markdown(f'<div class="칸 {종류}"><b>{제목}</b><div class="내용">{내용}</div></div>',
                unsafe_allow_html=True)


st.title("🛑 승인 대기함")
st.caption("되돌릴 수 없는 일 직전에 에이전트가 멈춘 건들입니다. "
           "기준에 걸리지 않은 건은 여기 오지 않고 이미 처리됐습니다.")

with st.sidebar:
    st.header("업무")
    for k, v in JOBS.items():
        st.markdown(f"**{v['이름']}**  \n<span style='font-size:12.5px;color:#6b7684'>"
                    f"나가는 것: {v['나가는 것']}</span>", unsafe_allow_html=True)
        st.caption("관문: " + ", ".join(n for n, _ in v["관문"]))
    st.divider()
    요약 = {}
    p = os.path.join(OUT, "summary.json")
    if os.path.exists(p):
        요약 = json.load(open(p, encoding="utf-8"))
        전체 = sum(v["전체"] for v in 요약.values())
        멈춤 = sum(v["멈춤"] for v in 요약.values())
        st.metric("한 바퀴 실행", f"{멈춤} / {전체}건 멈춤",
                  f"개입률 {멈춤/전체:.0%}", delta_color="off")
        st.caption("나머지 " + str(전체 - 멈춤) + "건은 사람을 거치지 않고 끝났다")
    st.divider()
    st.subheader("새 건 넣기")
    업무 = st.selectbox("업무", list(JOBS), key="새업무")
    후보 = jload(f"{업무}.json")
    고른 = st.selectbox("건", [f'{x["id"]}' for x in 후보], key="새건")
    if st.button("처리 시작", use_container_width=True):
        if not api_key():
            st.error("OPENAI_API_KEY 가 없습니다 (환경변수 또는 키체인 soulmat-openai)")
        else:
            건 = next(x for x in 후보 if x["id"] == 고른)
            건 = {k: v for k, v in 건.items() if not k.startswith(("사람이_", "_"))}
            with st.spinner("판정 중…"):
                r = graph.시작(업무, 건, thread=f'{업무}-{고른}-수동')
            st.success("멈췄습니다 — 아래 대기함에 있습니다" if r["멈췄나"]
                       else f'자동으로 끝났습니다 — {r["결과"]["메시지"]}')
            st.rerun()

대기 = graph.대기목록()
if not 대기:
    st.info("대기 중인 건이 없습니다. 왼쪽에서 새 건을 넣어 보세요.")
    st.stop()

st.subheader(f"대기 {len(대기)}건")
라벨 = {f'{JOBS.get(x["업무"],{}).get("이름","?")} · {x["건"].get("id","?")} '
        f'({len(x["승인화면"].get("멈춘 이유",[])) if x["승인화면"] else 0}가지 이유)': x
        for x in 대기}
고른 = st.radio("건 고르기", list(라벨), label_visibility="collapsed")
항목 = 라벨[고른]
화면 = 항목["승인화면"]

if not 화면:
    st.warning("이 건은 승인 화면 정보를 꺼낼 수 없습니다.")
    st.stop()

왼, 오 = st.columns([3, 2])
with 왼:
    칸("요청 원문", 화면.get("요청 원문", ""))
    칸("핵심 정보", 화면.get("핵심 정보", ""))
    칸("AI 판정", 화면.get("AI 판정", ""))
    칸("근거로 삼은 규정", 화면.get("근거 규정", ""))
    칸("왜 멈췄나", "\n".join("· " + x for x in 화면.get("멈춘 이유", [])), "경고")
    칸("통과시키면", 화면.get("통과시키면", ""), "무게")

with 오:
    st.markdown("#### 답하기")
    답 = st.radio("답", ["승인", "수정후승인", "반려", "다시판정"],
                  captions=["그대로 내보낸다", "고쳐서 내보낸다",
                            "막는다 (사유 필수)", f"지시를 주고 다시 시킨다 (상한 {graph.최대재판정})"],
                  label_visibility="collapsed")
    사유, 지시, 수정 = "", "", None
    if 답 == "반려":
        사유 = st.text_input("반려 사유 *", placeholder="나중에 기준을 고칠 재료가 됩니다")
    if 답 == "다시판정":
        지시 = st.text_input("지시", placeholder="예: 표준 단가로 다시 계산해")
    if 답 == "수정후승인":
        건 = 항목["건"]
        if 항목["업무"] == "견적":
            새 = st.number_input("합계(원)", value=int(건.get("합계", 0)), step=10000)
            수정 = {"합계": int(새)}
        elif 항목["업무"] == "경전":
            새 = st.text_area("고칠 번역", value=건.get("새ko", ""), height=90)
            수정 = {"새ko": 새}
        elif 항목["업무"] == "문의":
            기본 = (화면.get("AI 판정", "").split("보낼 답변: 「") + [""])[-1].rstrip("」")
            수정 = {"답변": st.text_area("보낼 답변", value=기본, height=90)}
        else:
            st.caption("이 업무는 수정 칸이 없습니다 — 승인 또는 반려로 답하세요.")

    막힘 = (답 == "반려" and not 사유.strip())
    if st.button("이 답으로 이어가기", type="primary", disabled=막힘,
                 use_container_width=True):
        with st.spinner("이어가는 중…"):
            r = graph.이어가기(항목["thread"], 답, 사유=사유, 지시=지시, 수정=수정)
        if r["멈췄나"]:
            st.warning("다시 판정했지만 같은 관문에 또 걸려 멈췄습니다.")
        else:
            st.success(r["결과"]["메시지"])
            st.caption(f'경로: {r["결과"]["경로"]}')
        st.rerun()
    if 막힘:
        st.caption("반려하려면 사유를 적어야 합니다.")

with st.expander("이 건이 지나온 길"):
    for l in 항목.get("log", []) or []:
        st.text(l)
    st.caption(f'thread_id: {항목["thread"]} · 다음 단계: {항목["다음단계"]}')
