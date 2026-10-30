# claude-basic-skills

LLM Wiki 와 grilling 을 위한 **Claude Code** 기본 스킬 5종.

| 스킬 | 하는 일 | 이렇게 부른다 |
|---|---|---|
| `wiki-setup` | 폴더 하나를 LLM Wiki 로 초기화 — `wiki/` 골격, 원본 인벤토리, `CLAUDE.md` 스키마(**세션 시작 시 무조건 위키부터 읽기** 규칙 포함), 폴더·파일명 관례, 첫 페이지 | "이 폴더 위키로 만들어줘" |
| `wiki-ingest` | 새 자료를 검증 → 관례에 맞는 폴더·파일명으로 배치 → 위키·catalog·index·log 반영 → 검증 | "이거 ingest 해줘", "올바른 폴더에 넣어줘" |
| `wiki-lint` | 기계 점검(링크·앵커·frontmatter·고아·log·catalog 대조·ingest 대기·충돌 사본) + 판단(모순·낡은 정보·공백·다음 질문) | "위키 점검해줘" |
| `grilling` | 계획을 실행하기 전 한 번에 한 질문씩 확정하는 인터뷰. 권장안·`AskUserQuestion` 선택지·쉬운 말, 끝나면 결정을 위키에 기록 | "grill me", "계획 점검" |
| `grill-me` | `grilling` 을 직접 시작하는 단축 명령 (자동 호출 안 됨) | `/grill-me` |

## LLM Wiki — 무엇이고 어떻게 변형했나

Andrej Karpathy 의 LLM Wiki 패턴: RAG 처럼 매번 원본을 다시 뒤지는 대신, LLM 이 원본과 사람 사이에 **지속되는 마크다운 위키**를 만들고 유지한다. 3계층 — **원본**(불변, 읽기만) · **위키**(LLM 소유) · **스키마**(`CLAUDE.md`). 연산 — **Ingest** · **Query**(좋은 답은 위키에 환원) · **Lint**. 특수 파일 — `index.md`(내용 지도) · `log.md`(append-only, `## [YYYY-MM-DD] 종류 | 요약`).

이 묶음은 실제 업무 폴더에서 수개월 돌려 다듬은 변형이다:

- **`raw/` 폴더가 없다.** 사람이 쌓아 온 기존 폴더 구조가 곧 원본층이다. 그래서 ingest 가 **배치**(어느 폴더에 어떤 이름으로)까지 맡는다.
- **`catalog.md`** 가 원본 인벤토리를 맡는다(`index.md` 는 위키 페이지 지도).
- `CLAUDE.md` 스키마에 **세션 시작 규칙**(무엇을 하든 index → overview → log 부터)과 **폴더·파일명 관례 표**가 들어간다. 관례는 위키마다 스키마에 두고, ingest 가 새 관례를 만들면 표에 추가한다 — 스킬에 특정 위키 사정을 박지 않는다.
- 기존 `CLAUDE.md` 가 있으면 덮어쓰지 않고 `<!-- llm-wiki:begin -->` … `<!-- llm-wiki:end -->` 블록만 끼워 넣는다.

자세한 비교: [`skills/wiki-setup/references/llm-wiki-pattern.md`](skills/wiki-setup/references/llm-wiki-pattern.md)

```
<위키 루트>/
├─ CLAUDE.md          스키마 — llm-wiki:begin … end 블록
├─ wiki/
│  ├─ index.md  overview.md  log.md  catalog.md
│  └─ entities/  concepts/  sources/
└─ (기존 폴더들 = 원본)
```

## 설치

```powershell
git clone https://github.com/bigbulgogiburger/claude-basic-skills.git
cd claude-basic-skills
.\install.ps1                      # ~/.claude/skills (모든 프로젝트)
.\install.ps1 -Project D:\내위키     # D:\내위키\.claude\skills (그 폴더에서만)
```

```bash
./install.sh                       # ~/.claude/skills
./install.sh --project ~/my-wiki
```

같은 이름의 스킬이 이미 있으면 덮기 전에 `skills-backup/<시각>/` 으로 옮겨 둔다. 스킬끼리 서로의 스크립트를 상대경로(`../wiki-lint/scripts/…`)로 부르므로 **다섯 개를 같은 폴더에 함께** 설치한다. 설치 후 Claude Code 를 새로 열면 잡힌다.

의존: Python 3.9+. 린터·스캐폴드는 표준 라이브러리만 쓴다. 원본 추출(`extract.py`)은

```bash
pip install pymupdf python-docx openpyxl python-pptx beautifulsoup4 pillow
```

## 쓰는 흐름

1. `wiki-setup` — 한 번. 끝나면 `CLAUDE.md` 에 "무엇을 하든 위키부터" 규칙이 들어가 있다.
2. `wiki-ingest` — 파일을 받을 때마다. 말로 준 정보도.
3. `wiki-lint` — 주기적으로. 💡 "다음에 알아볼 것 3개"가 핵심 산출물.
4. `grilling` — 무언가를 만들기 전에. 확정한 결정은 `log.md` 에 `결정` 항목으로 남는다.

## 스크립트

| 경로 | 용도 |
|---|---|
| `skills/wiki-setup/scripts/inventory.py` | 원본 인벤토리·catalog 초안 |
| `skills/wiki-setup/scripts/scaffold.py` | 골격·스키마 블록 생성 (멱등, 기존 파일 안 덮음, `--dry-run`) |
| `skills/wiki-ingest/scripts/extract.py` | PDF·DOCX·XLSX·PPTX·HTML·이미지 추출, 스캔 렌더, DOCX diff |
| `skills/wiki-ingest/scripts/slug.py` | GitHub 앵커 slug 계산 |
| `skills/wiki-lint/scripts/wiki_lint.py` | 기계 점검 (종료코드 1 = 🚨/🔴 있음) |
