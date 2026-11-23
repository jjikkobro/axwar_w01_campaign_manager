# 캠페인 예산 명세 · 2026-11-12

마케팅 작성 화면의 예산을 항목별 명세로 제공한다. 기존 캠페인 기안의 `budget`은 마케팅 집행비 소계이며, 상품 조달비는 SKU별 발주 검토와 별도 승인 흐름에 남는다. 전체 비용 합계는 두 금액을 합친 참고치다. 표본을 실제 회사 현금으로 자동 확정하거나 발주비를 두 번 지급하지 않는다.

## 화면과 입력

- 매체별 마케팅 고정비·기간비와 별도 마케팅비를 입력한다. 예측값 적용 후 항목별 수정 가능. 미확인 항목은 빈칸으로 남으며, 0은 명시적 값이다.
- SKU별 예상 발주량과 단가를 수정하면 상품 조달비 소계를 재계산한다. 원본 SKU의 MOQ와 공통 산식은 그대로 검증한다.
- 마케팅 소계·상품 조달 소계·전체 예상 비용 합계를 자동 표시한다. 중앙 설정식이 단순 합계와 다르면 `설정 산식 조정` 항목을 보여 항목과 합계 차이를 설명한다.
- `마케팅비 직접 입력`을 선택하면 항목별 예측 대신 예산 전체를 직접 입력할 수 있다. 기존 기안의 수동 예산과 명시적 0원도 유지한다.
- `발주량과 비용 적용하기`는 예측치를 신청안에 채택하는 사람의 동작이다. 이미 직접 입력한 예산은 이 버튼을 눌러도 유지한다.

## 저장과 근거

매체별 수동 고정비·기간비, 별도 마케팅비, 입력 방식은 기안의 `ax_plan.inputs.marketing_cost_inputs`에 저장한다. 재조회 후 다시 계산하면 해당 값이 복원된다. 서버는 항목별 계산 모드에서 마케팅 소계와 기안 예산의 일치를 확인한다. 직접 입력 모드는 예산 전체를 독립적으로 보존한다.

표본 기반 항목이 남아 있으면 기존의 적용 범위 확인과 근거 기록을 요구한다. 모든 매체 항목을 직접 입력한 경우에도 0원과 빈칸은 구분한다. 인플루언서비는 광고비에 포함된 항목이므로 같은 비용을 고정비와 기간비에 중복 입력하지 않도록 안내한다.

## 변경 파일

- 계산·검증: app/marketing_cost.py, app/ax_planning.py, app/server.py.
- 화면: web/budget-receipt.js, web/ax-planning.js, web/marketing-ux.js, web/marketing-cost.js, web/screen-adapter.js, web/design.js, web/design.css, web/campaign.html.
- 검증: tests/test_marketing_cost.py, scripts/verify_budget_receipt.py, docs/verification/marketing/BUDGET_RECEIPT_RESULTS.json.

## 검증

전체 단위 테스트 207건 통과. 별도 DB에서 오프라인 고정비 10,000원 + 기간비 50,000원 + 별도 비용 2,000원 = 마케팅 62,000원, SKU 12,000개 × 16,800원 = 조달 201,600,000원, 참고 합계 201,662,000원을 확인했다. SCM 요청 후 항목별 값이 복원됐고, 설정식 변경 시 조정액 6,200원이 표시되며 기존 저장 예산은 유지됐다. 모바일 가로 넘침·브라우저 오류가 없었다.

참고 자료가 없는 매체는 항목을 직접 입력하기 전 빈칸으로 남았다. 직접 입력한 0원은 예상 발주량 적용 후에도 유지돼 SCM 요청으로 저장됐다. 모든 검증은 별도 DB의 모의 데이터로 진행했다.

[화면/API 검증 결과](../../verification/marketing/BUDGET_RECEIPT_RESULTS.json), [로컬 적용 확인](../../verification/marketing/BUDGET_RECEIPT_LIVE.json)

```sh
python3 -m unittest discover -s tests -q
W01_BUDGET_RECEIPT_TEST_BASE_URL=http://127.0.0.1:8089 python3 -m scripts.verify_budget_receipt
```

화면 검증에는 별도 테스트 DB와 Playwright/Chromium이 필요하다. 테스트는 기안과 산식을 저장하며 실제 미리보기 8088에 쓰지 않도록 제한한다.
