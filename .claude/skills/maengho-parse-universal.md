# 맹호출림 범용 파싱 스킬 ✨

## 개요

**한글(HWP), PDF, 이미지(PNG/JPG) 모두 지원**하는 자동 일정 파싱 엔진.

- 파일 형식 자동 감지
- 최적의 파싱 방법 자동 선택
- 통일된 JSON 출력
- Collector 단계 직접 연동

## 사용법

### 기본 명령어

```bash
python ~/mr.kim/maengho/maengho_parse_universal.py \
  --file FILE \          # HWP, PDF, PNG, JPG 등 자동 감지
  --month N \            # 대상 월 (필수)
  [--output output.json] # 출력 파일 (선택)
```

### 예시

```bash
# PDF 파싱
python ~/mr.kim/maengho/maengho_parse_universal.py \
  --file ~/Downloads/평안남도주요일정(7월).pdf \
  --month 7

# 이미지 파싱 (Vision API)
python ~/mr.kim/maengho/maengho_parse_universal.py \
  --file ~/Downloads/7월.png \
  --month 7 \
  --output events-7.json

# HWP 파싱
python ~/mr.kim/maengho/maengho_parse_universal.py \
  --file ~/Downloads/7월도정보고.hwp \
  --month 7
```

## 지원 형식

| 형식 | 파일 확장자 | 파싱 방법 | 성공률 |
|------|-----------|---------|--------|
| PDF | `.pdf` | pdfplumber (테이블) | ⭐⭐⭐⭐⭐ |
| 이미지 | `.png, .jpg, .jpeg` | Claude Vision API | ⭐⭐⭐⭐ |
| 한글 | `.hwp, .hwpx` | olefile + 텍스트 | ⭐⭐ |

### 추천 형식 순위

1. **PDF** (최고) — 캘린더 형식, 구조화된 테이블
2. **PNG/JPG** — 캘린더 이미지, Vision으로 정확하게 읽음
3. **HWP** (주의) — 포맷 복잡, 인코딩 이슈 가능

## 출력 형식

### 정상 실행

```json
{
  "format": "PDF|Image|HWP",
  "month": 7,
  "events": [
    {
      "day": 2,
      "time": "12:00",
      "name": "통일원로의원 간담회",
      "location": "두소"
    },
    {
      "day": 4,
      "time": "12:00",
      "name": "음악극 한 많은 대동강",
      "location": "5층 통일강당"
    }
  ]
}
```

### 실패

```json
{
  "error": "파싱 실패 이유",
  "advice": "해결 방법"
}
```

## 동작 원리

### Phase 1: 형식 자동 감지

```python
file_path = "평안남도주요일정(7월).pdf"
ext = file_path.suffix.lower()  # ".pdf"

if ext == ".pdf":
    return parse_pdf(file_path)
elif ext in [".png", ".jpg"]:
    return parse_image(file_path)
elif ext == ".hwp":
    return parse_hwp(file_path)
```

### Phase 2: 형식별 파싱

#### PDF: pdfplumber

```python
with pdfplumber.open(file_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        # 날짜 정규식으로 행사 추출
        # 형식: "7. 2 | 12:00 | 행사명 | 장소"
```

#### 이미지: Claude Vision API

```python
# 이미지를 base64로 인코딩
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {...}},
            {"type": "text", "text": "캘린더에서 모든 일정을 추출해주세요"}
        ]
    }]
)
# Vision의 응답 파싱
```

#### HWP: olefile

```python
import olefile
ole = olefile.OleFileIO(file_path)
raw = ole.openstream("BodyText/Section0").read()
text = raw.decode('utf-8', errors='ignore')
# 텍스트 파싱
```

### Phase 3: 정규식으로 행사 추출

```python
# 패턴 1: "월. 일" 형식
date_pattern = r'(\d{1,2})[.\s]+(\d{1,2})'

# 패턴 2: "HH:MM" 형식 (선택)
time_pattern = r'(\d{1,2}):(\d{2})'

# 예: "7. 2 | 12:00 | 통일원로의원 간담회 | 두소"
#     ↓
#     {"day": 2, "time": "12:00", "name": "...", "location": "..."}
```

### Phase 4: 중복 제거

같은 (날짜, 제목)은 한 건만 유지.

## 설정

### 필수 라이브러리

```bash
pip install pdfplumber olefile anthropic
```

### 환경 변수

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## 워크플로우: Collector 자동화

```
사용자가 파일 업로드 (형식 자유)
   ↓
maengho_parse_universal.py
   (형식 자동 감지 + 파싱)
   ↓
JSON: events[]
   ↓
maengho_agent.py --collector-input events.json
   (Writer → Validator → Assembler)
   ↓
data-YYYY-MM.json 생성
```

## 예시 워크플로우

### 1단계: 파일 준비

```bash
# 캘린더 PDF 다운로드
# ~/Downloads/평안남도주요일정(8월).pdf
```

### 2단계: 파싱 실행

```bash
python ~/mr.kim/maengho/maengho_parse_universal.py \
  --file ~/Downloads/평안남도주요일정\(8월\).pdf \
  --month 8 \
  --output events-2026-08.json
```

### 3단계: 결과 확인

```bash
cat events-2026-08.json | jq '.events | length'
# 15건 추출됨
```

### 4단계: 기사 생성 (다음 단계)

```bash
python ~/mr.kim/maengho/maengho_agent.py \
  --collector-input events-2026-08.json \
  --month 8
```

## 문제 해결

### 1. "No module named pdfplumber"

```bash
pip install pdfplumber
```

### 2. "ANTHROPIC_API_KEY 설정 안 됨"

```bash
export ANTHROPIC_API_KEY=sk-ant-v0d...
python maengho_parse_universal.py --file file.png --month 7
```

### 3. PDF 파싱 결과 없음

원인:
- 스캔 이미지 PDF (OCR 필요)
- 텍스트 인코딩 오류

해결책:
```bash
# 스크린샷으로 변환 후 이미지 파싱
python maengho_parse_universal.py --file screenshot.png --month 7
```

### 4. HWP 파싱 실패 → PDF로 변환 권장

```bash
# HWP → PDF 변환 (한글 프로그램)
# 또는 온라인 변환 사용
# 그 후 PDF 파싱
python maengho_parse_universal.py --file converted.pdf --month 7
```

### 5. 이미지 파싱이 느림

Vision API 호출 때문. 5~10초 정상.

## 우선순위 선택 가이드

### 🥇 상황별 추천 형식

**"내가 어떤 형식의 파일을 가지고 있는가?"**

1. **PDF 캘린더** → 그대로 사용 (100% 추천)
   ```bash
   python maengho_parse_universal.py \
     --file 평안남도주요일정(8월).pdf --month 8
   ```

2. **스크린샷 이미지** → Vision API
   ```bash
   python maengho_parse_universal.py \
     --file 캘린더.png --month 8
   ```

3. **HWP 파일** → PDF로 변환 후
   ```bash
   # HWP를 PDF로 변환
   # 그 후 #1 사용
   ```

4. **원본 도정보고 PDF** (문서형) → HWP로 변환 또는 복사 후 사용

## 통합 마스터 스킬: maengho-engine

이 스킬은 **마스터 오케스트레이션 스킬**이 아니며, **각 단계별로 독립적으로 사용** 가능:

1. **파싱만 수행** (이 스킬)
   ```bash
   python maengho_parse_universal.py --file ... --month ...
   ```

2. **기사 생성** (Writer + Validator + Assembler)
   ```bash
   python maengho_agent.py --collector-input ... --month ...
   ```

3. **전체 자동화** (향후)
   ```bash
   # maengho-engine 스킬로 일괄 처리
   ```

---

**작성일:** 2026-08-04  
**담당:** 맹호출림 데이터 팀
