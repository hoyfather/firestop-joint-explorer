# 내화채움구조 선형조인트 탐색기

한국건설기술연구원(KICT) 건축자재등[내화채움구조] 전체 인정현황 중 선형조인트 항목을 검색하고 세부 인정내용 PDF를 보는 사이트입니다. Netlify가 이 저장소를 받아 배포합니다.

> 참고용 도구입니다. 설계·시공 적용 전 세부 인정내용 원문과 연구원 공고에서 적용 조건을 확인하세요.

## 구성

| 시각 (KST) | 주체 | 하는 일 |
|---|---|---|
| 매월 15일 10:17 | GitHub Actions (`.github/workflows/pages.yml`) | `scripts/update.py` → 연구원 인정현황·공고 확인 → `index.html`(DATA), `docs/`, `rows/`, `update-status.json` 갱신 후 커밋 |
| 커밋 직후 | Netlify (`netlify.toml`) | `scripts/build_site.py` 로 `dist/` 생성(띄어쓰기 보정, PDF.js 해제) 후 배포 |

GitHub 예약 실행은 지연될 수 있습니다. Actions 탭 "Monthly catalogue update"에서 Run workflow로 수동 실행할 수 있습니다. `build_site.py`는 세부 PDF 누락 등 이상이 있으면 실패하며, 이때 Netlify는 직전 배포를 그대로 유지합니다.

## 자동 갱신 동작

- 연구원 전체 인정현황 PDF에서 선형조인트 행(FS-FF/FC/HW/WW)을 추출하고, 기준일 이후의 신규인정·인정변경·인정취소 공고에서 세부 PDF를 찾아 연결합니다.
- 세부 PDF를 하나로 확정하지 못한 신규 항목은 PDF 없이 "원문 대조 확인 필요"로 표시됩니다.
- 신규 항목의 커튼월 분류(외벽 형태·프레임·단열재)는 자동으로 채워지지 않아 수작업 검토가 필요합니다.
- 기존 인정번호가 원본에서 사라지거나 항목 수가 급감하면 갱신을 중단하고 기존 데이터를 유지합니다.

`update.py`는 `index.html`의 `const DATA=[...];let cat=` 구간과 `<div class="alert"><b>…</b>…</div>` 문구를 직접 바꿉니다. `build_site.py`는 `<script type="application/json" id="sync-manifest">`도 사용합니다. 이 표지들은 유지해야 합니다.

## 로컬 확인

```
python3 scripts/build_site.py
python3 -m http.server -d dist 8000
```

## 공개 범위

Netlify 무료 요금제는 비밀번호 보호를 지원하지 않아 주소를 아는 누구나 접속할 수 있습니다. 검색엔진 색인은 `netlify.toml`의 `X-Robots-Tag`와 `robots.txt`로 거부합니다(접근 차단 기능은 아님). 이 저장소가 공개이면 자료와 PDF도 누구나 내려받을 수 있습니다.
