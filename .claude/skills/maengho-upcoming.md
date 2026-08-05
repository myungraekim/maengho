# 맹호출림 예정사항 추가 스킬

## 개요

월별 소식지 발행 시 다음 달 예정사항을 자동으로 추가하는 워크플로우.

## 개념

**시간 차이 원리:**
- `data-YYYY-MM.json` — N월 도정보고 기반, N월 활동 기록
- `data-YYYY-(M+1).json` — (N+1)월 도정보고 기반, (N+1)월 활동 기록
- 따라서: `data-YYYY-(M+1).json`의 coverItems = N월 예정사항

**예시 (8월호 발행 시):**
```
7월 도정보고 → data-2026-08.json (8월호)
8월 도정보고 → data-2026-09.json (9월호의 기초)

9월호의 coverItems = 8월 예정사항
→ 8월호의 upcomingItems에 복사
```

## 사용법

```bash
cd ~/mr.kim/maengho

# 수동 방식 (현재)
# 1. data-2026-09.json의 coverItems 확인
# 2. data-2026-08.json의 upcomingItems에 복사
# 3. git commit/push

# 자동 방식 (향후)
python maengho_upcoming.py --current 8 --next 9 --update
```

## 구현 체크리스트

### Phase A: 두 파일 비교
```python
def extract_upcoming_items(current_month, next_month):
    """
    다음달호의 coverItems를 현재달호의 upcomingItems로 변환
    
    입력:
      current_month: 8 (data-2026-08.json)
      next_month: 9 (data-2026-09.json)
    
    처리:
      1. data-2026-09.json 로드
      2. coverItems 추출
      3. 날짜 형식 유지 (예: "제목 (8. 15)")
      4. 리스트로 변환
    
    출력:
      upcoming_items: List[str]
    """
```

### Phase B: 파일 업데이트
```python
def update_upcoming_items(data_file, upcoming_items):
    """
    현재달호의 upcomingItems 업데이트
    
    입력:
      data_file: data-YYYY-MM.json 경로
      upcoming_items: 추가할 예정사항 리스트
    
    처리:
      1. JSON 로드
      2. upcomingItems 필드 업데이트
      3. JSON 저장 (indent=2, UTF-8)
    
    출력:
      성공: True, 실패: False + 에러 메시지
    """
```

### Phase C: Git 커밋
```python
def commit_changes(message):
    """
    예정사항 변경사항 커밋 및 푸시
    
    메시지 포맷:
    
    월호 최종: 다음달 예정사항 추가
    
    - upcomingItems: N월 주요 행사 K건 추가
    
    Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
    """
```

## 실행 흐름

```
[입력] --current 8 --next 9

  ↓

[Load] data-2026-09.json (9월호)
  → coverItems 추출
  → 예정사항 리스트 생성

  ↓

[Update] data-2026-08.json (8월호)
  → upcomingItems에 예정사항 추가
  → JSON 저장

  ↓

[Commit] git add/commit/push
  → 커밋 메시지 자동 생성
  → GitHub 동기화

  ↓

[출력] 완료 메시지
```

## 사용 예시

### 현재 (수동)
```bash
# 8월호 발행 후
# 1. 9월호 생성
python maengho_agent.py --hwp "2026-08.hwp" --month 8

# 2. 수동으로 예정사항 추가
# (JSON 직접 편집 또는 스크립트 실행)

# 3. 커밋/푸시
git add data-2026-08.json
git commit -m "..."
git push
```

### 향후 (자동)
```bash
# 한 번에 처리
python maengho_upcoming.py --current 8 --next 9 --update

# 또는
python maengho_upcoming.py --current 8 --next 9 --dry-run  # 미리보기
```

## 규칙

1. **coverItems는 activities 우선도 순으로 정렬**
   - 예: "제목 (월. 일)"

2. **중복 제거**
   - 현재호의 활동과 다음달 예정사항이 겹치지 않음

3. **날짜 형식 일관성**
   - "제목 (8. 15)" 형식 유지

4. **개수 제한 없음**
   - 다음달 예정사항 모두 추가

## 저장 위치

```
~/mr.kim/maengho/.claude/skills/maengho-upcoming.md  ← 이 파일
~/mr.kim/maengho/maengho_upcoming.py                 ← 구현 파일 (향후)
```

## 통합 워크플로우

```
[매달] HWP 도정보고 수신
  ↓
[1단계] maengho_agent.py 실행
  → data-YYYY-MM.json 생성
  ↓
[2단계] maengho_upcoming.py 실행
  → upcomingItems 자동 추가
  ↓
[3단계] git push
  → GitHub Pages 배포
  ↓
[완료] 소식지 발행
```

---

**작성일:** 2026-08-04  
**담당:** 맹호출림 자동화 팀  
**상태:** 개념 정의 완료 → 구현 대기
