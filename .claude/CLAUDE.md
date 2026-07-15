# 맹호출림 에이전트 팀 설정

평안남도 도정 소식지 자동화를 위한 마멀티 에이전트 하네스.

## 프로젝트 개요

- **목표**: HWP 도정보고 → JSON 소식지 자동 생성
- **대상**: 월별 도정보고 (매달 발행)
- **팀 구성**: 4명의 에이전트 + 1개 오케스트레이션 스킬

---

## Phase 1: Collector (수집가)

**책임**: HWP 파싱 & 행사 필터링  
**입력**: HWP 도정보고 파일 + target_month  
**출력**: Event[] (필터링된 행사 목록)

### 규칙
- SKIP_EXACT: 휴일, 개인 일정 제외 (MAENGHO_SPEC.md 참조)
- SKIP_PARTIAL: 키워드 기반 제외
- 중복 제거: (날짜, 제목 앞 6자) 기준
- 개수 제한: "위원회 간담회" 1건만

### 검증
```python
✓ 단락 추출 성공
✓ 월별 섹션 식별
✓ 필터링 규칙 적용
✓ 정렬 (날짜순)
```

---

## Phase 2: Writer (저술가)

**책임**: Claude API로 기사 생성  
**입력**: Event[] + governor  
**출력**: Event[] (subtitle + body + priority)

### 기사 규칙 (MAENGHO_SPEC.md §2)

**Subtitle**
- 길이: 12자 이내
- 형식: 행사 핵심 표현

**Body**
- 길이: 250~350자 (공백 포함)
- 시작: "정경조 평안남도지사는" 또는 "정경조 지사는"
- 어조: 문어체, 경어 없음 (신문 스타일)
- 금지: "주최했다", "주관했다" → "참석했다" 중심
- 마지막 문장: 반드시 다음 중 하나
  - "~을 강조했다"
  - "~의 뜻을 밝혔다"
  - "~을 다짐했다"

**Priority** (1~5점)
- 5점: 전체 도민 참여, 남북교류, 외부 언론 보도
- 4점: 지사 주재 핵심 회의
- 3점: 위원회 행사, 기념식, 추모식
- 2점: 문화공연, 뮤지컬
- 1점: 내부 행정회의 (편집 시 제외)

### API 설정
```python
model: "claude-sonnet-4-6"
max_tokens: 700
system: SYSTEM_PROMPT (도정 소식지 편집장 롤플레이)
```

### 폴백
- API 실패 시 자동 폴백 본문 생성
- JSON 파싱 오류 시 재시도 후 폴백

---

## Phase 3: Validator (검증가)

**책임**: 기사 품질 검증  
**입력**: Event[] (with subtitle/body/priority)  
**출력**: Event[] + warnings[]

### 검증 항목

| 항목 | 기준 | 경고 조건 |
|------|------|----------|
| subtitle | ≤ 12자 | > 12자 |
| body | 250~350자 | 범위 벗어남 |
| 시작 | "정경조 지사는" | 다른 시작 |
| 금지어 | "주최"/"주관" 없음 | 포함 시 |
| 마지막 | 규정 패턴 | 다른 패턴 |
| priority | 1~5 | 범위 벗어남 |

### 출력
- ✅ 통과: 그대로 진행
- ⚠️ 경고: 기록하고 진행 (사용자 검토)

---

## Phase 4: Assembler (조립가)

**책임**: JSON 조립 & 저장  
**입력**: Event[] (validated) + meta  
**출력**: data-YYYY-MM.json

### JSON 스키마 (MAENGHO_SPEC.md §1)

```json
{
  "meta": {
    "year": 2026,
    "reportMonth": 6,
    "issueMonth": 7,
    "issueLabel": "맹호출림 7월호",
    "governor": "정경조",
    "editor": "...",
    "contact": "010-7128-7551",
    "email": "kmr980@hanmail.net",
    "homepage": "https://www.ibuk5do.go.kr/main.do"
  },
  "coverItems": ["행사명 (월. 일)", ...],
  "activities": [
    {
      "id": 1,
      "title": "행사명",
      "date": "6. 1",
      "subtitle": "12자 이내",
      "body": "250~350자",
      "priority": 3,
      "image": "photos/2026-07/01_행사명.jpg",
      "imagePosition": "right|left"
    }
  ],
  "upcomingItems": [],
  "notice": {"title": "공지사항", "icon": "📌", "lines": []},
  "schedule": [BASE_SCHEDULE 12개월]
}
```

### 정렬
- activities: priority 내림차순 (5 → 1)
- imagePosition: id 홀수=right, 짝수=left
- coverItems: activities 순서대로

### 저장
- 인코딩: UTF-8
- 형식: JSON (indent=2)
- 위치: `data-YYYY-MM.json`

---

## Orchestration: Maengho Engine

**역할**: 4단계 에이전트 조율 & 에러 처리  
**상태 모델**: AgentState

### 실행 흐름

```
[Init] → parse args
   ↓
[Phase 1] Collector.collect()
   → raw_events
   ↓
[Phase 2] Writer.write()
   → subtitle + body + priority
   ↓
[Phase 3] Validator.validate()
   → warnings[]
   ↓
[Phase 4] Assembler.assemble()
   → final_json
   ↓
[Save] → data-YYYY-MM.json
   ↓
[Summary] print results + warnings
```

### CLI 옵션

| 옵션 | 설명 |
|------|------|
| `--hwp FILE` | HWP 파일 경로 (필수) |
| `--month N` | 보고 대상 월 (필수) |
| `--out FILE` | 출력 파일명 (기본: data-YYYY-MM.json) |
| `--no-api` | Claude API 사용 안 함 (폴백만) |
| `--parse-only` | 파싱만 수행, JSON 생성 안 함 |
| `--max-items N` | 최대 기사 수 (기본: 15) |
| `--governor NAME` | 도지사 이름 (기본: 정경조) |
| `--editor NAME` | 편집자 (기본: 김명래) |

### 예시

```bash
# 기본 (API 활성화)
python maengho_agent.py --hwp schedule.hwp --month 5

# 테스트 (API 미사용)
python maengho_agent.py --hwp schedule.hwp --month 5 --no-api

# 파싱만
python maengho_agent.py --hwp schedule.hwp --month 5 --parse-only
```

---

## 상태 관리

### AgentState
```python
phase: str              # init → collect → write → validate → assemble
hwp_file: str
target_month: int
issue_month: int

raw_events: Event[]     # Phase 1 출력
validated_events: Event[] # Phase 3 출력
final_json: dict        # Phase 4 출력

errors: str[]           # 실행 오류
warnings: str[]         # 경고 (통과하되 주의)
```

### 에러 처리
- **Critical**: 파일 미존재, 헤더 미발견, API 키 미설정 → 종료
- **Warning**: JSON 파싱 실패, 글자 수 범위 위반 → 폴백/경고만

---

## 명세서 참조

**MAENGHO_SPEC.md** 섹션별 대응:
- §1 JSON 스키마 → Phase 4 (Assembler)
- §2 기사 작성 규칙 → Phase 2 (Writer)
- §3 우선도 기준 → Phase 2 (Writer)
- §4 파싱 & 필터링 → Phase 1 (Collector)
- §5 정렬 규칙 → Phase 4 (Assembler)
- §6 이미지 경로 → Phase 4 (Assembler)
- §7 에러 처리 → 전 Phase
- §8 배포 → 외부 (git push)

---

## 설정 & 환경 변수

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## 파일 구조

```
~/Downloads/maengho/
├── maengho_agent.py          ← 실행 파일 (4단계 에이전트)
├── MAENGHO_SPEC.md           ← 명세서 (규칙, 스키마)
├── .claude/
│   ├── CLAUDE.md             ← 이 파일
│   ├── agents/
│   │   ├── collector.md
│   │   ├── writer.md
│   │   ├── validator.md
│   │   └── assembler.md
│   └── skills/
│       └── maengho-engine.md
├── data-2026-07.json         ← 생성된 데이터
├── maengho-template.html     ← 렌더러
└── photos/2026-07/           ← 사진
```

---

## 체크리스트

### 처음 실행
- [ ] ANTHROPIC_API_KEY 설정
- [ ] HWP 파일 준비
- [ ] `python maengho_agent.py --hwp file.hwp --month N` 실행

### 결과 확인
- [ ] data-YYYY-MM.json 생성 확인
- [ ] activities 개수 확인
- [ ] priority 정렬 확인 (5→1)
- [ ] 경고 메시지 검토

### 배포 전
- [ ] photos/YYYY-MM/ 폴더에 사진 추가
- [ ] JSON 내용 수동 검토
- [ ] notice, upcomingItems 수동 입력
- [ ] git add/commit/push
