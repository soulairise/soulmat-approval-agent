# 사람이 승인하는 에이전트 — 소울매트 업무 넷

되돌릴 수 없는 일 **직전에** 에이전트가 멈추고, 사람의 답을 받아 멈춘 자리부터 이어서 실행한다.
기준에 걸리지 않은 건은 사람을 거치지 않고 끝난다.

모두의연구소 「에이전트 팀 꾸리기」 Main Quest 05 · 노드 5806 프로젝트 (2026-09-28).
설계 판단과 측정은 **[REPORT.md](REPORT.md)** 에 있다.

## 한 바퀴 실행 결과

| 업무 | 전체 | 자동 | 멈춤 | 개입률 |
|---|---|---|---|---|
| 경전 수정 반영 | 27 | 16 | 11 | 41% |
| 견적서 발송 | 20 | 12 | 8 | 40% |
| 행사 홍보물 배포 | 20 | 8 | 12 | 60% |
| 고객 문의 자동 답변 | 20 | 8 | 12 | 60% |
| **합계** | **87** | **44** | **43** | **49%** |

**엔진은 하나고 업무는 선언이다.** 업무를 하나 더 얹는 일은 `jobs.py` 에 블록 하나를 더하는 것이다.

## 돌리는 법

파이썬 3.10 이상.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

키는 환경변수 `OPENAI_API_KEY` 또는 macOS 키체인에서 읽는다(`common.api_key()`).
**저장소에 키를 넣지 않는다.**

```bash
security add-generic-password -a "$USER" -s soulmat-openai -w
```

### 키 없이 도는 것부터

```bash
.venv/bin/python tests.py       # 구조 시험 8개 — 가짜 모델로 네트워크 없이 (약 2초)
.venv/bin/python metrics.py     # 지표 자체 검증
.venv/bin/python bench.py       # 멈춤 기준 비교표 — 관문이 계산 가능해서 LLM 이 필요 없다
```

### 키가 필요한 것

```bash
.venv/bin/python graph.py 견적          # 한 건만
.venv/bin/python run_all.py             # 87건 한 바퀴 (약 6분)
.venv/bin/python run_all.py 경전 --무처리 # 멈춘 건을 처리하지 않고 대기함에 남긴다
.venv/bin/streamlit run app.py          # 승인 화면 → http://localhost:8501
```

데이터를 다시 만들 때만:

```bash
.venv/bin/python make_data.py 견적 행사 문의   # 키 불필요
.venv/bin/python make_data.py 경전             # LLM 이 실제로 수정을 제안한다
.venv/bin/python relabel.py                    # 정답 라벨 다시 받기
```

## 파일

| 파일 | 하는 일 |
|---|---|
| `graph.py` | **HITL 엔진.** 준비 → 판정 → 관문 → (interrupt) → 집행/반려/재판정 |
| `jobs.py` | **업무 어댑터 넷.** 나가는 것 · 판정 · 관문 · 집행 · 화면을 선언한다 |
| `metrics.py` | 개입률 · 놓침 · 헛멈춤 |
| `bench.py` | 멈춤 기준 조합을 바꿔 가며 세 값을 비교 (LLM 불필요) |
| `run_all.py` | 87건 한 바퀴 · `output/runs.jsonl` |
| `app.py` | 승인 화면 (streamlit) |
| `tests.py` | 구조 시험 8개 — 재실행 함정·집행 1회·응답 4종·재판정 상한·대기 보관 |
| `make_data.py` · `relabel.py` | 처리 대상 건과 정답 라벨 |
| `data/` | `경전.json`(27) · `견적.json`(20) · `행사.json`(20) · `문의.json`(20) |
| `store/` | 체크포인트(SqliteSaver). **파일이라 프로그램을 껐다 켜도 대기 건이 남는다** |
| `output/` | `runs.jsonl` · `summary.json` · `bench.json` |

## 자료 출처

경전 279절은 소울매트 「에캄」 앱의 경전 데이터(요가수트라 195 · 하타요가 프라디피카 24 ·
바가바드기타 60)에서 가져왔다. 견적 단가는 소울매트 `품목단가표.json`(2026-08-23) 기준이다.
**고객 문의는 전부 지어낸 것이다** — 실제 고객 정보는 쓰지 않았다.
