# 원본 시안과 동일한 화면 구현 · 2026-11-10

사용자 지시: **“첨부한 스크린 시안과 완벽하게 동일하게 구현해.”**

앞선 마이그레이션은 섹션 내부를 새 폼으로 재구성했고 글꼴·헤더·흐름 표시·보조 패널을 추가해 원본과 달랐다. 이번 변경은 `W01_screens/screens`의 13개 Design Component를 화면의 단일 기준으로 삼아 원본 마크업·인라인 스타일·조건부 영역·반복 행·화면 로직을 직접 렌더링한다. 시안 원본 파일은 변경하지 않았다.

## 적용 사항

- 기존의 섹션 삭제/재생성, 상시 역할·기안 드롭다운, 추가 이력/근거 카드, 별도 7단계 내비게이션 삽입을 기본 화면에서 제거했다.
- 화면별 원본 헤더·단계 표시·2열 구성·표·입력 크기·여백·테두리·색상·버튼·선택창을 유지했다. 마케팅의 이전 캠페인 선택·새 기안·SKU 선택, 부서 판단·확인 체크·약정별 결정 컨트롤도 원본 로직을 사용한다.
- 글꼴을 대체 Nanum Gothic에서 원본 **IBM Plex Sans KR 400/500/600/700**으로 교체했다. Google Fonts의 실제 글꼴을 로컬에 보관하며 OFL 라이선스·출처·해시를 함께 남겼다. 기본 화면에서 외부 글꼴 요청은 없다.
- `sc-for`가 표 안에서 브라우저의 HTML 자동 보정으로 떨어져 나가는 문제를 수정했다. 파싱할 때 표/선택 요소를 임시 커스텀 태그로 보존하고, 반복·조건 처리를 마친 뒤 표준 DOM으로 조립한다. 표는 원본 로직의 실제 행 수로 표시한다.
- 원본 조건부 영역을 상시 노출시키던 처리를 제거했다. 선택값에 따라 원본과 같은 입력/모달이 열린다. 입력 후 재렌더링 시 포커스·커서·스크롤을 보존한다.
- 기존 PostgreSQL 저장·사건 이력·승인 경계는 유지한다. `screen-adapter.js`에서 데이터와 제출 동작만 연결하며 기본 화면 섹션을 다른 폼으로 바꾸지 않는다.
- 원본에 없는 증빙·추가 검토 입력은 제출 시 별도 확인 대화상자로 받는다. 상세 데이터 교체·첨부·기존 PO 확인·지급일 재판정은 별도 자료 관리 화면에 보존했다.
- 시안의 네 번째 매체인 `쿠폰·프로모션`도 서버 입력 목록에 추가했다. 승인 규정과 현금 계산 방식은 변경하지 않았다.

## 사용 방법

로컬 앱: **http://127.0.0.1:8087/**

- 처음 열면 시안 원본의 마케팅 기안 화면이 표시된다.
- 헤더의 역할 표시(예: **마케팅**)를 누르거나 **Alt+M**을 누르면 역할·화면·기안을 선택할 수 있다. 원본의 내 할 일/캠페인/결재함 메뉴에서도 선택창을 연다.
- 실제 기안을 선택하면 같은 서버 기안과 버전·진행 단계·부서 기록을 표시한다. 원본 단계 링크는 해당 기안을 유지한다.
- 기안이 선택되지 않은 후속 화면은 원본의 모의 예시이며 서버 승인·발주를 저장할 수 없다. 예시 전환은 실제 기안을 생성하지 않는다.
- 선택창의 **근거·자료·세부 검토 관리**는 `/operations`에서 기존 상세 기능을 연다. 기본 시안 화면에는 관리용 폼을 추가하지 않는다.
- `?reference=1`은 보존한 원본 DC 파일을, `?parity=1`은 실행용 추출물을 같은 초기 상태로 렌더링하는 비교 전용 경로다. 둘 다 DB 변경을 실행하지 않는다.

## 실데이터·승인 동작

실제 기안에서는 예시 금액·추천·품절·담당자·결정을 확정 사실로 복사하지 않는다. 기존 원본·완료 4주 평균·확인된 PO 회신·재무 시나리오·약정별 승인 결과를 같은 원본 화면 구조에 표시한다. 따라서 실제 데이터의 텍스트·행 수·상태에 따른 높이와 강조 색상은 달라질 수 있다.

시안 예시에 포함된 MOQ 배수, 조건부 승인 후 전달, 하회 구간 밖 지급만 허용하는 규칙은 실제 업무의 승인 규칙을 바꾸지 않는다. 실데이터 모드에서는 MOQ 최소량·승인된 수량/금액/지급일·연결 캠페인 승인을 검증한다. CEO가 승인한 하회 구간 지급 발주는 전달할 수 있고 조건부 승인·범위 변경은 재승인 전 차단한다. 실제 공급사 메시지·지급·입고는 연결하지 않는다.

## 검증

| 검증 | 결과 | 증거 |
|---|---|---|
| 원본 대비 화면 | 13개 × 데스크톱 1440×1000 / 모바일 390×844 = **26개 전체 PNG 바이트 일치**, 섹션 좌표·크기 일치 | [14-visual-parity.json](../verification/screen-reviews/14-visual-parity.json) |
| 원본 반복 표·선택창 | SCM 3개 SKU 행과 실제 SKU 텍스트 표시, `undefined` 미표시, 캠페인 선택창·입력 동작 | 위 스크립트에 포함 |
| 실제 기안 화면 | 13개 화면 조회·렌더링, 원본 외 상시 관리 폼/헤더 없음 | [14-source-live.json](../verification/screen-reviews/14-source-live.json) |
| 원본 화면 직접 업무 | 기안 입력/SCM 판단/재무 상신/평시 승인/일정표 종료 | [14-original-role-flow.json](../verification/screen-reviews/14-original-role-flow.json) |
| CEO·발주·분할 회신 | CEO 화면 승인 → 하회구간 지급 발주 → 2회 분할 회신 저장 | [14-original-ceo-flow.json](../verification/screen-reviews/14-original-ceo-flow.json) |
| 서버 회귀 | 82개 통과 | [14-visual-tests.txt](../verification/screen-reviews/14-visual-tests.txt) |

PNG 비교는 **같은 초기 상태·뷰포트·브라우저·글꼴**에서 원본 DC 마크업과 실행용 추출물을 렌더링한 결과다. 제공 묶음에 Claude `support.js`가 없으므로 로컬 DC 바인더로 원본을 재현했다. 별도 Claude 캔버스 엔진 캡처나 임의 브라우저·운영체제 전체의 픽셀 동일성을 주장하는 결과는 아니다. 원본 스타일·마크업·로직을 직접 사용하고 표/선택 요소의 실제 반복 표시도 검증했다.

마케팅 화면 캡처 (이미지·PDF 공개 제외) · SCM 화면 (이미지·PDF 공개 제외) · 재무 화면 (이미지·PDF 공개 제외) · CEO 화면 (이미지·PDF 공개 제외)

재현:

```sh
python -m scripts.migrate_screens
python -m unittest discover -s tests -v
W01_TEST_BASE_URL=http://127.0.0.1:8087 python -m scripts.verify_visual_parity
W01_TEST_BASE_URL=http://127.0.0.1:8087 python -m scripts.verify_source_live
W01_TEST_BASE_URL=http://127.0.0.1:8087 python -m scripts.verify_original_role_flow
W01_TEST_BASE_URL=http://127.0.0.1:8087 python -m scripts.verify_original_ceo_flow
```

브라우저 검증에는 Playwright/Chromium이 필요하다. 실제 입력 검증은 별도 로컬 검증 DB에서 모의 기안을 생성한다. 시나리오 테스트를 운영 DB에서 실행하지 않는다. 글꼴을 다시 받을 때만 `python -m scripts.fetch_design_fonts`를 사용한다.

## 변경 파일

- 기본 화면: `web/index.html`, `web/design.js`, `web/design-runtime.js`, `web/design.css`, `web/screen-adapter.js`
- 원본 이식: `scripts/migrate_screens.py`, `web/source-components.js`, `web/screens/` 13개·manifest, `web/references/` 원본 복사본
- 로컬 글꼴: `web/fonts/ibm-plex-sans-kr/`, `scripts/fetch_design_fonts.py`
- 별도 기존 자료 관리: `web/operations.html`, `web/operations.js`, `web/operations.css`
- 서버: `app/server.py`의 정적 경로, `app/marketing.py` 매체 목록
- 검증/기록: 위 검증 스크립트·JSON·PNG·테스트 결과, 본 문서·PROTOTYPE·CHANGELOG·검토 README

기존 DB·원본 `04_원본데이터`·`W01_screens`·보호 설정은 보존했다. 새 DB 테이블이나 운영 환경 설정을 만들지 않았고 온라인 재배포는 하지 않았다.
