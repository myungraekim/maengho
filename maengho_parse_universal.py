#!/usr/bin/env python3
"""
맹호출림 범용 파싱 스킬
한글(HWP), PDF, 이미지(PNG/JPG) 자동 파싱
"""

import argparse
import json
import re
from pathlib import Path
from typing import Optional

# PDF 파싱
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# 이미지 파싱 (Claude Vision)
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class UniversalParser:
    """형식 자동 감지 & 파싱"""

    def __init__(self):
        self.client = anthropic.Anthropic() if HAS_ANTHROPIC else None

    def parse(self, file_path: str, month: int) -> dict:
        """파일 형식 자동 감지 후 파싱"""
        path = Path(file_path)

        if not path.exists():
            return {"error": f"파일 없음: {file_path}"}

        ext = path.suffix.lower()

        print(f"📄 파일 감지: {ext}")

        if ext == '.pdf':
            return self._parse_pdf(file_path, month)
        elif ext in ['.hwp', '.hwpx']:
            return self._parse_hwp(file_path, month)
        elif ext in ['.png', '.jpg', '.jpeg']:
            return self._parse_image(file_path, month)
        else:
            return {"error": f"지원하지 않는 형식: {ext}"}

    def _parse_pdf(self, file_path: str, month: int) -> dict:
        """PDF 파싱 (캘린더 형식)"""
        if not HAS_PDFPLUMBER:
            return {"error": "pdfplumber 미설치: pip install pdfplumber"}

        print("🔍 PDF 파싱 중...")
        events = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    # 테이블 기반 추출
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            extracted = self._extract_events_from_calendar_table(table, month)
                            events.extend(extracted)

            # 중복 제거
            unique_events = []
            seen = set()
            for evt in events:
                key = (evt["day"], evt["name"][:20])
                if key not in seen:
                    unique_events.append(evt)
                    seen.add(key)

            # 정렬
            unique_events.sort(key=lambda x: x["day"])

            print(f"✅ {len(unique_events)}건 추출됨")
            return {
                "format": "PDF",
                "month": month,
                "events": unique_events
            }
        except Exception as e:
            return {"error": f"PDF 파싱 실패: {e}"}

    def _parse_hwp(self, file_path: str, month: int) -> dict:
        """HWP 파싱 (간단한 텍스트 추출)"""
        print("🔍 HWP 파싱 중...")

        try:
            # 기본 HWP 파싱 시도
            import olefile
            ole = olefile.OleFileIO(file_path)
            raw = ole.openstream("BodyText/Section0").read()
            text = raw.decode('utf-8', errors='ignore')

            events = self._extract_events_from_text(text, month)

            print(f"✅ {len(events)}건 추출됨")
            return {
                "format": "HWP",
                "month": month,
                "events": events
            }
        except Exception as e:
            return {
                "error": f"HWP 파싱 실패: {e}",
                "advice": "PDF로 변환해서 다시 시도하세요"
            }

    def _parse_image(self, file_path: str, month: int) -> dict:
        """이미지 파싱 (Claude Vision API)"""
        if not HAS_ANTHROPIC:
            return {"error": "anthropic 미설치: pip install anthropic"}

        print("🔍 이미지 파싱 중 (Vision API)...")

        try:
            with open(file_path, "rb") as f:
                image_data = f.read()

            # Base64 인코딩
            import base64
            base64_image = base64.standard_b64encode(image_data).decode("utf-8")

            # 이미지 형식 감지
            ext = Path(file_path).suffix.lower()
            media_type = "image/png" if ext == ".png" else "image/jpeg"

            # Claude Vision API 호출
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_image,
                                },
                            },
                            {
                                "type": "text",
                                "text": f"""이 캘린더 이미지에서 {month}월의 모든 일정을 추출해주세요.

형식:
월. 일 | 시간 | 행사명 | 장소

예:
7. 2 | 12:00 | 통일원로의원 간담회 | 두소
7. 4 | 12:00 | 음악극 한 많은 대동강 | 5층 통일강당

모든 일정을 이 형식으로 반환해주세요."""
                            }
                        ],
                    }
                ],
            )

            # 응답 파싱
            response_text = message.content[0].text
            events = self._parse_vision_response(response_text, month)

            print(f"✅ {len(events)}건 추출됨")
            return {
                "format": "Image",
                "month": month,
                "events": events,
                "raw_response": response_text
            }
        except Exception as e:
            return {"error": f"이미지 파싱 실패: {e}"}

    def _extract_events_from_calendar_table(self, table: list, month: int) -> list:
        """캘린더 테이블 파싱 (날짜행 + 이벤트행)"""
        events = []
        if not table or len(table) < 3:
            return events

        i = 0
        while i < len(table) - 1:
            current_row = table[i]
            if not current_row:
                i += 1
                continue

            # 현재 행이 날짜행인지 판단
            date_cells = {}  # col_idx → day

            for col_idx, cell in enumerate(current_row):
                if not cell:
                    continue
                cell_str = str(cell).strip()
                if cell_str.isdigit():
                    try:
                        day = int(cell_str)
                        if 1 <= day <= 31:
                            date_cells[col_idx] = day
                    except ValueError:
                        pass

            # 날짜행을 찾았으면 다음 행에서 이벤트 추출
            if date_cells:
                # 다음 행들을 확인하며 이벤트 수집 (최대 2행)
                for offset in range(1, min(3, len(table) - i)):
                    next_row = table[i + offset]
                    if not next_row:
                        break

                    # 다음 행이 모두 숫자면 (다음 주 날짜) 멈추기
                    has_number = any(str(cell).strip().isdigit() for cell in next_row if cell)
                    all_empty_or_number = all(
                        not cell or str(cell).strip() == "" or str(cell).strip().isdigit()
                        for cell in next_row
                    )
                    if has_number and all_empty_or_number:
                        break

                    # 이 행에서 시간 패턴 찾기
                    for col_idx, cell in enumerate(next_row):
                        if not cell:
                            continue

                        cell_str = str(cell).strip()

                        # 시간이 있는 셀 찾기
                        if ":" in cell_str:
                            time_match = re.search(r'(\d{1,2}):(\d{2})', cell_str)
                            time_str = f"{time_match.group(1)}:{time_match.group(2)}" if time_match else ""

                            # 이 셀이 속한 날짜 찾기
                            # 현재 열 또는 근처 열에서 날짜 찾기
                            day = None
                            for search_col in [col_idx, col_idx - 1, col_idx - 2, col_idx + 1]:
                                if search_col in date_cells:
                                    day = date_cells[search_col]
                                    break

                            if not day:
                                # 날짜를 못 찾으면 가장 가까운 날짜 사용
                                closest_dist = float('inf')
                                for d_col, d_day in date_cells.items():
                                    dist = abs(d_col - col_idx)
                                    if dist < closest_dist:
                                        closest_dist = dist
                                        day = d_day

                            if day:
                                # 행사명 추출
                                lines = [l.strip() for l in cell_str.split('\n')]
                                event_text = lines[0] if lines else ""

                                # 시간 제거
                                event_name = re.sub(r'\d{1,2}:\d{2}\s*', '', event_text).strip()

                                # 다음 셀에서 행사명 찾기 (현재 셀에 행사명이 없으면)
                                if (not event_name or event_name == "") and col_idx + 1 < len(next_row) and next_row[col_idx + 1]:
                                    next_cell_text = str(next_row[col_idx + 1]).strip()
                                    if next_cell_text and not re.match(r'^\d+$', next_cell_text):
                                        event_name = next_cell_text.split('\n')[0].strip()

                                # 장소 추출 (모든 라인에서)
                                location = ""
                                full_text = " ".join(lines)
                                location_match = re.search(r'\(([^)]+)\)', full_text)
                                if location_match:
                                    location = location_match.group(1).strip()

                                # 행사명에서 괄호 제거 및 정리
                                event_name = re.sub(r'\([^)]+\)', '', event_name).strip()
                                event_name = event_name.replace('\n', ' ').strip()
                                event_name = re.sub(r'\s+', ' ', event_name)  # 연속 공백 제거
                                event_name = event_name.replace(')', '').replace('(', '').strip()  # 남은 괄호 제거

                                if event_name and not event_name.startswith("(") and event_name not in ["", " "]:
                                    events.append({
                                        "day": day,
                                        "time": time_str,
                                        "name": event_name[:100],
                                        "location": location
                                    })

            i += 1

        return events

    def _extract_events_from_table(self, table: list, month: int) -> list:
        """캘린더 테이블에서 행사 추출"""
        events = []
        if not table or len(table) < 3:
            return events

        # 전체 테이블을 텍스트로 변환하여 행사 찾기
        all_text = ""
        for row in table:
            for cell in row:
                if cell:
                    all_text += str(cell) + "\n"

        # 행사 패턴: "시간 행사명\n(장소)" 또는 단순 행사명
        # 날짜를 먼저 찾은 후 그 아래 행사를 매칭

        # 모든 셀을 순회하며 날짜-이벤트 쌍 찾기
        day_event_map = {}  # day → [(time, name, location), ...]

        for row_idx, row in enumerate(table):
            if not row:
                continue

            # 이 행에서 날짜와 이벤트 추출
            current_day = None

            for col_idx, cell in enumerate(row):
                if not cell:
                    continue

                cell_str = str(cell).strip()

                # 날짜 찾기
                if cell_str.isdigit():
                    try:
                        day = int(cell_str)
                        if 1 <= day <= 31:
                            current_day = day
                            if day not in day_event_map:
                                day_event_map[day] = []
                        continue
                    except ValueError:
                        pass

                # 시간 + 행사명 찾기
                if ":" in cell_str and current_day:
                    # 형식: "시간 행사명 (장소)" 또는 단순 "시간 행사명"
                    time_match = re.search(r'(\d{1,2}):(\d{2})', cell_str)
                    time_str = f"{time_match.group(1)}:{time_match.group(2)}" if time_match else ""

                    # 시간 이후의 텍스트
                    event_text = re.sub(r'\d{1,2}:\d{2}\s*', '', cell_str).strip()

                    if event_text:
                        # 여러 줄일 수 있음 (\n으로 분리)
                        lines = event_text.split('\n')
                        name = lines[0].strip()
                        location = ""

                        # 장소는 괄호 안에
                        location_match = re.search(r'\(([^)]+)\)', event_text)
                        if location_match:
                            location = location_match.group(1)
                            name = re.sub(r'\([^)]+\)', '', name).strip()

                        day_event_map[current_day].append({
                            "time": time_str,
                            "name": name[:100],
                            "location": location
                        })

        # 결과 조합
        for day, event_list in sorted(day_event_map.items()):
            for event_info in event_list:
                if event_info["name"]:
                    events.append({
                        "day": day,
                        "time": event_info["time"],
                        "name": event_info["name"],
                        "location": event_info["location"]
                    })

        # 중복 제거
        unique_events = []
        seen = set()
        for evt in events:
            key = (evt["day"], evt["name"])
            if key not in seen:
                unique_events.append(evt)
                seen.add(key)

        # 최종 정렬
        unique_events.sort(key=lambda x: x["day"])

        return unique_events

    def _extract_events_from_text(self, text: str, month: int) -> list:
        """PDF 텍스트에서 행사 추출 (캘린더 형식)"""
        events = []

        # 패턴: "시간 행사명 (장소)" 형식
        # 예: "12:00 통일원로의원 간담회 (두소)"

        lines = text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # 시간 + 행사명 패턴 찾기
            time_match = re.search(r'^(\d{1,2}):(\d{2})\s+(.+)$', line)
            if time_match:
                time_str = f"{time_match.group(1)}:{time_match.group(2)}"
                event_text = time_match.group(3)

                # 이전 라인에서 날짜 찾기
                day = None
                for j in range(i - 1, max(-1, i - 5), -1):
                    prev_line = lines[j].strip()
                    # "월. 일" 형식의 날짜 찾기
                    date_match = re.search(r'(\d{1,2})\s+(\d{1,2})', prev_line)
                    if date_match:
                        candidate_day = int(date_match.group(2))
                        if 1 <= candidate_day <= 31:
                            day = candidate_day
                            break

                if day is None:
                    # 다른 날짜 형식 시도
                    for j in range(i - 1, max(-1, i - 5), -1):
                        prev_line = lines[j].strip()
                        nums = re.findall(r'\d+', prev_line)
                        if nums:
                            for num_str in nums:
                                candidate_day = int(num_str)
                                if 1 <= candidate_day <= 31:
                                    day = candidate_day
                                    break
                        if day:
                            break

                if day:
                    # 행사명과 장소 분리
                    location = ""
                    location_match = re.search(r'\(([^)]+)\)$', event_text)
                    if location_match:
                        location = location_match.group(1)
                        event_text = event_text[:location_match.start()].strip()

                    if event_text:
                        events.append({
                            "day": day,
                            "time": time_str,
                            "name": event_text[:100],
                            "location": location
                        })

            i += 1

        # 중복 제거
        unique_events = []
        seen = set()
        for evt in events:
            key = (evt["day"], evt["name"])
            if key not in seen:
                unique_events.append(evt)
                seen.add(key)

        # 날짜순 정렬
        unique_events.sort(key=lambda x: x["day"])

        return unique_events

    def _parse_vision_response(self, response: str, month: int) -> list:
        """Vision API 응답 파싱"""
        events = []

        # 형식: "월. 일 | 시간 | 행사명 | 장소"
        pattern = r'(\d{1,2})[.\s]*(\d{1,2})\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*(.+)'

        for match in re.finditer(pattern, response):
            month_num = int(match.group(1))
            day = int(match.group(2))
            time_str = match.group(3).strip()
            event_name = match.group(4).strip()
            location = match.group(5).strip()

            if month_num == month:
                events.append({
                    "day": day,
                    "time": time_str,
                    "name": event_name,
                    "location": location
                })

        return events


def main():
    parser = argparse.ArgumentParser(
        description="맹호출림 범용 파싱 스킬 (HWP/PDF/이미지)"
    )
    parser.add_argument("--file", "-f", required=True, help="파일 경로")
    parser.add_argument("--month", "-m", type=int, required=True, help="대상 월")
    parser.add_argument("--output", "-o", help="출력 파일 경로 (JSON)")

    args = parser.parse_args()

    # 파싱 실행
    universal_parser = UniversalParser()
    result = universal_parser.parse(args.file, args.month)

    # 결과 출력
    print("\n" + "="*60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("="*60)

    # 파일로 저장
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 저장됨: {output_path}")


if __name__ == "__main__":
    main()
