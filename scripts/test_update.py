import importlib.util,json,re,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('update',Path(__file__).parent/'update.py');u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
root=Path(__file__).resolve().parents[1]; fixtures=root/'inventory';
if not fixtures.exists(): fixtures=root.parent/'inventory'
base=root if (root/'docs').exists() else root.parent/'firestop'
oldhtml=(base/'index.html').read_text();old=json.loads(re.search(r'const DATA=(\[.*?\]);let cat=',oldhtml,re.S).group(1))
sep=u.inventory((fixtures/'september.pdf').read_bytes());octo=u.inventory((fixtures/'october.pdf').read_bytes())
assert len(sep)==57 and len(octo)==59
assert set(octo)-set(sep)=={'FS-FF26-1029-2','FS-WW26-1029-1'}
oldsep=[r for r in old if r['code'] in sep]
notices=[('2026-10-29','6036','[신규인정] ㈜드림이앤씨(031-304-1700) DR PAD')]
def reader(url):
 if url.startswith(u.DETAIL): return (fixtures/'notice6036.html').read_bytes()
 if 'c7569ef2' in url or '5782904d' in url: return u.read(url)
 raise ValueError(url)
updated,imgs,files,changes=u.refresh(oldsep,octo,notices,reader,baseline={k:v['row'] for k,v in sep.items()})
new={r['code']:r for r in updated if r['code'] not in sep}
assert len(updated)==59 and set(new)==set(octo)-set(sep)
for rec in new.values():
 assert rec['haspdf'] and rec['n'] in files and rec['n'] in imgs, (rec, sorted(files))
 assert u.norm(rec['structure']) in u.norm(rec['firsttext'])
assert new['FS-FF26-1029-2']['opening']=='350 이하'
assert new['FS-WW26-1029-1']['opening']=='260 이하'
assert len({r['n'] for r in updated})==59
try: u.refresh(old,sep,notices,reader,baseline={k:v['row'] for k,v in octo.items()})
except ValueError as e: assert '사라져' in str(e)
else: raise AssertionError('removed entries were accepted')
print('PASS September 57 → October 59; 2 additions + exact PDF structure checks; reject removed entries')
