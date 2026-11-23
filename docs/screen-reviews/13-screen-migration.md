# W01_screens 전체 마이그레이션 · 2026-11-10

사용자가 검토를 마친 `W01_screens` 전체 적용을 지시했으므로 기존의 화면별 컨펌 대기를 이번 13개 화면 일괄 적용 승인으로 갱신했다. 목표는 현업의 역할·업무 순서·승인권한을 보존하면서 시안을 서버 저장·계산·사건 이력에 연결하는 것이다. 화면 열람·AI 초안·기한 경과로 결정을 자동 확정하지 않는다.

## 화면별 적용

| 역할 | 화면 | 실제 연결 |
|---|---|---|
| 마케팅 | MKT_1_Proposal | 원본 기안/캠페인 참조, 캠페인명·매체·기간·예산·정산·기한·성과 근거, 선택 SKU 수요, DB 저장·SCM 제출 |
| 마케팅 | MKT_2_Wait | 제출 건의 현재 단계·약정별 결정·발주/회신·담당 작업 조회, 문의·보완·독촉·회수 요청 기록 |
| 마케팅 | MKT_3_Hold | 반려/보류 사유·조건, 상대방 통보 증빙, 재작성 또는 철회, 이전 사건 보존 |
| 마케팅 | MKT_4_Close | 승인·회신·재판정 대조, 기간 재고 검산, 일정표·상품·요청액·통보 기록, 검토 회차 종료 |
| SCM | SCM_1_Check | 다중 SKU 재고·완료 4주 판매·커버·일별 공급, 기존 PO 회신, 목표·MOQ·단가·신규 발주안, 부서 확인, 재무 인계 |
| SCM | SCM_2_WaitApproval | 재무/약정별 승인 현황, 다음 내 업무, 문의·보완·독촉 |
| SCM | SCM_3_PO | 유효 승인과 수량·단가·금액·지급일 일치 확인, 발주 ID·희망 입고일·회신 기한·전달 방식 저장 |
| SCM | SCM_4_WaitReply | 전달 발주·미회신 작업·진행 현황, 확인 요청, ⑥ 진입 |
| SCM | SCM_5_Receipt | 발주별 분할 수량·판매가능일·확정 지급일 입력, 지연·수량 불일치 감지, 마케팅 회신, 변경 시 재판정 |
| 재무 | FIN_1_Review | 4개 현금 시나리오·원본/공식 전망 비교·연체 작업·성과, 약정별 금액/유출일/현금 범위, 규정 라우팅·상신 |
| 재무 | FIN_2_Wait | 약정별 결재 감시·재전망 진입·수시 확인 요청, 회신 변경 재판정 |
| 승인권자 | APR_1_CEO | CEO/이사회 경로의 약정만 승인/조건부/보류/반려, 사유·조건·범위·버전 고정 |
| 승인권자 | APR_2_Normal | SCM·마케팅·Masil 대표 경로별 본인 몫 결정, 기안자 자기 승인 차단, 그룹 보고 후속 작업 |

모든 화면은 동일 기안 ID·버전을 사용한다. 상단 역할별 페이지 선택과 7단계 진행 흐름은 서버 기록에서 계산한다. 평시 결재는 APR_2_Normal, CEO 결재는 APR_1_CEO로 분기한다. 대기 화면은 클릭만으로 다음 단계가 진행되지 않는다. 부서 문의는 지정 담당 작업으로 생성하고 그 부서의 회신·근거로 완료한다.

## 원본과 다르게 처리한 시안 요소 및 근거

- 화면마다 별도였던 PLAN-026~028·금액·날짜·추천·모의 전환 버튼을 런타임 데이터로 사용하지 않는다. `W01_screens/README.md` §3의 이식 지침에 따라 실제 기안/부서 자료와 연결했다.
- 시안 JSON의 주간 평균 14개는 시스템의 **기준일 현재 완료된 최근 4주** 값과 다르다. 내장 평균을 복사하지 않고 원본 판매 행으로 계산한다. 비교 값·주차는 [원본 대조 기록](../verification/screen-reviews/13-screen-source-audit.json)에 남겼다.
- MOQ 배수 강제는 원본 근거가 없으므로 적용하지 않고 최소 수량만 검증한다. 기존 SCM 검토의 원본 산식·확인 회신 단일 반영을 유지한다.
- 시안의 고정 하회구간 8/29·최저 8.63억과 고정 반려 추천은 사용하지 않는다. 기본 합집합 영업일 종료는 8/28이며, 실제 값은 같은 입력/시나리오에서 산출한다. 성과·비용도 원본 표본으로 계산한다.
- 조건부 승인은 전달 권한이 아니다. 조건 충족 증빙과 사람 재승인 후에만 실행한다. 지급일·수량·요청액·기간·상품 변경은 해당 원본 검토·재상신 절차를 거친다.
- SKU 수요는 기안에서 선택 입력이다. 미입력은 0수요로 만들지 않는다. SCM은 SKU/수요 확인 작업 후 보완을 받아야 재무에 인계할 수 있다. 빈 정보 때문에 공급 가능을 자동 확정하지 않는다.
- 결재권한 선택과 역할 전환은 **시연용**이다. 서버는 계산된 권한과 선택 권한을 대조하지만 실제 개인 계정·이사회 의결 정족수는 구현 범위가 아니다.

## 상태·변경·이력

`app/execution.py`가 약정별 결정과 후속 업무를 분리한다. `app/server.py`의 `/api/execution`은 역할·기안 버전·중복 방지 키를 검증한 후 동일 PostgreSQL 트랜잭션에 사건 전후·담당자·시각·사유·근거를 저장한다. 새 테이블이나 기존 데이터 삭제는 없다.

재무 패킷 유효성은 경제적 원본·SCM 검토·재무 버전으로 검증한다. 단순 승인/문의 기록 때문에 자기 근거가 무효화되는 문제를 고쳤으며 경제적 근거 변경은 기존 승인 효력을 해제한다. 발주 시 승인 스냅샷을 고정한다. 공급 회신의 지급일/수량 변경은 재무 재판정으로 전환하고 새 지급일 대조와 사람 재승인까지 일정 확정을 차단한다. 이미 전달한 발주는 별도 변경 기안으로 처리한다.

같은 작업 ID의 제목·담당 상태가 바뀌면 작업 본문도 갱신한다. 이전 단계 완료 후 SCM/재무 인계 작업이 계속 대기로 남지 않도록 했다. 기안 보완 후에도 미응답 문의·통보 증빙과 이전 결정을 보존하되 이전 결정을 새 기안 승인으로 사용하지 않는다. 전속계약 통보와 그룹 보고는 별도 의무로 남고 담당자가 증빙을 기록한다. 외부 통보를 자동 전송하지 않는다.

## 검증 증거

- [단위/회귀 테스트](../verification/screen-reviews/13-screen-tests.txt): 82개 통과. 기존 현금 4시나리오 고정값·승인 규정·SCM/재무 회귀 포함.
- [서버 통합 시나리오](../verification/screen-reviews/13-screen-scenarios.json): 별도 로컬 PostgreSQL에서 정상·CEO/조건부·반려/재작성·회신 지급일 변경/재승인 4개. 입력은 스크립트에, 실제 기안 ID·상태·결정·사건 순서는 결과 JSON에 기록.
- [브라우저 표시 검증](../verification/screen-reviews/13-screen-browser.json): 13개 데스크톱 및 13개 모바일, JS 오류·예시 기안 누출·원본 .dc.html 링크·빈 화면·가로 넘침 검사.
- [빈 자료·서버 실패·재시도](../verification/screen-reviews/13-screen-empty-error.json): 13개 빈 화면과 실패 후 회복, DB 수정 없음.
- [직접 입력 역할 흐름](../verification/screen-reviews/13-screen-role-flow.json): Chromium에서 신규 기안 작성 → 마케팅 대기 → SCM 인계/대기 → 재무 상신/대기 → 평시 승인권자 → 일정표 정리/종료. API만 직접 호출하는 시연과 구분.
- [소스 대조](../verification/screen-reviews/13-screen-source-audit.json): 제공 묶음 22개 파일 해시 보존. 04_원본데이터·보호 설정은 수정하지 않았다.

재현:

```sh
python -m scripts.migrate_screens
python -m scripts.audit_screen_sources
python -m unittest discover -s tests -v
W01_TEST_BASE_URL=http://127.0.0.1:8087 python -m scripts.verify_screen_migration
W01_TEST_BASE_URL=http://127.0.0.1:8087 python -m scripts.verify_migrated_browser
W01_TEST_BASE_URL=http://127.0.0.1:8087 python -m scripts.verify_role_browser_flow
W01_TEST_BASE_URL=http://127.0.0.1:8087 python -m scripts.verify_screen_states
```

통합/브라우저 명령은 로컬 호스트만 허용한다. 전용 DB에서 실행한다. 시나리오 검증은 재무 기준을 변경하고 모의 기안을 생성한다. 운영 DB에서 실행하지 않는다. 브라우저 검증에는 별도 Playwright/Chromium이 필요하고 앱 실행 의존성에는 추가하지 않았다.

## 변경 파일과 현재 범위

| 분류 | 파일 |
|---|---|
| 원본 이식 | `scripts/migrate_screens.py`, 호환 진입점 `scripts/extract_design.py`, `web/screens/` 13개 HTML·manifest |
| UI 연결 | `web/design.js`, `web/design-runtime.js`, `web/design.css`, `web/index.html`, 기존 검토와 통합한 `web/scm.js`, `web/finance-screen.js` |
| 서버/업무 | `app/execution.py`, `app/server.py`, `app/workflow.py`, `app/finance_review.py`, `app/marketing.py`, `app/domain.py`, `app/policy.py` |
| 성과 원본 | `app/performance.py`, `data/performance_reference.json` (원본 디렉터리를 배포하지 않는 컨테이너용 출처·가정 포함 계산 스냅샷) |
| 검증/기록 | `tests/test_execution.py`, `scripts/verify_screen_migration.py`, `scripts/verify_migrated_browser.py`, `scripts/verify_role_browser_flow.py`, `scripts/verify_screen_states.py`, `scripts/audit_screen_sources.py`, 본 문서·결과·화면 캡처, `docs/guides/PROTOTYPE.md`, `docs/history/CHANGELOG.md` |
| 이전 UI 제거 | `web/screens/00.html`~`08.html`, `web/source-logic.js` 제거. 이전 숫자 해시는 새 역할 화면으로 호환 이동 |

기존 SCM·재무 변경과 증거 파일은 보존·통합했다. 과거 단계별 검증 스크립트/JSON은 당시 구현의 역사적 증거이며 현재 UI 검증은 위 13-screen 명령을 사용한다. 배포 원본 폴더 자체는 수정하지 않는다.

| 구분 | 범위 |
|---|---|
| 실제 작동 | 서버 DB 저장·첨부·계산·역할별 페이지·상신·결정 검증·후속 작업·변경 무효화·사건 이력·일정표 기록 |
| 모의 처리 | 승인자 역할의 명시적 입력, Corevia 발주 전달, 공급 회신, 상대방 통보·그룹 보고의 이행 기록 |
| 미연결 | 실제 개인 계정/부서 인증, 공급사·메일·ERP·은행·실제 입고·지급. AI 유료 호출은 수행하지 않음 |
| 계산 범위 | 원본 기준선과 현재 검토 건의 현금 영향/재고 검산. 다른 모의 기안의 신규 발주를 전사 실적 또는 재고 예약으로 자동 합산하지 않음 |

로컬 실행: **http://127.0.0.1:8087/**. 새 격리 DB `w01_migration_utf8`를 사용한다. 기존 DB와 온라인 앱을 변경하거나 재배포하지 않았다. 프로세스 종료 후에는 PROTOTYPE.md의 실행 절차로 다시 시작한다.
