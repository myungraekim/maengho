# Assembler Agent (조립가)

## 역할
검증된 기사들을 JSON 형식으로 조립하고 파일로 저장. 배포 준비.

## 입력
```python
Event[]:            # Validator에서 온 검증 완료 기사
target_month: int   # 보고 대상 월 (6)
issue_month: int    # 발행 월 (7)
governor: str       # 도지사 이름
editor: str         # 편집자
```

## 출력
```python
data: dict          # 최종 JSON 객체
file: "data-YYYY-MM.json"  # 저장된 파일
```

## JSON 스키마 (MAENGHO_SPEC.md §1)

### 전체 구조
```json
{
  "meta": { ... },
  "coverItems": [ ... ],
  "activities": [ ... ],
  "upcomingItems": [ ... ],
  "notice": { ... },
  "schedule": [ ... ]
}
```

### 1️⃣ Meta (메타데이터)

```json
{
  "year": 2026,
  "reportMonth": 6,        // 도정보고 대상 월
  "issueMonth": 7,         // 소식지 발행 월
  "issueLabel": "맹호출림 7월호",
  "governor": "정경조",
  "editor": "평안남도 비서실 정책보좌 김명래",
  "contact": "010-7128-7551",
  "email": "kmr980@hanmail.net",
  "homepage": "https://www.ibuk5do.go.kr/main.do"
}
```

### 2️⃣ Cover Items (표지 항목)

```json
"coverItems": [
  "역대 도지사 간담회 (6. 1)",
  "제71회 현충일 추념식 (6. 6)",
  ...
]
```

- 출처: activities 배열의 제목 + 날짜
- 순서: activities 정렬 순서대로
- 형식: `"{title} ({date})"`

### 3️⃣ Activities (주요 기사)

```json
"activities": [
  {
    "id": 1,
    "title": "역대 도지사 간담회",
    "date": "6. 6",
    "subtitle": "역대 도지사 한자리에",
    "body": "정경조 평안남도지사는 ... 다짐했다.",
    "priority": 3,
    "image": "photos/2026-07/01_역대도지사간담회.jpg",
    "imagePosition": "right"
  },
  ...
]
```

**정렬**: priority 내림차순 (5 → 4 → 3 → 2 → 1)

**ID 배정**: 정렬 후 순서대로 1, 2, 3, ...

**Image 경로** (MAENGHO_SPEC.md §6):
- 형식: `photos/2026-{MM}/{id:02d}_{safe_name}.jpg`
- safe_name: 제목에서 특수문자 제거, 15자 제한
  ```python
  safe_name = re.sub(r"[^\w가-힣]", "_", title)[:15]
  # "역대 도지사 간담회" → "역대_도지사_간담회"
  ```

**ImagePosition**: 
- id 홀수 (1, 3, 5, ...): "right"
- id 짝수 (2, 4, 6, ...): "left"

### 4️⃣ Upcoming Items (예정 항목)

```json
"upcomingItems": []  // 수동 입력 필드 (기본 빈 배열)
```

### 5️⃣ Notice (공지사항)

```json
"notice": {
  "title": "주요 공지사항",
  "icon": "📌",
  "lines": ["(공지사항을 직접 입력하세요)"]
}
```

### 6️⃣ Schedule (월별 예정)

```json
"schedule": [
  {
    "month": "1월",
    "items": "신년하례 / 국립현충원참배 / ..."
  },
  {
    "month": "2월",
    "items": "통일원로회의 / ..."
  },
  ...  // 12개월
]
```

- BASE_SCHEDULE (고정): 12개월 예정 항목
- 변경 필요 시 코드 수정

## 절차

### 1️⃣ Priority 정렬

```python
sorted_events = sorted(events, key=lambda x: -x.priority)
# 5점 → 4점 → 3점 → 2점 → 1점
```

### 2️⃣ Activities 배열 생성

```python
activities = []
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

### 3️⃣ Cover Items 생성

```python
cover_items = [f"{a['title']} ({a['date']})" for a in activities]
```

### 4️⃣ Meta 구성

```python
meta = {
  "year": 2026,
  "reportMonth": target_month,
  "issueMonth": issue_month,
  "issueLabel": f"맹호출림 {issue_month}월호",
  "governor": governor,
  "editor": editor,
  "contact": "010-7128-7551",
  "email": "kmr980@hanmail.net",
  "homepage": "https://www.ibuk5do.go.kr/main.do",
}
```

### 5️⃣ JSON 최종 조립

```python
data = {
  "meta": meta,
  "coverItems": cover_items,
  "activities": activities,
  "upcomingItems": [],
  "notice": {
    "title": "주요 공지사항",
    "icon": "📌",
    "lines": ["(공지사항을 직접 입력하세요)"],
  },
  "schedule": BASE_SCHEDULE,
}
```

### 6️⃣ 파일 저장

```python
output_file = f"data-2026-{issue_month:02d}.json"
with open(output_file, "w", encoding="utf-8") as f:
  json.dump(data, f, ensure_ascii=False, indent=2)
```

- 인코딩: UTF-8 (한글 직접 저장)
- 형식: indent=2 (가독성)
- 파일명: `data-YYYY-MM.json`

## 에러 처리

| 상황 | 처리 |
|------|------|
| 파일 쓰기 실패 | ❌ 에러 + 종료 |
| 디렉토리 권한 없음 | ❌ 에러 + 종료 |
| 디스크 부족 | ❌ 에러 + 종료 |

## 검증

- ✅ activities 개수 > 0
- ✅ coverItems 개수 == activities 개수
- ✅ id 순차 (1, 2, 3, ...)
- ✅ priority 내림차순
- ✅ imagePosition 교대 (right, left, right, ...)
- ✅ 파일 생성 완료

## 출력 예시

```
[PHASE 4] Assembler — JSON 조립
  ✅ 15건 JSON 조립 완료

[저장] JSON 파일
  ✅ data-2026-07.json (12.0 KB)
```

## 수동 입력 필드

사용자가 JSON 생성 후 **반드시 수정**해야 할 부분:

1. **photos/** — 사진 파일 이름을 image 경로와 맞춰 추가
   ```
   photos/2026-07/01_역대도지사간담회.jpg
   photos/2026-07/02_현충일추념식.jpg
   ...
   ```

2. **notice.lines** — 공지사항 입력
   ```json
   "notice": {
     "lines": [
       "2026년 도정 방향 안내",
       "상반기 주요 사업 현황"
     ]
   }
   ```

3. **upcomingItems** — 향후 예정 항목 (선택)
   ```json
   "upcomingItems": [
     {"title": "8월 주요 행사", "date": "예정"},
     ...
   ]
   ```

## 다음 단계

```bash
# 1. JSON 내용 확인 & 수정
cat data-2026-07.json

# 2. 사진 추가
cp 사진.jpg photos/2026-07/01_역대도지사간담회.jpg

# 3. maengho-template.html의 DATA_FILE 변경
# <script>const DATA_FILE = 'data-2026-07.json';</script>

# 4. 브라우저에서 미리보기
open maengho-template.html

# 5. 배포
git add data-2026-07.json
git commit -m "chore: 맹호출림 7월호"
git push
```

## 성공 기준
- ✅ data-YYYY-MM.json 파일 생성
- ✅ N건 activities 포함
- ✅ priority 내림차순 정렬
- ✅ 유효한 JSON 형식
- ✅ 파일 크기 > 0
