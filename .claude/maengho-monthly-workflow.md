# 맹호출림 월별 발행 완전 자동화 워크플로우

**목적**: 월별 소식지 발행 시 필요한 모든 수정 사항을 체계적으로 자동화  
**버전**: 2.0 (2026-09-28)  
**적용**: 9월호부터

---

## Phase 1: 데이터 수집 & 생성

### 1-1. 원본 파일 준비
```bash
# HWP 또는 PDF 파일에서 월별 데이터 추출
python3 maengho_agent.py --hwp schedule.hwp --month N
python3 maengho_agent.py --hwp schedule.hwp --month N+1
```

- **Month N**: 실시 사항 (기사/activities)
- **Month N+1**: 예정 사항 (upcomingItems)

### 1-2. 생성 결과
- `data-202X-0N.json` (현월호)
- `data-202X-0(N+1).json` (다음월호)

---

## Phase 2: 데이터 검증 & 수정

### 2-1. upcomingItems 추가 (중요!)
**규칙**: 다음달 예정사항을 현월호의 `upcomingItems`에 추가

```python
# data-202X-0N.json의 upcomingItems 항목 추가
{
  "title": "행사명",
  "date": "N+1. D",  # 다음달 날짜
  "priority": 3,
  "highlight": true  # 강조 항목만
}
```

**확인 체크리스트:**
- [ ] upcomingItems에 다음달 일정 12개 추가
- [ ] 날짜순 정렬 (10.3, 10.10, 10.17, 10.24, ...)
- [ ] 주요 행사는 priority 5로 강조
- [ ] 강조 항목은 highlight: true 설정

### 2-2. 공지사항 (notice) 업데이트

```json
"notice": {
  "title": "주요 공지사항",
  "icon": "📌",
  "lines": [
    "🏆 주요 행사 제목",
    "📅 일시: 날짜 / 📍 장소",
    "🎯 상세 내용",
    "✨ 참석 홍보 메시지"
  ]
}
```

**규칙:**
- 가장 주요한 행사 (우선도 5) 정보 포함
- 모든 도민 참여 유도 메시지
- 일시, 장소, 참여 안내 명확히

---

## Phase 3: 웹 템플릿 동기화

### 3-1. maengho-template.html 수정

**변경 대상:**
```javascript
// Line 803
const DATA_FILE = 'data-202X-0N.json?v=YYYYMMDD';
```

**규칙:**
- N = issueMonth (발행월)
- YYYYMMDD = 오늘 날짜
- 예: `data-2026-10.json?v=20260928`

### 3-2. 예정사항 페이지 동적 표시

**구현**: `buildUpcomingPage()` 함수  
- issueMonth 기반으로 월이름 자동 생성
- upcomingItems 객체 직접 렌더링
- 하드코딩된 월명 제거

**확인:**
- [ ] 예정사항 제목이 "10월 주요 예정사항" 등으로 변경
- [ ] upcomingItems의 모든 항목이 날짜별 표시
- [ ] 강조 항목(priority 5)이 최상단

---

## Phase 4: Git 배포

### 4-1. 커밋 순서
```bash
# 1단계: 데이터
git add data-202X-0N.json
git commit -m "N월호 데이터: upcomingItems 추가 / 공지사항 업데이트"

# 2단계: 템플릿
git add maengho-template.html
git commit -m "N월호 웹 업데이트: 데이터 동기화"

# 3단계: 배포
git push
```

### 4-2. 커밋 메시지 포맷
```
N월호 [타입]: 간단한 설명

- 항목1
- 항목2
- 항목3

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## Phase 5: 아티팩트 업데이트

### 5-1. 최신 데이터 Embed
```python
# 최신 JSON 데이터를 HTML에 직접 포함
const DATA_JSON = {...data...};
```

### 5-2. 아티팩트 발행
```bash
# Version 업그레이드 (현재 수정되면 다음 버전으로)
Artifact publish (URL 유지)
```

---

## 자동화 체크리스트

### 발행 전 최종 검증
- [ ] **데이터**: upcomingItems 12개 추가
- [ ] **정렬**: 날짜순 (10.3, 10.10, 10.17, 10.24, 10.31)
- [ ] **강조**: 주요 행사 priority 5 + highlight: true
- [ ] **공지**: notice.lines에 주요 행사 정보 포함
- [ ] **템플릿**: DATA_FILE 버전 업데이트
- [ ] **렌더링**: 예정사항 페이지가 현월 기반으로 표시
- [ ] **배포**: git push 완료

### 에이전트 체크리스트 (자동 검토 대상)
1. ✅ data-N.json의 upcomingItems 개수 = 12
2. ✅ upcomingItems 날짜순 정렬 확인
3. ✅ priority 5인 항목 존재 여부
4. ✅ notice.lines에 체육대회/주요행사 정보 포함
5. ✅ maengho-template.html DATA_FILE 버전
6. ✅ buildUpcomingPage 함수 issueMonth 기반 렌더링
7. ✅ git log 마지막 커밋 메시지 형식 확인

---

## 월별 적용 예시

### 9월호 (reportMonth=9, issueMonth=10)
- data-2026-10.json
- 10월 예정사항 12개
- 공지: 체육대회 (10.24)

### 10월호 (reportMonth=10, issueMonth=11)
- data-2026-11.json
- 11월 예정사항 12개
- 공지: [다음달 주요행사]

---

## 참고 링크
- MAENGHO_SPEC.md: 기사 작성 규칙
- feedback_maengho_verify_data.md: 데이터 검증 규칙
- feedback_maengho_date_sort.md: 정렬 규칙
