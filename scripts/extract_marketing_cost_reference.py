"""Read-only source snapshot; retains row ids and file hashes for budget evidence."""
import csv,hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent;original=root/'01_참가자_배포용/04_원본데이터';out={'sources':[],'as_of':'2026-07-01'}
for key,rel in [('campaigns','02_masil/master/m_campaign_ms.csv'),('spend','02_masil/marketing/mkt_ad_spend_ms.csv')]:
 p=original/rel;out[key]=list(csv.DictReader(p.open(),delimiter='|'));out['sources'].append({'file':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'provenance':'원본 사실'})
(root/'data/marketing_cost_reference.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':print('마케팅 비용 근거 스냅샷 생성 · 원본 변경 없음')
