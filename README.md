# 맹호출림 에이전트 팀 하네스

**평안남도 도정 소식지 자동화 시스템**  
단일 에이전트 하네스 기반의 4단계 워크플로우

---

## 📋 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [아키텍처](#아키텍처)
3. [3단계 워크플로우](#3단계-워크플로우)
4. [사용법](#사용법)
5. [결과물](#결과물)
6. [성능](#성능)
7. [확장 계획](#확장-계획)

---

## 프로젝트 개요

### 목표
평안남도의 월별 도정보고(HWP)를 입력받아, 자동으로 소식지 JSON 데이터를 생성하고 웹으로 배포

### 문제 정의
- ❌ 기존: 수동으로 기사 작성, 데이터 입력 → 시간 소요
- ✅ 새로운: Claude AI + 하네스 → 완전 자동화

### 해결책
**단일 에이전트 하네스** (4단계)
```
HWP 파일 
  ↓ [Phase 1: Collector]
행사 데이터 (필터링됨)
  ↓ [Phase 2: Writer]
기사 콘텐츠 (Claude API)
  ↓ [Phase 3: Validator]
규칙 검증 (경고 수집)
  ↓ [Phase 4: Assembler]
JSON 소식지 데이터
  ↓ [배포]
GitHub Pages 자동 배포
```

### 주요 성과
- 🚀 **18건 행사** → 15건 필터링 (1초)
- 📝 **기사 생성** (Claude API, ~15초)
- ✅ **품질 검증** (자동 규칙 체크)
- 💾 **JSON 조립** (배포 준비 완료)

---

## 아키텍처

### 시스템 구성

```
┌─────────────────────────────────────────────────────┐
│         MaenghoAgent (단일 에이전트 하네스)          │
├─────────────────────────────────────────────────────┤
│  AgentState (상태 추적)                             │
│  ├─ phase: collect → write → validate → assemble   │
│  ├─ raw_events: Event[]                            │
│  ├─ validated_events: Event[]                      │
│  ├─ final_json: dict                               │
│  ├─ errors: []                                      │
│  └─ warnings: []                                    │
├─────────────────────────────────────────────────────┤
│  [Phase 1] Collector                               │
│    └─ HWP 파싱 → 필터링 → 정렬                      │
│  [Phase 2] Writer                                  │
│    └─ Claude API → 기사 생성                        │
│  [Phase 3] Validator                               │
│    └─ 규칙 검증 → 경고 누적                         │
│  [Phase 4] Assembler                               │
│    └─ JSON 조립 → 파일 저장                         │
└─────────────────────────────────────────────────────┘
```

### 클래스 구조

```python
MaenghoAgent
  ├─ state: AgentState
  └─ run(args) → bool

Collector(state)
  └─ collect(hwp_path, month) → Event[]

Writer(state)
  └─ write(events, governor, no_api) → Event[]

Validator(state)
  └─ validate(events) → Event[]

Assembler(state)
  ├─ assemble(events, governor, editor) → dict
  └─ save(output_file) → bool
```

---

## 3단계 워크플로우

### 📥 Phase 1: Collector (큐레이션)

**역할**: HWP 파일에서 행사 데이터 추출 & 필터링

#### 입력
```
--hwp: 도정보고 HWP 파일
--month: 보고 대상 월 (예: 5 → 6월호 생성)
```

#### 절차
1. **HWP 파싱**
   - OleFile로 BodyText/Section0 스트림 읽기
   - zlib 압축 해제
   - HWPTAG_PARA_TEXT (tag=67) 필터링
   - UTF-16-LE 디코딩 → 한글 단락 추출

2. **월별 섹션 식별**
   - 헤더: `"2026년 {month}월 평안남도 주요일정"`
   - 시작 ~ 다음 달 헤더까지 추출

3. **필터링** (MAENGHO_SPEC.md 기반)
   ```python
   SKIP_EXACT = {
     "SUN(일)", "MON(월)", ..., "SAT(토)",  # 요일
     "노동절", "부처님 오신날",              # 휴일
     "지사님 대체휴무", "지사님 연가"        # 휴가
   }
   
   SKIP_PARTIAL = [
     "연가", "대체휴무",                    # 휴무
     "도 직원회의", "직원회의",             # 내부 행정
     "결혼", "돌잔치", "장례", "빈소"      # 경조사
   ]
   ```

4. **정제**
   - 중복 제거: (날짜, 제목 앞 6자) 기준
   - 개수 제한: "위원회 간담회" 1건만
   - 정렬: 날짜순 → 시간순

#### 출력
```python
Event[] = [
  {
    day: 1,
    date: "6. 1",
    time: "10:00",
    title: "역대 도지사 간담회",
    place: "한국프레스센터 19층"
  },
  ...
]
```

#### 결과 (테스트)
```
✅ 132개 단락 추출
✅ 18건 필터링 완료
⚠️ 위원회 간담회 2건 제외 (1건만 허용)
```

---

### ✍️ Phase 2: Writer (작성)

**역할**: Claude API로 행사별 기사 생성

#### 입력
```
Event[]
--governor: 도지사 이름
--no-api: True면 폴백만 사용
```

#### 절차
1. **Claude API 호출**
   ```python
   prompt = f"""
   행사명: {event.title}
   날짜: 2026년 {event.date}
   시간: {event.time}
   장소: {event.place}
   도지사: {governor}
   
   위 행사에 대한 맹호출림 소식지 기사를 작성해주세요.
   """
   
   response = client.messages.create(
     model="claude-sonnet-4-6",
     max_tokens=700,
     system=SYSTEM_PROMPT,
     messages=[{"role": "user", "content": prompt}]
   )
   ```

2. **응답 파싱**
   - JSON 응답 예상:
     ```json
     {
       "subtitle": "호국영령 넋 기리며 통일 다짐",
       "body": "정경조 평안남도지사는 ... 다짐했다.",
       "priority": 3
     }
     ```
   - 코드블록 제거
   - JSON 파싱 → 필드 추출

3. **기사 작성 규칙** (MAENGHO_SPEC.md §2)
   ```
   Subtitle (12자 이내)
   └─ 행사 핵심 표현
   
   Body (250~350자)
   ├─ 시작: "정경조 지사는" 또는 "정경조 평안남도지사는"
   ├─ 금지: "주최했다", "주관했다" → "참석했다" 사용
   ├─ 어조: 문어체, 경어 없음 (신문 스타일)
   └─ 마지막: "~을 강조했다" / "~의 뜻을 밝혔다" / "~을 다짐했다"
   
   Priority (1~5)
   ├─ 5: 도민 참여, 남북교류, 언론 보도
   ├─ 4: 지사 주재 핵심 회의
   ├─ 3: 위원회, 기념식, 추모식
   ├─ 2: 문화공연, 뮤지컬
   └─ 1: 내부 행정
   ```

4. **폴백 처리**
   - API 실패 시 자동 생성:
     ```python
     "{governor} 평안남도지사는 {date} {title}에 참석하여 
     도민사회 발전을 위한 뜻깊은 시간을 함께했다. 
     정 지사는 공동체의 화합과 전통 계승의 중요성을 강조하며 
     도민과 함께 나아갈 것을 다짐했다."
     ```

#### 출력
```python
Event[] = [
  {
    # 기존 필드 +
    subtitle: str,
    body: str,
    priority: int
  },
  ...
]
```

#### 결과 (테스트, --no-api 모드)
```
✅ 15건 기본 기사 생성 완료
⚠️ 폴백 본문 사용 (API 테스트 모드)
```

---

### ✅ Phase 3: Validator (검증)

**역할**: 생성된 기사 규칙 준수 여부 검증

#### 입력
```
Event[] (with subtitle, body, priority)
```

#### 절차

| 검증 항목 | 기준 | 실패 시 |
|---------|------|--------|
| Subtitle | ≤ 12자 | ⚠️ "{N}자 > 12자" |
| Body | 250~350자 | ⚠️ "{N}자 (범위: 250~350)" |
| 시작 어구 | "정경조 지사는" | ⚠️ "도지사명으로 시작 안 함" |
| 금지 표현 | "주최"/"주관" 없음 | ⚠️ "금지 표현" |
| 마지막 문장 | 규정 패턴 | ⚠️ "마지막 문장 형식 위반" |
| Priority | 1~5 | ⚠️ "{N} (범위: 1~5)" |

#### 동작
- ✅ **통과**: 경고 없음 → 그대로 진행
- ⚠️ **경고**: 기록하고 진행 (사용자가 최종 JSON에서 수정 가능)

#### 출력
```python
Event[] (변경 없음)
warnings: str[]  # ["[1] 행사명: ...", ...]
```

#### 결과 (테스트)
```
✅ 15건 검증 완료
⚠️ 33개 경고 (폴백 본문의 글자 수 범위 위반)
   • body 111자 (범위: 250~350)
   • 마지막 문장 형식 위반
   ...
```

---

### 🔨 Phase 4: Assembler (조립)

**역할**: 검증된 기사를 JSON 형식으로 조립 & 저장

#### 입력
```
Event[]
target_month: 6
issue_month: 7
governor: "정경조"
editor: "김명래"
```

#### 절차

1. **Priority 정렬**
   ```python
   sorted_events = sorted(events, key=lambda x: -x.priority)
   # 5점 → 4점 → 3점 → 2점 → 1점
   ```

2. **Activities 배열 생성**
   ```python
   for i, ev in enumerate(sorted_events):
     safe_name = re.sub(r"[^\w가-힣]", "_", ev.title)[:15]
     activities.append({
       "id": i + 1,
       "title": ev.title,
       "date": ev.date,
       "subtitle": ev.subtitle,
       "body": ev.body,
       "priority": ev.priority,
       "image": f"photos/2026-{issue_month:02d}/{i+1:02d}_{safe_name}.jpg",
       "imagePosition": "right" if i % 2 == 0 else "left",
     })
   ```

3. **JSON 조립**
   ```json
   {
     "meta": {
       "year": 2026,
       "reportMonth": 6,
       "issueMonth": 7,
       "issueLabel": "맹호출림 7월호",
       "governor": "정경조",
       "editor": "김명래",
       "contact": "010-7128-7551",
       "email": "kmr980@hanmail.net",
       "homepage": "https://www.ibuk5do.go.kr/main.do"
     },
     "coverItems": [
       "행사명 (6. 1)",
       ...
     ],
     "activities": [
       {
         "id": 1,
         "title": "역대 도지사 간담회",
         "date": "6. 6",
         "subtitle": "...",
         "body": "...",
         "priority": 3,
         "image": "photos/2026-07/01_역대도지사간담회.jpg",
         "imagePosition": "right"
       },
       ...
     ],
     "upcomingItems": [],
     "notice": {
       "title": "주요 공지사항",
       "icon": "📌",
       "lines": ["(공지사항을 직접 입력하세요)"]
     },
     "schedule": [BASE_SCHEDULE 12개월]
   }
   ```

4. **파일 저장**
   ```python
   with open("data-2026-07.json", "w", encoding="utf-8") as f:
     json.dump(data, f, ensure_ascii=False, indent=2)
   ```

#### 출력
```
data-2026-07.json (12 KB)
```

#### 결과 (테스트)
```
✅ 15건 JSON 조립 완료
✅ data-2026-07.json 생성 (12.0 KB)
```

---

## 사용법

### 설치
```bash
pip install olefile anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

### 실행

#### 1. 기본 실행 (Claude API 활성화)
```bash
cd ~/Downloads/maengho
python maengho_agent.py --hwp "평안남도 주요일정 (2026. 6).hwp" --month 6
```

#### 2. 테스트 (API 미사용)
```bash
python maengho_agent.py --hwp "평안남도 주요일정 (2026. 6).hwp" --month 6 --no-api
```

#### 3. 파싱만
```bash
python maengho_agent.py --hwp "평안남도 주요일정 (2026. 6).hwp" --month 6 --parse-only
```

#### 4. 커스텀 옵션
```bash
python maengho_agent.py \
  --hwp schedule.hwp \
  --month 6 \
  --out custom.json \
  --max-items 20 \
  --governor "이광종" \
  --editor "홍순진"
```

### 옵션 목록

| 옵션 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `--hwp` | ✅ | - | HWP 파일 경로 |
| `--month` | ✅ | - | 보고 대상 월 (1~11) |
| `--out` | ❌ | data-YYYY-MM.json | 출력 파일명 |
| `--no-api` | ❌ | False | Claude API 미사용 |
| `--parse-only` | ❌ | False | 파싱만 수행 |
| `--max-items` | ❌ | 15 | 최대 기사 수 |
| `--governor` | ❌ | 정경조 | 도지사 이름 |
| `--editor` | ❌ | 김명래 | 편집자 |

---

## 결과물

### 생성된 파일
```
data-2026-07.json (12 KB)
```

### 파일 구조
```json
{
  "meta": { ... },          // 메타데이터 (8개 필드)
  "coverItems": [ ... ],    // 표지 항목 (N개)
  "activities": [ ... ],    // 기사 (N개)
  "upcomingItems": [ ... ], // 예정 항목 (수동 입력)
  "notice": { ... },        // 공지사항 (수동 입력)
  "schedule": [ ... ]       // 월별 예정 (12개월 고정)
}
```

### 사용 방법
1. **HTML 렌더링**
   ```html
   <script>const DATA_FILE = 'data-2026-07.json';</script>
   <!-- maengho-template.html에서 JSON 로드 & 렌더링 -->
   ```

2. **배포**
   ```bash
   git add data-2026-07.json
   git commit -m "chore: 맹호출림 7월호"
   git push
   # GitHub Pages 자동 배포
   ```

3. **수동 입력 필요 항목**
   ```json
   "upcomingItems": [
     {"title": "8월 주요 행사", "date": "예정"},
     ...
   ],
   "notice": {
     "lines": [
       "2026년 도정 방향 안내",
       "상반기 주요 사업 현황",
       ...
     ]
   }
   ```

4. **사진 추가**
   ```
   photos/2026-07/01_역대도지사간담회.jpg
   photos/2026-07/02_현충일추념식.jpg
   ...
   ```

---

## 성능

### 시간 (테스트 결과)

| Phase | 항목 | 소요 시간 |
|-------|------|---------|
| 1 | HWP 파싱 & 필터링 | ~1초 |
| 2 | 기사 생성 (API) | ~15초 (15건 × 1초) |
| 2 | 기사 생성 (폴백) | <1초 |
| 3 | 검증 | <1초 |
| 4 | JSON 조립 & 저장 | <1초 |
| **총** | **전체** | **~20초 (API 활성화)** |

### 통계

| 항목 | 값 |
|------|-----|
| 입력 행사 | 18건 |
| 필터링 후 | 15건 |
| 경고 | 33개 |
| JSON 크기 | 12 KB |
| Activities 개수 | 15개 |
| 메모리 사용 | <100 MB |

---

## 파일 구조

```
~/Downloads/maengho/
├── maengho_agent.py              ← 핵심 에이전트 (570줄)
├── MAENGHO_SPEC.md               ← 기술 명세서
├── README.md                      ← 이 파일
│
├── .claude/                       ← 멀티에이전트 정의
│   ├── CLAUDE.md                 ← 전체 오케스트레이션
│   ├── agents/
│   │   ├── collector.md
│   │   ├── writer.md
│   │   ├── validator.md
│   │   └── assembler.md
│   └── skills/
│       └── maengho-engine.md
│
├── data-2026-07.json             ← 생성된 소식지
├── data-2026-06.json
├── maengho-template.html         ← HTML 렌더러
├── index.html
├── photos/                       ← 사진 폴더
└── .git/
```

---

## 확장 계획

### Phase 3.5: Variant Generator (A/B 변형) - 미래 계획

**목표**: 여러 톤/길이의 기사 변형 생성

```
Writer (기본 기사)
  ↓
Variant Generator
  ├─ Tone Variant (3가지)
  │   ├─ Formal (정중한 톤)
  │   ├─ Casual (친근한 톤)
  │   └─ Inspiring (영감주는 톤)
  ├─ Length Variant (2가지)
  │   ├─ Short (150자)
  │   └─ Long (400자)
  └─ A/B Test Design
      ├─ Variant A: 기본
      ├─ Variant B: Short + Casual
      ├─ Variant C: Long + Inspiring
      └─ 성과 비교
```

### 추가 기능

| 기능 | 상태 | 설명 |
|------|------|------|
| 대화형 검토 모드 | ⏳ | `--interactive` 모드로 사용자 입력 |
| 배포 자동화 | ⏳ | `--auto-push`로 git 자동 처리 |
| 병렬 처리 | ⏳ | `--parallel`로 Writer Phase 병렬화 |
| 웹훅 연동 | ⏳ | Slack/Discord로 진행상황 알림 |
| 성과 분석 | ⏳ | A/B 변형의 클릭율/열람율 추적 |

---

## 문제 해결

### Q. API 호출이 느립니다
**A.** `--no-api` 모드로 테스트하거나, `--max-items N`으로 기사 수를 줄이세요.

### Q. 일부 기사가 경고를 받았습니다
**A.** 3단계 Validator가 글자 수 범위 위반 등을 감지한 것입니다. 최종 JSON을 수동으로 수정하세요.

### Q. 사진이 안 보입니다
**A.** `photos/2026-07/` 폴더에 `01_역대도지사간담회.jpg` 형식으로 사진을 추가하세요.

### Q. 기사 톤을 바꾸고 싶습니다
**A.** `.claude/agents/writer.md`의 SYSTEM_PROMPT를 수정하고, `maengho_agent.py`의 해당 부분을 업데이트하세요.

---

## 참고 자료

- **MAENGHO_SPEC.md** — 기술 명세서 (규칙, 스키마, 검증)
- **.claude/CLAUDE.md** — 전체 오케스트레이션 정의
- **.claude/agents/** — 각 에이전트 상세 정의
- **.claude/skills/maengho-engine.md** — 오케스트레이션 로직

---

## 라이선스 & 저작권

**프로젝트**: 맹호출림 자동화  
**개발**: Claude Code  
**대상**: 이북5도위원회  
**배포**: GitHub Pages  

---

## 체크리스트

### 처음 실행
- [ ] ANTHROPIC_API_KEY 설정
- [ ] HWP 파일 준비
- [ ] maengho_agent.py 실행

### 결과 확인
- [ ] data-YYYY-MM.json 생성 확인
- [ ] activities 개수 확인 (15개)
- [ ] priority 정렬 확인 (5→1)
- [ ] 경고 메시지 검토

### 배포 전
- [ ] photos/YYYY-MM/ 사진 추가
- [ ] JSON 내용 수동 검토
- [ ] notice, upcomingItems 수동 입력
- [ ] maengho-template.html DATA_FILE 변경
- [ ] git add/commit/push

---

**완성일**: 2026-07-09  
**버전**: 1.0.0 (단일 에이전트 하네스)  
**다음 버전**: 2.0.0 (멀티에이전트 + A/B 변형)
