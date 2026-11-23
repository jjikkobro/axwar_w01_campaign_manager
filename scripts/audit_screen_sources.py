"""Keep supplied fixtures separate from original inputs and live calculations."""
from pathlib import Path
from datetime import date,timedelta
import hashlib,json
ROOT=Path(__file__).resolve().parent.parent
def main():
 manifest=json.loads((ROOT/'web/screens/manifest.json').read_text());source=json.loads((ROOT/'W01_screens/data/sku_inventory_po.json').read_text());data=json.loads((ROOT/'data/seed.json').read_text());diff=[]
 for s in source:
  rows=sorted((r for r in data['sales']['rows'] if r['sku_id']==s['id'] and date.fromisoformat(r['week'])+timedelta(days=7)<=date(2026,7,1)),key=lambda r:r['week'])[-4:]
  avg=sum(int(r['sold_qty']) for r in rows)/len(rows)
  if s['avg']!=avg:diff.append({'sku':s['id'],'screen_fixture_average':s['avg'],'system_completed_4_week_average':avg,'weeks':[r['week'] for r in rows],'decision':'화면 상수를 사용하지 않고 완료 4주 원본 계산을 표시'})
 changed=[p for p,h in manifest['files'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
 assert not changed,changed
 out={'source_package_files':len(manifest['files']),'source_files_unchanged':True,'fixture_discrepancies':diff,'fixture_policy':'내장 JSON은 원본 스냅샷/계산 참고 자료. 서버 자료를 덮어쓰거나 미래 가정을 확정하지 않음.','overrides':[{'source':'SCM MOQ 배수','applied':'원본에 근거한 MOQ 최소량. 배수 강제 없음.'},{'source':'CEO 예시 하회종료 8/29, 최저 8.63억','applied':'선택 시나리오와 같은 입력에서 재계산. 원본 기본 합집합 영업일 종료 8/28.'},{'source':'조건부 승인 후 발주 예시','applied':'조건 충족 증빙과 사람 재승인 전 전달 차단.'}]}
 (ROOT/'docs/verification/screen-reviews/13-screen-source-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'source_files_unchanged':True,'average_discrepancies':len(diff)},ensure_ascii=False))
if __name__=='__main__':main()
