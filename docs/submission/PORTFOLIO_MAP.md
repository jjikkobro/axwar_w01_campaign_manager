# 포트폴리오 읽기 안내

## 먼저 읽기

1. [설계 설명 7개 문항](DESIGN_EXPLANATION.md): 선택한 문제, 부서 간 영향, 원본·가정·모의 처리 구분, 실제 작동 범위.
2. [루트 README](../../README.md): 프로젝트 소개, 테스트·배포 구성, 구현·모의·후속 설계, 따라 해 보기.
3. [전체 문서 색인](../README.md): 기능 설명·원본 대조·검증 기록.

## 생각과 구현을 함께 보기

| 중점 | 구현 | 설명·증거 |
|---|---|---|
| 기획 단계에서 재고·현금 제약 확인 | `app/marketing.py`, `app/scm.py`, `app/finance.py` | [업무 흐름 확장](../features/workflow/W01_UPGRADE.md) |
| 지급일·회수 확인에 따른 결재선 재판정 | `app/finance_review.py`, `app/finance_advice.py` | [재무 판단](../features/finance/FINANCE_ADVICE.md) |
| 반려·조건부 승인·재검토와 후속 작업 연결 | `app/workflow.py`, `app/execution.py` | [시나리오 결과](../verification/system/SCENARIO_RESULTS.json) |
| AI 초안과 사람의 결정 분리 | `app/drafts.py`, `app/review_ai.py`, `app/prompt_settings.py` | [GPT 검토](../features/administration/GPT_REVIEW.md) |
| 현업이 산식을 시험하고 적용 | `app/formulas.py` | [산식 설정](../features/administration/FORMULA_SETTINGS.md) |
| 원본과 실제 화면 대조 | `web/`, `W01_screens/` | [화면 검토 색인](../screen-reviews/README.md) |

## 자료 출처와 기여 구분

`01_참가자_배포용/`는 대회에서 제공한 문제·가상기업 원본 자료입니다. 참가자가 제작한 코드·추가 설계·설명·검증 결과와 구분합니다. 앱에서 사용하지 않는 고객별 재구매 CSV 한 파일은 사용자의 선택에 따라 제외했고 [자료 개요](DATA_PROVENANCE.md)를 남겼습니다. `W01_screens/`는 화면 시안·참조 자료이며, 동작 코드와 동일시하지 않습니다.

`data/`는 실행을 위한 원본 추출값·참고 계산입니다. 원본 자료와 원본 식별자·출처·가정 표시를 함께 확인합니다. 실제 개인·기업의 운영 데이터로 해석하지 않습니다.

## 검증 기록을 읽을 때

`tests/`는 자동 테스트 코드, `scripts/verify_*`는 실행 조건이 있는 검증 도구, `docs/verification/`은 과거 실행 결과입니다. 과거 통과 수를 현재 재실행 결과로 주장하지 않습니다. 일부 시나리오는 DB를 변경하므로 별도 테스트 DB에서 실행합니다. 실제 외부 승인·발주·입금이 수행됐다는 증거는 아닙니다.
