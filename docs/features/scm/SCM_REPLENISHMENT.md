# SCM 정기 보충과 수요 확인 개선 · 2026-11-11

## 원본과 가정

- 원본 업무: Business_Process_Map.md §2.2의 재고 커버·최근 4주 평균에 따른 재고 보충. calculation_definitions.md §1.3의 현재고/이동 중 재고/목표량/MOQ 산식.
- 원본 SKU: 리드타임 6·8·12주, 안전재고 최소 4주·최대 6주, SKU별 MOQ.
- 사용자 지정 가정: 매주 검토하고 다음 주 도달 여부를 확인하되 리드타임도 포함한다. 검토 기준일부터 7일 간격으로 발주 계산안을 생성한다.
- 목표량에 리드타임+최대 안전재고를 사용하는 것은 계획 가정이다. 자동 발주의 실제 금액 한도·새 승인 규정·지급일을 만들지 않는다. 단가는 과거 PO 참고치다.

## 최종 산식

W = 최근 완료 4주 평균 주간 판매, L = 원본 SKU 리드타임(주), Smin/Smax = 원본 안전재고 주수.

- 발주 검토: `현재고 + L+1주 이내 예상 입고 − W × (L+1) − 같은 기간 다른 승인 캠페인 수요 <= W × Smin`.
- 보충 목표: `W × (L+Smax) + 목표기간의 다른 승인 캠페인 수요`.
- 제안량: `max(목표량 − 현재고 − 미입고 발주량 − 목표기간의 다른 확인 입고량, 0)`에 MOQ 최소량 반영. MOQ 배수 주문을 강제하지 않는다.
- 주문일은 조건을 충족한 이번 검토일, 예상 입고일은 주문일+리드타임이다. 이미 리드타임 안에 부족이 예정된 경우 주문만으로 해결됐다고 표시하지 않고 기존 수급 공백을 표시한다.
- `replenishment_trigger`, `replenishment_target`은 관리자→계산식 설정에서 SCM 수정 가능. 기본 판매·안전재고·MOQ 산식도 기존 설정을 사용한다.

기존 PO 확인 회신은 실제 공급 원장에서 한 번만 사용한다. 미확인 PO는 발주일+리드타임을 별도 예상 입고 시나리오로만 사용하며, 통합 in_transit를 다시 가산하지 않는다. 명시적 불가 회신은 예상 공급에도 넣지 않는다. 만료된 예상 입고일을 임의로 오늘로 옮기지 않는다.

## 계산과 실제 집행 분리

정기 보충을 실행한다는 계획과 캠페인의 순증 수요를 별도로 검산한다. 정기 보충 물량·과거 단가 참고 비용과 캠페인 추가분을 구분한다. 초기의 누적 기본 판매 부족을 전부 캠페인 추가 발주량으로 간주하지 않는다. 보충 시나리오가 가능하더라도 공급능력·입고일·지급일 확인과 실제 승인은 별도다.

새 계산은 원본 재고·PO·AP와 실제 현금 전망에 가상 주문을 넣지 않는다. 확정 재고와 가정의 잔액을 함께 표시하며, 장기 캠페인은 리드타임 안에 준비 가능한 경우 `정기 보충·추가 발주 검토 가능`으로 안내한다. 기간이 촉박하거나 계획으로도 부족하면 부족일·수량·조정 대안을 유지한다. 조정 필요를 자동으로 공급 거절에 매핑하지 않는다.

## 이번 문제의 원인

1. 미래 기본 판매는 계속 차감하지만 정기 보충이 없는 원장만으로 장기 캠페인을 판단했다.
2. 저장된 신청 예상안의 전체 JSON 지문이 현재 기안과 다르면 채택 물량도 제외했다. 현재 기안의 기간·SKU·주간 수요·금액을 대조하고 최신 자료로 재검산하도록 개선했다. 실제 값이 바뀌거나 재검산의 채택 수량·단가가 달라지면 재사용하지 않는다.
3. 문제 캠페인은 수요 누락/참고 범위 이탈이 없는데 담당자 확인 기록이 없다는 이유만으로 일반 오류 모달을 표시했다.

## 담당자가 할 일

- SCM: 같은 재고 대조 카드에서 정기 보충 일정·기존 발주 예상 입고·리드타임 공백을 펼쳐 확인한다. 공급능력과 실제 일자는 별도 확인한다.
- 정상 수요: 대조 결과 전달 모달에서 입력 수요와 과거 근거를 확인하고 체크한다. 확인 기록과 인계가 같은 트랜잭션으로 저장된다. 실패하면 둘 다 저장하지 않는다.
- 참고 범위 이탈/관측 부족: 같은 모달에 보완 근거를 입력한다. 통계 범위 이탈만으로 잘못된 계획이나 거절로 단정하지 않는다.
- 실제 누락: 같은 화면의 `이 화면에서 수요 보완` 또는 전달 버튼에서 SKU별 수요·근거를 명시적으로 입력한다. 빈칸은 0으로 바꾸지 않는다. 보완 후 기존 검토·승인 유효성을 해제하고 재대조한다.
- 재무: 계획 유출일·금액·현금 영향 확인과 기존 승인 규정 적용. 정기 보충 계획을 확인했다는 SCM 기록이 실제 자금 확보나 최종 승인을 대신하지 않는다.

## 적용 파일

- 계산: app/replenishment.py, app/formulas.py, app/ax_planning.py, app/scm.py, app/scm_advice.py.
- 저장·작업: app/server.py, app/operations.py.
- 화면: web/scm-context.js, web/screen-adapter.js, web/design.js, web/design.css, web/campaign.html, web/ax-planning.js, web/screens/SCM_1_Check.html, scripts/migrate_screens.py.
- 검증: tests/test_replenishment.py, tests/test_scm_advice.py, scripts/verify_scm_replenishment.py, scripts/verify_scm_demand_inline.py.
- 원본·시안 원본·보호된 설정 폴더·.gitignore와 실제 캠페인 데이터는 이번 변경으로 수정하지 않았다.

## 검증

단위 테스트 185건. [격리 DB 인계·실패 시 원복·화면 결과](../../verification/scm/SCM_REPLENISHMENT_RESULTS.json), [누락 수요를 같은 화면에서 보완한 결과](../../verification/scm/SCM_DEMAND_INLINE_RESULTS.json), [실제 미리보기 읽기 검증](../../verification/scm/SCM_REPLENISHMENT_LIVE.json). 데스크톱/모바일 가로 넘침 없음, 화면 오류 없음. 실제 외부 발주·은행 지급·최종 승인 실행 없음.

```sh
PYTHONPATH=/tmp/w01-deps:. PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
W01_REPLENISHMENT_TEST_BASE_URL=http://127.0.0.1:8089 python3 -m scripts.verify_scm_replenishment
W01_REPLENISHMENT_TEST_BASE_URL=http://127.0.0.1:8089 python3 -m scripts.verify_scm_demand_inline
```

화면 검증 명령은 별도 테스트 DB와 Chromium/Playwright가 필요하며 테스트 데이터를 저장한다. 실제 미리보기 8088 쓰기는 금지한다. 원본 사본의 미확인 상태에서 실행해야 하는 인계 검증은 반복 실행 전에 테스트 사본을 별도로 준비한다.
