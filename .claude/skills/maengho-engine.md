# Maengho Engine Skill (오케스트레이션)

## 역할
4단계 에이전트(Collector → Writer → Validator → Assembler)를 조율하고, 전체 워크플로우 관리.

## 책임
- 입력값 검증
- 각 에이전트 순서대로 실행
- 상태(AgentState) 추적
- 에러 처리 & 재시도
- 최종 결과 리포팅

## 아키텍처

```
[Maengho Engine]
  ├─ Parse CLI Args
  ├─ Init AgentState
  ├─ Phase 1: Collector
  │   └─ Event[] (raw_events)
  ├─ Phase 2: Writer
  │   └─ Event[] (with subtitle/body/priority)
  ├─ Phase 3: Validator
  │   └─ Event[] (warnings[])
  ├─ Phase 4: Assembler
  │   └─ data: JSON
  ├─ Save File
  └─ Print Summary
```

## 상태 모델 (AgentState)

```python
@dataclass
class AgentState:
  phase: str              # 현재 단계
  hwp_file: str
  target_month: int
  issue_month: int
  
  raw_events: Event[]     # Phase 1 출력
  validated_events: Event[]  # Phase 3 출력
  final_json: dict        # Phase 4 출력
  
  errors: str[]           # Critical 에러
  warnings: str[]         # 경고 (진행)
```

## 실행 흐름

### 1️⃣ 초기화

```python
state = AgentState()
print("평南 猛虎出林 소식지 생성 에이전트")
```

### 2️⃣ CLI 인자 파싱

```
--hwp FILE             필수 (HWP 파일 경로)
--month N              필수 (보고 월)
--out FILE             선택 (출력 파일명, 기본: data-YYYY-MM.json)
--no-api               선택 (API 미사용, 폴백만)
--parse-only           선택 (파싱만 수행)
--max-items N          선택 (최대 기사 수, 기본: 15)
--governor NAME        선택 (도지사 이름, 기본: 정경조)
--editor NAME          선택 (편집자, 기본: 김명래)
```

### 3️⃣ Phase 1: Collector 실행

```python
state.phase = "collect"
collector = Collector(state)
events = collector.collect(args.hwp, args.month)

if not events:
  state.add_error("행사 추출 실패")
  return False

state.raw_events = events
```

**확인 포인트**:
- ✅ 파일 존재
- ✅ 월별 헤더 발견
- ✅ 행사 N개 필터링

### 4️⃣ 파싱 결과 출력

```
  1. [6. 6] 역대 도지사 간담회 (한국프레스센터 19층)
  2. [6. 6] 제71회 현충일 추념식 (국립서울현충원)
  ...
  18. [6. 27] 민주평통 ... (이북5도청)
```

### 5️⃣ --parse-only 확인

```python
if args.parse_only:
  info("--parse-only 모드: JSON 생성 없이 종료")
  return True
```

### 6️⃣ 최대 항목 수 제한

```python
if len(events) > args.max_items:
  state.add_warning(f"{len(events)}건 → {args.max_items}건 처리")
  events = events[:args.max_items]
```

### 7️⃣ Phase 2: Writer 실행

```python
state.phase = "write"
writer = Writer(state)
events = writer.write(events, args.governor, args.no_api)

state.raw_events = events  # 기사 추가
```

**로직**:
- no_api=False → Claude API 호출
- no_api=True → 폴백 본문만 생성
- API 실패 → 자동 폴백

**진행률 표시**:
```
  [████░░░░░░░░░░░░░░░░] 20%  행사명
```

### 8️⃣ Phase 3: Validator 실행

```python
state.phase = "validate"
validator = Validator(state)
events = validator.validate(events)

state.validated_events = events
```

**경고 누적**: 검증 실패 항목별 경고 기록

### 9️⃣ Phase 4: Assembler 실행

```python
state.phase = "assemble"
assembler = Assembler(state)
data = assembler.assemble(events, args.governor, args.editor)

state.final_json = data
```

**처리**:
- priority 정렬
- activities 배열 생성
- image 경로 생성
- cover_items 생성

### 🔟 파일 저장

```python
output_file = args.out or f"data-2026-{state.issue_month:02d}.json"
if not assembler.save(output_file):
  return False
```

### 1️⃣1️⃣ 최종 리포트

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ 완료!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ⚠️ 경고 33건
     • 위원회 간담회 제외: 위원회 간담회
     • body 111자 (범위: 250~350)
     ... 외 30건

  다음 단계:
  1. photos/2026-07/ 폴더에 사진 추가
  2. data-2026-07.json 내용 확인 & 수정
  3. git add/commit/push
```

## 에러 처리 전략

### Critical (종료)
```python
if not events:
  state.add_error("...")
  return False
```

상황:
- 파일 미존재
- 월 헤더 미발견
- ANTHROPIC_API_KEY 미설정 (no_api=False일 때)

### Warning (진행)
```python
state.add_warning("...")
```

상황:
- JSON 파싱 실패 (폴백 사용)
- API 타임아웃 (폴백 사용)
- 글자 수 범위 위반 (경고만 기록)
- 마지막 문장 형식 위반 (경고만 기록)

## 고급 기능 (미래)

### 대화형 검토 모드 (--interactive)
```
[1/15] 역대 도지사 간담회
부제: 역대 도지사 한자리에
본문: ...

→ Enter(유지) / e(수정) / d(삭제) / q(종료)
```

### 배포 자동화 (--auto-push)
```python
if args.auto_push:
  # git add/commit/push 자동 실행
  subprocess.run(["git", "add", output_file])
  subprocess.run(["git", "commit", "-m", f"chore: 맹호출림 {issue_month}월호"])
  subprocess.run(["git", "push"])
```

### 성능 최적화 (--parallel)
```python
if args.parallel:
  # Phase 2 (Writer) 병렬 처리
  from concurrent.futures import ThreadPoolExecutor
  with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(writer.write, ev) for ev in events]
    events = [f.result() for f in futures]
```

## CLI 사용 예시

### 기본 실행
```bash
python maengho_agent.py --hwp schedule.hwp --month 5
```

### 테스트 (API 미사용)
```bash
python maengho_agent.py --hwp schedule.hwp --month 5 --no-api
```

### 파싱만
```bash
python maengho_agent.py --hwp schedule.hwp --month 5 --parse-only
```

### 커스텀 이름
```bash
python maengho_agent.py --hwp schedule.hwp --month 5 \
  --governor "이광종" --editor "홍순진"
```

### 최대 개수 조정
```bash
python maengho_agent.py --hwp schedule.hwp --month 5 --max-items 20
```

## 성공 기준

- ✅ 모든 Phase 정상 실행
- ✅ data-YYYY-MM.json 생성
- ✅ N건 activities 포함
- ✅ 경고 기록 (선택)
- ✅ 종료 코드 0

## 실패 기준

- ❌ Phase 1 실패 → 즉시 종료 (코드 1)
- ❌ 파일 저장 실패 → 즉시 종료 (코드 1)
- ⚠️ Phase 2,3 경고 → 진행 (코드 0)

## 로깅

```
[PHASE X] 단계명 — 상세 설명
  ✅ 성공
  ⚠️ 경고
  ✗  에러
```

색상:
- GREEN: 성공 ✅
- YELLOW: 경고 ⚠️
- RED: 에러 ✗
- CYAN: 정보 ℹ️
- BLUE: 헤더

## 성능

- 18건 파싱: ~1초
- 15건 API: ~15초 (rate limit 0.3초/건)
- 검증: < 1초
- 조립 & 저장: < 1초
- **총 시간**: ~20초 (API 활성화 시)

## 메모리

- raw_events: ~1-2 KB
- validated_events: ~2-3 KB
- final_json: ~10-20 KB
- **총 메모리**: < 100 MB
