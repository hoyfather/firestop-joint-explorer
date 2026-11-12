#!/usr/bin/env python3
"""Netlify 빌드: 저장소 자료로 dist/ 를 만든다 (표준 라이브러리만 사용).

- index.html 의 DATA 에 띄어쓰기 보정(원본 행 줄바꿈 기준) 적용
- 화면 상단 반영 정보(sync-manifest) 채움
- docs/, rows/, assets/ 복사, PDF.js 압축본 해제
- 세부 PDF 누락 등 이상이 있으면 실패 → Netlify 는 직전 배포를 유지
"""
import base64
import datetime as dt
import gzip
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_artifact import DATA_RE, MANIFEST_RE, TEXT_FIELDS, build_vocab, join_lines  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'


def main():
    html = (ROOT / 'index.html').read_text(encoding='utf8')
    m = DATA_RE.search(html)
    if not m or not MANIFEST_RE.search(html):
        raise SystemExit('index.html 에서 DATA 또는 sync-manifest 표지를 찾지 못했습니다')
    data = json.loads(m.group(1))
    status = json.loads((ROOT / 'update-status.json').read_text(encoding='utf8'))
    baseline = json.loads((ROOT / 'baseline-inventory.json').read_text(encoding='utf8'))

    vocab = build_vocab(baseline.values())
    fixed = 0
    for rec in data:
        raw = baseline.get(rec['code'])
        if not raw:
            continue
        for field, col in TEXT_FIELDS.items():
            if ' '.join((raw[col] or '').split()) == ' '.join(str(rec.get(field, '')).split()):
                new = join_lines(raw[col], vocab)
                if new != rec[field]:
                    rec[field] = new
                    fixed += 1

    missing = [r['code'] for r in data if r.get('haspdf') and not (ROOT / 'docs' / f"{r['n']}.pdf").exists()]
    if missing:
        raise SystemExit('세부 PDF 파일 누락: ' + ', '.join(missing))
    if len({r['code'] for r in data}) != len(data):
        raise SystemExit('인정번호 중복')

    manifest = {
        'reference_date': status.get('catalog_reference_date', ''),
        'checked_utc': status.get('last_checked_utc', ''),
        'synced_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'source_commit': os.environ.get('COMMIT_REF', ''),
        'changes': status.get('changes', []),
        'record_count': len(data),
    }
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out = DATA_RE.sub(lambda _: 'const DATA=' + data_json + ';let cat=', html, count=1)
    out = MANIFEST_RE.sub(lambda x: x.group(1) + json.dumps(manifest, ensure_ascii=False).replace('<', '\\u003c') + x.group(3), out, count=1)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / 'index.html').write_text(out, encoding='utf8')
    shutil.copytree(ROOT / 'docs', DIST / 'docs')
    shutil.copytree(ROOT / 'rows', DIST / 'rows')
    (DIST / 'assets').mkdir()
    for f in ('viewer.js', 'pdfjs-LICENSE.txt'):
        shutil.copy2(ROOT / 'assets' / f, DIST / 'assets' / f)
    for packed in (ROOT / 'assets').glob('*.mjs.gz.b64'):
        (DIST / 'assets' / packed.name.removesuffix('.gz.b64')).write_bytes(gzip.decompress(base64.b64decode(packed.read_text())))
    (DIST / 'robots.txt').write_text('User-agent: *\nDisallow: /\n', encoding='utf8')
    print(f'built dist: {len(data)} records, {fixed} text cells fixed, reference {manifest["reference_date"]}')


if __name__ == '__main__':
    main()
