# Obsidian Site

`F:\workspace\obsidian\para`의 Markdown을 GitHub Pages에서 볼 수 있는 정적 HTML 사이트로 변환하는 전시용 프로젝트다.

## 역할

- Obsidian vault는 원본 기억/글쓰기 공간이다.
- 이 폴더는 공개 전시용 HTML/CSS 산출물을 만든다.
- GitHub Pages에는 `site/` 폴더의 정적 파일을 올리는 것을 목표로 한다.

## 현재 변환 규칙

- 원본: `F:\workspace\obsidian\para`
- 출력: `F:\workspace\obsidian-site\site`
- Obsidian 폴더 구조를 HTML 경로로 유지한다.
- `Area/100. 일기`도 포함한다.
- `.obsidian`, `.git`, `Attached file`은 제외한다.
- `_system`은 내부 운영 문서라 기본 제외한다.
- 이미지 파일은 아직 자동 복사하지 않는다. 웹 발행용 이미지는 나중에 압축본을 사이트 assets에 넣는다.

## 다음 단계

1. 변환 결과를 브라우저로 확인한다.
2. 공개하면 안 되는 글이 섞여 있는지 점검한다.
3. GitHub Pages 저장소 구조를 결정한다.
4. 필요한 이미지 압축/삽입 루틴을 추가한다.
