# -*- coding: utf-8 -*-
"""공통 — 경로·모델·키."""
import json
import os
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "output")
STORE = os.path.join(BASE, "store")
for d in (DATA, OUT, STORE):
    os.makedirs(d, exist_ok=True)

MODEL = "gpt-4o-mini"      # 에이전트의 판정
LABEL_MODEL = "gpt-4.1"    # 정답 라벨. 판정 모델과 다르게 둔다


def api_key():
    """환경변수 → macOS 키체인. 키를 파일·셸 히스토리에 남기지 않는다."""
    if os.getenv("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    try:
        k = subprocess.run(["security", "find-generic-password", "-a", os.environ["USER"],
                            "-s", "soulmat-openai", "-w"],
                           capture_output=True, text=True, check=True).stdout.strip()
        os.environ["OPENAI_API_KEY"] = k
        return k
    except Exception:
        return ""


def ask(prompt, model=None, temperature=0.0):
    from langchain_openai import ChatOpenAI
    api_key()
    m = ChatOpenAI(model=model or MODEL, temperature=temperature,
                   timeout=180, max_retries=3)
    return m.invoke(prompt).content.strip()


def jload(p):
    return json.load(open(os.path.join(DATA, p), encoding="utf-8"))


def jdump(obj, p):
    json.dump(obj, open(os.path.join(DATA, p), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
