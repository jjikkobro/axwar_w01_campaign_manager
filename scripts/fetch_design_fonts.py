"""Download exactly the family/weights linked by the supplied screen helmet."""
import hashlib,json,re,urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
URL='https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap'
ROOT=Path(__file__).resolve().parent.parent/'web/fonts/ibm-plex-sans-kr'
def main():
 css=urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read().decode();ROOT.mkdir(exist_ok=True,parents=True)
 def fetch(u):
  data=urllib.request.urlopen(u,timeout=30).read();ext='.ttf' if data[:4]==b'\x00\x01\x00\x00' else '.woff2';name=hashlib.sha256(u.encode()).hexdigest()[:20]+ext;(ROOT/name).write_bytes(data)
  return u,name,hashlib.sha256(data).hexdigest()
 files=[]
 for u,name,h in ThreadPoolExecutor(max_workers=4).map(fetch,dict.fromkeys(re.findall(r'url\((https://[^)]+)\)',css))):
  css=css.replace(u,'/fonts/ibm-plex-sans-kr/'+name);files.append({'name':name,'sha256':h,'url':u})
 (ROOT/'font.css').write_text(css)
 license_url='https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexsanskr/OFL.txt'
 (ROOT/'OFL.txt').write_bytes(urllib.request.urlopen(license_url,timeout=20).read())
 (ROOT/'SOURCE.json').write_text(json.dumps({'family':'IBM Plex Sans KR','weights':[400,500,600,700],'source':URL,'license_source':license_url,'files':files},indent=2)+'\n')
 print('Original font assets and OFL license stored locally')
if __name__=='__main__':main()
