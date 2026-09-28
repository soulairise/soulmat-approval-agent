# -*- coding: utf-8 -*-
"""HITL 엔진 — 되돌릴 수 없는 일 직전에 멈추고, 사람의 답을 받아 이어서 실행한다.

  START → 준비 → 판정 → 관문 ─┬─ 통과 ─────────────────→ 집행 → END
                              └─ 멈춤 → interrupt → 응답
                                     ├ 승인 / 수정후승인 ─→ 집행 → END
                                     ├ 반려(사유) ────────→ 반려처리 → END
                                     └ 다시판정(상한 2) ──→ 판정

**관문 노드 안에는 interrupt 말고 아무 부작용도 두지 않는다.**
멈춘 단계는 재개할 때 처음부터 한 번 더 실행된다 — 체크포인트에 '몇 번째 줄'이 아니라
'단계 이름'만 적히기 때문이다. 관문 안에서 알림을 보내면 담당자가 답한 순간 같은 알림이
두 번 나간다. 그래서 바깥으로 나가는 동작은 전부 `집행` 노드에만 둔다.
`tests.py` 가 이 성질을 실제로 확인한다.

체크포인터는 파일(SqliteSaver)이다. 승인 대기는 초 단위가 아니라서, 담당자가 퇴근한 사이
프로그램이 꺼져도 대기 건이 남아 있어야 한다.
"""
import json
import operator
import os
import sqlite3
import time
from typing import Annotated, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from common import OUT, STORE
from jobs import JOBS, 멈출까

DB = os.path.join(STORE, "checkpoints.sqlite")
최대재판정 = 2


class S(TypedDict, total=False):
    업무: str
    건: dict
    판정: dict
    멈춤사유: list
    응답: dict
    결과: dict
    재판정: int
    켠관문: list
    log: Annotated[list, operator.add]


def n_준비(s):
    return {"log": [f'[준비] {JOBS[s["업무"]]["이름"]} · {s["건"]["id"]}'],
            "재판정": s.get("재판정", 0)}


def n_판정(s):
    판정 = JOBS[s["업무"]]["판정"](s["건"])
    return {"판정": 판정, "log": [f'[판정] {판정["결정"]} — {판정["근거"][:50]}']}


def n_관문(s):
    사유 = 멈출까(s["업무"], s["건"], s["판정"], s.get("켠관문"))
    return {"멈춤사유": 사유,
            "log": [f'[관문] ' + (f'멈춤 {len(사유)}건: '
                                  + ", ".join(x["관문"] for x in 사유)
                                  if 사유 else "통과 — 사람을 거치지 않는다")]}


def 갈림(s):
    return "승인대기" if s.get("멈춤사유") else "집행"


def n_승인대기(s):
    """**이 노드 안에는 interrupt 말고 아무것도 두지 않는다.**
    재개하면 이 함수가 처음부터 다시 돌기 때문이다."""
    업무 = JOBS[s["업무"]]
    화면 = 업무["화면"](s["건"], s["판정"])
    응답 = interrupt({
        "id": s["건"]["id"], "업무": s["업무"], "업무이름": 업무["이름"],
        "멈춘 이유": [x["사유"] for x in s["멈춤사유"]],
        **화면,
        "고를 수 있는 답": ["승인", "수정후승인", "반려", "다시판정"],
    })
    if isinstance(응답, str):
        응답 = {"답": 응답}
    return {"응답": 응답, "log": [f'[승인] 담당자 답변: {응답.get("답")}']}


def 응답갈림(s):
    답 = (s.get("응답") or {}).get("답", "반려")
    if 답 in ("승인", "수정후승인"):
        return "집행"
    if 답 == "다시판정" and s.get("재판정", 0) < 최대재판정:
        return "재판정"
    return "반려처리"


def n_재판정(s):
    지시 = (s.get("응답") or {}).get("지시", "")
    n = s.get("재판정", 0) + 1
    건 = dict(s["건"])
    건["_다시판정지시"] = 지시
    return {"건": 건, "재판정": n,
            "log": [f'[재판정 {n}/{최대재판정}] 지시: {지시 or "(없음)"}']}


def n_집행(s):
    """**바깥으로 나가는 동작은 전부 여기에만 있다.**"""
    응답 = s.get("응답") or {"답": "자동"}
    결과 = JOBS[s["업무"]]["집행"](s["건"], s["판정"], 응답)
    결과["경로"] = "자동" if 응답["답"] == "자동" else f'사람({응답["답"]})'
    return {"결과": 결과, "log": [f'[집행] {결과["메시지"]}']}


def n_반려처리(s):
    사유 = (s.get("응답") or {}).get("사유", "(사유 없음)")
    return {"결과": {"반려": True, "사유": 사유, "경로": "사람(반려)",
                     "메시지": f"반려했다 — {사유}"},
            "log": [f'[반려] {사유}']}


def build(checkpointer):
    g = StateGraph(S)
    for 이름, fn in [("준비", n_준비), ("판정", n_판정), ("관문", n_관문),
                     ("승인대기", n_승인대기), ("재판정", n_재판정),
                     ("집행", n_집행), ("반려처리", n_반려처리)]:
        g.add_node(이름, fn)
    g.add_edge(START, "준비")
    g.add_edge("준비", "판정")
    g.add_edge("판정", "관문")
    g.add_conditional_edges("관문", 갈림, ["승인대기", "집행"])
    g.add_conditional_edges("승인대기", 응답갈림, ["집행", "재판정", "반려처리"])
    g.add_edge("재판정", "판정")
    g.add_edge("집행", END)
    g.add_edge("반려처리", END)
    return g.compile(checkpointer=checkpointer)


# ── 실행 도우미 ────────────────────────────────────────────────────
def 커넥션():
    """SqliteSaver 는 컨텍스트 매니저라 연결을 직접 쥔다. 스레드 검사는 끈다 —
    streamlit 이 재실행마다 다른 스레드에서 같은 연결을 만진다."""
    conn = sqlite3.connect(DB, check_same_thread=False)
    return conn, SqliteSaver(conn)


def 시작(업무, 건, 켠관문=None, thread=None):
    """한 건을 넣는다. 멈추면 승인 화면을, 끝나면 결과를 돌려준다."""
    conn, cp = 커넥션()
    try:
        app = build(cp)
        cfg = {"configurable": {"thread_id": thread or f'{업무}-{건["id"]}'}}
        out = app.invoke({"업무": 업무, "건": 건, "켠관문": 켠관문}, cfg)
        return _정리(out, cfg["configurable"]["thread_id"])
    finally:
        conn.close()


def 이어가기(thread, 답, 사유="", 지시="", 수정=None):
    """멈춘 건을 담당자의 답으로 이어간다."""
    conn, cp = 커넥션()
    try:
        app = build(cp)
        cfg = {"configurable": {"thread_id": thread}}
        out = app.invoke(Command(resume={"답": 답, "사유": 사유,
                                         "지시": 지시, "수정":수정}), cfg)
        return _정리(out, thread)
    finally:
        conn.close()


def _정리(out, thread):
    멈춤 = out.get("__interrupt__")
    화면 = None
    if 멈춤:
        v = 멈춤[0].value if hasattr(멈춤[0], "value") else 멈춤[0]
        화면 = v
    return {"thread": thread, "멈췄나": bool(멈춤), "승인화면": 화면,
            "결과": out.get("결과"), "판정": out.get("판정"),
            "멈춤사유": out.get("멈춤사유") or [], "log": out.get("log") or []}


def 대기목록():
    """체크포인터에 남아 있는 건 중 아직 안 끝난 것. 다음에 실행할 단계가 있으면 대기 중이다."""
    conn, cp = 커넥션()
    try:
        app = build(cp)
        대기 = []
        # thread 목록은 체크포인트 테이블에서 바로 읽는다
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints").fetchall()]
        except sqlite3.OperationalError:
            return []
        for t in ids:
            st = app.get_state({"configurable": {"thread_id": t}})
            if st.next:                      # 다음에 실행할 단계가 있으면 대기
                v = st.tasks[0].interrupts[0].value if (st.tasks and st.tasks[0].interrupts) else None
                vals = st.values or {}
                대기.append({"thread": t, "다음단계": list(st.next), "승인화면": v,
                             "건": vals.get("건", {}), "업무": vals.get("업무", ""),
                             "판정": vals.get("판정", {}), "log": vals.get("log", [])})
        return 대기
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    from common import jload
    업무 = sys.argv[1] if len(sys.argv) > 1 else "견적"
    건들 = jload(f"{업무}.json")
    r = 시작(업무, 건들[0])
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str)[:1500])
