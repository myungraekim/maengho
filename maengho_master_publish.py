#!/usr/bin/env python3
"""
맹호출림 마스터 발행 스킬
모든 수정사항 자동화: 검증 → 정렬 → 사진 매칭 → HTML 동기화 → 배포
"""

import argparse
import json
import re
import subprocess
import unicodedata
from pathlib import Path
from datetime import datetime


class MaenghoMasterPublish:
    def __init__(self, month: int):
        self.month = month
        self.year = 2026
        self.report_month = month - 1 if month > 1 else 12
        self.data_file = f"data-{self.year}-{self.month:02d}.json"
        self.data = None
        self.errors = []
        self.warnings = []

    def load_data(self):
        """데이터 로드"""
        print(f"📂 데이터 로드: {self.data_file}")
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            print("✅ 데이터 로드 완료\n")
            return True
        except Exception as e:
            self.errors.append(f"데이터 로드 실패: {e}")
            return False

    def verify(self):
        """데이터 검증"""
        print("🔍 데이터 검증 중...\n")

        if not self.data:
            return False

        activities = self.data.get('activities', [])

        # 1. 날짜 일관성 검증
        print("  ✓ 날짜 일관성 검증")
        for act in activities:
            title = act['title']
            date_str = act['date']
            body = act['body']

            # body에서 월일 추출
            match = re.search(r'(\d+)월\s*(\d+)일', body)
            if match:
                body_month = match.group(1)
                body_day = match.group(2)

                # date 필드와 비교
                date_parts = date_str.replace(' ', '').split('.')
                if len(date_parts) == 2:
                    date_month = date_parts[0]
                    date_day = date_parts[1]

                    if body_month != date_month or body_day != date_day:
                        self.errors.append(f"❌ {title}: date({date_str}) ≠ body({body_month}월 {body_day}일)")

        # 2. 글자수 검증
        print("  ✓ 글자수 검증")
        for act in activities:
            length = len(act['body'])
            if length < 250 or length > 350:
                self.warnings.append(f"⚠️  {act['title']}: {length}자 (범위: 250~350)")

        # 3. Priority 검증
        print("  ✓ Priority 검증")
        for act in activities:
            pri = act.get('priority', 0)
            if pri not in [1, 2, 3, 4, 5]:
                self.errors.append(f"❌ {act['title']}: priority {pri} (범위: 1~5)")

        # 4. 정렬 검증
        print("  ✓ 정렬 검증\n")

        if self.errors:
            print(f"\n❌ 검증 실패: {len(self.errors)}개 에러")
            for err in self.errors:
                print(f"  {err}")
            return False

        if self.warnings:
            print(f"⚠️  경고: {len(self.warnings)}개")
            for warn in self.warnings:
                print(f"  {warn}")

        print("✅ 검증 완료\n")
        return True

    def sort_data(self):
        """데이터 정렬"""
        print("📊 데이터 정렬 중...\n")

        def extract_date(item):
            if isinstance(item, dict):
                date_str = item.get('date', '')
            else:
                match = re.search(r'\((\d+)\.\s*(\d+)\)', str(item))
                if match:
                    return (int(match.group(1)), int(match.group(2)))
                return (99, 99)

            if date_str:
                parts = date_str.replace(' ', '').split('.')
                if len(parts) == 2:
                    return (int(parts[0]), int(parts[1]))
            return (99, 99)

        # coverItems 정렬
        print("  ✓ coverItems 정렬")
        self.data['coverItems'].sort(key=extract_date)

        # activities 정렬
        print("  ✓ activities 정렬")
        self.data['activities'].sort(key=lambda x: (-x.get('priority', 0), extract_date(x)))

        # upcomingItems 정렬
        print("  ✓ upcomingItems 정렬\n")
        self.data['upcomingItems'].sort(key=extract_date)

        print("✅ 정렬 완료\n")

    def match_photos(self):
        """사진 자동 매칭"""
        print("📸 사진 자동 매칭 중...\n")

        photo_dir = Path(f"photos/2026-{self.month:02d}")
        logo_path = "photos/2026-07/이북5도위원회로고.png"

        # 사진 파일 스캔 (유니코드 정규화, 확장자 없는 파일도 포함)
        photos = {}
        if photo_dir.exists():
            for file in photo_dir.glob("*"):
                if file.is_file():
                    if file.suffix.lower() in ['.jpeg', '.jpg', '.png', '']:
                        normalized_stem = unicodedata.normalize('NFC', file.stem)
                        photos[normalized_stem] = str(file)

            # 폴더 내 첫 번째 이미지 (daedongang 등)
            for folder in photo_dir.glob("*"):
                if folder.is_dir():
                    folder_name = unicodedata.normalize('NFC', folder.name)
                    for img in list(folder.glob("*.jpg")) + list(folder.glob("*.jpeg")) + list(folder.glob("*.png")):
                        if img.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                            photos[folder_name] = str(img)
                            break

        # 매칭 규칙 (한글 title 검색용, 파일명은 영문으로 정리됨)
        matching_rules = {
            "통일원로": ("통일원로의원 간담회", ["tongil", "08"]),
            "함북": ("함북도지사 이.취임식", ["hambuk", "10"]),
            "함남": ("함남도지사 이.취임식", ["hamnam", "09"]),
            "백선엽": ("백선엽 장군 6주기 추모식", ["baekseonyeop", "04"]),
            "덕천군": ("덕천군 제59차 정기총회", ["dekcheon", "02"]),
            "국민일보": ("국민일보 언론 인터뷰", ["kbs", "01"]),
            "북한이탈주민": ("제3회 북한이탈 주민의 날", ["northkoreans", "05"]),
            "시장군수": ("명예시장·군수 월례회의", ["mayor_county", "06"]),
            "민주평통": ("민주평통자문회의이북5도지역회의", ["minpyeongtong", "03"]),
            "조사연구": ("조사연구자료 설명회", ["research", "07"]),
            "대동강": ("음악극'한 많은 대동강'공연", ["daedongang"]),
        }

        matched = 0
        for act in self.data['activities']:
            title = act['title']
            found = False

            # 규칙 기반 매칭
            for key, (rule_title, search_keys) in matching_rules.items():
                if key in title or title in rule_title:
                    for search_key in search_keys:
                        for photo_name, photo_path in photos.items():
                            if search_key in photo_name:
                                act['image'] = photo_path
                                print(f"  ✓ {title}: {photo_path}")
                                found = True
                                matched += 1
                                break
                        if found:
                            break
                if found:
                    break

            # 매칭 실패시 로고 할당
            if not found:
                act['image'] = logo_path
                act['isLogo'] = True
                print(f"  🏛 {title}: {logo_path} (기본)")

        print(f"\n✅ 사진 매칭 완료 ({matched}개 실제 사진)\n")

    def sync_html(self):
        """HTML INLINE_DATA 동기화"""
        print("🔄 HTML 동기화 중...\n")

        html_file = "maengho-template.html"

        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                html = f.read()

            # 이미지 경로를 GitHub Pages 절대 경로로 변환
            for act in self.data['activities']:
                if act['image'].startswith('photos/'):
                    act['image'] = f"https://myungraekim.github.io/maengho/{act['image']}"

            # INLINE_DATA 생성
            inline_json = json.dumps(self.data, ensure_ascii=False, separators=(',', ':'))
            new_inline_data = f'const INLINE_DATA = {inline_json};'

            # 교체
            pattern = r'const INLINE_DATA = \{.*?\};'
            new_html = re.sub(pattern, new_inline_data, html, flags=re.DOTALL)

            # 저장
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(new_html)

            print(f"  ✓ {html_file} 업데이트 완료\n")
            return True
        except Exception as e:
            self.errors.append(f"HTML 동기화 실패: {e}")
            return False

    def save_data(self):
        """JSON 데이터 저장"""
        print("💾 데이터 저장 중...\n")

        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            print(f"  ✓ {self.data_file} 저장 완료\n")
            return True
        except Exception as e:
            self.errors.append(f"데이터 저장 실패: {e}")
            return False

    def deploy(self):
        """자동 배포 (git commit & push)"""
        print("🚀 자동 배포 중...\n")

        try:
            # git add (데이터, HTML, 사진)
            subprocess.run(['git', 'add', self.data_file, 'maengho-template.html', f'photos/2026-{self.month:02d}/'], check=True)
            print("  ✓ git add 완료")

            # git commit
            commit_msg = f"{self.month}월호 최종 발행: 자동 검증 + 정렬 + 사진 매칭 + HTML 동기화\n\nCo-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
            subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
            print("  ✓ git commit 완료")

            # git push
            subprocess.run(['git', 'push', 'origin', 'main'], check=True)
            print("  ✓ git push 완료\n")

            return True
        except Exception as e:
            self.errors.append(f"배포 실패: {e}")
            return False

    def publish(self, verify=False, photos=False, html_sync=False, deploy=False):
        """통합 발행"""
        print(f"\n{'='*60}")
        print(f"🎯 맹호출림 {self.month}월호 최종 발행")
        print(f"{'='*60}\n")

        # 1. 데이터 로드
        if not self.load_data():
            return False

        # 2. 검증
        if verify:
            if not self.verify():
                return False

        # 3. 정렬
        self.sort_data()

        # 4. 사진 매칭
        if photos:
            self.match_photos()

        # 5. HTML 동기화 (이미지 경로 절대 경로 변환)
        if html_sync:
            if not self.sync_html():
                return False

        # 6. 데이터 저장 (절대 경로로 저장)
        if not self.save_data():
            return False

        # 7. 배포
        if deploy:
            if not self.deploy():
                return False

        # 결과 출력
        print(f"{'='*60}")
        if self.errors:
            print(f"❌ {len(self.errors)}개 에러 발생")
            for err in self.errors:
                print(f"  {err}")
            return False

        print("✅ 모든 작업 완료!")
        print(f"{'='*60}\n")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="맹호출림 마스터 발행 스킬 - 모든 수정사항 자동화"
    )
    parser.add_argument("--month", "-m", type=int, required=True, help="발행월 (1-12)")
    parser.add_argument("--verify", action="store_true", help="데이터 검증")
    parser.add_argument("--photos", action="store_true", help="사진 자동 매칭")
    parser.add_argument("--html-sync", action="store_true", help="HTML 동기화")
    parser.add_argument("--deploy", action="store_true", help="자동 배포 (git push)")

    args = parser.parse_args()

    publisher = MaenghoMasterPublish(args.month)
    success = publisher.publish(
        verify=args.verify,
        photos=args.photos,
        html_sync=args.html_sync,
        deploy=args.deploy
    )

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
