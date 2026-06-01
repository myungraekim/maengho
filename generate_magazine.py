#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
平南 맹호출림 — Claude Code 자동화 스크립트
============================================================
사용법:
  # 기본 실행 (5월 일정 → 6월호)
  python generate_magazine.py --hwp 파일.hwp --month 5

  # 출력 파일명 지정
  python generate_magazine.py --hwp 파일.hwp --month 5 --out data-2026-06.json

  # API 없이 뼈대만 생성 (테스트용)
  python generate_magazine.py --hwp 파일.hwp --month 5 --no-api

  # 파싱 결과만 확인
  python generate_magazine.py --hwp 파일.hwp --month 5 --parse-only

필요 패키지:
  pip install olefile anthropic

환경변수:
  export ANTHROPIC_API_KEY=sk-ant-...

기사 중요도 기준 (priority 1~5):
  5점: 전체 도민 참여 행사, 남북교류, 외부 언론 보도
  4점: 지사 주재 핵심 회의 (통일원로, 시장군수월례회의)
  3점: 위원회 행사, 기념식, 추모식
  2점: 문화공연, 뮤지컬 관련
  1점: 내부 행정회의, 도직원회의
============================================================
"""

import sys, os, re, json, zlib, time, argparse, textwrap
from pathlib import Path
import olefile

# ─── 컬러 출력 ───────────────────────────────────────────────────
RESET = "\033[0m";  BOLD = "\033[1m"
BLUE  = "\033[34m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
RED   = "\033[31m"; CYAN  = "\033[36m"; DIM = "\033[2m"

def ok(msg):   print(f"  {GREEN}✅{RESET} {msg}")
def info(msg): print(f"  {CYAN}ℹ️ {RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠️ {RESET} {msg}")
def err(msg):  print(f"  {RED}✗  {RESET} {msg}")
def hdr(msg):  print(f"\n{BOLD}{BLUE}{msg}{RESET}")
def dim(msg):  print(f"  {DIM}{msg}{RESET}")


# ══════════════════════════════════════════════════════════════════
# STEP 1 ─ HWP 파일 파싱
# ══════════════════════════════════════════════════════════════════

def extract_hwp_paragraphs(hwp_path: str) -> list[str]:
    """HWP5 BodyText/Section0 에서 단락 텍스트 목록을 추출합니다."""
    ole  = olefile.OleFileIO(hwp_path)
    raw  = ole.openstream("BodyText/Section0").read()
    try:
        body = zlib.decompress(raw, -15)
    except Exception:
        body = raw

    paras = []
    i = 0
    while i < len(body) - 4:
        hdr_word = int.from_bytes(body[i:i+4], "little")
        tag      = hdr_word & 0x3FF
        size     = (hdr_word >> 20) & 0xFFF
        if size == 0xFFF:
            size = int.from_bytes(body[i+4:i+8], "little")
            i += 8
        else:
            i += 4
        data = body[i : i + size]
        i   += size

        # HWPTAG_PARA_TEXT = 67
        if tag == 67 and size > 0:
            txt = data.decode("utf-16-le", errors="ignore")
            txt = "".join(c for c in txt if c.isprintable() or c in "\n\r\t ")
            txt = txt.strip()
            if txt:
                paras.append(txt)

    return paras


def parse_month_schedule(paras: list[str], target_month: int) -> list[dict]:
    """
    달력 구조의 HWP 단락에서 특정 월 일정을 파싱합니다.

    HWP 캘린더 구조:
      "2026년 5월 평안남도 주요일정"
      SUN(일) / MON(월) / ...
      1 / 2 / 3 / ...  ← 날짜 숫자
      시간 (10:00 등)
      행사 제목 (여러 줄)
      (장소)
      다음 날짜 ...
    """
    SKIP = {
        "SUN(일)", "MON(월)", "TUE(화)", "WED(수)", "THU(목)", "FRI(금)", "SAT(토)",
        "노동절", "부처님 오신날", "대체휴일", "대체 휴일", "대체휴무",
        "도민의 날 대회\n대체 휴무", "지사님 대체휴무", "지사님 연가",
        "고정안",
    }
    SKIP_PARTIAL = ["연가", "대체휴무", "대체 휴무", "건강검진", "안과진료",
                    "황지윤 직원 오찬", "직원 오찬", "주요일정", "氠瑢"]
    SKIP_EXACT_DIGITS = set(str(n) for n in range(1, 8))  # 요일 행 숫자

    # ── 5월 섹션 찾기 ──
    header_5  = f"2026년 {target_month}월 평안남도 주요일정"
    header_nx = f"2026년 {target_month+1}월 평안남도 주요일정"

    start_idx = next((i for i, p in enumerate(paras) if header_5 in p), None)
    if start_idx is None:
        raise ValueError(f"{target_month}월 헤더를 찾을 수 없습니다.")

    end_idx = next((i for i, p in enumerate(paras) if i > start_idx and header_nx in p), len(paras))
    section = paras[start_idx:end_idx]

    time_re  = re.compile(r"^\d{1,2}[:;]\d{2}$")
    place_re = re.compile(r"^[（(](.+)[）)]$")
    date_re  = re.compile(r"^(\d{1,2})$")

    events          = []
    current_day     = None
    current_time    = ""
    title_parts     = []
    pending_events  = []   # (day, time, title_parts) 버퍼

    def flush(day, time_str, t_parts, place=""):
        title = " ".join(t_parts).strip()
        title = re.sub(r"\s+", " ", title)
        if not title or len(title) < 3:
            return
        # 개인일정·휴가 필터
        for skip in SKIP_PARTIAL:
            if skip in title:
                return
        events.append({
            "day":   day,
            "date":  f"{target_month}. {day}",
            "time":  time_str,
            "title": title,
            "place": place,
        })

    for p in section:
        # 1) 헤더·요일 스킵
        if p in SKIP or any(s in p for s in SKIP_PARTIAL):
            continue

        # 2) 날짜 숫자 인식
        dm = date_re.match(p)
        if dm:
            d = int(dm.group(1))
            if 1 <= d <= 31:
                # 이전 버퍼 flush (장소 없이)
                if title_parts and current_day:
                    flush(current_day, current_time, title_parts)
                    title_parts = []
                current_day  = d
                current_time = ""
                title_parts  = []
                continue

        if current_day is None:
            continue

        # 3) 시간 인식
        if time_re.match(p):
            if title_parts:
                flush(current_day, current_time, title_parts)
                title_parts = []
            current_time = p.replace(";", ":")
            continue

        # 4) 장소 인식
        pm = place_re.match(p)
        if pm:
            place = pm.group(1)
            if title_parts:
                flush(current_day, current_time, title_parts, place)
                title_parts = []
            current_time = ""
            continue

        # 5) 제목 조각 누적
        title_parts.append(p)

    # 마지막 버퍼
    if title_parts and current_day:
        flush(current_day, current_time, title_parts)

    # ── 중복 제거 (같은 날+제목 앞 6자 기준) ──
    seen   = set()
    clean  = []
    for e in events:
        key = (e["day"], e["title"][:6])
        if key not in seen:
            seen.add(key)
            clean.append(e)

    return sorted(clean, key=lambda x: (x["day"], x.get("time", "")))


# ══════════════════════════════════════════════════════════════════
# STEP 2 ─ Claude API 기사 생성
# ══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """당신은 평안남도 도정 소식지 '맹호출림'의 편집장입니다.
주어진 행사 정보를 바탕으로 아래 규칙을 엄격히 지켜 기사를 작성하세요.

[규칙]
1. subtitle: 행사 핵심을 표현하는 12자 이내 문구
2. body: 공백 포함 250~350자의 기사 본문
   - "정경조 평안남도지사는" 또는 "정경조 지사는"으로 시작
   - 행사 날짜, 장소, 핵심 내용 포함
   - 공동체 정신·도민 화합·전통 계승·통일 기반 등 도정 가치 연결
   - 반드시 완전한 문장으로 끝낼 것 (문장 중간에 절대 끊지 말 것)
   - 마지막 문장: "~의 뜻을 밝혔다" / "~강조했다" / "~다짐했다" 형태
   - 문어체, 경어 없이 서술 (신문 기사 스타일)
3. priority: 기사 중요도 점수 (1~5 정수)
   5점: 전체 도민 참여 행사, 남북교류, 외부 언론 보도
   4점: 지사 주재 핵심 회의 (통일원로, 시장군수월례회의)
   3점: 위원회 행사, 기념식, 추모식
   2점: 문화공연, 뮤지컬 관련
   1점: 내부 행정회의, 도직원회의
4. JSON만 출력 (```코드블록, 설명문 절대 불가)

출력 형식:
{"subtitle": "...", "body": "...", "priority": 숫자}"""

def generate_article(ev: dict, client, governor: str = "정경조") -> dict:
    """단일 행사에 대한 기사를 Claude에게 생성 요청합니다."""
    prompt = (
        f"행사명: {ev['title']}\n"
        f"날짜: 2026년 {ev['date']}\n"
        f"시간: {ev.get('time', '')}\n"
        f"장소: {ev.get('place', '이북5도청')}\n"
        f"도지사: {governor}\n\n"
        "위 행사에 대한 맹호출림 소식지 기사를 작성해주세요."
    )

    import anthropic
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # 코드블록 제거
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        result = json.loads(raw)
        return {
            "subtitle": result.get("subtitle", "")[:20],
            "body":     result.get("body", ""),
            "priority": int(result.get("priority", 3)),
        }
    except json.JSONDecodeError as e:
        warn(f"JSON 파싱 오류: {e}")
        return {"subtitle": "", "body": _fallback_body(ev, governor), "priority": 3}
    except Exception as e:
        warn(f"API 오류: {type(e).__name__}: {e}")
        return {"subtitle": "", "body": _fallback_body(ev, governor), "priority": 3}


def _fallback_body(ev: dict, governor: str) -> str:
    """API 실패 시 기본 본문 생성."""
    place = ev.get("place", "이북5도청")
    return (
        f"{governor} 평안남도지사는 {ev['date']} {ev['title']}에 참석하여 "
        f"도민사회 발전을 위한 뜻깊은 시간을 함께했다. "
        f"정 지사는 공동체의 화합과 전통 계승의 중요성을 강조하며 "
        f"도민과 함께 나아갈 것을 다짐했다."
    )


# ══════════════════════════════════════════════════════════════════
# STEP 3 ─ JSON 조립
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

def build_magazine_json(events_with_articles: list[dict],
                         target_month: int, issue_month: int,
                         governor: str, editor: str) -> dict:
    """맹호출림 JSON 데이터 최종 조립."""
    photo_dir = f"photos/2026-{issue_month:02d}"

    # priority 내림차순 정렬 (안정 정렬 — 같은 점수는 날짜 순서 유지)
    sorted_events = sorted(events_with_articles, key=lambda x: -x.get("priority", 3))

    activities = []
    for i, ev in enumerate(sorted_events):
        safe_name = re.sub(r"[^\w가-힣]", "_", ev["title"])[:15]
        activities.append({
            "id":            i + 1,
            "title":         ev["title"],
            "date":          ev["date"],
            "subtitle":      ev.get("subtitle", ""),
            "body":          ev.get("body", ""),
            "priority":      ev.get("priority", 3),
            "image":         f"{photo_dir}/{i+1:02d}_{safe_name}.jpg",
            "imagePosition": "right" if i % 2 == 0 else "left",
        })

    cover_items = [f"{a['title']} ({a['date']})" for a in activities]

    return {
        "meta": {
            "year":        2026,
            "reportMonth": target_month,
            "issueMonth":  issue_month,
            "issueLabel":  f"맹호출림 {issue_month}월호",
            "governor":    governor,
            "editor":      editor,
            "contact":     "010-7128-7551",
            "email":       "kmr980@hanmail.net",
            "homepage":    "https://www.ibuk5do.go.kr/main.do",
        },
        "coverItems":    cover_items,
        "activities":    activities,
        "upcomingItems": [],   # 수동 입력
        "notice": {
            "title": "주요 공지사항",
            "icon":  "📌",
            "lines": ["(공지사항을 직접 입력하세요)"],
        },
        "schedule": BASE_SCHEDULE,
    }


# ══════════════════════════════════════════════════════════════════
# STEP 4 ─ 대화형 검토 모드
# ══════════════════════════════════════════════════════════════════

def interactive_review(events_with_articles: list[dict]) -> list[dict]:
    """생성된 항목을 터미널에서 하나씩 검토·수정합니다."""
    hdr("📋 생성 결과 검토")
    print(f"  {len(events_with_articles)}개 항목을 검토합니다.")
    print("  Enter=유지  e=수정  d=삭제  q=검토 종료\n")

    final = []
    for i, ev in enumerate(events_with_articles):
        print(f"  [{BOLD}{i+1:02d}/{len(events_with_articles)}{RESET}] "
              f"{CYAN}{ev['title']}{RESET}  {DIM}({ev['date']}){RESET}")
        if ev.get("subtitle"):
            print(f"       부제: {ev['subtitle']}")
        if ev.get("body"):
            wrapped = textwrap.fill(ev["body"], width=60, initial_indent="       ")
            print(f"       본문:\n{wrapped}")
        print()

        cmd = input("       → ").strip().lower()
        if cmd == "q":
            final.extend(events_with_articles[i:])
            break
        elif cmd == "d":
            warn(f"항목 삭제: {ev['title']}")
            continue
        elif cmd == "e":
            print("       새 본문 입력 (엔터로 완료):")
            new_body = input("       ").strip()
            if new_body:
                ev["body"] = new_body
            new_sub = input("       새 부제 (건너뛰려면 엔터): ").strip()
            if new_sub:
                ev["subtitle"] = new_sub
            ok("수정 완료")
        final.append(ev)
        print()

    return final


# ══════════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="平南 맹호출림 소식지 자동화 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            예시:
              python generate_magazine.py --hwp schedule.hwp --month 5
              python generate_magazine.py --hwp schedule.hwp --month 5 --no-api
              python generate_magazine.py --hwp schedule.hwp --month 5 --parse-only
        """)
    )
    parser.add_argument("--hwp",        required=True,               help="HWP 파일 경로")
    parser.add_argument("--month",      type=int, required=True,     help="보고 대상 월 (예: 5)")
    parser.add_argument("--out",        default=None,                help="출력 JSON 파일명")
    parser.add_argument("--no-api",     action="store_true",         help="Claude API 없이 뼈대만 생성")
    parser.add_argument("--parse-only", action="store_true",         help="파싱 결과만 출력하고 종료")
    parser.add_argument("--review",     action="store_true",         help="대화형 검토 모드 활성화")
    parser.add_argument("--max-items",  type=int, default=15,        help="최대 기사 수 (기본: 15)")
    parser.add_argument("--governor",   default="정경조",             help="도지사 이름")
    parser.add_argument("--editor",     default="평안남도 비서실 정책보좌 김명래", help="편집자")
    args = parser.parse_args()

    issue_month = args.month + 1
    out_file    = args.out or f"data-2026-{issue_month:02d}.json"

    # ── 헤더 ──
    print(f"\n{BOLD}{'━'*54}{RESET}")
    print(f"{BOLD}  平南 猛虎出林  소식지 자동화 스크립트{RESET}")
    print(f"{BOLD}{'━'*54}{RESET}")
    print(f"  대상월  : {CYAN}{args.month}월 실시사항{RESET}")
    print(f"  발행호수: {CYAN}{issue_month}월호{RESET}")
    print(f"  출력    : {CYAN}{out_file}{RESET}\n")

    # ══ STEP 1: HWP 파싱 ══════════════════════════════════════
    hdr(f"[1/3] HWP 파일 파싱")
    info(f"{Path(args.hwp).name}")

    if not Path(args.hwp).exists():
        err(f"파일을 찾을 수 없습니다: {args.hwp}")
        sys.exit(1)

    paras  = extract_hwp_paragraphs(args.hwp)
    events = parse_month_schedule(paras, args.month)

    if not events:
        err(f"{args.month}월 일정을 파싱할 수 없습니다.")
        sys.exit(1)

    ok(f"{len(events)}건 추출 완료")
    print()

    # 파싱 결과 출력
    for i, ev in enumerate(events, 1):
        place_str = f"  {DIM}({ev['place']}){RESET}" if ev["place"] else ""
        print(f"  {DIM}{i:2d}.{RESET} {BOLD}[{ev['date']}]{RESET}  "
              f"{ev['title']}{place_str}")

    if args.parse_only:
        print(f"\n  → --parse-only 모드: JSON 생성 없이 종료합니다.")
        return

    # 최대 항목 수 제한
    if len(events) > args.max_items:
        warn(f"{len(events)}건 중 상위 {args.max_items}건만 처리합니다.")
        warn("--max-items N 으로 개수를 조정할 수 있습니다.")
        events = events[:args.max_items]

    # ══ STEP 2: 기사 생성 ═════════════════════════════════════
    hdr(f"[2/3] 기사 본문 생성  ({len(events)}건)")

    events_with_articles = []

    if args.no_api:
        info("--no-api 모드: 기본 본문으로 생성합니다.")
        for ev in events:
            ev["subtitle"] = ev["title"][:12]
            ev["body"]     = _fallback_body(ev, args.governor)
            events_with_articles.append(ev)
        ok("뼈대 생성 완료")

    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            err("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
            err("export ANTHROPIC_API_KEY=sk-ant-... 후 재실행하세요.")
            sys.exit(1)

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            err("anthropic 패키지가 없습니다: pip install anthropic")
            sys.exit(1)

        print()
        for i, ev in enumerate(events, 1):
            bar     = "█" * i + "░" * (len(events) - i)
            pct     = int(i / len(events) * 100)
            title_s = ev["title"][:22].ljust(22)
            print(f"\r  [{bar}] {pct:3d}%  {title_s}", end="", flush=True)

            article = generate_article(ev, client, args.governor)
            ev.update(article)
            events_with_articles.append(ev)

            if i < len(events):
                time.sleep(0.3)   # API rate limit 여유

        print()  # 줄바꿈
        ok(f"{len(events_with_articles)}건 기사 생성 완료")

    # ── 대화형 검토 ──
    if args.review:
        events_with_articles = interactive_review(events_with_articles)
        ok(f"검토 후 최종 {len(events_with_articles)}건")

    # ══ STEP 3: JSON 저장 ═════════════════════════════════════
    hdr(f"[3/3] JSON 파일 저장")

    data      = build_magazine_json(events_with_articles, args.month,
                                    issue_month, args.governor, args.editor)
    json_str  = json.dumps(data, ensure_ascii=False, indent=2)

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(json_str)

    size_kb = Path(out_file).stat().st_size / 1024
    ok(f"{out_file}  ({size_kb:.1f} KB, {len(events_with_articles)}건)")

    # ── 완료 메시지 ──
    print(f"\n{BOLD}{'━'*54}{RESET}")
    print(f"{BOLD}{GREEN}  ✅ 완료!{RESET}")
    print(f"{'━'*54}")
    print(f"\n  다음 단계:")
    print(f"  {CYAN}1.{RESET} {out_file} 열어서 내용 확인·수정")
    print(f"  {CYAN}2.{RESET} photos/2026-{issue_month:02d}/ 폴더에 행사 사진 추가")
    print(f"  {CYAN}3.{RESET} maengho-template.html 상단의 DATA_FILE 값을")
    print(f"     '{out_file}' 으로 변경")
    print(f"  {CYAN}4.{RESET} 브라우저에서 열기 → Ctrl+P → PDF 저장\n")

    # ── 간단 미리보기 ──
    print(f"  {BOLD}생성된 기사 미리보기 (첫 3건):{RESET}")
    for act in data["activities"][:3]:
        print(f"\n  {CYAN}▸ {act['title']}  ({act['date']}){RESET}")
        if act.get("subtitle"):
            print(f"    부제: {act['subtitle']}")
        if act.get("body"):
            print(textwrap.fill(act["body"], width=56,
                                initial_indent="    "))
    print()


if __name__ == "__main__":
    main()
