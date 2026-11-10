from pathlib import Path
import base64
import gzip
for path in Path('assets').glob('*.mjs.gz.b64'):
    path.with_name(path.name.removesuffix('.gz.b64')).write_bytes(gzip.decompress(base64.b64decode(path.read_text())))
