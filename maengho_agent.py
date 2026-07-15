#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
맹호출림 단일 에이전트 하네스
================================================================
MAENGHO_SPEC.md 기반 자동화 에이전트

[에이전트 단계]
  1. Collector  — HWP 파싱 & 행사 필터링
  2. Writer     — Claude API로 기사 생성
  3. Validator  — 규칙 검증 (글자 수, 어조, 완성도)
  4. Assembler  — JSON 조립 & 배포 준비

사용법:
  python maengho_agent.py --hwp schedule.hwp --month 5
  python maengho_agent.py --hwp schedule.hwp --month 5 --no-api
"""

import sys, os, re, json, zlib, time, argparse, textwrap
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
import olefile

# ─── 컬러 출력 ───────────────────────────────────────────────────
RESET = "\033[0m"; BOLD = "\033[1m"
BLUE = "\033[34m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
RED = "\033[31m"; CYAN = "\033[36m"; DIM = "\033[2m"

def ok(msg): print(f"  {GREEN}✅{RESET} {msg}")
def info(msg): print(f"  {CYAN}ℹ️ {RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠️ {RESET} {msg}")
def err(msg): print(f"  {RED}✗  {RESET} {msg}")
def hdr(msg): print(f"\n{BOLD}{BLUE}{msg}{RESET}")

# ══════════════════════════════════════════════════════════════════
# 에이전트 상태 모델
# ══════════════════════════════════════════════════════════════════

@dataclass
class Event:
    """파싱된 행사 정보"""
    day: int
    date: str          # "6. 1"
    time: str
    title: str
    place: str
    subtitle: str = ""
    body: str = ""
    priority: int = 3

    @property
    def id(self) -> int:
        """정렬 후 배정될 ID (런타임에 계산)"""
        return getattr(self, "_id", 0)

    @id.setter
    def id(self, value: int):
        self._id = value


@dataclass
class AgentState:
    """에이전트 실행 상태"""
    phase: str = "init"  # init → collect → write → validate → assemble
    hwp_file: str = ""
    target_month: int = 0
    issue_month: int = 0

    raw_events: list[Event] = field(default_factory=list)
    validated_events: list[Event] = field(default_factory=list)
    final_json: dict = field(default_factory=dict)

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str):
        self.errors.append(msg)
        err(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)
        warn(msg)


# ══════════════════════════════════════════════════════════════════
# PHASE 1 — Collector: HWP 파싱 & 필터링
# ══════════════════════════════════════════════════════════════════

class Collector:
    """HWP 파일 파싱 및 행사 데이터 수집"""

    # MAENGHO_SPEC.md 기반 필터링 규칙
    SKIP_EXACT = {
        "SUN(일)", "MON(월)", "TUE(화)", "WED(수)", "THU(목)", "FRI(금)", "SAT(토)",
        "노동절", "부처님 오신날", "대체휴일", "대체 휴일", "대체휴무",
        "도민의 날 대회\n대체 휴무", "지사님 대체휴무", "지사님 연가", "고정안",
    }

    SKIP_PARTIAL = [
        "연가", "대체휴무", "대체 휴무", "건강검진", "안과진료",
        "황지윤 직원 오찬", "직원 오찬", "주요일정", "氠瑢",
        "도 직원회의", "직원회의",
        "결혼", "돌잔치", "장례", "빈소", "부고", "영결식"
    ]

    def __init__(self, state: AgentState):
        self.state = state

    def collect(self, hwp_path: str, target_month: int) -> list[Event]:
        """HWP 파일 파싱 및 행사 추출"""
        self.state.phase = "collect"
        self.state.hwp_file = hwp_path
        self.state.target_month = target_month
        self.state.issue_month = target_month + 1

        hdr("[PHASE 1] Collector — HWP 파싱 & 필터링")

        if not Path(hwp_path).exists():
            self.state.add_error(f"파일을 찾을 수 없습니다: {hwp_path}")
            return []

        try:
            paras = self._extract_hwp_paragraphs(hwp_path)
            info(f"단락 {len(paras)}개 추출")

            raw_events = self._parse_month_schedule(paras, target_month)
            ok(f"{len(raw_events)}건 필터링 완료")

            self.state.raw_events = raw_events
            return raw_events

        except Exception as e:
            self.state.add_error(f"파싱 실패: {e}")
            return []

    def _extract_hwp_paragraphs(self, hwp_path: str) -> list[str]:
        """HWP5 BodyText/Section0 에서 단락 추출"""
        ole = olefile.OleFileIO(hwp_path)
        raw = ole.openstream("BodyText/Section0").read()
        try:
            body = zlib.decompress(raw, -15)
        except:
            body = raw

        paras = []
        i = 0
        while i < len(body) - 4:
            hdr_word = int.from_bytes(body[i:i+4], "little")
            tag = hdr_word & 0x3FF
            size = (hdr_word >> 20) & 0xFFF
            if size == 0xFFF:
                size = int.from_bytes(body[i+4:i+8], "little")
                i += 8
            else:
                i += 4
            data = body[i : i + size]
            i += size

            if tag == 67 and size > 0:
                txt = data.decode("utf-16-le", errors="ignore")
                txt = "".join(c for c in txt if c.isprintable() or c in "\n\r\t ")
                txt = txt.strip()
                if txt:
                    paras.append(txt)

        return paras

    def _parse_month_schedule(self, paras: list[str], target_month: int) -> list[Event]:
        """달력 구조 파싱 및 필터링 (MAENGHO_SPEC.md 기준)"""
        header = f"2026년 {target_month}월 평안남도 주요일정"
        header_next = f"2026년 {target_month+1}월 평안남도 주요일정"

        start_idx = next((i for i, p in enumerate(paras) if header in p), None)
        if start_idx is None:
            raise ValueError(f"{target_month}월 헤더 미발견")

        end_idx = next((i for i, p in enumerate(paras) if i > start_idx and header_next in p), len(paras))
        section = paras[start_idx:end_idx]

        time_re = re.compile(r"^\d{1,2}[:;]\d{2}$")
        place_re = re.compile(r"^[（(](.+)[）)]$")
        date_re = re.compile(r"^(\d{1,2})$")

        events = []
        current_day = None
        current_time = ""
        title_parts = []

        def flush(day, time_str, t_parts, place=""):
            title = " ".join(t_parts).strip()
            title = re.sub(r"\s+", " ", title)
            if not title or len(title) < 3:
                return
            for skip in self.SKIP_PARTIAL:
                if skip in title:
                    return
            events.append(Event(
                day=day,
                date=f"{target_month}. {day}",
                time=time_str,
                title=title,
                place=place,
            ))

        for p in section:
            if p in self.SKIP_EXACT or any(s in p for s in self.SKIP_PARTIAL):
                continue

            dm = date_re.match(p)
            if dm:
                d = int(dm.group(1))
                if 1 <= d <= 31:
                    if title_parts and current_day:
                        flush(current_day, current_time, title_parts)
                        title_parts = []
                    current_day = d
                    current_time = ""
                    title_parts = []
                    continue

            if current_day is None:
                continue

            if time_re.match(p):
                if title_parts:
                    flush(current_day, current_time, title_parts)
                    title_parts = []
                current_time = p.replace(";", ":")
                continue

            pm = place_re.match(p)
            if pm:
                place = pm.group(1)
                if title_parts:
                    flush(current_day, current_time, title_parts, place)
                    title_parts = []
                current_time = ""
                continue

            title_parts.append(p)

        if title_parts and current_day:
            flush(current_day, current_time, title_parts)

        # 중복 제거 (날짜, 제목 앞 6자)
        seen = set()
        clean = []
        for e in events:
            key = (e.day, e.title[:6])
            if key not in seen:
                seen.add(key)
                clean.append(e)

        sorted_events = sorted(clean, key=lambda x: (x.day, x.time))

        # "위원회 간담회" 개수 제한 (1건만)
        title_count = {}
        final = []
        for e in sorted_events:
            base = e.title
            if "위원회 간담회" in e.title:
                base = "위원회 간담회"

            if base not in title_count:
                title_count[base] = 0

            title_count[base] += 1
            if base == "위원회 간담회" and title_count[base] > 1:
                self.state.add_warning(f"위원회 간담회 제외: {e.title}")
                continue

            final.append(e)

        return final


# ══════════════════════════════════════════════════════════════════
# PHASE 2 — Writer: Claude API 기사 생성
# ══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """당신은 평안남도 도정 소식지 '맹호출림'의 편집장입니다.
주어진 행사 정보를 바탕으로 아래 규칙을 엄격히 지켜 기사를 작성하세요.

[기사 작성 규칙]
1. subtitle: 행사 핵심을 표현하는 12자 이내 문구

2. body: 공백 포함 250~350자의 기사 본문
   ▸ 어조·시점
     - "정경조 평안남도지사는" 또는 "정경조 지사는"으로 시작
     - 도지사가 행사를 주최·주관했다는 표현 금지
       → 반드시 "참석했다" / "함께했다" / "자리했다" 등 참여 중심 서술
     - 문어체, 경어 없이 서술 (신문 기사 스타일)
   ▸ 내용 구성
     - 행사 날짜, 장소, 핵심 내용 포함
     - 실향민의 아픔·고향에 대한 그리움·도민 화합·전통 계승·통일 기반 등
       행사 성격에 맞는 도정 가치와 연결
     - 반드시 완전한 문장으로 끝낼 것 (문장 중간에 절대 끊지 말 것)
   ▸ 마지막 문장 형태 (하나 선택)
     - "~을 강조했다"
     - "~의 뜻을 밝혔다"
     - "~을 다짐했다"

3. priority: 기사 중요도 점수 (1~5 정수)
   5점: 전체 도민 참여 행사, 실향민 대규모 행사, 남북교류, 외부 언론 보도
   4점: 지사 주재 핵심 회의 (통일원로, 시장군수월례회의)
   3점: 위원회 행사, 기념식, 추모식, 문화행사
   2점: 문화공연, 뮤지컬 관련
   1점: 내부 행정회의 (도직원회의 등 — 편집 시 자동 제외됨)

4. JSON만 출력 (```코드블록, 설명문 절대 불가)

출력 형식:
{"subtitle": "...", "body": "...", "priority": 숫자}"""


class Writer:
    """Claude API를 통한 기사 생성"""

    def __init__(self, state: AgentState):
        self.state = state

    def write(self, events: list[Event], governor: str = "정경조", no_api: bool = False) -> list[Event]:
        """기사 생성"""
        self.state.phase = "write"
        hdr(f"[PHASE 2] Writer — 기사 생성 ({len(events)}건)")

        if no_api:
            return self._write_fallback(events, governor)

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            self.state.add_error("ANTHROPIC_API_KEY 환경변수 미설정")
            return self._write_fallback(events, governor)

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            self.state.add_error("anthropic 패키지 미설치: pip install anthropic")
            return self._write_fallback(events, governor)

        print()
        for i, ev in enumerate(events, 1):
            bar = "█" * i + "░" * (len(events) - i)
            pct = int(i / len(events) * 100)
            title_s = ev.title[:20].ljust(20)
            print(f"\r  [{bar}] {pct:3d}%  {title_s}", end="", flush=True)

            article = self._generate_article(ev, client, governor)
            ev.subtitle = article["subtitle"]
            ev.body = article["body"]
            ev.priority = article["priority"]

            if i < len(events):
                time.sleep(0.3)

        print()
        ok(f"{len(events)}건 기사 생성 완료")
        return events

    def _write_fallback(self, events: list[Event], governor: str) -> list[Event]:
        """API 미사용 시 폴백 기사 생성"""
        info("폴백 모드: 기본 본문으로 생성")
        for ev in events:
            ev.subtitle = ev.title[:12]
            ev.body = self._fallback_body(ev, governor)
            ev.priority = 3
        ok(f"{len(events)}건 기본 기사 생성 완료")
        return events

    def _generate_article(self, ev: Event, client, governor: str) -> dict:
        """Claude API 호출 (MAENGHO_SPEC.md 기준)"""
        prompt = (
            f"행사명: {ev.title}\n"
            f"날짜: 2026년 {ev.date}\n"
            f"시간: {ev.time}\n"
            f"장소: {ev.place or '이북5도청'}\n"
            f"도지사: {governor}\n\n"
            "위 행사에 대한 맹호출림 소식지 기사를 작성해주세요."
        )

        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=700,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
            result = json.loads(raw)
            return {
                "subtitle": result.get("subtitle", "")[:20],
                "body": result.get("body", ""),
                "priority": int(result.get("priority", 3)),
            }
        except json.JSONDecodeError:
            self.state.add_warning(f"JSON 파싱 오류: {ev.title}")
            return {"subtitle": "", "body": self._fallback_body(ev, governor), "priority": 3}
        except Exception as e:
            self.state.add_warning(f"API 오류 ({ev.title}): {e}")
            return {"subtitle": "", "body": self._fallback_body(ev, governor), "priority": 3}

    def _fallback_body(self, ev: Event, governor: str) -> str:
        """API 실패 시 기본 본문"""
        place = ev.place or "이북5도청"
        return (
            f"{governor} 평안남도지사는 {ev.date} {ev.title}에 참석하여 "
            f"도민사회 발전을 위한 뜻깊은 시간을 함께했다. "
            f"정 지사는 공동체의 화합과 전통 계승의 중요성을 강조하며 "
            f"도민과 함께 나아갈 것을 다짐했다."
        )


# ══════════════════════════════════════════════════════════════════
# PHASE 3 — Validator: 규칙 검증
# ══════════════════════════════════════════════════════════════════

class Validator:
    """기사 품질 검증 (MAENGHO_SPEC.md 기준)"""

    # 마지막 문장 허용 패턴
    FINAL_PATTERNS = [
        "을 강조했다",
        "을 밝혔다",
        "을 다짐했다",
        "를 강조했다",
        "를 밝혔다",
        "를 다짐했다",
    ]

    def __init__(self, state: AgentState):
        self.state = state

    def validate(self, events: list[Event]) -> list[Event]:
        """기사 규칙 검증"""
        self.state.phase = "validate"
        hdr("[PHASE 3] Validator — 규칙 검증")

        valid = []
        for i, ev in enumerate(events, 1):
            issues = self._check_article(ev)
            if issues:
                for issue in issues:
                    self.state.add_warning(f"[{i}] {ev.title}: {issue}")
            valid.append(ev)

        ok(f"{len(valid)}건 검증 완료 ({len(self.state.warnings)}개 경고)")
        self.state.validated_events = valid
        return valid

    def _check_article(self, ev: Event) -> list[str]:
        """개별 기사 검증"""
        issues = []

        # subtitle 길이
        if len(ev.subtitle) > 12:
            issues.append(f"subtitle {len(ev.subtitle)}자 > 12자")

        # body 길이
        body_len = len(ev.body)
        if body_len < 250 or body_len > 350:
            issues.append(f"body {body_len}자 (범위: 250~350)")

        # 시작 어구
        if not any(ev.body.startswith(p) for p in ["정경조 지사는", "정경조 평안남도지사는"]):
            issues.append("도지사명으로 시작하지 않음")

        # 금지 표현
        if "주최했다" in ev.body or "주관했다" in ev.body:
            issues.append("금지 표현 ('주최했다'/'주관했다')")

        # 마지막 문장
        if not any(ev.body.endswith(p) for p in self.FINAL_PATTERNS):
            issues.append("마지막 문장 형식 위반")

        # priority 범위
        if not 1 <= ev.priority <= 5:
            issues.append(f"priority {ev.priority} (범위: 1~5)")

        return issues


# ══════════════════════════════════════════════════════════════════
# PHASE 4 — Assembler: JSON 조립 & 배포 준비
# ══════════════════════════════════════════════════════════════════

BASE_SCHEDULE = [
    {"month": "1월",  "items": "신년하례 / 국립현충원참배 / 읍·면·동장위촉식 / 행정자문위원회의 / 이북도민 실태조사 및 생활지원(연중)"},
    {"month": "2월",  "items": "통일원로회의 / 시장·군수월례회의(매월3주차 금요일)"},
    {"month": "3월",  "items": "읍면동장회의 / 시도사무소장회의 / 사회통합교육(반기1회) / 명예 도민증수여(분기1회)"},
    {"month": "4월",  "items": "정부포상추천 및 심사 방법 개선방안 토의 / 고향 찾아주기 프로그램 발전 / 행정자문위원회의"},
    {"month": "5월",  "items": "도민의 날 / 평안남도 명문가 찾기 / 원자력발전소견학(변동가능) / 3세가 찾아가는 뿌리 찾기 / 통일원로회의"},
    {"month": "6월",  "items": "국외이북도민 고국방문단 초청행사(6.22~26) / 명예 도민증 수여 / 시도사무소장 순회회의 / 6.25참전용사 감사·위안행사"},
    {"month": "7월",  "items": "제3회 북한이탈주민의 날 / 행정자문위원회의 / 한 많은 대동강 뮤지컬 공연"},
    {"month": "8월",  "items": "화천 하나원방문 / 통일원로회의"},
    {"month": "9월",  "items": "제1회 평안남도 음식 문화 축제(예정) / 명예도민증수여 / 읍면·동장 분기 회의 / 시도사무소장 순회회의"},
    {"month": "10월", "items": "제44회 이북도민 대통령기체육대회(10.17~18) / 정부 포상 수여 / 사회통합교육(후반기) / 행정자문위원회의"},
    {"month": "11월", "items": "이북도민 청년의 날 정부포상 수여 / 통일원로회의 / 평안남도 무형유산 발굴 및 이수자 증 수여"},
    {"month": "12월", "items": "2026년도 사업 분석 / 명예도민증수여 / 읍면동장분기회의 / 평안남도 명문가증수여 / 3세대가 찾아가는 뿌리 찾기 결과 포상"},
]


class Assembler:
    """최종 JSON 조립 및 배포 준비"""

    def __init__(self, state: AgentState):
        self.state = state

    def assemble(self, events: list[Event], governor: str, editor: str) -> dict:
        """JSON 조립 (MAENGHO_SPEC.md 기준)"""
        self.state.phase = "assemble"
        hdr("[PHASE 4] Assembler — JSON 조립")

        # priority 내림차순 정렬
        sorted_events = sorted(events, key=lambda x: -x.priority)

        # activities 배열 생성
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
                "image": f"photos/2026-{self.state.issue_month:02d}/{i+1:02d}_{safe_name}.jpg",
                "imagePosition": "right" if i % 2 == 0 else "left",
            })

        cover_items = [f"{a['title']} ({a['date']})" for a in activities]

        data = {
            "meta": {
                "year": 2026,
                "reportMonth": self.state.target_month,
                "issueMonth": self.state.issue_month,
                "issueLabel": f"맹호출림 {self.state.issue_month}월호",
                "governor": governor,
                "editor": editor,
                "contact": "010-7128-7551",
                "email": "kmr980@hanmail.net",
                "homepage": "https://www.ibuk5do.go.kr/main.do",
            },
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

        self.state.final_json = data
        ok(f"{len(activities)}건 JSON 조립 완료")
        return data

    def save(self, output_file: str) -> bool:
        """JSON 파일 저장"""
        hdr("[저장] JSON 파일")

        try:
            json_str = json.dumps(self.state.final_json, ensure_ascii=False, indent=2)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(json_str)

            size_kb = Path(output_file).stat().st_size / 1024
            ok(f"{output_file} ({size_kb:.1f} KB)")
            return True
        except Exception as e:
            self.state.add_error(f"저장 실패: {e}")
            return False


# ══════════════════════════════════════════════════════════════════
# 메인 하네스
# ══════════════════════════════════════════════════════════════════

class MaenghoAgent:
    """단일 에이전트 하네스"""

    def __init__(self):
        self.state = AgentState()

    def run(self, args) -> bool:
        """에이전트 실행"""
        print(f"\n{BOLD}{'━'*60}{RESET}")
        print(f"{BOLD}  平南 猛虎出林  소식지 생성 에이전트{RESET}")
        print(f"{BOLD}{'━'*60}{RESET}\n")

        # Phase 1: Collector
        collector = Collector(self.state)
        events = collector.collect(args.hwp, args.month)
        if not events:
            return False

        # 파싱 결과 출력
        for i, ev in enumerate(events, 1):
            place_str = f"  {DIM}({ev.place}){RESET}" if ev.place else ""
            print(f"  {DIM}{i:2d}.{RESET} {BOLD}[{ev.date}]{RESET}  {ev.title}{place_str}")

        if args.parse_only:
            info("--parse-only 모드: 종료")
            return True

        # 최대 항목 수 제한
        if len(events) > args.max_items:
            self.state.add_warning(f"{len(events)}건 → {args.max_items}건 처리")
            events = events[:args.max_items]

        print()

        # Phase 2: Writer
        writer = Writer(self.state)
        events = writer.write(events, args.governor, args.no_api)

        # Phase 3: Validator
        validator = Validator(self.state)
        events = validator.validate(events)

        # Phase 4: Assembler
        assembler = Assembler(self.state)
        assembler.assemble(events, args.governor, args.editor)

        # 저장
        output_file = args.out or f"data-2026-{self.state.issue_month:02d}.json"
        if not assembler.save(output_file):
            return False

        # 완료 요약
        print(f"\n{BOLD}{'━'*60}{RESET}")
        print(f"{BOLD}{GREEN}  ✅ 완료!{RESET}")
        print(f"{'━'*60}\n")

        if self.state.warnings:
            print(f"  {YELLOW}⚠️ 경고 {len(self.state.warnings)}건{RESET}")
            for w in self.state.warnings[:3]:
                print(f"     • {w}")
            if len(self.state.warnings) > 3:
                print(f"     ... 외 {len(self.state.warnings) - 3}건")

        print(f"\n  다음 단계:")
        print(f"  {CYAN}1.{RESET} photos/2026-{self.state.issue_month:02d}/ 폴더에 사진 추가")
        print(f"  {CYAN}2.{RESET} {output_file} 내용 확인 & 수정")
        print(f"  {CYAN}3.{RESET} git add/commit/push\n")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="맹호출림 단일 에이전트 하네스",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--hwp", required=True, help="HWP 파일 경로")
    parser.add_argument("--month", type=int, required=True, help="보고 대상 월")
    parser.add_argument("--out", default=None, help="출력 JSON 파일명")
    parser.add_argument("--no-api", action="store_true", help="Claude API 미사용")
    parser.add_argument("--parse-only", action="store_true", help="파싱만 수행")
    parser.add_argument("--max-items", type=int, default=15, help="최대 기사 수")
    parser.add_argument("--governor", default="정경조", help="도지사 이름")
    parser.add_argument("--editor", default="평안남도 비서실 정책보좌 김명래", help="편집자")
    args = parser.parse_args()

    agent = MaenghoAgent()
    success = agent.run(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
