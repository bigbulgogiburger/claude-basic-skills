#!/usr/bin/env python3
"""LLM Wiki 골격 생성 — 기존 파일을 절대 덮어쓰지 않는다(멱등).

만드는 것:
  wiki/{index,overview,log,catalog}.md, wiki/{entities,concepts,sources}/
  CLAUDE.md  — 없으면 새로 만들고, 있으면 LLM Wiki 블록을 첫 제목 아래에 끼워 넣는다
이미 llm-wiki:begin 표시가 있는 CLAUDE.md, 이미 있는 wiki 파일은 건드리지 않고 SKIP 으로 보고한다.

Usage:
  python scaffold.py <root> --name "결혼 준비" --domain "예식·스드메·하객 준비" [--exclude 스킬 _tools] [--dry-run]
"""
import argparse
import datetime
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), 'assets')
sys.path.insert(0, HERE)
import inventory  # noqa: E402

BEGIN = '<!-- llm-wiki:begin'
CONVENTIONS_PLACEHOLDER = '| _(setup 중 실제 폴더에서 관찰한 관례로 채운다)_ | | | |'


def render(name, **kv):
    with open(os.path.join(ASSETS, name), encoding='utf-8') as f:
        t = f.read()
    for k, v in kv.items():
        t = t.replace('{{' + k + '}}', v)
    return t


def insert_block(text, block):
    """첫 H1 바로 아래(없으면 맨 위)에 블록을 넣는다."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith('# '):
            return ''.join(lines[:i + 1]) + '\n' + block + '\n' + ''.join(lines[i + 1:])
    return block + '\n' + text


def hub_files(name, domain, today, catalog_md):
    return {
        'index.md': f"""# {name} 위키 — 색인 (index)

{name} LLM Wiki 내비게이션 허브. 질문이 생기면 여기서 관련 페이지를 찾아 들어간다.
운영 규칙은 상위 [`CLAUDE.md`](../CLAUDE.md), 원본 목록은 [catalog.md](catalog.md), 작업 이력은 [log.md](log.md).

## 시작점
- [📌 Overview](overview.md) — {domain}

## 엔티티 (사람·조직·시스템·거래처)
_(아직 없음 — ingest 하면서 추가)_

## 개념 (주제·절차·구조)
_(아직 없음)_

## 소스 요약
_(아직 없음)_
""",
        'overview.md': f"""# {name} — Overview

> {domain}

_(setup 직후 초안. 원본을 훑어 이 위키가 다루는 범위·주요 주체·현재 진행 상황을 한 페이지로 정리한다.)_

## 범위

## 주요 주체

## 지금 진행 중인 것

## 미결 이슈
""",
        'log.md': f"""# 작업 로그 (log)

append-only. 새 항목은 맨 끝에 `## [YYYY-MM-DD] <종류> | <한 줄 요약>` 형식으로 추가한다.
최근 상황은 `grep "^## \\[" wiki/log.md | tail -10` 으로 본다.

## [{today}] setup | LLM Wiki 초기화 — {name}
- wiki-setup 스킬로 골격 생성: index · overview · log · catalog · entities/ · concepts/ · sources/
- CLAUDE.md 에 LLM Wiki 블록(세션 시작 시 위키 먼저 읽기 규칙 포함)
""",
        'catalog.md': catalog_md,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--name', required=True, help='위키 이름 (예: 영업팀 업무, 결혼 준비)')
    ap.add_argument('--domain', required=True, help='한 줄 도메인 설명')
    ap.add_argument('--exclude', nargs='*', default=[], help='원본 집계에서 뺄 폴더·패턴')
    ap.add_argument('--today', default=datetime.date.today().isoformat())
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        sys.exit(f'[!] 폴더 없음: {root}')

    report = []

    def write(path, content):
        rel = os.path.relpath(path, root).replace('\\', '/')
        if a.dry_run:
            report.append(('WOULD-CREATE', rel))
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        report.append(('CREATE', rel))

    wiki = os.path.join(root, 'wiki')
    for d in ('entities', 'concepts', 'sources'):
        p = os.path.join(wiki, d)
        if os.path.isdir(p):
            report.append(('SKIP', f'wiki/{d}/ (이미 있음)'))
        elif a.dry_run:
            report.append(('WOULD-CREATE', f'wiki/{d}/'))
        else:
            os.makedirs(p)
            report.append(('CREATE', f'wiki/{d}/'))

    files = inventory.scan(root, a.exclude)
    catalog_md = inventory.catalog(files, a.exclude, a.today)
    for fname, content in hub_files(a.name, a.domain, a.today, catalog_md).items():
        p = os.path.join(wiki, fname)
        if os.path.exists(p):
            report.append(('SKIP', f'wiki/{fname} (이미 있음 — 덮어쓰지 않음)'))
        else:
            write(p, content)

    excludes = ''.join(f', `{e}`' for e in a.exclude)
    block = render('CLAUDE.block.md', NAME=a.name, DOMAIN=a.domain, TODAY=a.today,
                   EXCLUDES=excludes, CONVENTIONS=CONVENTIONS_PLACEHOLDER)
    p = os.path.join(root, 'CLAUDE.md')
    if not os.path.exists(p):
        write(p, f'# {a.name} LLM Wiki — 스키마 / 운영 규칙\n\n'
                 f'> 한국어로 답하고, 기술용어는 원어를 유지한다.\n\n' + block)
    else:
        with open(p, encoding='utf-8') as f:
            text = f.read()
        if BEGIN in text:
            report.append(('SKIP', 'CLAUDE.md (LLM Wiki 블록 이미 있음)'))
        elif a.dry_run:
            report.append(('WOULD-INSERT', 'CLAUDE.md (기존 내용 보존, 첫 제목 아래에 블록 삽입)'))
        else:
            with open(p, 'w', encoding='utf-8', newline='\n') as f:
                f.write(insert_block(text, block))
            report.append(('INSERT', 'CLAUDE.md (기존 내용 보존, 첫 제목 아래에 블록 삽입)'))

    print(f'■ {root}  (원본 {len(files):,}개 집계)')
    for kind, what in report:
        print(f'  {kind:<13} {what}')


if __name__ == '__main__':
    main()
