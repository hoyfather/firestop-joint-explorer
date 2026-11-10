import hashlib, json, re
from pathlib import Path
from urllib.parse import urlencode
from update import ATTACH, DOWNLOAD, norm, read

root = Path(__file__).resolve().parent.parent
html = (root / 'index.html').read_text(encoding='utf8')
items = json.loads(re.search(r'const DATA=(\[.*?\]);let cat=', html, re.S).group(1))
records = {f"docs/{x['n']}.pdf": x for x in items}
expected = json.loads((root / 'scripts/original-pdf-sha256.json').read_text())
resolved = {}
errors = []
for path, sha in expected.items():
    rec = records[path]
    try:
        page = read(rec['notice']).decode('utf8')
        candidates = list(dict.fromkeys((n,s) for n,s in ATTACH.findall(page) if n.lower().endswith('.pdf')))
        candidates.sort(key=lambda p: norm(rec['structure']) not in norm(p[0]))
        for name, system in candidates:
            url = DOWNLOAD + urlencode({'filegubun':'government','systemfilename':system,'userfilename':name})
            content = read(url)
            if hashlib.sha256(content).hexdigest() == sha:
                resolved[path] = content
                print('verified', path, len(content), flush=True)
                break
        else:
            errors.append(path)
            print('no exact match', path, flush=True)
    except Exception as e:
        errors.append(path)
        print('error', path, str(e), flush=True)
if errors:
    raise SystemExit('Original checksum mismatch or retrieval failure: ' + ', '.join(errors))
for path, content in resolved.items():
    (root / path).write_bytes(content)
print('All original PDF checksums verified:', len(resolved))
