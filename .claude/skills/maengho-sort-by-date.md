# 맹호출림 날짜 순서 정렬 스킬

## 개요

소식지의 모든 항목(기사, 표지 항목, 예정사항)을 **월일 순서대로 정렬**하는 워크플로우.

## 문제 상황

- coverItems 순서 뒤죽박죽 → 시간 흐름을 따르지 못함
- upcomingItems 순서 뒤죽박죽 → 예정사항을 일정대로 보기 어려움
- activities 내에서도 같은 priority 내 날짜 순서 미정렬

**결과:** 독자가 월일 순서를 찾기 어려움

## 해결책

### 1단계: 날짜 추출 함수

```python
def extract_date(item):
    """날짜를 추출해서 정렬 키(월, 일)로 변환"""
    if isinstance(item, dict):
        date_str = item.get('date', '')  # "7. 18" 형식
    else:
        # 문자열: "제목 (7. 18)" 형식
        match = re.search(r'\((\d+)\.\s*(\d+)\)', item)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (99, 99)  # 날짜 없으면 맨 뒤
    
    # 객체의 date 필드 파싱
    if date_str:
        parts = date_str.replace(' ', '').split('.')
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))
    return (99, 99)
```

### 2단계: 정렬 로직

**coverItems 정렬:**
```python
data['coverItems'].sort(key=extract_date)
```

**activities 정렬:**
```python
# priority 우선, 같은 priority 내에서 날짜순
data['activities'].sort(key=lambda x: (-x.get('priority', 0), extract_date(x)))
```

**upcomingItems 정렬:**
```python
data['upcomingItems'].sort(key=extract_date)
```

### 3단계: JSON 저장

```python
with open('data-YYYY-MM.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

## 자동화 스크립트

```bash
python3 << 'EOF'
import json
import re

# 소식지 로드
with open('data-2026-MM.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

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

# 정렬
data['coverItems'].sort(key=extract_date)
data['activities'].sort(key=lambda x: (-x.get('priority', 0), extract_date(x)))
data['upcomingItems'].sort(key=extract_date)

# 저장
with open('data-2026-MM.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("✅ 정렬 완료!")
EOF
```

## 적용 시점

**각 월호 발행 후:**
1. 데이터 수동 입력/편집 완료
2. 이 스크립트 실행
3. git commit/push

## 통합 워크플로우

```
[매달 HWP 도정보고]
  ↓
[maengho_agent.py 실행]
  → data-YYYY-MM.json 생성
  ↓
[maengho_upcoming.py 실행]
  → upcomingItems 추가
  ↓
[maengho_sort_by_date.py 실행]  ← 이 스킬
  → 모든 항목 날짜순 정렬
  ↓
[git push]
  → GitHub Pages 배포
```

---

**핵심:** 월일 순서는 정보의 시간 흐름을 보여주는 기본. 각 호 발행 전 마지막 단계로 정렬 실행.

**작성일:** 2026-08-04  
**담당:** 맹호출림 자동화 팀
