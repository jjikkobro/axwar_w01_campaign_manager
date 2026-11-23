# W01 최종 수정 완료 보고

검증일: 2026-11-09 · v0.2. 온라인 재배포 없이 로컬 PostgreSQL·HTTP 서버에서 검증했습니다.

## 변경 파일 목록

| 파일 | 변경 내용 |
|---|---|
| app/finance.py | 신규: 4개 현금 시나리오·연체·주별 비교·결재 규칙·작업 정의 |
| app/workflow.py | 신규: 대기 건 재판정·작업 생성/완료·변경/유지 이력 |
| app/drafts.py | 신규: 근거 패킷·선택적 AI 초안, 승인/상태 변경 분리 |
| app/domain.py | 승인 유형·입력 필드 제한·재무 차단·조건부 승인 연결 |
| app/db.py | 재무 결정/작업 마이그레이션·출처 정규화 |
| app/server.py | 재무 확정/연체 회신/약정 분류/초안 API·원본 대조·이력 |
| data/seed.json | 공식 전망을 부서 주장으로 추가, 원본 스냅샷 출처 표시 |
| scripts/seed.py | 기존 자료 보존·작업 초기화 |
| scripts/verify_scenarios.py | 신규: 독립 로컬 DB에서 네 시연 자동 실행·보고서 저장 |
| web/index.html, web/app.js | 재무 결정/작업 화면·6종 출처·요청/회신/승인 UI |
| tests/test_domain.py, tests/test_finance.py, tests/test_drafts.py | 회귀·권한 경계·AI 응답 어댑터 검증 |
| docs/guides/PROTOTYPE.md, CHANGELOG.md | 사용법·가정·규칙·수정 이력 갱신 |
| docs/verification/system/SCENARIO_RESULTS.json, REGRESSION_RESULTS.json, TEST_OUTPUT.txt | 실행·회귀 증거 |

기존 미커밋 프로토타입 기반 파일(Dockerfile, requirements.txt, .dockerignore, web/style.css·글꼴 등)도 최종 소스에 포함됩니다. 이번 요청의 핵심 변경과 위 표에서 구분했습니다. 원본·설정 폴더·.gitignore는 변경하지 않았습니다.

## 네 가지 실제 실행 결과

입력 날짜·금액·회신은 교육용 시연입니다. DB 저장·계산·상태 전환은 실제 코드가 수행했습니다.

| 시연 | 입력과 조건 | 상태 변화·결과 | 이력 |
|---|---|---|---|
| 정상 | 9/21 신규 지급 100만원, 하회구간 밖 | SCM 전결 → 사람 승인 → 모의 발주·회신 → 회신 기록 완료 | 사건 34개 · JSON에 원문 |
| 확장·부서영향 | 7/21 더마 신규 지급 100만원, 평시 SCM과 충돌 | CEO 상신 → 재무 의견 → 조건부 승인·실행 차단 → 반려·보완 작업 → 사람 재승인 → 회신 기록 완료 | 사건 42개 · JSON에 원문 |
| 변경 | 8/25·7/21 두 승인 대기 건, 연체 AR 6건의 7/1 회수 모의 회신 후 시나리오 변경 | 승인 대기 → 재검토 필요. 8/25는 CEO→SCM, 7/21은 CEO 유지. 변경/유지 근거 모두 기록 | 사건 61개 · JSON에 원문 |
| 정보 부족 | 유출일 미입력 → 재무가 7/21 신규 100만원 확인 | 판정 불가·확인 작업 → 상신 차단 → 재무 회신 → 검토 중·CEO 상신 대상으로 재판정 | 사건 12개 · JSON에 원문 |

전체 입력·작업·상태·재무 결정·결재선 변경 전후: [SCENARIO_RESULTS.json](../../verification/system/SCENARIO_RESULTS.json). 상신과 승인은 자동 확정되지 않았으며 승인권자 역할의 명시적 호출로만 수행했습니다.

## 회귀 테스트 결과

31개 통과 · 실패 0 · 오류 0. [전체 출력](../../verification/system/TEST_OUTPUT.txt), [기계 판독 결과](../../verification/system/REGRESSION_RESULTS.json).

| 연체채권 / 채무 | 최저잔액(원) | 하회 영업일 구간 |
|---|---:|---|
| 7/1 회수 가정 / 7/1 지급 가정 | 1,647,835,595 | 2026-07-21 ~ 2026-08-21 |
| 7/1 회수 가정 / 지급일 미확인으로 미반영 | 2,102,010,710 | 2026-07-21 ~ 2026-08-21 |
| 회수일 미확인으로 유입 제외 / 7/1 지급 가정 | 1,467,664,440 | 2026-07-21 ~ 2026-08-28 |
| 회수일 미확인으로 유입 제외 / 지급일 미확인으로 미반영 | 1,921,839,555 | 2026-07-21 ~ 2026-08-21 |

기초잔액 5,148,063,540원 · 발주 3,749,760,000원 · AP 중복 차감 0건 · 합집합 7/21~8/28.

원본 데이터·보호 설정 76개 파일의 전후 SHA-256 일치. 원본 파일은 새 가정이나 회신으로 덮어쓰지 않았습니다.

## 실제 작동 / 모의 처리 / 설계 단계

| 구분 | 범위 |
|---|---|
| 실제 작동 | PostgreSQL 영속 저장, 현금 4종, 합집합/확정 재판정, 날짜 분리, 작업 생성·완료, 입력 검증, 재무 결정 이력, 승인 유형 규칙, 상신 패킷, 조건부 실행 차단 |
| 모의 처리 | 공급자·회수 확인 회신, 승인권자 역할의 승인·조건부·반려, 외부 전송 없는 발주 기록, AI API 응답 어댑터 테스트 |
| 연결 코드 구현·실연결 미검증 | AI_BASE_URL/AI_API_KEY/AI_MODEL을 사용하는 Responses API 초안. 실제 키·유료 호출 없음. 미설정 시 규칙 기반 초안으로 표시 |
| 설계/후속 범위 | 실제 개인별 인증·부서 권한, 은행·공급자 실연동, PDF 자동 추출, 분할입고 다중 일정 |
| 선택 기능 미구현 | 기안 25건 일괄 분석·날짜 역전 12건·3영업일 상신기준일. 해당 회귀값은 이번 완료 범위에서 제외 |

## 유의할 결과 해석

- 고정 현금값은 회신 전 원본 스냅샷 기준입니다. 확인 회신 이후에는 회신이 우선하므로 네 시나리오 결과가 일부 같아질 수 있습니다.
- 공식 전망의 발주 누락은 추정이며 확정 원인이 아닙니다. 주차값 마감 시점도 추가 확인 대상입니다.
- 평시 SCM이라는 결재선이 공급 충분·현금 안전 또는 자동 집행 허용을 뜻하지 않습니다.
- 역할 선택은 시연 기능입니다. 실제 계정별 권한을 구현했다고 주장하지 않습니다.
- 온라인 배포·운영 DB 변경은 이번 작업에서 실행하지 않았습니다.

## Git 저장 파일 전체 목록

기존 미커밋 프로토타입 기반 파일을 포함한 최초 저장 목록입니다.

- `.dockerignore`
- `Dockerfile`
- `app/__init__.py`
- `app/db.py`
- `app/domain.py`
- `app/drafts.py`
- `app/finance.py`
- `app/server.py`
- `app/workflow.py`
- `axhub.yaml`
- `data/seed.json`
- `docs/history/CHANGELOG.md`
- `docs/history/reports/FINAL_REPORT.md`
- `docs/guides/PROTOTYPE.md`
- `docs/verification/system/REGRESSION_RESULTS.json`
- `docs/verification/system/SCENARIO_RESULTS.json`
- `docs/verification/system/TEST_OUTPUT.txt`
- `requirements.txt`
- `scripts/migrate.py`
- `scripts/seed.py`
- `scripts/verify_scenarios.py`
- `tests/test_domain.py`
- `tests/test_drafts.py`
- `tests/test_finance.py`
- `web/app.js`
- `web/fonts/NanumGothic-Regular.ttf`
- `web/fonts/OFL.txt`
- `web/index.html`
- `web/style.css`
