# Claude Code 스킬 설치 — 기본은 개인 스킬 폴더 ~/.claude/skills.
# 같은 이름의 스킬이 이미 있으면 덮기 전에 <대상>/../skills-backup/<시각>/ 로 옮겨 둔다.
#   .\install.ps1                     # ~/.claude/skills
#   .\install.ps1 -Project D:\repo    # D:\repo\.claude\skills (그 프로젝트에서만)
#   .\install.ps1 -Target D:\somewhere  # 직접 지정
param(
    [string]$Project,
    [string]$Target
)
$ErrorActionPreference = 'Stop'

if (-not $Target) {
    if ($Project) { $Target = Join-Path $Project '.claude\skills' }
    else { $Target = Join-Path $HOME '.claude\skills' }
}
$src = Join-Path $PSScriptRoot 'skills'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path (Split-Path $Target -Parent) "skills-backup\$stamp"
New-Item -ItemType Directory -Force -Path $Target | Out-Null

foreach ($skill in Get-ChildItem -LiteralPath $src -Directory) {
    $dest = Join-Path $Target $skill.Name
    if (Test-Path -LiteralPath $dest) {
        New-Item -ItemType Directory -Force -Path $backup | Out-Null
        Move-Item -LiteralPath $dest -Destination (Join-Path $backup $skill.Name)
        Write-Host "  backup  $($skill.Name) -> $backup"
    }
    Copy-Item -LiteralPath $skill.FullName -Destination $dest -Recurse
    Write-Host "  install $($skill.Name) -> $dest"
}
Write-Host "done. 의존 패키지: pip install pymupdf python-docx openpyxl python-pptx beautifulsoup4 pillow"
