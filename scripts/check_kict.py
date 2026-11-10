#!/usr/bin/env python3
"""Check the official inventory; never modify the reviewed catalog or PDFs."""
from html.parser import HTMLParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import sys

LIST_URL = 'https://www.kict.re.kr/governmentWeb/getGovernmentContentList.es?mid=a10602050000&pid=92'
DOWNLOAD_URL = 'https://www.kict.re.kr/attachFileDownload.es?'
BASELINE_SHA256 = '3ee1744d1fd9964e0e1cfab011516eb6a1f42d783b2d6c0deed36b4a441974b3'

class Rows(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack = []; self.rows = []
    def handle_starttag(self, tag, attrs):
        if tag == 'ul': self.stack.append({'text': [], 'onclick': []})
        if self.stack and tag == 'a':
            v = dict(attrs).get('onclick', '')
            if v: self.stack[-1]['onclick'].append(v)
    def handle_data(self, data):
        if self.stack: self.stack[-1]['text'].append(data)
    def handle_endtag(self, tag):
        if tag == 'ul' and self.stack: self.rows.append(self.stack.pop())

def read(url):
    with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; FirestopInventoryCheck/1.0)'}),timeout=40) as r:
        return r.read()

def run():
    parser=Rows(); parser.feed(read(LIST_URL).decode('utf-8'))
    hits=[]
    for row in parser.rows:
        title=' '.join(' '.join(row['text']).split())
        if '내화채움구조' not in title or '전체 인정현황' not in title: continue
        for action in row['onclick']:
            match=re.search(r"egov_download_atchfile\('government',\s*'[^']*',\s*'([^']*)',\s*'([^']*)'\)",action)
            if match: hits.append((title,match.group(1),match.group(2)))
    if not hits: raise RuntimeError('전체 인정현황 첨부파일을 찾지 못했습니다. 기존 데이터는 유지합니다.')
    title,name,system=hits[0]
    content=read(DOWNLOAD_URL+urlencode({'filegubun':'government','systemfilename':system,'userfilename':name}))
    if not content.startswith(b'%PDF'): raise RuntimeError('다운로드 결과가 PDF가 아닙니다. 기존 데이터는 유지합니다.')
    source_hash=hashlib.sha256(content).hexdigest()
    result={'last_checked_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'), 'source_title':title,
      'source_url':LIST_URL, 'source_sha256':source_hash, 'catalog_reference_date':'2026-10-31',
      'source_differs':source_hash!=BASELINE_SHA256,'catalog_automatically_updated':False}
    Path('update-status.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    try: run()
    except Exception as exc:
        print('점검 실패:',str(exc),file=sys.stderr);sys.exit(1)
