#!/usr/bin/env bash
# Claude Code 스킬 설치 — 기본은 개인 스킬 폴더 ~/.claude/skills.
# 같은 이름의 스킬이 이미 있으면 덮기 전에 <대상>/../skills-backup/<시각>/ 로 옮겨 둔다.
#   ./install.sh                     # ~/.claude/skills
#   ./install.sh --project DIR       # DIR/.claude/skills (그 프로젝트에서만)
#   ./install.sh --target DIR        # 직접 지정
set -euo pipefail

case "${1:-}" in
  "") target="$HOME/.claude/skills" ;;
  --project) target="${2:?--project 에 경로가 필요합니다}/.claude/skills" ;;
  --target) target="${2:?--target 에 경로가 필요합니다}" ;;
  *) echo "usage: $0 [--project DIR | --target DIR]" >&2; exit 2 ;;
esac

src="$(cd "$(dirname "$0")" && pwd)/skills"
backup="$(dirname "$target")/skills-backup/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$target"

for skill in "$src"/*/; do
  name="$(basename "$skill")"
  dest="$target/$name"
  if [ -e "$dest" ]; then
    mkdir -p "$backup"
    mv "$dest" "$backup/$name"
    echo "  backup  $name -> $backup"
  fi
  cp -R "$skill" "$dest"
  echo "  install $name -> $dest"
done
echo "done. 의존 패키지: pip install pymupdf python-docx openpyxl python-pptx beautifulsoup4 pillow"
