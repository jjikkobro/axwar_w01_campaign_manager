# 공통 산식·일정 적용 · 2026-11-11

## 적용 원칙

마케팅 작성, SCM 검토, 재무·승인 근거, 발주 초안과 입고·일정 검산은 서버의 공통 모델을 사용한다. 역할별 화면은 필요한 결과만 표시한다. 사람의 채택값·수동 입력·실제 발주·회신은 계산 추천과 구분하며 자동 변경하지 않는다.

- `app/formulas.py`: 역할별 산식·기본값·사용 화면·변경 이력. 기본 산식도 모델 지문에 포함하므로 산식을 새로 추가하거나 기본식을 바꿔도 기존 예상안의 최신 여부를 다시 확인한다.
- `app/planning.py`: 공통 제안량·예상 입고일·역산 발주시한·회신 기한 초안·SKU 판매 평균.
- `app/replenishment.py`: 같은 리드타임·재고 부족·MOQ·예상 금액 산식으로 정기 보충과 캠페인 추가분 계산. MOQ 중복 적용 제거.
- `app/ax_planning.py`, `app/scm.py`: 공통 계획을 호출한다. 페이지 전용으로 계산한 다른 제안량·입고일을 생성하지 않는다.
- `app/planning_schedule.py`: 같은 서버 리드타임 날짜 계산을 사용한다. 기존에 승인 검토 여유일을 더해 마케팅 예상 입고일과 달라지던 중복 계산을 제거했다. 실제 계약 확정일·지급일을 자동 추정하지 않는다.
- 발주 초안의 희망 입고일·회신 기한도 서버에서 가져온다. 실제 입력한 희망일이나 공급자의 확인 회신이 있으면 그 값을 우선하며 원래 기록을 보존한다.

## 마케팅 화면

예상 발주량·비용 계산 결과에 `공통 산식 · 정기 보충·예상 일정 근거`를 추가했다. 제품별 정기 보충량·캠페인 추가 제안량·예상 입고·역산 발주 검토시한·보충 일정을 펼쳐 확인한다. 실제 SCM 발주·입고 회신 일정은 기존 대기·일정 화면에서 조회하며 계획값으로 덮어쓰지 않는다.

공통 기본 리드타임은 원본 주수×7 달력일이다. 관리자 계산식 설정의 `입고 리드타임 일수`에서 SCM이 바꾸면 관련 계획 화면에 함께 반영한다. 예를 들어 `주수×5`를 입력하면 달력일 30일 가정이 된다. 영업일 달력을 자동 생성하는 의미가 아니다. 원본 SKU 주수와 적용 일수는 별도로 구분한다.

## 산식 변경 전파

1. 관리자에서 역할별 영향 미리보기와 확인 후 적용한다. 미리보기에는 공통 제안량·입고일의 전후 값도 표시된다.
2. `/api/state`, `/api/cases/:id`, `/api/ax-planning`에 공통 계산 기준을 포함한다. 실제 기본식·사용자 식·원본 자료 버전·재무 기준·공유 공급 변경을 함께 추적한다.
3. 열린 캠페인 화면과 통합 계획 화면은 10초마다, 또는 창이 다시 활성화될 때 기준 변경을 확인한다. 관리자 설정 페이지는 저장 후 최신 기준을 다시 읽는다.
4. 작성 중 입력이 없으면 새 기준으로 화면을 갱신한다. 입력 중이면 기안 버전이 같을 때 직접 입력을 유지하고 과거 예상안만 무효화한다. 실제 기안 버전도 바뀌면 입력을 보존한 채 최신 기안 재확인을 안내한다.
5. 모달을 작성 중이면 자동으로 닫거나 덮어쓰지 않는다. 오래된 기준의 실행을 막고 갱신을 안내한다. 최신 기준을 여는 동작은 사용자가 선택한다.
6. 캠페인 저장·검토·상신·승인·발주 요청에 조회 시점의 기준을 함께 보낸다. 서버는 트랜잭션 안에서 기준을 대조해 바뀐 기준의 오래된 요청을 차단한다. 기존 자동 승인 금지·버전 충돌·승인 범위 검증도 유지한다.

재무 화면의 과거 기안 사전검토는 저장 기록으로 명시한다. 현재 기준과 다르면 간편 확인을 비활성화하고 현재 공통 계획을 별도로 확인하도록 한다. 이력을 현재 계산 결과처럼 덮어쓰지 않는다. 서로 다른 부서가 직접 채택한 값이나 실제 회신일이 계산 추천과 다른 것은 산식 불일치로 취급하지 않는다.

## 변경 파일

- 서버: app/planning.py, app/formulas.py, app/replenishment.py, app/ax_planning.py, app/planning_schedule.py, app/scm.py, app/scm_advice.py, app/server.py.
- 화면: web/calculation-sync.js, web/campaign-scope.js, web/ax-planning.js, web/screen-adapter.js, web/scm-context.js, web/design.js, web/design.css, web/settings.js, web/hub.js, web/campaign.html, web/hub.html.
- 검증·기록: tests/test_shared_planning.py, scripts/verify_shared_calculations.py, docs/verification/workflow/SHARED_CALCULATION_RESULTS.json, docs/history/CHANGELOG.md, docs/guides/PROTOTYPE.md, docs/guides/PROJECT_RULES.md.

원본 데이터, 시안 원본, .claude/.codex/.agents/.gitignore는 수정하지 않는다. 실제 진행 중 캠페인의 입력·승인·발주 기록을 이번 코드 변경으로 수정하지 않는다.

## 검증

- 전체 단위 테스트 191건 통과. 마케팅/SCM의 제안량·정기 보충·예상 입고·역산일, 공통 평균 판매, MOQ 한 번 적용, 기본 산식 추가 감지, 실제 기록 불변성 확인.
- 별도 PostgreSQL DB에서 `lead_weeks * 7 → lead_weeks * 5`를 적용했다. 마케팅·SCM·재무·승인 화면이 새 기준을 읽고, 동일 SKU의 예상 입고가 두 계산에서 모두 2026-07-31로 일치했다. 이 변경은 검증용 DB에만 적용했다.
- 마케팅 작성 중 제목을 보존하고 이전 예상안을 무효화했다. 이전 기준의 저장 요청은 서버에서 거절됐다. 화면 오류와 모바일 가로 넘침 없음.
- 실제 외부 주문·지급·AI 호출·온라인 재배포는 수행하지 않았다.

[격리 DB 실행 결과](../../verification/workflow/SHARED_CALCULATION_RESULTS.json), [실제 로컬 화면 확인](../../verification/workflow/SHARED_CALCULATION_LIVE.json)

```sh
python3 -m unittest discover -s tests -q
W01_SHARED_CALC_TEST_BASE_URL=http://127.0.0.1:8089 python3 -m scripts.verify_shared_calculations
```

화면 검증은 별도 DB의 서버와 Playwright/Chromium이 필요하다. 산식을 실제로 변경하는 테스트이므로 운영 DB에 연결하지 말아야 한다. 스크립트는 8088의 쓰기를 거부한다.
