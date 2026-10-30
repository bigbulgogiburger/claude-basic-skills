#!/usr/bin/env python3
"""포맷별 텍스트·구조 추출. 스캔 PDF는 --render 로 이미지를 뽑아 Read 도구로 눈으로 본다.

Usage:
  python extract.py <file>                    구조 요약 + 텍스트
  python extract.py <file> --render 1,2,9     해당 페이지/슬라이드를 PNG로 (1-based)
  python extract.py <file> --render all       전부
  python extract.py <file> --outdir <폴더>     PNG 저장 위치 (기본: 시스템 임시폴더/extract_out)
  python extract.py <file> --grep "계약금액"   해당 문자열 주변만 출력
  python extract.py <a> <b> --diff            두 문서(docx) 문단 단위 diff

의존: pip install pymupdf python-docx openpyxl python-pptx beautifulsoup4 pillow
"""
import sys, os, re, zipfile, argparse, difflib, tempfile

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

OUT_DEFAULT = os.path.join(tempfile.gettempdir(), 'extract_out')


def _need(mod, pkg=None):
    try:
        return __import__(mod)
    except ImportError:
        sys.exit(f"[!] {mod} 없음 → pip install {pkg or mod}")


# ── PDF ───────────────────────────────────────────────────────────────
def pdf(path, render=None, outdir=OUT_DEFAULT, grep=None):
    fitz = _need('fitz', 'pymupdf')
    d = fitz.open(path)
    total_text = sum(len(p.get_text().strip()) for p in d)
    scanned = total_text < 50 * len(d)
    print(f"■ PDF {len(d)}p · {round(d[0].rect.width)}x{round(d[0].rect.height)}pt "
          f"· 텍스트 {total_text:,}자 → {'⚠️ 스캔 이미지(--render 로 눈으로 확인)' if scanned else '추출 가능'}")
    for i, p in enumerate(d, 1):
        imgs = len(p.get_images(full=True))
        t = p.get_text().strip()
        print(f"  p{i}: 텍스트 {len(t):>6}자 · 이미지 {imgs}")
    if not scanned:
        print("\n── 텍스트 ──")
        for i, p in enumerate(d, 1):
            t = p.get_text().strip()
            if not t:
                continue
            if grep:
                for m in re.finditer(re.escape(grep), t):
                    print(f"  p{i} …{t[max(0,m.start()-90):m.end()+90]}…")
            else:
                print(f"\n--- p{i} ---\n{t}")
    if render:
        os.makedirs(outdir, exist_ok=True)
        pages = range(len(d)) if render == 'all' else [int(x) - 1 for x in render.split(',')]
        print("\n── 렌더 ──")
        for i in pages:
            f = os.path.join(outdir, f"{os.path.splitext(os.path.basename(path))[0]}_p{i+1}.png")
            d[i].get_pixmap(dpi=110).save(f)
            print(f"  {f}")
        print("  → Read 도구로 열어 눈으로 확인할 것")


# ── DOCX ──────────────────────────────────────────────────────────────
def docx_paras(path):
    """문단 텍스트 리스트. run 병합 후 반환 (tracked change 는 삽입분만 = 변경 반영 후 상태)."""
    x = zipfile.ZipFile(path).read('word/document.xml').decode('utf8')
    out = []
    for q in re.findall(r'<w:p[ >].*?</w:p>', x, re.S):
        t = ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', q, re.S))
        t = t.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        if t.strip():
            out.append(t)
    return out


def docx(path, grep=None):
    z = zipfile.ZipFile(path)
    ps = docx_paras(path)
    tracked = '<w:ins' in z.read('word/document.xml').decode('utf8')
    has_comments = 'word/comments.xml' in z.namelist()
    print(f"■ DOCX 문단 {len(ps)}개"
          f"{' · ⚠️ 변경내용 추적 있음(아래는 변경 반영 후 상태)' if tracked else ''}"
          f"{' · 💬 코멘트 있음' if has_comments else ''}")
    if has_comments:
        c = z.read('word/comments.xml').decode('utf8')
        print("\n── 코멘트 ──")
        for m in re.finditer(r'<w:comment [^>]*w:id="(\d+)"[^>]*w:author="([^"]*)"[^>]*>(.*?)</w:comment>', c, re.S):
            t = ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', m.group(3), re.S))
            print(f"  [{m.group(1)}] {m.group(2)}: {t}")
    print("\n── 본문 ──")
    for i, t in enumerate(ps):
        if grep and grep not in t:
            continue
        print(f"  {i:>3}| {t}")


def docx_diff(a, b):
    pa, pb = docx_paras(a), docx_paras(b)
    print(f"■ diff  A={os.path.basename(a)} ({len(pa)}문단)  B={os.path.basename(b)} ({len(pb)}문단)\n")
    n = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, pa, pb).get_opcodes():
        if op == 'equal':
            continue
        n += 1
        print(f"[{n}] {op.upper()}")
        for x in pa[i1:i2]:
            print(f"  - A: {x}")
        for x in pb[j1:j2]:
            print(f"  + B: {x}")
        print()
    print(f"변경 블록 {n}개")


# ── XLSX ──────────────────────────────────────────────────────────────
def xlsx(path, grep=None):
    openpyxl = _need('openpyxl')
    wb = openpyxl.load_workbook(path, data_only=False)
    media = [n for n in zipfile.ZipFile(path).namelist() if '/media/' in n]
    print(f"■ XLSX 시트 {len(wb.sheetnames)}개: {wb.sheetnames}"
          f"{f' · 이미지 {len(media)}개 {media}' if media else ''}")
    for sn in wb.sheetnames:
        ws = wb[sn]
        print(f"\n── {sn} ({ws.dimensions}) ──")
        for r in ws.iter_rows():
            cells = [(c.coordinate, c.value) for c in r if c.value not in (None, '')]
            if not cells:
                continue
            line = ' | '.join(f'{k}={str(v)[:60]}' for k, v in cells)
            if grep and grep not in line:
                continue
            print(f"  {line}")


# ── PPTX ──────────────────────────────────────────────────────────────
def pptx(path, grep=None):
    _need('pptx', 'python-pptx')
    from pptx import Presentation
    pr = Presentation(path)
    media = [n for n in zipfile.ZipFile(path).namelist() if '/media/' in n]
    print(f"■ PPTX 슬라이드 {len(pr.slides)}장" + (f" · 미디어 {len(media)}개" if media else ""))
    for i, s in enumerate(pr.slides, 1):
        texts = [sh.text_frame.text.strip() for sh in s.shapes
                 if sh.has_text_frame and sh.text_frame.text.strip()]
        blob = ' / '.join(texts)
        if grep and grep not in blob:
            continue
        print(f"\n--- slide {i} ---")
        for t in texts:
            print(f"  {t}")


# ── HTML / TEXT ───────────────────────────────────────────────────────
def html(path, grep=None):
    _need('bs4', 'beautifulsoup4')
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(open(path, encoding='utf8', errors='replace').read(), 'html.parser')
    t = soup.get_text('\n', strip=True)
    print(f"■ HTML 텍스트 {len(t):,}자")
    for line in t.split('\n'):
        if grep and grep not in line:
            continue
        print(f"  {line}")


def plain(path, grep=None):
    t = open(path, encoding='utf8', errors='replace').read()
    print(f"■ TEXT {len(t):,}자")
    for i, line in enumerate(t.split('\n'), 1):
        if grep and grep not in line:
            continue
        print(f"  {i:>4}| {line}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--render')
    ap.add_argument('--outdir', default=OUT_DEFAULT)
    ap.add_argument('--grep')
    ap.add_argument('--diff', action='store_true')
    a = ap.parse_args()

    if a.diff:
        if len(a.files) != 2:
            sys.exit("--diff 는 파일 2개 필요")
        return docx_diff(*a.files)

    for f in a.files:
        if not os.path.exists(f):
            print(f"[!] 없음: {f}")
            continue
        if os.path.basename(f).startswith('~$'):
            print(f"[skip] Office 임시 잠금파일: {f}")
            continue
        ext = os.path.splitext(f)[1].lower()
        print(f"\n{'='*70}\n{f}\n{'='*70}")
        try:
            if ext == '.pdf':
                pdf(f, a.render, a.outdir, a.grep)
            elif ext in ('.docx', '.dotx'):
                docx(f, a.grep)
            elif ext in ('.xlsx', '.xlsm', '.xltx'):
                xlsx(f, a.grep)
            elif ext in ('.pptx', '.potx'):
                pptx(f, a.grep)
            elif ext in ('.html', '.htm'):
                html(f, a.grep)
            elif ext in ('.md', '.txt', '.json', '.csv', '.sql', '.py'):
                plain(f, a.grep)
            elif ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'):
                _need('PIL', 'pillow')
                from PIL import Image
                im = Image.open(f)
                alpha = im.mode in ('RGBA', 'LA', 'P') and 'transparency' in im.info or im.mode in ('RGBA', 'LA')
                line = f"■ 이미지 {im.size} {im.mode}"
                corner = None
                if alpha:
                    corner = im.convert('RGBA').getpixel((0, 0))
                    line += f" · 코너 RGBA {corner}"
                print(line)
                if corner and corner[3] < 8:
                    print("  ⚠️ 이미 투명 배경이다 — 배경 제거를 다시 돌리지 말 것. "
                          "투명 영역 RGB가 보통 (0,0,0)이라 밝기 기준 로직이 불투명하게 되살려 "
                          "검은 사각형이 된다. `a<8 → (255,255,255,0)` 정리 + 크롭만 할 것. "
                          "(references/wiki-rules.md §투명 PNG)")
                print("  → Read 도구로 직접 볼 것")
            else:
                print(f"[?] 미지원 확장자 {ext} — 직접 열어 확인")
        except Exception as e:
            print(f"[!] 실패: {type(e).__name__}: {e}")


if __name__ == '__main__':
    main()
