#!/usr/bin/env python3
"""내화채움구조 선형조인트 탐색기 - 사내 공유본(Claude 아티팩트) 동기화.

GitHub 저장소(hoyfather/firestop-joint-explorer)의 월간 자동 갱신 결과(DATA, PDF,
원본 행 이미지, 점검 기록)를 아티팩트 페이지에 반영할 파일을 만든다.
표준 라이브러리만 사용한다.

  python3 -I sync_artifact.py --repo REPO_DIR --page CURRENT_PAGE.html --out OUT_DIR

결과
  OUT_DIR/index.html   새 페이지 (항상 생성)
  OUT_DIR/docs, rows   바뀐 PDF·행 이미지만 복사
  OUT_DIR/plan.json    status, batches(게시 묶음), warnings, summary
페이지 안의 표지: `const DATA=[...];let cat=`, `<div class="alert">`,
`<script type="application/json" id="sync-manifest">`.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

DATA_RE = re.compile(r'const DATA=(\[.*?\]);let cat=', re.S)
ALERT_RE = re.compile(r'<div class="alert"><b>.*?</div>', re.S)
MANIFEST_RE = re.compile(r'(<script type="application/json" id="sync-manifest">)(.*?)(</script>)', re.S)
WORD = re.compile(r'[0-9A-Za-z가-힣]+')
LETTERS = re.compile(r'[A-Za-z가-힣]+')
# 인정현황 표의 열 번호 (scripts/update.py 와 동일)
TEXT_FIELDS = {'company': 3, 'product': 4, 'structure': 5, 'support': 6, 'usage': 7, 'material': 9, 'opening': 10}
SEED_WORDS = {'콘크리트', '커튼월', '알루미늄', '프레임', '선형', '조인트', '선형조인트', '그라스울', '판넬', '패널',
              '유형', '이상', '이하', '부재', '스터드', '샌드위치', '미네랄울', '내화채움구조', '수평부재', '수직부재', '관통부'}
BATCH_LIMIT = 50_000_000


def is_word(ch):
    return bool(ch) and bool(WORD.fullmatch(ch))


def lines_of(cell):
    return [x.strip() for x in (cell or '').split('\n') if x.strip()]


def build_vocab(rows):
    """줄 경계에 걸리지 않은(잘리지 않은) 단어만 모은다."""
    vocab = set(SEED_WORDS)
    for row in rows:
        for cell in row:
            ls = lines_of(cell if isinstance(cell, str) else '')
            for i, line in enumerate(ls):
                for m in WORD.finditer(line):
                    cut_start = m.start() == 0 and i > 0 and (is_word(ls[i - 1][-1]) or ls[i - 1].endswith('-'))
                    cut_end = m.end() == len(line) and i + 1 < len(ls) and is_word(ls[i + 1][0])
                    if not cut_start and not cut_end:
                        vocab.add(m.group())
    return vocab


def keep_space(left, right, vocab):
    """줄 끝 조각(left)과 다음 줄 첫 조각(right) 사이 띄어쓰기를 유지할지 판단.

    잘린 단어 조각일 때만 붙인다. 둘 다 완전한 단어이거나, 한글과 숫자가
    맞닿는 경우(에코씰 / 200MS)는 원래 띄어쓰기였을 수 있어 유지한다.
    """
    hangul = re.compile(r'[가-힣]')
    if (hangul.match(left[-1]) and right[0].isdigit()) or (left[-1].isdigit() and hangul.match(right[0])):
        return True
    if left in vocab and right in vocab:
        return True
    if left + right in vocab:
        return False                                  # 콘크 / 리트 -> 콘크리트
    lead = LETTERS.match(right)
    head = lead.group() if lead else ''
    if head and head != right and right[len(head):].isdigit() and left + head in vocab:
        return False                                  # 유 / 형1 -> 유형1
    if hangul.fullmatch(left[-1]) and hangul.match(right[0]):
        for k in range(1, len(left)):                 # 알루미늄프 / 레임 -> 알루미늄 + 프레임
            if left[:k] in vocab and left[k:] + right in vocab:
                return False
        for k in range(1, len(right)):
            if left + right[:k] in vocab and right[k:] in vocab:
                return False
    return True


def join_lines(cell, vocab):
    """PDF 표 칸 안의 강제 줄바꿈을 원래 띄어쓰기에 가깝게 잇는다."""
    ls = lines_of(cell)
    if not ls:
        return ''
    out = ls[0]
    for prev, nxt in zip(ls, ls[1:]):
        a, b = prev[-1], nxt[0]
        if prev == '-' or nxt == '-':
            sep = ' '
        elif a == '-' and len(prev) >= 2 and is_word(prev[-2]):
            sep = ''                                  # 바닥- / 커튼월, WB-ST- / 001
        elif a in '_(' or b in ')],.:;%':
            sep = ''
        elif a == '/':
            sep = ' ' if len(prev) >= 2 and prev[-2] == ' ' else ''
        elif is_word(a) and is_word(b):
            sep = ' ' if keep_space(WORD.findall(prev)[-1], WORD.findall(nxt)[0], vocab) else ''
        else:
            sep = ' '
        out += sep + nxt
    return re.sub(r' {2,}', ' ', out).strip()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json_block(html, rx, what):
    m = rx.search(html)
    if not m:
        raise SystemExit(f'{what} 표지를 찾지 못했습니다')
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--page', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--now', help='테스트용 현재 시각 (ISO, UTC)')
    args = ap.parse_args()
    repo, out = Path(args.repo), Path(args.out)
    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)

    repo_html = (repo / 'index.html').read_text(encoding='utf8')
    data = json.loads(load_json_block(repo_html, DATA_RE, '저장소 DATA').group(1))
    status = json.loads((repo / 'update-status.json').read_text(encoding='utf8'))
    baseline = json.loads((repo / 'baseline-inventory.json').read_text(encoding='utf8'))
    try:
        commit = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        commit = ''

    page = Path(args.page).read_text(encoding='utf8')
    old_data = json.loads(load_json_block(page, DATA_RE, '페이지 DATA').group(1))
    mm = load_json_block(page, MANIFEST_RE, '페이지 manifest')
    try:
        old_manifest = json.loads(mm.group(2) or '{}')
    except json.JSONDecodeError:
        old_manifest = {}
    if not ALERT_RE.search(page):
        raise SystemExit('페이지 alert 표지를 찾지 못했습니다')

    warnings = []
    # 1) 표시용 문자 보정
    vocab = build_vocab(baseline.values())
    for rec in data:
        raw = baseline.get(rec['code'])
        if not raw:
            warnings.append(f"{rec['code']}: 원본 행이 없어 띄어쓰기 보정을 건너뜀")
            continue
        for field, col in TEXT_FIELDS.items():
            if ' '.join((raw[col] or '').split()) != ' '.join(str(rec.get(field, '')).split()):
                continue                              # 저장소 값이 원본 행과 다르면 손대지 않음
            rec[field] = join_lines(raw[col], vocab)

    # 2) 파일 비교
    old_pdf, old_row = old_manifest.get('pdf', {}), old_manifest.get('row', {})
    new_pdf, new_row, upload = {}, {}, []
    for rec in data:
        n = str(rec['n'])
        row_path = repo / 'rows' / f'{n}.png'
        if row_path.exists():
            new_row[n] = sha256(row_path)
            if old_row.get(n) != new_row[n]:
                upload.append(f'rows/{n}.png')
        else:
            warnings.append(f"{rec['code']}: 원본 행 이미지 없음")
        if rec.get('haspdf'):
            pdf_path = repo / 'docs' / f'{n}.pdf'
            if not pdf_path.exists():
                warnings.append(f"{rec['code']}: 세부 PDF 파일 없음 (PDF 연결 해제 표시)")
                rec['haspdf'] = False
                continue
            new_pdf[n] = sha256(pdf_path)
            if old_pdf.get(n) != new_pdf[n]:
                upload.append(f'docs/{n}.pdf')

    # 3) 점검 기록 확인
    checked = dt.datetime.fromisoformat(status['last_checked_utc'])
    month_run = now.replace(day=15, hour=0, minute=0, second=0, microsecond=0)
    if now >= month_run and checked < month_run:
        warnings.append(f"이번 달 GitHub 자동 점검 기록이 없습니다 (마지막 점검 {checked:%Y-%m-%d %H:%M} UTC). 저장소 Actions 실행 결과를 확인하세요.")
    if not status.get('catalog_automatically_updated', False):
        warnings.append('GitHub 점검 기록에 자동 갱신 완료 표시가 없습니다.')
    unclassified = [r['code'] for r in data if r.get('category') == '바닥-커튼월' and not r.get('form') and not r.get('cancel')]
    if unclassified:
        warnings.append('커튼월 분류(외벽 형태·프레임·단열재) 미입력: ' + ', '.join(unclassified))
    unmatched = [r['code'] for r in data if not r.get('haspdf') and not r.get('cancel')]
    if unmatched:
        warnings.append('세부 PDF 미연결: ' + ', '.join(unmatched))

    data_changed = old_data != data
    ref = status.get('catalog_reference_date', '')
    manifest = {
        'reference_date': ref,
        'checked_utc': status.get('last_checked_utc', ''),
        'synced_utc': now.isoformat(timespec='seconds'),
        'source_commit': commit,
        'changes': status.get('changes', []),
        'record_count': len(data),
        'pdf': new_pdf,
        'row': new_row,
    }
    manifest_json = json.dumps(manifest, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

    new_page = DATA_RE.sub(lambda m: 'const DATA=' + data_json + ';let cat=', page, count=1)
    new_page = ALERT_RE.sub(lambda m: f'<div class="alert"><b>{ref} 인정현황 기준 · {len(data)}건</b> · 원문 공고와 세부 인정내용을 확인하세요.</div>', new_page, count=1)
    new_page = MANIFEST_RE.sub(lambda m: m.group(1) + manifest_json + m.group(3), new_page, count=1)

    # 4) 검증
    check = json.loads(DATA_RE.search(new_page).group(1))
    assert len(check) == len(data) and len({r['code'] for r in check}) == len(check), 'DATA 검증 실패'
    assert json.loads(MANIFEST_RE.search(new_page).group(2))['record_count'] == len(data)
    if '\x1b' in new_page:
        raise SystemExit('페이지에 제어 문자가 있습니다')

    # 5) 출력
    if out.exists():
        shutil.rmtree(out)
    (out / 'docs').mkdir(parents=True)
    (out / 'rows').mkdir(parents=True)
    (out / 'index.html').write_text(new_page, encoding='utf8')
    batches, cur, size = [], [], 0
    for rel in upload:
        shutil.copy2(repo / rel, out / rel)
        s = (out / rel).stat().st_size
        if cur and size + s > BATCH_LIMIT:
            batches.append(cur)
            cur, size = [], 0
        cur.append(rel)
        size += s
    if cur:
        batches.append(cur)

    pdf_up = sum(1 for x in upload if x.startswith('docs/'))
    row_up = len(upload) - pdf_up
    if data_changed or upload:
        summary = f"사내본 갱신: 인정현황 {ref} 기준 {len(data)}건, 목록 변경 {'있음' if data_changed else '없음'}, PDF {pdf_up}건·행 이미지 {row_up}건 교체"
    else:
        summary = f"변경 없음: 인정현황 {ref} 기준 {len(data)}건 유지 (점검 기록만 갱신)"
    plan = {
        'status': 'updated' if (data_changed or upload) else 'unchanged',
        'data_changed': data_changed,
        'reference_date': ref,
        'checked_utc': manifest['checked_utc'],
        'source_commit': commit,
        'changes': manifest['changes'],
        'upload_count': len(upload),
        'batches': batches,
        'warnings': warnings,
        'summary': summary,
    }
    (out / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
