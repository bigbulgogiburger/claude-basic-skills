#!/usr/bin/env python3
"""GitHub 스타일 앵커 slug 계산. 손으로 짜맞추면 거의 틀린다 — 이걸 쓴다.

규칙: ①소문자화 ②[\\w\\- ] 밖 문자 제거(공백은 남김) ③공백→하이픈
핵심 함정: ②에서 공백이 보존되므로 이모지·`·`·`—` 를 지우면 그 자리 양옆 공백이
각각 하이픈이 되어 하이픈이 연달아 생긴다.

Usage:
  python slug.py "4-2. ✅ 계약 체결 완료 (2026-07-28)"
  python slug.py --file wiki/concepts/주제.md      # 모든 heading의 앵커
  python slug.py --file <md> --grep 견적서                          # 특정 heading만
"""
import sys, re, argparse, io, collections

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r'[^\w\- ]', '', s, flags=re.U)
    return s.replace(' ', '-')


def headings(path):
    """(level, text, anchor) 리스트. 중복 slug 는 GitHub 관행대로 -1, -2 를 붙인다."""
    t = io.open(path, encoding='utf8').read()
    seen = collections.Counter()
    out = []
    for m in re.finditer(r'^(#{1,6})\s+(.*)$', t, re.M):
        lvl, txt = len(m.group(1)), m.group(2).strip()
        s = slug(txt)
        seen[s] += 1
        anchor = s if seen[s] == 1 else f'{s}-{seen[s]-1}'
        out.append((lvl, txt, anchor))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('heading', nargs='*')
    ap.add_argument('--file')
    ap.add_argument('--grep')
    a = ap.parse_args()

    if a.file:
        for lvl, txt, anchor in headings(a.file):
            if a.grep and a.grep not in txt:
                continue
            print(f'{"  "*(lvl-1)}{"#"*lvl} {txt}')
            print(f'{"  "*(lvl-1)}   → #{anchor}')
        return

    if not a.heading:
        sys.exit(__doc__)
    for h in a.heading:
        print(f'#{slug(h)}')


if __name__ == '__main__':
    main()
