# -*- coding: utf-8 -*-
"""멈춤 기준 비교표.  `python bench.py`  (**LLM 불필요 · 몇 초**)

교안 3강의 표를 네 업무에 대해 만든다. 관문을 전부 계산 가능한 함수로 짠 덕에
LLM 없이 조합을 바꿔 가며 몇 번이고 다시 잴 수 있다.

읽는 법 — 위로 갈수록 기준이 헐겁고 아래로 갈수록 빡빡하다.
개입률과 놓침은 반대로 움직인다. **둘을 동시에 0으로 만드는 기준은 거의 없다.**
"""
import json
import os

from common import OUT, jload
from jobs import JOBS
from metrics import 재기, 줄


def 조합(업무):
    이름들 = [n for n, _ in JOBS[업무]["관문"]]
    조 = [("기준 없음 (전부 자동)", [])]
    조 += [(f"{n} 하나만", [n]) for n in 이름들]
    for i in range(len(이름들) - 1):
        조.append((f"{이름들[i]}+{이름들[i+1]}", 이름들[i:i + 2]))
    조.append(("전체 관문 (기본)", None))
    조.append(("전부 멈춤", "ALL"))
    return 조


def 돌리기():
    표 = {}
    for 업무 in JOBS:
        건들 = jload(f"{업무}.json")
        봐야 = sum(1 for x in 건들 if x["사람이_봐야하나"])
        print(f"\n■ {업무} — {JOBS[업무]['이름']} · {len(건들)}건 "
              f"(사람이 봐야 하는 건 {봐야}건 = {봐야/len(건들):.0%})")
        print(f"  나가는 것: {JOBS[업무]['나가는 것']}")
        행 = []
        for 라벨, 켠 in 조합(업무):
            if 켠 == "ALL":
                m = {"n": len(건들), "멈춘": len(건들), "개입률": 1.0,
                     "놓침": 0, "헛멈춤": len(건들) - 봐야,
                     "_놓친목록": [], "_헛멈춘목록": []}
            else:
                m = 재기(업무, 건들, 켠관문=켠)
            표시 = 줄(라벨, m, 폭=22)
            if m["놓침"] == 0 and m["헛멈춤"] == 0:
                표시 += "   ← 둘 다 0"
            print("   " + 표시)
            행.append({"기준": 라벨, "켠관문": 켠 if 켠 != "ALL" else "전부",
                       **{k: v for k, v in m.items() if not k.startswith("_")}})
        기본 = 재기(업무, 건들)
        if 기본["_놓친목록"]:
            print("   놓친 건: " + ", ".join(f'{i}({r})' for i, r in 기본["_놓친목록"]))
        if 기본["_헛멈춘목록"]:
            print("   헛멈춘 건: " + ", ".join(f'{i}({"+".join(g)})'
                                              for i, g in 기본["_헛멈춘목록"]))
        표[업무] = 행
    json.dump(표, open(os.path.join(OUT, "bench.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n저장: output/bench.json")
    return 표


if __name__ == "__main__":
    돌리기()
