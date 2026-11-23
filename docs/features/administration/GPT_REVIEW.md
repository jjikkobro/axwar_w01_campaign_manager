# GPT 검토 연결 · 2026-11-12

## 사용

1. 로컬 http://127.0.0.1:8088/admin#tab=prompts&role=SCM 접속.
2. OpenAI API 키와 사용 가능한 모델 입력. 연결 사용을 선택하고 저장.
3. 저장된 연결 테스트 실행. 테스트도 외부 API를 호출합니다.
4. 각 캠페인 담당 화면의 검토 초안 생성 실행. 필요하면 검토 의견에 반영한 뒤 사람이 확정.

기본 모델은 gpt-5-mini. 단계별 프롬프트는 담당 역할이 수정하며 고정된 승인권한 경계는 유지합니다. 입력·기준 자료가 바뀌면 이전 초안을 재생성합니다. 키는 채팅·소스에 넣지 않습니다.

## 정기 보충

추가 발주 없이 정기 보충으로 가능한 검토는 재고로 가능으로 처리합니다. 보충 SKU·수량과 미확인 입고·공급능력 후속 확인을 사유에 자동 추가하며 기존 담당자 의견은 보존합니다. 정기 보충 가정은 확정 입고와 구분하고 담당자의 명시적 인계·후속 확인은 유지합니다.

## 구현 파일

- 서버: app/ai_settings.py, app/drafts.py, app/review_ai.py, app/prompt_settings.py, app/server.py, app/scm.py, app/scm_advice.py.
- 화면: web/admin.js, web/review-ai.js, web/screen-adapter.js, web/campaign.html, web/design.css.
- 검증: tests/test_ai_settings.py, tests/test_prompt_settings.py, tests/test_replenishment.py, tests/test_scm_advice.py, scripts/serve_gpt_test.py, scripts/verify_gpt_browser.py.

## 저장과 권한

키 저장은 시연용 SCM 관리자 역할로 제한합니다. 기본 서버 전용 경로는 .axhub/local-runtime/secrets/openai.json이며 git ignore 적용, 파일 권한 600, 디렉터리 700입니다. AI_SETTINGS_PATH로 경로 변경 가능. 공개 설정·DB 사건 이력·GPT 입력 자료에 키를 포함하지 않습니다. 환경 변수는 파일 설정이 없을 때만 사용합니다. 실제 개인별 인증은 기존 시연 범위와 동일하게 미구현입니다.

## 검증 범위

단위 테스트 221건 통과. 별도 로컬 DB에서 키 비노출·감사 이력·단계별 프롬프트 적용·SCM 자동 사유·7단계 초안·사람 반영·입력 변경 후 반영 차단·모바일·캠페인 버전 보존 검증. [기계 판독 결과](../../verification/administration/GPT_REVIEW_RESULTS.json).

실제 작동: 설정 저장·프롬프트 적용·Responses API 호출 코드·서버 계산 기반 문맥·초안 표시·수동 반영. 모의 처리: 검증 중 OpenAI 외부 응답. 미검증: 실제 키로 유료 API 호출 성공. 초안 생성만으로 결재·발주·지급을 실행하지 않습니다.


## AXhub 배포 저장 방식

Docker 환경은 AI_SETTINGS_BACKEND=postgres로 설정하며 w01_ai_connection에 암호화한 연결 설정을 저장합니다. SESSION_SECRET에서 파생한 Fernet 키를 사용하며 공개 API·업무 사건 이력에 원문 키를 넣지 않습니다. 재배포 후에도 DB 설정을 읽습니다. SESSION_SECRET을 변경하면 이전 설정을 복호화할 수 없으므로 키를 다시 등록해야 합니다. 로컬 기본 파일 저장은 그대로 유지합니다. 로컬 GPT 키의 AXhub 이전은 실행하지 않았습니다.
