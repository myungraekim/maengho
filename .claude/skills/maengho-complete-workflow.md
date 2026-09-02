# 맹호출림 소식지 완전 자동화 워크플로우

**마지막 업데이트:** 2026-08-06  
**상태:** ✅ 완전 자동화 완성 (8월호 검증됨)

---

## 📋 전체 흐름 (한 번에 끝내기)

```
Raw Data (PDF/이미지/HWP)
    ↓
[1단계] 파싱 → events.json
    ↓
[2단계] 마스터 스크립트 → data-YYYY-MM.json
    ↓
[3단계] 사진 정리 & 권한 수정
    ↓
[4단계] 배포 & 웹사이트 반영
```

---

## 🚀 빠른 시작 (5분 안에)

### Step 1: 파일 준비
```bash
cd ~/mr.kim/maengho

# 원본 파일을 Downloads에 준비
# 예: ~/Downloads/평안남도주요일정(8월).pdf
```

### Step 2: 데이터 파싱
```bash
python3 maengho_parse_universal.py \
  --file ~/Downloads/평안남도주요일정\(8월\).pdf \
  --month 8 \
  --output events-2026-08.json
```

**지원 형식:** PDF (최고) > PNG/JPG > HWP  
**추천:** 캘린더 형식의 PDF 사용

---

### Step 3: 기사 자동 생성 & 검증 & 배포

```bash
python3 maengho_master_publish.py --month 8 --verify --deploy
```

**옵션:**
- `--month N` : 발행월 (필수)
- `--verify` : 데이터 검증 (권장)
- `--deploy` : git 자동 push (권장)

**출력 결과:**
- ✓ data-2026-08.json 생성
- ✓ 검증 완료 (날짜, 글자수, priority)
- ✓ HTML 동기화
- ✓ git push 완료

---

### Step 4: 갤러리 사진 추가 (있으면)

```bash
# 1. 사진을 이 경로에 복사
cp ~/Downloads/사진*.jpg ~/mr.kim/maengho/photos/2026-08/daedongang/

# 2. 파일명 정렬 (01.jpg ~ 10.jpg)
# Finder에서 우클릭 → 배치 이름바꾸기 사용

# 3. 파일 권한 수정 (중요!)
chmod 644 ~/mr.kim/maengho/photos/2026-08/daedongang/*.jpg

# 4. 최종 배포
python3 maengho_master_publish.py --month 8 --deploy
```

---

## 📊 데이터 검증 체크리스트

마스터 스크립트가 자동으로 확인하는 항목:

| 항목 | 기준 | 실패시 |
|------|------|--------|
| 날짜 | date 필드 = body 내용 | ❌ 에러 |
| 글자 수 | 250~350자 | ⚠️ 경고 |
| Priority | 1~5 범위 | ❌ 에러 |
| 정렬 | priority 내림차순 + 날짜 | ✓ 자동 정렬 |

**에러 발생시:** 에러 메시지를 읽고 JSON에서 직접 수정 후 재실행

---

## 📸 사진 매칭 규칙 (자동)

마스터 스크립트가 자동으로 수행:

```python
매칭 규칙:
"통일원로" → 통일원로의원 간담회 → tongil.jpeg
"국민일보" → 국민일보 언론 인터뷰 → 01_kbs.png
"덕천군" → 덕천군 정기총회 → dekcheon.jpeg
... (더 많음)

매칭 실패 → 이북5도위원회 로고로 자동 할당
```

---

## 🎯 주요 파일 위치

```
~/mr.kim/maengho/
├── data-2026-08.json          ← 생성된 소식지 데이터
├── maengho-template.html      ← 웹사이트 렌더러
├── maengho_master_publish.py  ← 마스터 스크립트 (핵심!)
├── maengho_parse_universal.py ← 파싱 스크립트
├── photos/
│   ├── 2026-07/logo.png
│   └── 2026-08/
│       ├── 01_kbs.png
│       ├── 02_dekcheon.jpeg
│       ├── ... (활동 사진)
│       └── daedongang/        ← 갤러리 (01.jpg~10.jpg)
└── .claude/
    └── skills/
        ├── maengho-master-publish.md    ← 마스터 스크립트 설명
        └── maengho-parse-universal.md   ← 파싱 스크립트 설명
```

---

## 🔧 문제 해결

### 문제 1: "사진이 안 보입니다"

**원인:** 파일 권한이 `-rw-------` (소유자만 읽기)  
**해결:**
```bash
chmod 644 ~/mr.kim/maengho/photos/2026-08/daedongang/*.jpg
chmod 644 ~/mr.kim/maengho/photos/2026-08/*.jpeg
chmod 644 ~/mr.kim/maengho/photos/2026-08/*.png
```

### 문제 2: "JSON 검증 에러"

**원인:** 날짜 불일치, 글자 수 범위 위반  
**해결:**
```bash
# 1. 에러 메시지 읽기
# 2. data-2026-08.json 수정
# 3. 다시 실행
python3 maengho_master_publish.py --month 8 --verify --deploy
```

### 문제 3: "파싱 결과가 이상합니다"

**해결:**
1. PDF 파일 확인 (캘린더 형식 권장)
2. PNG 스크린샷으로 재시도
3. 직접 JSON 작성

---

## 📅 월별 반복 체크리스트

매월 초 (발행일 기준 3일 전):

- [ ] **1. 원본 파일 준비**
  - PDF: `~/Downloads/평안남도주요일정(N월).pdf`
  - 또는 PNG/JPG 스크린샷

- [ ] **2. 파싱 실행**
  ```bash
  python3 maengho_parse_universal.py --file FILE --month N
  ```

- [ ] **3. 데이터 검증**
  ```bash
  python3 maengho_master_publish.py --month N --verify
  ```
  → 에러 있으면 JSON 수정 후 재실행

- [ ] **4. 사진 준비 (있으면)**
  - daedongang 갤러리: 10개 사진 → 01.jpg~10.jpg
  - 권한 수정: `chmod 644 *.jpg`

- [ ] **5. 최종 배포**
  ```bash
  python3 maengho_master_publish.py --month N --verify --deploy
  ```

- [ ] **6. 웹사이트 확인**
  → https://myungraekim.github.io/maengho/

- [ ] **7. 단톡방 공유**
  ```
  맹호출림 N월호 📰
  https://myungraekim.github.io/maengho/
  ```

---

## 🎯 성능 지표

| 작업 | 시간 |
|------|------|
| PDF 파싱 | 30초 |
| 데이터 검증 | 10초 |
| HTML 동기화 | 5초 |
| git 배포 | 10초 |
| **총 소요시간** | **~1분** |

---

## 💾 자동 처리 목록

마스터 스크립트가 매번 자동으로:

- ✅ JSON 데이터 로드
- ✅ 날짜 검증 (date vs body)
- ✅ 글자수 검증 (250~350자)
- ✅ Priority 검증 (1~5)
- ✅ coverItems 정렬 (월일순)
- ✅ activities 정렬 (priority 내림차순)
- ✅ upcomingItems 정렬 (월일순)
- ✅ 사진 자동 매칭
- ✅ HTML INLINE_DATA 동기화
- ✅ 이미지 경로 → 절대 URL 변환
- ✅ JSON 저장
- ✅ git add/commit/push

---

## 🔑 핵심 명령어 (복사-붙여넣기용)

### 모든 작업 한 번에 (권장)
```bash
cd ~/mr.kim/maengho && python3 maengho_master_publish.py --month 8 --verify --deploy
```

### 검증만 (배포 전 확인)
```bash
cd ~/mr.kim/maengho && python3 maengho_master_publish.py --month 8 --verify
```

### 파싱 (원본 → events.json)
```bash
python3 ~/mr.kim/maengho/maengho_parse_universal.py --file FILE --month N
```

### 사진 권한 수정
```bash
chmod 644 ~/mr.kim/maengho/photos/2026-08/daedongang/*.jpg
```

---

## 📝 다음 달을 위한 체크사항

**8월호 완성 시점 (2026-08-06) 정보:**

- ✅ 파싱 완전 자동화 (PDF/이미지/HWP 지원)
- ✅ 기사 생성 완전 자동화 (Claude API)
- ✅ 데이터 검증 완전 자동화
- ✅ 사진 매칭 완전 자동화
- ✅ HTML 동기화 완전 자동화
- ✅ git 배포 완전 자동화
- ✅ 갤러리 페이지 추가 (8월호 한정)

**앞으로:**
- 9월호부터는 이 문서의 "빠른 시작" 섹션만 따라가면 됨
- 대부분 자동이므로 1분이면 완성 가능

---

**작성:** 김명래  
**검증:** Claude Haiku 4.5  
**상태:** 🟢 운영 중
