#!/usr/bin/env python3
"""LLM Wiki 기계 점검 — 사람이(LLM이) 판단할 것 말고, 기계가 확실히 잡을 수 있는 것만.

검사 항목 (심각도순):
  🚨 CONFLICT        Google Drive·Dropbox·Syncthing 충돌 사본 (위키·원본 전체)
  🔴 BROKEN-LINK     없는 위키 페이지로 가는 링크 / [[wikilink]]
  🔴 BROKEN-ANCHOR   없는 제목으로 가는 #앵커 (GitHub slug 규칙)
  🔴 FRONTMATTER     누락 · type/updated/sources 필드 누락 · updated 날짜 형식
  🟡 DUP-HEADING     같은 페이지 안 중복 제목 (앵커가 -1 로 밀린다. log·catalog 는 제외)
  🟡 RAW-LINK        위키에서 원본 파일로 건 링크가 깨짐 (원본 이동·이름변경 의심)
  🟡 SOURCE-MISSING  frontmatter sources 에 적힌 원본 경로가 없음
  🟡 ORPHAN          인바운드 링크 0 / UNREACHABLE  index.md 에서 링크로 닿지 않음
  🟡 LOG             log.md 형식 위반 · 날짜 역행(중간 삽입 의심)
  🟡 CATALOG         catalog 총계 ≠ 실제 원본 수 · catalog 에 파일명이 없는 원본(폴더별 개수)
  🟡 INGEST-PENDING  log.md 마지막 저장 이후 수정된 원본 = ingest 가 밀렸을 가능성
  🟡 STALE           updated 가 --stale-days 보다 오래된 페이지
  🔵 GAPS            (미확인)·확인 필요·TBD·TODO·미정 표시가 많은 페이지

Usage:
  python wiki_lint.py <root>/wiki
  python wiki_lint.py <root>/wiki --exclude 스킬 .openchrome     원본 집계에서 뺄 폴더 (CLAUDE.md §catalog 규칙 참고)
  python wiki_lint.py <root>/wiki --stale-value "12,300,000"     남아 있으면 안 되는 낡은 값 전수 검색
  python wiki_lint.py <root>/wiki --skip-raw                     원본 스캔 생략(빠름)
  python wiki_lint.py <root>/wiki --quiet                        항목별 상세 대신 요약만

종료코드: 🚨·🔴 가 0건이면 0, 있으면 1.

앵커 함정: GitHub slug 는 소문자화 → [\\w\\- ] 밖 제거(공백 보존) → 공백을 하이픈으로.
이모지·`·`·`—` 를 지우면 양옆 공백이 각각 하이픈이 되어 하이픈이 연달아 생긴다.
"""
import argparse
import collections
import datetime
import fnmatch
import io
import os
import re
import sys
from urllib.parse import unquote

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HUBS = {'index.md', 'log.md', 'catalog.md', 'overview.md'}
RAW_EXCLUDES = ['wiki', '.git', '.obsidian', '.trash', 'node_modules', '__pycache__', '.venv',
                '~$*', '.~lock*', 'CLAUDE.md', 'AGENTS.md', 'desktop.ini', 'Thumbs.db',
                '.DS_Store', '*.stackdump']
CONFLICT_PAT = re.compile(r'충돌하는 사본|conflicted copy|\(Conflict|\.sync-conflict-|-conflict-\d', re.I)
GAP_PAT = re.compile(r'\(미확인\)|확인 필요|\bTBD\b|\bTODO\b|미정')
LINK_PAT = re.compile(r'(?<!!)\[([^\]]{0,300}?)\]\(\s*<?([^)>\s]*?)(#[^)\s>]*)?>?\s*\)')
WIKILINK_PAT = re.compile(r'\[\[([^\]|#]+)(#[^\]|]+)?(?:\|[^\]]*)?\]\]')
LOG_HEAD = re.compile(r'^## \[(\d{4}-\d{2}-\d{2})\] \S.*\|')


def slug(h):
    s = h.strip().lower()
    s = re.sub(r'[^\w\- ]', '', s, flags=re.U)
    return s.replace(' ', '-')


def strip_fences(t):
    """코드블록 안의 # 줄은 제목이 아니다. 줄 수는 보존한다."""
    return re.sub(r'```.*?```', lambda m: '\n' * m.group(0).count('\n'), t, flags=re.S)


def strip_code(t):
    """코드블록·인라인코드 안의 링크 예시는 검사하지 않는다.
    제목 slug 에는 쓰지 말 것 — GitHub 은 제목 속 인라인코드 글자도 앵커에 넣는다."""
    return re.sub(r'`[^`\n]*`', '', strip_fences(t))


def frontmatter(t):
    if not t.startswith('---'):
        return None
    parts = re.split(r'^---\s*$', t, maxsplit=2, flags=re.M)
    return parts[1] if len(parts) >= 3 else None


def fm_sources(fm):
    m = re.search(r'^sources:\s*(.*)$', fm, re.M)
    if not m:
        return []
    inline = m.group(1).strip()
    if inline.startswith('['):
        return [x or y for x, y in re.findall(r'"([^"]+)"|\'([^\']+)\'', inline)]
    items = []
    for line in fm[m.end():].splitlines():
        mm = re.match(r'^\s+-\s+["\']?(.+?)["\']?\s*$', line)
        if not mm:
            break
        items.append(mm.group(1))
    return items


def raw_excluded(rel, patterns):
    parts = rel.split('/')
    for p in patterns:
        p = p.strip().strip('/').replace('\\', '/')
        if '/' in p:
            if rel == p or rel.startswith(p + '/'):
                return True
        elif p and any(fnmatch.fnmatch(x, p) for x in parts):
            return True
    return False


def scan_raw(root, extra):
    pats = RAW_EXCLUDES + list(extra)
    out = []
    for dp, dns, fns in os.walk(root):
        rd = os.path.relpath(dp, root).replace('\\', '/')
        rd = '' if rd == '.' else rd
        dns[:] = [d for d in dns if not raw_excluded(f'{rd}/{d}'.lstrip('/'), pats)]
        for f in fns:
            rel = f'{rd}/{f}'.lstrip('/')
            if not raw_excluded(rel, pats):
                try:
                    out.append((rel, os.path.getmtime(os.path.join(dp, f))))
                except OSError:
                    pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('wiki', help='wiki/ 폴더 경로')
    ap.add_argument('--root', help='원본 루트 (기본: wiki 의 부모)')
    ap.add_argument('--exclude', nargs='*', default=[], help='원본 집계 제외 폴더·패턴')
    ap.add_argument('--stale-value', nargs='*', default=[], help='남아 있으면 안 되는 낡은 값')
    ap.add_argument('--stale-days', type=int, default=180)
    ap.add_argument('--skip-raw', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--today', default=datetime.date.today().isoformat())
    a = ap.parse_args()

    wiki = os.path.abspath(a.wiki)
    root = os.path.abspath(a.root or os.path.dirname(wiki))
    today = datetime.date.fromisoformat(a.today)
    files = sorted(os.path.relpath(os.path.join(dp, f), wiki).replace('\\', '/')
                   for dp, _, fns in os.walk(wiki) for f in fns if f.endswith('.md'))
    if not files:
        sys.exit(f'[!] {wiki} 에 .md 없음')
    T = {f: io.open(os.path.join(wiki, f), encoding='utf-8', errors='replace').read() for f in files}
    stems = collections.defaultdict(list)
    for f in files:
        stems[os.path.splitext(os.path.basename(f))[0]].append(f)

    iss = collections.defaultdict(list)   # severity -> [(file, line, kind, detail)]

    def add(sev, f, ln, kind, detail=''):
        iss[sev].append((f, ln, kind, detail))

    # heading → anchor 집합, 중복 heading
    heads = {}
    for f, t in T.items():
        seen = collections.Counter()
        heads[f] = set()
        for m in re.finditer(r'^(#{1,6})\s+(.*?)\s*#*\s*$', strip_fences(t), re.M):
            s = slug(m.group(2))
            seen[s] += 1
            heads[f].add(s if seen[s] == 1 else f'{s}-{seen[s] - 1}')
        if os.path.basename(f) in ('log.md', 'catalog.md'):
            continue                      # 로그 항목마다 반복되는 「미결」「위키 반영」 소제목은 정상
        for s, k in seen.items():
            if k > 1:
                add('🟡', f, 0, 'DUP-HEADING', f'#{s} ×{k} (두 번째부터 앵커가 #{s}-1 …)')

    # 링크·앵커 → 그래프
    graph = collections.defaultdict(set)
    for f, t in T.items():
        body = strip_code(t)
        base = os.path.dirname(f)
        for m in LINK_PAT.finditer(body):
            tgt, anc = unquote(m.group(2) or ''), unquote(m.group(3) or '')
            ln = body[:m.start()].count('\n') + 1
            if re.match(r'^[a-z][a-z0-9+.-]*:', tgt, re.I):
                continue                                   # http:, mailto:, file: …
            if tgt and not tgt.endswith('.md'):
                p = os.path.normpath(os.path.join(wiki, base, tgt))
                if '.' in os.path.basename(tgt) and not os.path.exists(p):
                    add('🟡', f, ln, 'RAW-LINK', tgt)
                continue
            if tgt:
                p = os.path.normpath(os.path.join(base, tgt)).replace('\\', '/')
                if p.startswith('..'):
                    if not os.path.exists(os.path.normpath(os.path.join(wiki, p))):
                        add('🔴', f, ln, 'BROKEN-LINK', f'{tgt} (위키 밖으로 나가는 .md 경로)')
                    continue
                if p not in T:
                    add('🔴', f, ln, 'BROKEN-LINK', tgt)
                    continue
                tf = p
                graph[f].add(tf)
            else:
                tf = f
            if anc[1:] and anc[1:].lower() not in heads[tf]:
                add('🔴', f, ln, 'BROKEN-ANCHOR', f'{tgt or "(self)"}{anc}')
        for m in WIKILINK_PAT.finditer(body):
            name = m.group(1).strip()
            ln = body[:m.start()].count('\n') + 1
            cands = stems.get(os.path.splitext(os.path.basename(name))[0], [])
            if not cands:
                add('🔴', f, ln, 'BROKEN-LINK', f'[[{name}]]')
                continue
            graph[f].add(cands[0])
            anc = m.group(2)
            if anc and slug(anc[1:]) not in heads[cands[0]]:
                add('🔴', f, ln, 'BROKEN-ANCHOR', f'[[{name}{anc}]]')

    # frontmatter · sources · stale · gaps
    gaps = []
    for f, t in T.items():
        if os.path.basename(f) in HUBS:
            continue
        fm = frontmatter(t)
        if fm is None:
            add('🔴', f, 1, 'FRONTMATTER', '없음')
            continue
        for k in ('type', 'updated', 'sources'):
            if not re.search(rf'^{k}:', fm, re.M):
                add('🔴', f, 1, 'FRONTMATTER', f'{k} 누락')
        m = re.search(r'^updated:\s*["\']?([^"\'\s]+)', fm, re.M)
        if m:
            try:
                d = datetime.date.fromisoformat(m.group(1))
                if (today - d).days > a.stale_days:
                    add('🟡', f, 1, 'STALE', f'updated {d} ({(today - d).days}일 전)')
            except ValueError:
                add('🔴', f, 1, 'FRONTMATTER', f'updated 형식 {m.group(1)} (YYYY-MM-DD 여야 함)')
        for src in fm_sources(fm):
            # 경로처럼 생긴 것만 본다: URL·설명문(「」, →, 괄호 머리말)·와일드카드는 제외
            if (not re.search(r'\.\w{1,5}$', src) or '*' in src or re.match(r'^[a-z]+://', src, re.I)
                    or src.startswith('(') or '「' in src or '→' in src):
                continue
            src_x = os.path.expanduser(src)
            cands = [src_x] if os.path.isabs(src_x) else [os.path.join(root, src_x), os.path.join(wiki, src_x)]
            if not any(os.path.exists(p) for p in cands):
                add('🟡', f, 1, 'SOURCE-MISSING', src)
        n = len(GAP_PAT.findall(t))
        if n:
            gaps.append((n, f))

    # 고아 · index 에서 도달 불가
    inbound = collections.Counter(t for f, ts in graph.items() for t in ts if t != f)
    reach, stack = set(), ['index.md'] if 'index.md' in T else []
    while stack:
        x = stack.pop()
        if x not in reach:
            reach.add(x)
            stack.extend(graph[x])
    for f in files:
        if os.path.basename(f) in HUBS or os.path.basename(f).startswith('_'):
            continue
        if inbound[f] == 0:
            add('🟡', f, 0, 'ORPHAN', '인바운드 링크 0')
        elif 'index.md' in T and f not in reach:
            add('🟡', f, 0, 'UNREACHABLE', 'index.md 에서 링크로 닿지 않음')

    # log.md
    last_log = None
    if 'log.md' in T:
        prev = None
        for i, line in enumerate(T['log.md'].splitlines(), 1):
            if not line.startswith('## '):
                continue
            m = LOG_HEAD.match(line)
            if not m:
                add('🟡', 'log.md', i, 'LOG', f'형식 위반: {line[:70]}')
                continue
            d = m.group(1)
            if prev and d < prev:
                add('🟡', 'log.md', i, 'LOG', f'날짜 역행 {prev} → {d} (중간 삽입·재정렬 의심)')
            prev = d
            last_log = d if not last_log or d > last_log else last_log
    else:
        add('🔴', 'log.md', 0, 'LOG', 'log.md 없음')

    # 원본 대조 · 충돌 사본
    raw = [] if a.skip_raw else scan_raw(root, a.exclude)
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if CONFLICT_PAT.search(fn):
                add('🚨', os.path.relpath(os.path.join(dp, fn), root).replace('\\', '/'), 0, 'CONFLICT', '충돌 사본')
    uncataloged = []
    if raw and 'catalog.md' in T:
        cat = T['catalog.md']
        m = re.search(r'총\s*\*{0,2}\s*([\d,]+)\s*\*{0,2}\s*개', cat)
        if m and int(m.group(1).replace(',', '')) != len(raw):
            add('🟡', 'catalog.md', 0, 'CATALOG',
                f'헤더 총계 {m.group(1)} ≠ 실제 원본 {len(raw):,} (제외 규칙이 다르면 --exclude 로 맞출 것)')
        uncataloged = sorted((r for r in raw if os.path.basename(r[0]) not in cat), key=lambda r: -r[1])
        if uncataloged:
            by_top = collections.Counter(r.split('/')[0] if '/' in r else '(루트)' for r, _ in uncataloged)
            add('🟡', 'catalog.md', 0, 'CATALOG',
                f'catalog 에 파일명이 없는 원본 {len(uncataloged)}개 — 폴더별: '
                + ', '.join(f'{k} {n}' for k, n in by_top.most_common(8))
                + ' (폴더를 요약 등재한 경우는 정상)')
    fresh = []
    if raw and 'log.md' in T:
        # 기준은 log.md 가 마지막으로 저장된 시각 — 날짜 단위로 자르면 같은 날 ingest 한 파일까지 잡힌다
        cut = os.path.getmtime(os.path.join(wiki, 'log.md'))
        fresh = sorted((r for r in raw if r[1] > cut), key=lambda r: -r[1])
        if fresh:
            add('🟡', 'catalog.md', 0, 'INGEST-PENDING',
                f'log.md 마지막 저장({datetime.datetime.fromtimestamp(cut):%Y-%m-%d %H:%M}) 이후 '
                f'수정된 원본 {len(fresh)}개 — 아래 목록')

    # 낡은 값
    stale_hits = collections.defaultdict(list)
    for val in a.stale_value:
        for f, t in T.items():
            for m in re.finditer(re.escape(val), t):
                ctx = t[max(0, m.start() - 60):m.end() + 40].replace('\n', ' ')
                stale_hits[val].append((f, t[:m.start()].count('\n') + 1, ctx))

    # ── 출력 ──
    print(f'■ LLM Wiki lint — {wiki}')
    print(f'  페이지 {len(files)}개 · 원본 {"스캔 생략" if a.skip_raw else f"{len(raw):,}개"}'
          f' · log 최신 {last_log or "-"}'
          + (f' ({(today - datetime.date.fromisoformat(last_log)).days}일 전)' if last_log else ''))
    labels = {'🚨': '지금 처리', '🔴': '깨짐', '🟡': '구조·정합성', '🔵': '데이터 공백'}
    for sev in ('🚨', '🔴', '🟡'):
        items = iss[sev]
        kinds = collections.Counter(k for _, _, k, _ in items)
        print(f'\n{sev} {labels[sev]} — {len(items)}건' +
              (f'  ({", ".join(f"{k} {n}" for k, n in kinds.most_common())})' if items else '  ✅'))
        if a.quiet:
            continue
        for f, ln, k, d in sorted(items, key=lambda x: (x[2], x[0], x[1]))[:200]:
            print(f'  [{k}] {f}' + (f':L{ln}' if ln else '') + (f'  {d}' if d else ''))
        if len(items) > 200:
            print(f'  … 외 {len(items) - 200}건')
    if fresh and not a.quiet:
        print(f'\n  ingest 대기 후보 — log 최신일 이후 수정된 원본 (최근순 상위 30 / 총 {len(fresh)}):')
        for rel, mt in fresh[:30]:
            print(f'    {datetime.date.fromtimestamp(mt)}  {rel}'
                  + ('' if os.path.basename(rel) in T.get('catalog.md', '') else '   ← catalog 미등재'))
    if gaps:
        print(f'\n🔵 {labels["🔵"]} — 표시 많은 페이지 상위 10')
        for n, f in sorted(gaps, reverse=True)[:10]:
            print(f'  {n:>3}  {f}')
    if a.stale_value:
        print('\n■ 낡은 값 잔존')
        for val in a.stale_value:
            print(f'  {val}: {len(stale_hits[val])}건')
            for f, ln, c in stale_hits[val]:
                print(f'    {f}:L{ln}  …{c}…')
        print('  ⚠️ 이력 표기(취소선, "수정 전" 열)는 정상 — 문맥을 보고 판단')

    sys.exit(1 if iss['🚨'] or iss['🔴'] else 0)


if __name__ == '__main__':
    main()
