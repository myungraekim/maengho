# Writer Agent (저술가)

## 역할
Claude API를 통해 행사 정보로부터 기사(subtitle + body + priority)를 생성.

## 입력
```python
Event[]:          # Collector에서 온 필터링된 행사 목록
governor: str     # 도지사 이름 (기본: "정경조")
no_api: bool      # True면 폴백만 사용
```

## 출력
```python
Event[]:  [
  {
    # 기존 필드
    day, date, time, title, place,
    # 새로 추가
    subtitle: str,       # "호국영령 넋 기리며 통일 다짐"
    body: str,          # "정경조 평안남도지사는 ... 다짐했다."
    priority: int       # 1~5
  },
  ...
]
```

## 절차

### 1️⃣ API 세팅
- ANTHROPIC_API_KEY 환경변수 확인
- anthropic 패키지 import
- Anthropic 클라이언트 초기화

### 2️⃣ 각 행사별 API 호출
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

### 3️⃣ 응답 파싱
```python
# JSON 응답 예상
{
  "subtitle": "호국영령 넋 기리며 통일 다짐",
  "body": "정경조 평안남도지사는 ... 다짐했다.",
  "priority": 3
}
```

- 코드블록 제거 (```` → "")
- JSON 파싱
- 필드 추출: subtitle, body, priority

### 4️⃣ 검증 & 정제

| 필드 | 처리 |
|------|------|
| subtitle | 20자 초과 시 절단 |
| body | 그대로 사용 |
| priority | int로 변환, 기본값 3 |

### 5️⃣ API 실패 시 폴백 (MAENGHO_SPEC.md §7)

```python
fallback_body = f"""
{governor} 평안남도지사는 {event.date} {event.title}에 참석하여 
도민사회 발전을 위한 뜻깊은 시간을 함께했다. 
정 지사는 공동체의 화합과 전통 계승의 중요성을 강조하며 
도민과 함께 나아갈 것을 다짐했다.
"""

return {
  "subtitle": "",
  "body": fallback_body,
  "priority": 3
}
```

## System Prompt

**역할**: 평안남도 도정 소식지 '맹호출림'의 편집장

**규칙**:
1. **Subtitle** (12자 이내)
   - 행사 핵심 표현
   
2. **Body** (250~350자, 공백 포함)
   - 어조: "정경조 지사는" 또는 "정경조 평안남도지사는"으로 시작
   - 문어체, 경어 없음
   - 행사 날짜, 장소, 핵심 내용 포함
   - 실향민·고향·도민 화합·전통 계승·통일 기반 연결
   - 마지막 문장: "~을 강조했다" / "~의 뜻을 밝혔다" / "~을 다짐했다" 중 하나
   - 금지: "주최했다", "주관했다" → "참석했다" 중심

3. **Priority** (1~5)
   - 5: 도민 참여, 남북교류, 언론 보도
   - 4: 지사 주재 핵심 회의
   - 3: 위원회, 기념식, 추모식
   - 2: 문화공연, 뮤지컬
   - 1: 내부 행정

4. **출력**: JSON만 (설명, 코드블록 금지)

## 에러 처리

| 상황 | 처리 |
|------|------|
| JSON 파싱 실패 | ⚠️ 경고 + 폴백 |
| API 타임아웃 | ⚠️ 경고 + 폴백 |
| API 오류 | ⚠️ 경고 + 폴백 |
| ANTHROPIC_API_KEY 미설정 | ❌ 중단 (--no-api 옵션 제안) |

## 성능

- Rate limit: 각 요청 후 0.3초 대기
- max_tokens: 700 (안전 마진)
- 총 시간: N건 × (API 응답시간 + 0.3초)

## 테스트 모드

```python
if no_api:
  # API 없이 폴백으로만 생성
  for event in events:
    event.subtitle = event.title[:12]
    event.body = fallback_body(event)
    event.priority = 3
  return events
```

## 성공 기준
- ✅ N건 기사 생성 (또는 폴백)
- ✅ 각 기사 subtitle + body + priority 포함
- ✅ JSON 파싱 성공율 90% 이상
- ✅ events[] 반환
