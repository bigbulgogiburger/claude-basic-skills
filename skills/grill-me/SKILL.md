---
name: grill-me
description: grilling 인터뷰를 명시적으로 시작하는 단축 명령. 사용자가 /grill-me 로 직접 부를 때만 쓴다.
disable-model-invocation: true
---

# grill-me

`grilling` 세션을 시작한다. 같은 skills 폴더의 `../grilling/SKILL.md` 를 읽고 그 절차를 그대로 따른다.

`grilling` 스킬을 찾을 수 없을 때만 아래 핵심 규칙으로 진행한다:

- 이 계획의 모든 측면을 서로 합의할 때까지 집요하게 묻는다. 결정 트리의 가지를 하나씩 내려가며 결정 사이의 의존관계를 순서대로 푼다.
- 질문은 **한 번에 하나**, 매 질문에 **내 권장안**을 붙인다. 선택형이면 `AskUserQuestion` 선택지로 묻는다.
- 코드·문서·LLM Wiki(`wiki/index.md`)를 뒤져 답할 수 있는 건 묻지 않고 직접 확인한다.
- 사용자가 합의했다고 확인하기 전에는 계획을 실행하지 않는다.
