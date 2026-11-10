import hashlib, io, json, re, zipfile
from pathlib import Path
from urllib.parse import urlencode
from update import ATTACH, DOWNLOAD, read
root = Path(__file__).resolve().parent.parent
html = (root/'index.html').read_text(encoding='utf8')
records = {f"docs/{x['n']}.pdf":x for x in json.loads(re.search(r'const DATA=(\[.*?\]);let cat=',html,re.S).group(1))}
expected = json.loads((root/'scripts/original-pdf-sha256.json').read_text())
wanted = {p:h for p,h in expected.items() if records[p]['notice'].endswith(('=5029','=5623'))}
resolved = {}
for notice in sorted({records[p]['notice'] for p in wanted}):
    html = read(notice).decode('utf8')
    for name, system in dict.fromkeys(ATTACH.findall(html)):
        if not name.lower().endswith('.zip'): continue
        url = DOWNLOAD + urlencode({'filegubun':'government','systemfilename':system,'userfilename':name})
        archive = zipfile.ZipFile(io.BytesIO(read(url)))
        for member in archive.infolist():
            if not member.filename.lower().endswith('.pdf'): continue
            content=archive.read(member)
            digest=hashlib.sha256(content).hexdigest()
            for path, sha in wanted.items():
                if sha==digest:
                    resolved[path]=content
                    print('verified',path,len(content),flush=True)
if set(resolved)!=set(wanted):
    raise SystemExit('Unresolved: '+', '.join(sorted(set(wanted)-set(resolved))))
for path, content in resolved.items():
    (root/path).write_bytes(content)
print('All ZIP PDF checksums verified:',len(resolved))
