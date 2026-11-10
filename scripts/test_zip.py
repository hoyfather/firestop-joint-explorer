import io, zipfile
from pathlib import Path
from update import DETAIL, find_pdf

pdf = (Path(__file__).resolve().parent.parent / 'docs/842.pdf').read_bytes()
buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w') as archive:
    archive.writestr('MG-LJ-FC-PP.pdf', pdf)
notice = "egov_download_atchfile('government','x','source.zip','x.zip')"
def reader(url):
    return notice.encode() if url.startswith(DETAIL) else buffer.getvalue()
record = {'structure':'MG-LJ-FC-PP', 'company':'테스트 (031-123-4567)'}
match = find_pdf(record, [('2026-10-29','1','테스트 031-123-4567')], reader)
assert match and match[0] == pdf
print('ZIP attachment matching passed')
