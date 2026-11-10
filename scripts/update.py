#!/usr/bin/env python3
"""Refresh the catalogue from the KICT inventory; uncertain PDF matches are never published."""
import argparse, hashlib, io, json, re, sys, zipfile
from datetime import datetime, timezone
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import fitz
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
LIST = 'https://www.kict.re.kr/governmentWeb/getGovernmentContentList.es?mid=a10602050000&pid=92'
NOTICES = 'https://www.kict.re.kr/governmentWeb/getGovernmentContentList.es?mid=a10602050000&pid=83&currentPage='
DETAIL = 'https://www.kict.re.kr/governmentWeb/getGovernmentContentsView.es?mid=a10602050000&pid=83&id='
DOWNLOAD = 'https://www.kict.re.kr/attachFileDownload.es?'
CODE = re.compile(r'FS-(FF|FC|HW|WW)\d{2}-\d{4}-\d+')
ATTACH = re.compile(r"egov_download_atchfile\('government',\s*'[^']*',\s*'([^']*)',\s*'([^']*)'\)")
CATEGORIES = {'FF':'바닥-바닥', 'FC':'바닥-커튼월','HW':'벽 상부','WW':'벽-벽'}

@lru_cache(maxsize=256)
def read(url):
    with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0 FirestopInventory/1.0'}), timeout=45) as response:
        return response.read()

def norm(value):
    return re.sub(r'[^0-9a-z가-힣]', '', value.lower())

def clean(value):
    return ' '.join((value or '').split())

class Rows(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.rows=[]
    def handle_starttag(self, tag, attrs):
        if tag=='ul': self.stack.append({'text':[], 'actions':[]})
        if self.stack and tag=='a':
            attrs=dict(attrs); self.stack[-1]['actions'].extend([attrs.get('href',''), attrs.get('onclick','')])
    def handle_data(self, data):
        if self.stack: self.stack[-1]['text'].append(data)
    def handle_endtag(self, tag):
        if tag=='ul' and self.stack: self.rows.append(self.stack.pop())

def inventory_url():
    p=Rows(); p.feed(read(LIST).decode('utf8'))
    for row in p.rows:
        title=clean(' '.join(row['text']))
        if '내화채움구조' not in title or '전체 인정현황' not in title: continue
        date=re.search(r'(20\d\d)\.\s*(\d\d)\.\s*(\d\d)', title)
        for action in row['actions']:
            match=ATTACH.search(action)
            if match and date:
                name, system=match.groups()
                return title, '-'.join(date.groups()), DOWNLOAD+urlencode({'filegubun':'government','systemfilename':system,'userfilename':name})
    raise RuntimeError('공식 인정현황의 날짜와 PDF를 찾지 못했습니다')

def inventory(data):
    if not data.startswith(b'%PDF'): raise ValueError('인정현황이 PDF가 아닙니다')
    document=fitz.open(stream=data,filetype='pdf'); pdf=pdfplumber.open(io.BytesIO(data)); found={}
    for i,page in enumerate(document):
        if not re.search(r'FS-(?:FF|FC|HW|WW)',page.get_text()): continue
        for table in pdf.pages[i].find_tables():
            rows=table.extract()
            for idx,row in enumerate(rows):
                if len(row)!=13: continue
                code=re.sub(r'\s+', '', row[2] or '')
                if not CODE.fullmatch(code): continue
                if code in found: raise ValueError('인정번호 중복: '+code)
                if not row[5] or not row[11]: raise ValueError('필수 필드 누락: '+code)
                coords=table.rows[idx].cells[2]
                if not coords: raise ValueError('원본 행 위치 확인 실패: '+code)
                bounds=fitz.Rect(0,coords[1],page.rect.width,coords[3])
                found[code]={'row':row,'page':i+1,'image':page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),clip=bounds).tobytes('png')}
    if len(found)<10: raise ValueError('선형조인트 항목이 비정상적으로 적어 갱신을 중단합니다')
    return found

def notices_since(since, reader=read):
    out=[]
    for page in range(1,31):
        p=Rows();p.feed(reader(NOTICES+str(page)).decode('utf8'))
        dates=[]
        for row in p.rows:
            title=clean(' '.join(row['text'])); dm=re.search(r'20\d{2}-\d{2}-\d{2}',title)
            actions=' '.join(row['actions']); mid=re.search(r"government_content_detail_move\(this.href,\s*'(\d+)'",actions)
            if not dm or not mid: continue
            date=dm.group(); dates.append(date)
            if date>=since and any(t in title for t in ('신규인정','인정변경','인정취소')):
                out.append((date,mid.group(1),title))
        if not dates: raise ValueError('공고 목록 페이지를 읽지 못했습니다')
        if min(dates)<since: return out
    raise ValueError('공고 검색 범위를 초과했습니다')

def find_pdf(record, notices, reader=read):
    target=norm(record['structure']); company=record['company']
    phone=re.search(r'\d{2,3}-\d{3,4}-\d{4}',company)
    if len(target)<6: return None
    for date,ident,title in notices:
        if phone and phone.group() not in title: continue
        if not phone and norm(company.split('(')[0]) not in norm(title): continue
        source=reader(DETAIL+ident).decode('utf8')
        attachments=list(dict.fromkeys(ATTACH.findall(source)))
        candidates=[]
        for name, system in attachments:
            if name.lower().endswith('.pdf') and target in norm(name):
                candidates.append((name, system, None))
            elif name.lower().endswith('.zip'):
                url=DOWNLOAD+urlencode({'filegubun':'government','systemfilename':system,'userfilename':name})
                archive=zipfile.ZipFile(io.BytesIO(reader(url)))
                for member in archive.infolist():
                    if member.filename.lower().endswith('.pdf') and target in norm(member.filename) and member.file_size < 100_000_000:
                        candidates.append((name, system, member.filename))
        if len(candidates)!=1: continue
        name,system,member=candidates[0]
        url=DOWNLOAD+urlencode({'filegubun':'government','systemfilename':system,'userfilename':name})
        content=reader(url)
        if member is not None: content=zipfile.ZipFile(io.BytesIO(content)).read(member)
        if not content.startswith(b'%PDF'): continue
        doc=fitz.open(stream=content,filetype='pdf'); first=' '.join(doc[i].get_text() for i in range(min(2,len(doc))))
        if target not in norm(first): continue
        return content, len(doc), first, DETAIL+ident, date
    return None

def refresh(old, entries, notices, reader=read, baseline=None):
    if len(entries)<len(old)*.65: raise ValueError('항목 수가 급감해 갱신을 중단합니다')
    previous={x['code']:x for x in old}; used={x['n'] for x in old}; nextid=max(used or {0})+1; result=[]; images={}; files={}; changes=[]
    missing=set(previous)-set(entries)
    if missing: raise ValueError('기존 인정번호가 원본에서 사라져 자동 갱신을 중단합니다: '+', '.join(sorted(missing)))
    for code,item in entries.items():
        row=item['row']; olditem=previous.get(code); rec=dict(olditem) if olditem else {}
        if not olditem: rec={'n':nextid,'haspdf':False,'source_type':'원본 확인 필요','pages':0,'firsttext':'','notice':'','form':'','frame':'','insulation':'','evidence':'','issue':''};nextid+=1
        values=[clean(x) for x in row]
        rec.update(code=code,category=CATEGORIES[CODE.fullmatch(code).group(1)],page=item['page'],company=values[3],product=values[4],structure=values[5],support=values[6],usage=values[7],performance=values[8],material=values[9],opening=values[10],expiry=values[11],cancel=('취소' in ' '.join(values)))
        images[rec['n']]=item['image']
        prior = (baseline or {}).get(code)
        if olditem and prior is None: raise ValueError('비교 기준이 없는 기존 인정번호: '+code)
        changed=not olditem or [clean(x) for x in prior[2:]] != values[2:]
        if changed:
            changes.append(code)
            if olditem and any(clean(prior[i]) != values[i] for i in (5,6,9,10)):
                rec.update(haspdf=False,firsttext='',form='',frame='',insulation='',evidence='',issue='인정현황 변경: 세부 인정내용을 원문에서 확인해야 합니다.')
        if not rec['cancel']:
                match=find_pdf(rec,notices,reader)
                if match and (changed or not rec['haspdf'] or match[3] != rec.get('notice') or not (ROOT/'docs'/f"{rec['n']}.pdf").exists() or hashlib.sha256(match[0]).digest() != hashlib.sha256((ROOT/'docs'/f"{rec['n']}.pdf").read_bytes()).digest()):
                    content,pages,first,notice,_=match
                    rec.update(haspdf=True,pages=pages,firsttext=first,notice=notice,source_type='공고 첨부파일',form='',frame='',insulation='',evidence='',issue='')
                    files[rec['n']]=content
                elif not olditem:
                    rec['issue']='세부 PDF를 자동으로 확정하지 못했습니다. 연구원 공고를 확인하세요.'
        if rec['cancel']: rec['haspdf']=False
        result.append(rec)
    return result,images,files,changes

def main():
    title,date,url=inventory_url(); data=read(url); entries=inventory(data)
    path=ROOT/'index.html'; html=path.read_text(encoding='utf8'); m=re.search(r'const DATA=(\[.*?\]);let cat=',html,re.S)
    if not m: raise RuntimeError('기존 목록을 찾지 못했습니다')
    old=json.loads(m.group(1)); statuspath=ROOT/'update-status.json'; status=json.loads(statuspath.read_text())
    since=status.get('catalog_reference_date','2026-10-31')
    if date < since: raise ValueError('원본 기준일이 기존 자료보다 오래되어 갱신을 중단합니다')
    notices=notices_since(since)
    baseline_path=ROOT/'baseline-inventory.json'
    baseline=json.loads(baseline_path.read_text(encoding='utf8'))
    result,images,files,changes=refresh(old,entries,notices,baseline=baseline)
    updated=html[:m.start(1)]+json.dumps(result,ensure_ascii=False,separators=(',',':'))+html[m.end(1):]
    updated=re.sub(r'<div class="alert"><b>.*?</div>',f'<div class="alert"><b>{date} 인정현황 기준 · {len(result)}건</b> · 원문 공고와 세부 인정내용을 확인하세요.</div>',updated,count=1)
    for n,img in images.items(): (ROOT/'rows'/f'{n}.png').write_bytes(img)
    for n,content in files.items(): (ROOT/'docs'/f'{n}.pdf').write_bytes(content)
    path.write_text(updated,encoding='utf8')
    baseline_path.write_text(json.dumps({code:item['row'] for code,item in entries.items()},ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
    result_status={'last_checked_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_title':title,'source_url':url,'source_sha256':hashlib.sha256(data).hexdigest(),'catalog_reference_date':date,'catalog_automatically_updated':True,'changes':changes,'unmatched_pdf_count':sum(not r['haspdf'] and not r['cancel'] for r in result)}
    statuspath.write_text(json.dumps(result_status,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result_status,ensure_ascii=False))

if __name__=='__main__': main()
