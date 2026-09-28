# -*- coding: utf-8 -*-
"""경전 수정안의 정답 라벨을 다시 받는다.  `python relabel.py`

처음 라벨은 판정 모델과 다른 모델(gpt-4.1)에게 맡겼는데 '이유' 칸을 자주 빠뜨렸고,
무엇보다 「순수의식 → 순수 의식」을 자동 통과로 놓았다. puruṣa 의 고정 역어를 건드리는
수정이라 뜻이 흔들릴 수 있는 자리다. 라벨도 틀린다는 것을 그대로 남기고,
사람이 27건을 전부 읽고 확인했다 — 뒤집을 만한 판정은 없었다(2026-09-28).
"""
import json
import re

from common import LABEL_MODEL, ask, jdump, jload

프롬프트 = """너는 요가 경전 데이터의 최종 검수자다. 아래는 기계가 낸 한국어 번역 수정안이다.

각 수정안에 대해 판정하라 — **이 수정이 그대로 반영되면 수련자가 읽는 뜻이 달라지는가?**

'예'로 두어야 하는 경우:
- 낱말이 다른 낱말로 바뀐다 (띄어쓰기만 달라지는 것도 포함. 굳어진 역어일 수 있다)
- 문장의 주체·대상·시제·양태(가능/당위)가 달라진다
- 판단이 서지 않는다
'아니오'로 두어야 하는 경우:
- 명백한 오탈자를 바로잡는다
- 쉼표·가운뎃점처럼 뜻을 바꾸지 않는 기호만 손본다

{항목}

JSON 배열만 출력하라. **이유는 반드시 채운다.**
[{{"ref":"I.2","사람이_봐야하나":true,"이유":"'-ㄹ 수 있다'가 붙어 양태가 달라진다"}}]"""


def _json(s):
    m = re.search(r"\[.*\]", s, re.S)
    return json.loads(m.group(0)) if m else []


def main():
    건 = jload("경전.json")
    라벨 = {}
    for i in range(0, len(건), 9):
        덩이 = 건[i:i + 9]
        항목 = "\n".join(
            f'- {x["id"]} ({x["ref"]}): 「{x["옛ko"]}」 → 「{x["새ko"]}」' for x in 덩이)
        for x in _json(ask(프롬프트.format(항목=항목), model=LABEL_MODEL)):
            # ref 가 "S01 (III.14)" 처럼 돌아온다. 정확히 같기를 기대하면 하나도 안 맞는다.
            ref = str(x.get("ref", ""))
            for c in 덩이:
                if c["id"] in ref or ref in (c["id"], c["ref"]):
                    라벨[c["id"]] = x
                    break
        print(f"  {i//9+1}/{-(-len(건)//9)} · 누적 {len(라벨)}/{len(건)}", flush=True)

    빠짐 = 0
    for c in 건:
        lb = 라벨.get(c["id"])
        if lb is None:
            빠짐 += 1
            continue
        # "예"/"아니오" 문자열로 돌아온다. bool("아니오") 는 True 라 그대로 쓰면 전부 참이 된다.
        v = lb.get("사람이_봐야하나", True)
        c["사람이_봐야하나"] = (v if isinstance(v, bool)
                              else str(v).strip() not in ("아니오", "false", "False", "no", "N"))
        c["_라벨근거"] = [str(lb.get("이유") or "이유 없음")]
    jdump(건, "경전.json")
    봐야 = sum(1 for x in 건 if x["사람이_봐야하나"])
    print(f"\n{len(건)}건 · 봐야 {봐야}건({봐야/len(건):.0%}) · 라벨 못 받은 건 {빠짐}건")


if __name__ == "__main__":
    main()
