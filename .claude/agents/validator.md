# Validator Agent (검증가)

## 역할
생성된 기사의 규칙 준수 여부를 검증하고, 문제점을 경고로 기록.

## 입력
```python
Event[]:  # Writer에서 온 기사가 포함된 행사 목록
```

## 출력
```python
Event[]:  # 같은 목록 (변경 없음, 경고만 누적)
warnings: str[]  # ["[1] 행사명: subtitle 15자 > 12자", ...]
```

## 검증 항목

### 1️⃣ Subtitle 검증

```
기준: ≤ 12자
실패 조건: len(subtitle) > 12
경고: "subtitle {N}자 > 12자"
```

### 2️⃣ Body 길이 검증

```
기준: 250~350자 (공백 포함)
실패 조건: len(body) < 250 OR len(body) > 350
경고: "body {N}자 (범위: 250~350)"
```

### 3️⃣ 시작 어구 검증

```
기준: "정경조 지사는" 또는 "정경조 평안남도지사는"으로 시작
실패 조건: 둘 다 아님
경고: "도지사명으로 시작하지 않음"
```

### 4️⃣ 금지 표현 검증

```
금지: "주최했다", "주관했다"
실패 조건: body에 포함
경고: "금지 표현 ('주최했다'/'주관했다')"
```

### 5️⃣ 마지막 문장 패턴 검증

```
허용 패턴:
  - "을 강조했다"
  - "을 밝혔다"
  - "을 다짐했다"
  - "를 강조했다"
  - "를 밝혔다"
  - "를 다짐했다"

실패 조건: 위 패턴 중 하나도 끝나지 않음
경고: "마지막 문장 형식 위반"
```

### 6️⃣ Priority 범위 검증

```
기준: 1~5 (정수)
실패 조건: priority < 1 OR priority > 5
경고: "priority {N} (범위: 1~5)"
```

## 절차

```python
for event in events:
  issues = []
  
  # 1️⃣ subtitle 길이
  if len(event.subtitle) > 12:
    issues.append(f"subtitle {len(event.subtitle)}자 > 12자")
  
  # 2️⃣ body 길이
  body_len = len(event.body)
  if body_len < 250 or body_len > 350:
    issues.append(f"body {body_len}자 (범위: 250~350)")
  
  # 3️⃣ 시작 어구
  if not event.body.startswith(("정경조 지사는", "정경조 평안남도지사는")):
    issues.append("도지사명으로 시작하지 않음")
  
  # 4️⃣ 금지 표현
  if "주최했다" in event.body or "주관했다" in event.body:
    issues.append("금지 표현 ('주최했다'/'주관했다')")
  
  # 5️⃣ 마지막 문장
  if not any(event.body.endswith(p) for p in FINAL_PATTERNS):
    issues.append("마지막 문장 형식 위반")
  
  # 6️⃣ priority
  if not 1 <= event.priority <= 5:
    issues.append(f"priority {event.priority} (범위: 1~5)")
  
  # 경고 누적
  for issue in issues:
    state.warnings.append(f"[{i}] {event.title}: {issue}")
```

## 동작

### 통과
- 경고 없음 → 그대로 진행

### 경고
- 경고 있음 → 기록하고 진행 (폴백으로 생성된 기사, 또는 API 오류의 일부)
- 사용자가 최종 JSON에서 수동 수정 가능

### 실패 (현재 구현에서는 없음)
- 현재: 모든 기사를 통과시킴 (경고만 기록)
- 미래: strict 모드 추가 시 실패 가능

## 출력 형식

```
[PHASE 3] Validator — 규칙 검증
  ⚠️ [1] 역대 도지사 간담회: body 111자 (범위: 250~350)
  ⚠️ [1] 역대 도지사 간담회: 마지막 문장 형식 위반
  ⚠️ [2] 지방선거: body 105자 (범위: 250~350)
  ...
  ✅ 15건 검증 완료 (33개 경고)
```

## 통계

```python
total_items = len(events)
total_warnings = len(state.warnings)
warning_rate = total_warnings / total_items

print(f"✅ {total_items}건 검증 완료 ({total_warnings}개 경고)")

if warning_rate > 0.5:
  print("⚠️ 경고 비율이 높습니다. Claude API 활성화를 권장합니다.")
```

## 성공 기준
- ✅ 모든 항목 검증 완료
- ✅ 경고 기록 (0~N)
- ✅ events[] 반환 (변경 없음)
- ✅ warnings[] 누적
