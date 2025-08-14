'''
# 단일 파일 변환
python whisper_srt_converter.py input.srt

# 출력 파일명 지정
python whisper_srt_converter.py input.srt -o output.srt

# 파일 미리보기 (변환 전 확인)
python whisper_srt_converter.py --preview input.srt

# 폴더 내 모든 whisper 파일 변환
python whisper_srt_converter.py --batch ./videos

# 특정 패턴의 파일들만 변환
python whisper_srt_converter.py --batch ./videos --pattern "*_en.srt"

# 출력 폴더 지정
python whisper_srt_converter.py --batch ./videos -o ./converted

# 조용한 모드 (로그 최소화)
python whisper_srt_converter.py input.srt --quiet

# 보고서 생성 안함
python whisper_srt_converter.py input.srt --no-report

# 도움말
python whisper_srt_converter.py -h
'''


import re
import sys
import argparse
from pathlib import Path
from datetime import datetime

class WhisperSRTConverter:
    """Whisper 출력 형식의 SRT 변환기 (완전 기능 버전)"""
    
    def __init__(self, verbose=True):
        # Whisper 형식 패턴들
        self.patterns = [
            # 기본 Whisper 패턴: "번호 시간-->시간 텍스트"
            r'^(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s+(.+)$',
            # 시간 앞에 공백이 더 많은 경우
            r'^(\d+)\s*(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*(.+)$',
            # 점 구분자 버전
            r'^(\d+)\s+(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\s+(.+)$',
        ]
        self.verbose = verbose
        self.stats = {'processed': 0, 'failed': 0, 'total_duration': 0}
    
    def log(self, message, level="INFO"):
        """로깅 함수"""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            symbols = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️"}
            print(f"[{timestamp}] {symbols.get(level, 'ℹ️')} {message}")
    
    def detect_encoding(self, file_path):
        """파일 인코딩 자동 감지"""
        encodings = ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr', 'latin1', 'utf-16']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    content = file.read()
                self.log(f"인코딩 감지: {encoding}", "SUCCESS")
                return content, encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        raise UnicodeDecodeError("지원되는 인코딩을 찾을 수 없습니다")
    
    def time_to_seconds(self, time_str):
        """시간 문자열을 초로 변환"""
        # 00:01:30,500 또는 00:01:30.500 → 90.5초
        time_str = time_str.replace('.', ',')  # 점을 쉼표로 통일
        time_part, ms = time_str.split(',')
        h, m, s = map(int, time_part.split(':'))
        return h * 3600 + m * 60 + s + int(ms) / 1000
    
    def normalize_time(self, time_str):
        """시간 형식을 표준화 (점을 쉼표로 변경)"""
        return time_str.replace('.', ',')
    
    def parse_whisper_srt(self, content):
        """Whisper 형식의 SRT 파싱"""
        lines = content.strip().split('\n')
        blocks = []
        failed_lines = []
        
        self.log(f"총 {len(lines)}줄 처리 시작...")
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # 여러 패턴 시도
            matched = False
            for pattern_idx, pattern in enumerate(self.patterns):
                match = re.match(pattern, line)
                
                if match:
                    try:
                        number = int(match.group(1))
                        start_time = self.normalize_time(match.group(2))
                        end_time = self.normalize_time(match.group(3))
                        text = match.group(4).strip()
                        
                        # 시간 유효성 검사
                        start_sec = self.time_to_seconds(start_time)
                        end_sec = self.time_to_seconds(end_time)
                        
                        if end_sec <= start_sec:
                            self.log(f"줄 {line_num}: 잘못된 시간 순서 (시작: {start_time}, 끝: {end_time})", "WARN")
                        
                        block = {
                            'number': number,
                            'start_time': start_time,
                            'end_time': end_time,
                            'text': text,
                            'duration': end_sec - start_sec,
                            'pattern_used': pattern_idx + 1
                        }
                        blocks.append(block)
                        matched = True
                        
                        # 진행상황 출력
                        if len(blocks) % 50 == 0:
                            self.log(f"{len(blocks)}개 블록 처리됨...")
                        
                        break
                        
                    except (ValueError, IndexError) as e:
                        self.log(f"줄 {line_num} 파싱 에러: {e}", "ERROR")
                        failed_lines.append((line_num, line[:100]))
                        continue
            
            if not matched:
                failed_lines.append((line_num, line[:100]))
                if len(failed_lines) <= 10:  # 처음 10개만 출력
                    self.log(f"줄 {line_num} 패턴 불일치: {line[:50]}...", "WARN")
        
        # 통계 업데이트
        self.stats['processed'] = len(blocks)
        self.stats['failed'] = len(failed_lines)
        self.stats['total_duration'] = sum(block['duration'] for block in blocks)
        
        self.log(f"파싱 완료: {len(blocks)}개 성공, {len(failed_lines)}개 실패", "SUCCESS")
        
        if failed_lines and len(failed_lines) > 10:
            self.log(f"실패한 줄이 {len(failed_lines)}개 더 있습니다.", "WARN")
        
        return blocks, failed_lines
    
    def format_standard_srt(self, block):
        """표준 SRT 형식으로 변환"""
        return f"{block['number']}\n{block['start_time']} --> {block['end_time']}\n{block['text']}"
    
    def validate_converted_file(self, file_path):
        """변환된 파일이 올바른지 검증"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # 표준 SRT 패턴으로 다시 파싱해보기
            standard_pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:.*(?:\n(?!\d+\n\d{2}:\d{2}:\d{2}).*)*?)?)(?=\n\d+\n\d{2}:\d{2}:\d{2}|\Z)'
            matches = re.findall(standard_pattern, content, re.MULTILINE | re.DOTALL)
            
            self.log(f"변환 검증: {len(matches)}개 블록이 표준 SRT 형식으로 올바르게 변환됨", "SUCCESS")
            
            # 빈 텍스트 블록 확인
            empty_blocks = [m for m in matches if not m[3].strip()]
            if empty_blocks:
                self.log(f"경고: {len(empty_blocks)}개 블록의 텍스트가 비어있음", "WARN")
            
            return len(matches) > 0, len(matches)
            
        except Exception as e:
            self.log(f"검증 실패: {e}", "ERROR")
            return False, 0
    
    def generate_report(self, blocks, failed_lines, output_path):
        """변환 보고서 생성"""
        report_path = output_path.with_suffix('.report.txt')
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"=== Whisper SRT 변환 보고서 ===\n")
            f.write(f"변환 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"입력 파일: {output_path.stem}\n\n")
            
            f.write(f"📊 통계:\n")
            f.write(f"  - 성공적으로 변환된 블록: {len(blocks)}개\n")
            f.write(f"  - 실패한 라인: {len(failed_lines)}개\n")
            f.write(f"  - 총 영상 길이: {self.stats['total_duration']:.1f}초 ({self.stats['total_duration']/60:.1f}분)\n")
            f.write(f"  - 평균 자막 길이: {self.stats['total_duration']/len(blocks):.1f}초\n\n")
            
            if blocks:
                f.write(f"🎯 패턴 사용 통계:\n")
                pattern_counts = {}
                for block in blocks:
                    pattern_counts[block['pattern_used']] = pattern_counts.get(block['pattern_used'], 0) + 1
                
                for pattern_id, count in pattern_counts.items():
                    f.write(f"  - 패턴 {pattern_id}: {count}개\n")
                f.write("\n")
            
            if failed_lines:
                f.write(f"❌ 실패한 라인들 (처음 20개):\n")
                for line_num, line_content in failed_lines[:20]:
                    f.write(f"  줄 {line_num}: {line_content}\n")
                if len(failed_lines) > 20:
                    f.write(f"  ... 및 {len(failed_lines)-20}개 더\n")
                f.write("\n")
            
            if blocks:
                f.write(f"📝 샘플 블록들:\n")
                for i in [0, len(blocks)//2, -1]:
                    if i < len(blocks):
                        block = blocks[i] if i >= 0 else blocks[i]
                        f.write(f"  블록 {block['number']}:\n")
                        f.write(f"    시간: {block['start_time']} --> {block['end_time']}\n")
                        f.write(f"    텍스트: {block['text'][:100]}...\n\n")
        
        self.log(f"상세 보고서 생성: {report_path.name}", "SUCCESS")
        return report_path
    
    def convert_file(self, input_path, output_path=None, generate_report=True):
        """Whisper SRT를 표준 SRT로 변환"""
        input_path = Path(input_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {input_path}")
        
        if output_path is None:
            output_path = input_path.with_name(f"{input_path.stem}_standard.srt")
        else:
            output_path = Path(output_path)
        
        self.log(f"변환 시작: {input_path.name}")
        
        # 파일 읽기
        content, encoding = self.detect_encoding(input_path)
        self.log(f"파일 크기: {len(content)} 문자, 인코딩: {encoding}")
        
        # 파싱
        blocks, failed_lines = self.parse_whisper_srt(content)
        
        if not blocks:
            self.log("변환할 수 있는 SRT 블록을 찾지 못했습니다.", "ERROR")
            self.log("파일 내용 샘플 (처음 10줄):")
            lines = content.split('\n')[:10]
            for i, line in enumerate(lines, 1):
                print(f"  {i:2d}: {repr(line)}")
            return None
        
        # 번호 순으로 정렬
        blocks.sort(key=lambda x: x['number'])
        
        # 표준 SRT 형식으로 변환
        converted_blocks = [self.format_standard_srt(block) for block in blocks]
        converted_content = '\n\n'.join(converted_blocks)
        
        # 저장
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(converted_content)
        
        self.log(f"변환 완료: {output_path.name}", "SUCCESS")
        self.log(f"📊 처리 결과: {len(blocks)}개 블록, {len(failed_lines)}개 실패")
        
        # 검증
        is_valid, valid_count = self.validate_converted_file(output_path)
        if not is_valid:
            self.log("변환된 파일 검증 실패!", "ERROR")
        elif valid_count != len(blocks):
            self.log(f"검증 경고: 원본 {len(blocks)}개 vs 변환 후 {valid_count}개", "WARN")
        
        # 샘플 출력
        if blocks:
            self.log("변환 샘플:")
            print("=" * 50)
            print(self.format_standard_srt(blocks[0]))
            if len(blocks) > 1:
                print("\n" + self.format_standard_srt(blocks[1]))
            print("=" * 50)
        
        # 보고서 생성
        if generate_report:
            self.generate_report(blocks, failed_lines, output_path)
        
        return output_path
    
    def batch_convert(self, input_folder, output_folder=None, pattern="*whisper*.srt"):
        """폴더 내 모든 Whisper SRT 파일 일괄 변환"""
        input_path = Path(input_folder)
        
        if not input_path.exists():
            raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {input_folder}")
        
        if output_folder:
            output_path = Path(output_folder)
            output_path.mkdir(exist_ok=True)
        else:
            output_path = input_path / "converted"
            output_path.mkdir(exist_ok=True)
        
        # Whisper SRT 파일 찾기
        whisper_files = list(input_path.glob(pattern))
        
        # 추가 패턴들도 시도
        additional_patterns = ["*_en*.srt", "*english*.srt", "*subtitle*.srt"]
        for add_pattern in additional_patterns:
            whisper_files.extend(input_path.glob(add_pattern))
        
        # 중복 제거
        whisper_files = list(set(whisper_files))
        
        self.log(f"발견된 파일: {len(whisper_files)}개", "SUCCESS")
        
        results = {'success': 0, 'failed': 0}
        
        for srt_file in whisper_files:
            try:
                self.log(f"\n{'='*60}")
                output_file = output_path / f"{srt_file.stem}_standard.srt"
                
                result = self.convert_file(srt_file, output_file)
                if result:
                    results['success'] += 1
                    self.log(f"✅ {srt_file.name} 완료", "SUCCESS")
                else:
                    results['failed'] += 1
                    self.log(f"❌ {srt_file.name} 실패", "ERROR")
                    
            except Exception as e:
                results['failed'] += 1
                self.log(f"❌ {srt_file.name} 오류: {e}", "ERROR")
        
        # 배치 요약
        self.log(f"\n🎉 배치 변환 완료!")
        self.log(f"📊 결과: 성공 {results['success']}개, 실패 {results['failed']}개")
        
        return results
    
    def preview_file(self, file_path, lines=10):
        """파일 미리보기"""
        try:
            content, encoding = self.detect_encoding(file_path)
            lines_list = content.split('\n')[:lines]
            
            print(f"\n📄 파일 미리보기: {file_path}")
            print(f"📊 파일 정보: {len(content)} 문자, {len(lines_list)} 줄 (처음 {lines}줄), 인코딩: {encoding}")
            print("=" * 60)
            
            for i, line in enumerate(lines_list, 1):
                print(f"{i:2d}: {repr(line)}")
            
            print("=" * 60)
            
            # 패턴 매칭 테스트
            matched_lines = 0
            for line in lines_list:
                for pattern in self.patterns:
                    if re.match(pattern, line.strip()):
                        matched_lines += 1
                        break
            
            print(f"🎯 패턴 매칭: {matched_lines}/{len(lines_list)} 줄이 Whisper 형식과 일치")
            
        except Exception as e:
            self.log(f"미리보기 실패: {e}", "ERROR")

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description='🎯 Whisper SRT 변환기 - Whisper 출력을 표준 SRT로 변환',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python whisper_srt_converter.py input.srt
  python whisper_srt_converter.py input.srt -o output.srt
  python whisper_srt_converter.py --batch ./videos
  python whisper_srt_converter.py --preview input.srt
        """
    )
    
    parser.add_argument('input', nargs='?', help='입력 SRT 파일 또는 폴더 경로')
    parser.add_argument('-o', '--output', help='출력 파일 또는 폴더 경로')
    parser.add_argument('--batch', action='store_true', help='배치 모드 (폴더 내 모든 파일 처리)')
    parser.add_argument('--pattern', default='*whisper*.srt', help='배치 모드에서 찾을 파일 패턴')
    parser.add_argument('--preview', action='store_true', help='파일 미리보기 모드')
    parser.add_argument('--quiet', action='store_true', help='로그 출력 최소화')
    parser.add_argument('--no-report', action='store_true', help='보고서 생성 안함')
    
    args = parser.parse_args()
    
    if not args.input:
        parser.print_help()
        return
    
    # 변환기 초기화
    converter = WhisperSRTConverter(verbose=not args.quiet)
    
    try:
        if args.preview:
            # 미리보기 모드
            converter.preview_file(args.input)
            
        elif args.batch:
            # 배치 모드
            converter.batch_convert(args.input, args.output, args.pattern)
            
        else:
            # 단일 파일 모드
            result = converter.convert_file(
                args.input, 
                args.output, 
                generate_report=not args.no_report
            )
            
            if result:
                converter.log(f"🎉 변환 성공: {result}", "SUCCESS")
            else:
                converter.log("변환 실패", "ERROR")
                sys.exit(1)
                
    except KeyboardInterrupt:
        converter.log("사용자에 의해 중단됨", "WARN")
        sys.exit(1)
    except Exception as e:
        converter.log(f"오류 발생: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()