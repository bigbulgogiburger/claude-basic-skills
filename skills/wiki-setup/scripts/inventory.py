#!/usr/bin/env python3
"""LLM Wiki 원본층 인벤토리 — 위키 루트 아래 원본 파일을 폴더별로 센다.

이 위키 구조에는 raw/ 폴더가 없다. 위키 루트 아래 기존 폴더·파일이 그대로 원본층이고,
wiki/·CLAUDE.md·AGENTS.md·도구 폴더만 빼고 센다. catalog.md 초안을 만들 때도 쓴다.

Usage:
  python inventory.py <root>                          폴더별 개수·용량·확장자 요약
  python inventory.py <root> --exclude 스킬 .openchrome  제외할 경로(루트 기준) 또는 이름 패턴 추가
  python inventory.py <root> --catalog                 catalog.md 본문(마크다운)을 출력
  python inventory.py <root> --json                    기계용 목록

기본 제외: wiki/, .git/, .obsidian/, node_modules/, __pycache__/, Office 잠금(~$*, .~lock*),
          CLAUDE.md, AGENTS.md, desktop.ini, Thumbs.db, .DS_Store
"""
import argparse
import collections
import datetime
import fnmatch
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DEFAULT_EXCLUDES = [
    'wiki', '.git', '.obsidian', '.trash', 'node_modules', '__pycache__', '.venv',
    '~$*', '.~lock*', 'CLAUDE.md', 'AGENTS.md', 'desktop.ini', 'Thumbs.db', '.DS_Store',
    '*.stackdump',
]


def human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f}{unit}' if unit in ('B', 'KB') else f'{n:.1f}{unit}'
        n /= 1024


def excluded(rel, patterns):
    """rel: 루트 기준 '/' 경로. 패턴이 '/' 를 포함하면 경로 접두로, 아니면 경로 조각 이름으로 비교."""
    parts = rel.split('/')
    for p in patterns:
        p = p.strip().strip('/').replace('\\', '/')
        if not p:
            continue
        if '/' in p:
            if rel == p or rel.startswith(p + '/'):
                return True
        elif any(fnmatch.fnmatch(part, p) for part in parts):
            return True
    return False


def scan(root, extra_excludes=()):
    """[(rel_path, size, mtime)] — 루트 기준 '/' 경로, 정렬됨."""
    patterns = DEFAULT_EXCLUDES + list(extra_excludes)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace('\\', '/')
        rel_dir = '' if rel_dir == '.' else rel_dir
        dirnames[:] = [d for d in dirnames
                       if not excluded(f'{rel_dir}/{d}'.lstrip('/'), patterns)]
        for f in filenames:
            rel = f'{rel_dir}/{f}'.lstrip('/')
            if excluded(rel, patterns):
                continue
            try:
                st = os.stat(os.path.join(dirpath, f))
            except OSError:
                continue
            out.append((rel, st.st_size, st.st_mtime))
    return sorted(out)


def group(files):
    g = collections.OrderedDict()
    for rel, size, mtime in files:
        top = rel.split('/')[0] if '/' in rel else ''
        g.setdefault(top, []).append((rel, size, mtime))
    return g


def summary(root, files):
    total = sum(s for _, s, _ in files)
    print(f'■ {root}')
    print(f'  원본 파일 {len(files):,}개 · {human(total)}\n')
    for top, items in group(files).items():
        exts = collections.Counter(os.path.splitext(r)[1].lower() or '(없음)' for r, _, _ in items)
        top3 = ', '.join(f'{e} {n}' for e, n in exts.most_common(3))
        size = human(sum(s for _, s, _ in items))
        name = f'{top}/' if top else '(루트 파일)'
        print(f'  {name:<40} {len(items):>5}개 · {size:>8} · {top3}')


def catalog(files, excludes, today):
    total = len(files)
    lines = [
        '# 전체 소스 카탈로그 (catalog)',
        '',
        f'> 원본 파일 인벤토리. 총 **{total}개** 파일 '
        f'(제외: `wiki/`·`CLAUDE.md`·`AGENTS.md`·Office 임시 `~$`/`.~lock`'
        + ''.join(f'·`{e}`' for e in excludes) + ').',
        f'> 최종 갱신: {today} (setup: 최초 생성 — inventory.py 자동 집계)',
        '',
    ]
    for top, items in group(files).items():
        size = human(sum(s for _, s, _ in items))
        head = f'## `{top}/` — {len(items)}개 · {size}' if top else f'## 루트 파일 — {len(items)}개 · {size}'
        lines += [head, '']
        for rel, s, _ in items:
            shown = rel[len(top) + 1:] if top else rel
            ext = os.path.splitext(rel)[1].lstrip('.').lower() or '-'
            lines.append(f'- {shown}  `({ext}, {human(s)})`')
        lines.append('')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--exclude', nargs='*', default=[])
    ap.add_argument('--catalog', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    if not os.path.isdir(a.root):
        sys.exit(f'[!] 폴더 없음: {a.root}')
    files = scan(a.root, a.exclude)
    if a.json:
        print(json.dumps([{'path': r, 'size': s, 'mtime': m} for r, s, m in files], ensure_ascii=False))
    elif a.catalog:
        print(catalog(files, a.exclude, datetime.date.today().isoformat()))
    else:
        summary(a.root, files)


if __name__ == '__main__':
    main()
