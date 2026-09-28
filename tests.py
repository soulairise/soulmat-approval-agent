# -*- coding: utf-8 -*-
"""엔진이 교안의 요구를 실제로 지키는지 확인한다.  `python tests.py`  (키 불필요)

LLM 은 가짜로 갈아 끼운다. 확인하려는 것은 판단의 품질이 아니라 **구조**다.
"""
import os
import sqlite3
import sys

import graph
import jobs

os.environ.setdefault("OPENAI_API_KEY", "sk-테스트용-가짜")

호출 = {"승인대기": 0, "집행": 0, "판정": 0}


def 가짜판정(건):
    호출["판정"] += 1
    return {"결정": "발송", "근거": "가짜", "근거규정": "가짜", "답변": "가짜 답변"}


def 세는집행(원래):
    def f(건, 판정, 응답):
        호출["집행"] += 1
        return 원래(건, 판정, 응답)
    return f


def 세는승인대기(원래):
    def f(s):
        호출["승인대기"] += 1
        return 원래(s)
    return f


def 준비(tmpdb):
    for v in jobs.JOBS.values():
        v["판정"] = 가짜판정
    jobs.JOBS["견적"]["집행"] = 세는집행(jobs.견적_집행)
    graph.n_승인대기 = 세는승인대기(graph.n_승인대기)
    graph.DB = tmpdb
    for k in 호출:
        호출[k] = 0


멈추는건 = {"id": "T1", "업무": "견적", "거래처": "새거래처", "신규거래처": True,
            "품목": "요가매트 1일 렌트", "표준단가": 5000, "단가": 4000,
            # 합계는 한도(100만)를 **넘겨야** 한다. 딱 100만으로 두면 '초과' 가 아니라
            # 관문이 안 걸린다 — 처음에 여기서 틀렸다. 경계값은 시험으로 못 박는다.
            "수량": 60, "일수": 5, "합계": 1_200_000, "요청": ""}
자동건 = {**멈추는건, "id": "T2", "거래처": "광운대학교", "신규거래처": False,
          "단가": 5000, "수량": 10, "일수": 1, "합계": 50_000}


def t1_자동():
    r = graph.시작("견적", 자동건)
    assert not r["멈췄나"], "기준에 안 걸린 건은 멈추면 안 된다"
    assert r["결과"]["경로"] == "자동"
    return "기준에 안 걸린 건은 사람을 거치지 않고 끝난다"


def t2_멈춤과재개():
    r = graph.시작("견적", 멈추는건)
    assert r["멈췄나"], "기준에 걸린 건은 멈춰야 한다"
    assert r["결과"] is None, "멈춘 시점에 집행이 일어나면 안 된다"
    화면 = r["승인화면"]
    for 칸 in ("요청 원문", "핵심 정보", "AI 판정", "근거 규정", "통과시키면", "멈춘 이유"):
        assert 화면.get(칸), f"승인 화면에 「{칸}」 이 없다"
    assert len(r["멈춤사유"]) == 3, f'관문 셋이 다 걸려야 한다: {r["멈춤사유"]}'
    # 경계값: 딱 한도면 '초과' 가 아니다
    from jobs import 견적_금액
    assert 견적_금액({"합계": 1_000_000}, None) is None
    assert 견적_금액({"합계": 1_000_001}, None)
    r2 = graph.이어가기(r["thread"], "승인")
    assert not r2["멈췄나"] and r2["결과"]["발송"], "재개하면 집행까지 가야 한다"
    return "되돌릴 수 없는 일 직전에 멈추고, 답을 받아 이어서 실행한다"


def t3_묻는단계는다시돈다():
    """교안이 경고한 성질. 멈춘 단계는 재개할 때 처음부터 한 번 더 실행된다."""
    before = 호출["승인대기"]
    r = graph.시작("견적", {**멈추는건, "id": "T3"})
    중간 = 호출["승인대기"] - before
    graph.이어가기(r["thread"], "승인")
    총 = 호출["승인대기"] - before
    assert 중간 == 1 and 총 == 2, f"멈춘 단계가 다시 안 돌았다: {중간}, {총}"
    return (f"멈춘 단계(승인대기)는 재개 때 다시 실행된다 ({총}회) — "
            "그래서 이 노드 안에 바깥으로 나가는 동작을 두면 두 번 나간다")


def t4_집행은한번뿐():
    """t3 의 성질에도 불구하고 실제 발송은 한 번이어야 한다."""
    before = 호출["집행"]
    r = graph.시작("견적", {**멈추는건, "id": "T4"})
    assert 호출["집행"] == before, "멈춘 동안 집행이 일어났다"
    graph.이어가기(r["thread"], "승인")
    assert 호출["집행"] == before + 1, f"집행이 {호출['집행']-before}번 일어났다"
    return "승인대기가 두 번 돌아도 집행은 정확히 한 번 — 부작용을 집행 노드에만 뒀기 때문"


def t5_네답():
    for 답, 기대 in (("승인", "발송"), ("수정후승인", "발송"),
                     ("반려", "반려"), ("다시판정", "발송")):
        r = graph.시작("견적", {**멈추는건, "id": f"T5{답}"})
        r2 = graph.이어가기(r["thread"], 답, 사유="규정 밖", 지시="절반으로",
                            수정={"합계": 500_000})
        if 답 == "다시판정":
            assert r2["멈췄나"], "다시판정하면 같은 관문에 또 걸려 다시 멈춘다"
            r2 = graph.이어가기(r["thread"], "승인")
        assert r2["결과"].get(기대), f'{답} → {기대} 가 안 됐다: {r2["결과"]}'
        if 답 == "수정후승인":
            assert r2["결과"]["금액"] == 500_000, "수정값이 집행에 반영되지 않았다"
    return "승인 / 수정후승인 / 반려(사유) / 다시판정 네 답이 모두 다른 길로 간다"


def t6_재판정상한():
    r = graph.시작("견적", {**멈추는건, "id": "T6"})
    for _ in range(graph.최대재판정 + 2):
        if not r["멈췄나"]:
            break
        r = graph.이어가기(r["thread"], "다시판정", 지시="다시")
    assert not r["멈췄나"], "상한을 넘겨도 계속 돈다"
    assert r["결과"].get("반려"), "상한에 닿으면 반려로 떨어져야 한다"
    return f"다시판정은 {graph.최대재판정}번까지만 — 넘으면 반려로 떨어진다"


def t7_대기건이남는다():
    """프로그램을 껐다 켜도 대기 건이 살아 있어야 한다 (파일 체크포인터)."""
    graph.시작("견적", {**멈추는건, "id": "T7"})
    대기 = [x for x in graph.대기목록() if x["건"].get("id") == "T7"]
    assert 대기, "대기 목록에 안 뜬다"
    assert 대기[0]["승인화면"], "대기 건에서 승인 화면을 못 꺼낸다"
    assert os.path.exists(graph.DB), "체크포인트가 파일로 남지 않았다"
    크기 = os.path.getsize(graph.DB)
    return f"대기 건이 파일에 남는다 ({os.path.basename(graph.DB)} {크기:,}바이트)"


def t8_관문은계산가능():
    """관문은 LLM 을 부르지 않는다 — 판정 호출 수가 늘지 않는지로 확인한다."""
    before = 호출["판정"]
    for 업무 in jobs.JOBS:
        from common import jload
        for 건 in jload(f"{업무}.json")[:3]:
            jobs.멈출까(업무, 건, {"결정": "x", "근거": "x", "근거규정": "x", "답변": ""})
    assert 호출["판정"] == before, "관문이 판정(LLM)을 불렀다"
    return "관문 13개 전부 LLM 없이 돈다 — 값을 바꿔 가며 비교할 수 있다"


if __name__ == "__main__":
    import tempfile
    tmp = os.path.join(tempfile.mkdtemp(), "t.sqlite")
    준비(tmp)
    시험 = [t1_자동, t2_멈춤과재개, t3_묻는단계는다시돈다, t4_집행은한번뿐,
            t5_네답, t6_재판정상한, t7_대기건이남는다, t8_관문은계산가능]
    실패 = 0
    for t in 시험:
        try:
            print(f"  ✓ {t.__name__:24} {t()}")
        except AssertionError as e:
            실패 += 1
            print(f"  ✗ {t.__name__:24} {e}")
        except Exception as e:
            실패 += 1
            print(f"  ✗ {t.__name__:24} {type(e).__name__}: {e}")
    print(f"\n{len(시험)-실패}/{len(시험)} 통과")
    sys.exit(1 if 실패 else 0)
