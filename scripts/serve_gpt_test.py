"""Isolated HTTP integration fixture. Never contacts OpenAI or accepts real API keys."""
import json,os
from unittest.mock import patch
from urllib.parse import urlparse
from app import server
from app.ai_settings import path

def mocked_response(request,timeout=30):
 if request.get_header('Authorization')!='Bearer sk-test-browser-placeholder':raise RuntimeError('이 테스트 서버에는 모의 키만 사용할 수 있습니다.')
 body=json.loads(request.data)
 assert body['store'] is False and 'tools' not in body
 text='[요약]\n- 모의 GPT: 입력 근거를 확인했습니다.\n[위험]\n- 미확인 공급 일정은 후속 확인이 필요합니다.\n[대안]\n- 담당 부서와 지급·입고 조건을 협의하세요.\n[확인 질문]\n- 판매가능일은 확인되었나요?\n[근거]\n- 제공된 캠페인·자료 버전을 사용했습니다.'
 if '테스트 전용 지침' in body['instructions']:text+='\n- 테스트 전용 지침이 적용되었습니다.'
 class Response:
  def __enter__(self):return self
  def __exit__(self,*args):return False
  def read(self,*args):return json.dumps({'output':[{'content':[{'type':'output_text','text':text}]}]}).encode()
 return Response()
if __name__=='__main__':
 db=urlparse(os.environ.get('DATABASE_URL','')).path
 if not db.startswith('/w01_gpt_') or str(path()).startswith(str(server.ROOT)) or os.environ.get('PORT')!='8089':raise RuntimeError('격리 DB·임시 키 파일·8089 포트가 필요합니다.')
 with patch('app.drafts.urlopen',side_effect=mocked_response):server.main()
