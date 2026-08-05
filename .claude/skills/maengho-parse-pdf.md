# 맹호출림 PDF 파싱 스킬

## 개요

**pdfplumber**를 사용해 평안남도 도정보고 **캘린더 형식 PDF**에서 행사 정보를 자동 추출하는 스킬.

구조화된 테이블 형식 (요일별 캘린더)에 특화.

## 사용법

### 기본 명령어

```bash
python ~/mr.kim/maengho/maengho_parse_universal.py --file FILE.pdf --month N [--output output.json]
```

### 예시

```bash
# 7월 일정 PDF 파싱 → 콘솔 출력
python ~/mr.kim/maengho/maengho_parse_universal.py \
  --file ~/Downloads/평안남도주요일정(7월).pdf \
  --month 7

# 8월 일정 PDF 파싱 → JSON 파일로 저장
python ~/mr.kim/maengho/maengho_parse_universal.py \
  --file ~/Downloads/평안남도주요일정(8월).pdf \
  --month 8 \
  --output events-2026-08.json
```

## 출력 형식

### 정상 실행

```json
{
  "format": "PDF",
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

### 실패 (에러)

```json
{
  "error": "PDF 파싱 실패: ...",
  "format": "PDF",
  "month": 7,
  "events": []
}
```

## 알고리즘

### 1단계: 날짜행 감지

테이블의 각 행을 순회하며 **모두 숫자 또는 비어있는 셀**로 구성된 행 찾기.
이것이 달력의 날짜 행.

### 2단계: 이벤트 추출

날짜행 바로 다음 행(들)에서 `HH:MM` 시간 패턴 찾기.

### 3단계: 날짜 매칭

시간이 있는 셀의 열(col)에서 인근 날짜 찾기.
같은 주의 같은 열이므로 정확한 매칭 가능.

### 4단계: 정리

- 행사명에서 괄호/줄바꿈 제거
- 장소는 괄호 안 텍스트로 추출
- 중복 제거

## 설정

### 필수 라이브러리

```bash
pip install pdfplumber
```

## 지원 형식

✅ **완벽 지원**
- 캘린더 형식 PDF (한국 도정보고)
- 요일별 표 구조
- 텍스트 기반 PDF

❌ **미지원**
- 스캔 이미지 PDF → 이미지 파싱 사용
- 자유 형식 문서 → 텍스트 파싱 시도

## 문제 해결

### 1. "ModuleNotFoundError: No module named 'pdfplumber'"

```bash
pip install pdfplumber
```

### 2. 일부 행사만 추출됨

원인: PDF 구조 복잡성 (시간/행사명 다른 열에 있음)

해결책: 
- JSON 출력 확인
- 수동으로 누락된 행사 추가
- 이미지 형식으로 재파싱 시도

### 3. 행사명이 잘려있음

→ 정상. JSON에서 전체 내용 확인 가능.
실제 사용 시 `maengho_agent.py`가 기사 생성하며 정리.

## 워크플로우

```
PDF 파일 준비 (캘린더 형식)
   ↓
maengho_parse_universal.py --file ... --month ...
   ↓
events-*.json 생성
   ↓
maengho_agent.py에서 사용 (Collector 입력)
   ↓
data-YYYY-MM.json 최종 생성
```

---

**작성일:** 2026-08-04  
**상태:** ✅ 완성 (기본 기능)  
**담당:** 맹호출림 데이터 팀
