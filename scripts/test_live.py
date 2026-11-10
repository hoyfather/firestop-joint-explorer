import importlib.util,json,re
from pathlib import Path
spec=importlib.util.spec_from_file_location('update',Path(__file__).with_name('update.py'));u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
r=Path('.');old=json.loads(re.search(r'const DATA=(\[.*?\]);let cat=',(r/'index.html').read_text(),re.S).group(1))
sep=u.inventory((r/'inventory/september.pdf').read_bytes());octo=u.inventory((r/'inventory/october.pdf').read_bytes()); notices=u.notices_since('2026-09-30')
oldsep=[x for x in old if x['code'] in sep]
updated,imgs,files,changes=u.refresh(oldsep,octo,notices,baseline={k:v['row'] for k,v in sep.items()})
for c in ('FS-FF26-1029-2','FS-WW26-1029-1'):
 item=next(x for x in updated if x['code']==c)
 assert item['haspdf'] and item['n'] in files and '6036' in item['notice'],(c,item)
print('LIVE PASS:',len(sep),'→',len(octo),'추가 항목과 실제 공고 PDF 2건 확인')
