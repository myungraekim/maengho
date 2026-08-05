# 맹호출림 마스터 발행 스킬

## 개요

**모든 수정사항을 자동으로 처리**하는 통합 스킬.
- 데이터 검증
- 날짜/내용 정렬
- 사진 매칭
- HTML 동기화
- 자동 배포

## 사용법

```bash
python ~/mr.kim/maengho/maengho_master_publish.py --month 8 --verify --deploy
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `--month N` | 발행월 (필수) |
| `--verify` | 데이터 검증 실행 |
| `--deploy` | git 자동 커밋 & push |
| `--photos` | 사진 자동 매칭 |
| `--html-sync` | HTML INLINE_DATA 동기화 |

## 자동 처리 목록

### 1️⃣ **데이터 검증** (`--verify`)
- ✅ 날짜 일관성 확인
- ✅ 본문 길이 검증 (250~350자)
- ✅ priority 범위 확인 (1~5)
- ✅ 정렬 상태 확인

### 2️⃣ **날짜/내용 정렬** (자동 실행)
- ✅ coverItems: 월일순 정렬
- ✅ activities: priority 내림차순 + 월일순 정렬
- ✅ upcomingItems: 월일순 정렬
- ✅ 본문 내용: 활동 날짜와 동기화

### 3️⃣ **사진 매칭** (`--photos`)
- ✅ photos/YYYY-MM/ 폴더 스캔
- ✅ 항목명과 파일명 자동 매칭
- ✅ 없는 사진: 이북5도위원회 로고 자동 할당

### 4️⃣ **HTML 동기화** (`--html-sync`)
- ✅ data-YYYY-MM.json 읽기
- ✅ HTML의 INLINE_DATA 자동 업데이트
- ✅ meta 정보 동기화

### 5️⃣ **자동 배포** (`--deploy`)
- ✅ git add
- ✅ git commit (자동 메시지)
- ✅ git push origin main

## 예시

### 기본 발행 (모든 검증 + 배포)
```bash
python maengho_master_publish.py --month 8 --verify --photos --html-sync --deploy
```

### 검증만
```bash
python maengho_master_publish.py --month 8 --verify
```

### 사진 재매칭
```bash
python maengho_master_publish.py --month 8 --photos --deploy
```

## 자동화된 규칙

### 날짜 정렬 규칙
```python
# coverItems & upcomingItems
date 오름차순 (빠른 날짜 먼저)

# activities
(-priority, date)  # priority는 내림차순, date는 오름차순
```

### 사진 매칭 규칙
```python
# 파일명과 항목명 자동 매칭
"통일원로.jpeg" → "통일원로의원 간담회"
"국민일보.png" → "국민일보 언론 인터뷰"

# 없는 사진
→ photos/2026-07/이북5도위원회로고.png
```

### 본문 동기화 규칙
```python
# 활동의 date 필드 변경 → 본문의 "7월 X일" 자동 변경
date: "7. 13" → body: "7월 13일"
```

## 흐름도

```
┌─────────────────────────────────────┐
│  maengho_master_publish.py          │
│  --month 8 --verify --deploy        │
└────────────┬────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
  ✅ 검증         ✅ 정렬
  ├─ 날짜        ├─ coverItems
  ├─ 본문        ├─ activities
  ├─ priority    └─ upcomingItems
  └─ 정렬
    │
    ├─→ ✅ 사진 매칭
    │   ├─ 파일명 검색
    │   ├─ 자동 할당
    │   └─ 로고 폴백
    │
    ├─→ ✅ HTML 동기화
    │   ├─ INLINE_DATA 업데이트
    │   └─ meta 정보 동기화
    │
    └─→ ✅ 자동 배포
        ├─ git add
        ├─ git commit
        └─ git push
```

## 실제 사용 예

### 시나리오 1: 신규 발행
```bash
# 9월호 준비 완료 → 한 번에 발행
python maengho_master_publish.py --month 9 \
  --verify --photos --html-sync --deploy

# 결과:
# ✅ 데이터 검증 완료
# ✅ 사진 매칭 완료 (5건)
# ✅ HTML 동기화 완료
# ✅ git push 완료
```

### 시나리오 2: 데이터 수정
```bash
# 8월호 내용 수정 후 자동 정렬 & 배포
python maengho_master_publish.py --month 8 \
  --verify --html-sync --deploy

# 자동 처리:
# - coverItems/activities/upcomingItems 정렬
# - 본문 날짜 동기화
# - HTML 업데이트
# - git 커밋 & push
```

### 시나리오 3: 사진만 재추가
```bash
# 새 사진 폴더에 추가 → 자동 매칭
python maengho_master_publish.py --month 8 \
  --photos --html-sync --deploy
```

## 검증 규칙

### 날짜 일관성
- ✅ activity.date == body에 표현된 날짜
- ✅ coverItems 날짜 = activities 날짜
- ✅ 날짜 형식: "월. 일" (예: "7. 2")

### 본문 조건
- ✅ 길이: 250~350자
- ✅ 첫 문장: "정경조 평안남도지사는 7월 X일..."
- ✅ 마지막: "~을 강조했다", "~의 뜻을 밝혔다", "~을 다짐했다"

### Priority 범위
- ✅ 1~5 범위 내
- ✅ 정렬: 내림차순 (5 → 1)

## 자동 커밋 메시지 예

```
8월호 최종 발행: 데이터 검증 + 정렬 + 사진 매칭 + HTML 동기화

체크리스트:
- 데이터 검증 완료 (16개 활동)
- 날짜/내용 정렬 완료
- 사진 매칭 완료 (11개 실제 사진)
- HTML INLINE_DATA 동기화 완료
- git push 완료

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

## 다시는 반복하지 않기!

이 스킬로:
- ✅ 수동 정렬 → **자동 정렬**
- ✅ 수동 날짜 수정 → **자동 동기화**
- ✅ 수동 사진 매칭 → **자동 매칭**
- ✅ 수동 HTML 업데이트 → **자동 동기화**
- ✅ 수동 커밋 → **자동 배포**

**한 번의 명령어로 모든 작업 완료!** 🚀

---

**작성일:** 2026-08-05  
**상태:** ✅ 구현 완료  
**담당:** 맹호출림 자동화 팀
**구현 파일:** `maengho_master_publish.py`
