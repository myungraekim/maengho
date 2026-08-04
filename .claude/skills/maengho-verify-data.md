# 맹호출림 데이터 검증 스킬

## 개요

소식지 발행 전 **데이터의 정확성을 검증**하는 체크리스트.

## 검증 항목

### 1단계: 날짜 일관성 검증

각 항목마다 다음을 확인:
- [ ] **활동 본문의 날짜 = title의 date 필드**
  - 예: date: "7. 2" → body에 "7월 2일"
  - 불일치하면: 원본 캘린더 확인 → 수정

- [ ] **coverItems 날짜 = activities의 해당 항목 날짜**
  - coverItems: "항목명 (7. 2)"
  - activities: title 매칭 + date 확인
  
- [ ] **upcomingItems 날짜 = 원본 일정표**
  - 다음달 도정보고에서 추출한 날짜와 일치

### 2단계: 내용 검증

- [ ] **기사 첫 문장이 정확한 날짜로 시작**
  ```
  예: "정경조 평안남도지사는 7월 2일 낮 12시 두소에서 열린..."
  ```

- [ ] **본문 길이: 250~350자**
  - 너무 짧음: 원본 자료 확인 후 추가 서술
  - 너무 김: 요약 정리

- [ ] **마지막 문장이 규정 패턴**
  ```
  ✓ "~을 강조했다"
  ✓ "~의 뜻을 밝혔다"  
  ✓ "~을 다짐했다"
  ```

### 3단계: 우선도 검증

- [ ] **priority가 올바르게 할당되었는가?**
  ```
  5점: 전체 도민 참여, 남북교류, 외부 언론 보도
  4점: 지사 주재 핵심 회의
  3점: 위원회 행사, 기념식, 추모식
  2점: 문화공연, 뮤지컬
  1점: 내부 행정회의
  ```

### 4단계: 정렬 검증

- [ ] **coverItems이 월일순 정렬되었나?**
  ```
  7. 2 → 7. 4 → 7. 11 → ... (빠른 날짜 먼저)
  ```

- [ ] **activities가 priority 내림차순 + 월일순 정렬되었나?**
  ```
  priority 5 (날짜순)
  priority 4 (날짜순)
  priority 3 (날짜순)
  ...
  ```

- [ ] **upcomingItems이 월일순 정렬되었나?**

## 자동 검증 스크립트

```python
import json
import re

def validate_issue(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    errors = []
    
    # 1. 날짜 일관성 검증
    for act in data['activities']:
        date_str = act.get('date', '')
        body = act.get('body', '')
        
        # date: "7. 2" 형식에서 월, 일 추출
        match = re.search(r'(\d+)\.\s*(\d+)', date_str)
        if match:
            month, day = match.groups()
            # body에서 "7월 2일" 검색
            if not re.search(f'{month}월\\s*{day}일', body):
                errors.append(f"❌ {act['title']}: date({date_str}) ≠ body 날짜")
    
    # 2. 글자수 검증
    for act in data['activities']:
        body = act.get('body', '')
        length = len(body)
        if length < 250 or length > 350:
            errors.append(f"⚠️ {act['title']}: {length}자 (범위: 250~350)")
    
    # 3. priority 범위 검증
    for act in data['activities']:
        pri = act.get('priority', 0)
        if pri not in [1, 2, 3, 4, 5]:
            errors.append(f"❌ {act['title']}: priority {pri} (범위: 1~5)")
    
    # 4. 정렬 검증
    def extract_date(item):
        if isinstance(item, dict):
            date_str = item.get('date', '')
        else:
            match = re.search(r'\((\d+)\.\s*(\d+)\)', item)
            if match:
                return (int(match.group(1)), int(match.group(2)))
            return (99, 99)
        if date_str:
            parts = date_str.replace(' ', '').split('.')
            if len(parts) == 2:
                return (int(parts[0]), int(parts[1]))
        return (99, 99)
    
    # coverItems 정렬 검증
    cover_dates = [extract_date(item) for item in data['coverItems']]
    if cover_dates != sorted(cover_dates):
        errors.append(f"❌ coverItems이 월일순 정렬되지 않음")
    
    # upcomingItems 정렬 검증
    upcoming_dates = [extract_date(item) for item in data['upcomingItems']]
    if upcoming_dates != sorted(upcoming_dates):
        errors.append(f"❌ upcomingItems이 월일순 정렬되지 않음")
    
    return errors

# 실행
errors = validate_issue('data-2026-08.json')
if errors:
    print("🔍 검증 결과:\n")
    for err in errors:
        print(err)
else:
    print("✅ 모든 검증 완료!")
```

## 발행 전 체크리스트

```
[ ] 1. 원본 도정보고 캘린더와 대조 확인
[ ] 2. 자동 검증 스크립트 실행
[ ] 3. 에러 항목 수동 수정
[ ] 4. 정렬 재실행
[ ] 5. 재검증
[ ] 6. git commit/push
```

## 문제 발견 시

**일반적인 오류:**
- 본문 날짜 = HWP 파싱 오류 → 원본 캘린더 이미지 확인 후 수정
- priority 불일치 → 행사 규모/성격 재평가 후 수정
- 글자수 부족 → 행사 상세 정보 추가
- 정렬 오류 → `maengho-sort-by-date.md` 실행

---

**핵심:** 정확한 날짜와 내용은 소식지의 신뢰도를 결정. 발행 전 반드시 검증.

**작성일:** 2026-08-04  
**담당:** 맹호출림 데이터 품질 팀
