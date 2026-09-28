# -*- coding: utf-8 -*-
"""네 업무 전체를 한 바퀴 돌린다.  `python run_all.py [업무...]`

기준에 안 걸린 건은 사람 없이 끝까지 가고, 걸린 건은 멈춰서 대기 목록에 남는다.
멈춘 건은 `--처리` 를 주면 아래 정책대로 답을 넣어 이어간다. 정책은 시연용이고,
실제 판단은 데모 화면(app.py)에서 사람이 한다.

    시연 정책 — AI 판정이 '보류'면 반려, '반영/발송/배포'면 승인.
               단 경전의 고정 역어 위반은 무조건 반려(뜻이 흔들리는 자리라서),
               견적의 표준 단가 미달은 '수정 후 승인'(표준가로 고쳐 보낸다).
"""
import json
import os
import sys
import time

import graph
from common import OUT, jload
from jobs import JOBS


def 정책(업무, 화면, 멈춤사유, 건, 판정):
    관문들 = {x["관문"] for x in 멈춤사유}
    if 업무 == "경전" and "고정역어" in 관문들:
        return {"답": "반려", "사유": "고정 역어를 건드린다 — 앱 전체 표기가 어긋난다"}
    if 업무 == "견적" and "단가" in 관문들 and 건["단가"] < 건["표준단가"]:
        return {"답": "수정후승인", "수정": {"합계": 건["표준단가"] * 건["수량"] * 건["일수"]},
                "사유": "표준 단가로 고쳐 보낸다"}
    if 판정["결정"] in ("보류",):
        return {"답": "반려", "사유": f'AI 도 보류로 봤다 — {판정["근거"][:40]}'}
    return {"답": "승인", "사유": ""}


def main(업무들, 처리=True):
    기록 = open(os.path.join(OUT, "runs.jsonl"), "a", encoding="utf-8")
    요약 = {}
    for 업무 in 업무들:
        건들 = jload(f"{업무}.json")
        자동, 멈춤, 답별 = 0, 0, {}
        t0 = time.time()
        for 건 in 건들:
            thread = f'{업무}-{건["id"]}-{int(t0)}'
            r = graph.시작(업무, 건, thread=thread)
            if r["멈췄나"]:
                멈춤 += 1
                if 처리:
                    답 = 정책(업무, r["승인화면"], r["멈춤사유"], 건, r["판정"])
                    r2 = graph.이어가기(thread, **{k: v for k, v in 답.items()
                                                   if k in ("답", "사유", "지시", "수정")})
                    답별[답["답"]] = 답별.get(답["답"], 0) + 1
                    r["최종"] = r2["결과"]
                    r["담당자답"] = 답
            else:
                자동 += 1
                r["최종"] = r["결과"]
            기록.write(json.dumps({"업무": 업무, "id": 건["id"], **r},
                                  ensure_ascii=False, default=str) + "\n")
            기록.flush()
            print(f'  {업무} {건["id"]} {"멈춤" if r["멈췄나"] else "자동"}'
                  f'{" → " + r.get("담당자답",{}).get("답","") if r["멈췄나"] and 처리 else ""}',
                  flush=True)
        요약[업무] = {"전체": len(건들), "자동": 자동, "멈춤": 멈춤,
                      "개입률": 멈춤 / len(건들), "담당자답": 답별,
                      "초": round(time.time() - t0, 1)}
    기록.close()

    print("\n── 실행 결과 ──")
    print("| 업무 | 전체 | 자동 | 멈춤 | 개입률 | 담당자 처리 |")
    print("|---|---|---|---|---|---|")
    합 = {"전체": 0, "자동": 0, "멈춤": 0}
    for 업무, v in 요약.items():
        for k in 합:
            합[k] += v[k]
        답 = " · ".join(f"{k} {n}" for k, n in v["담당자답"].items()) or "-"
        print(f'| {JOBS[업무]["이름"]} | {v["전체"]} | {v["자동"]} | {v["멈춤"]} | '
              f'{v["개입률"]:.0%} | {답} |')
    print(f'| **합계** | **{합["전체"]}** | **{합["자동"]}** | **{합["멈춤"]}** | '
          f'**{합["멈춤"]/합["전체"]:.0%}** | |')
    json.dump(요약, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n저장: output/runs.jsonl · output/summary.json")


if __name__ == "__main__":
    골라 = [a for a in sys.argv[1:] if not a.startswith("-")] or list(JOBS)
    main(골라, 처리="--무처리" not in sys.argv)
