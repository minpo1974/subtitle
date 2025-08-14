import re
import os
import argparse
import sys

def extract_subtitles_method1(srt_file_path, output_file_path):
    """
    방법 1: 정규식을 사용한 추출
    """
    with open(srt_file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # SRT 패턴: 번호 -> 시간 -> 텍스트 -> 빈줄
    # 정규식으로 시간 정보가 포함된 줄을 찾아서 제거
    lines = content.split('\n')
    subtitle_lines = []
    
    for line in lines:
        line = line.strip()
        # 빈 줄이거나 숫자만 있는 줄이거나 시간 정보가 있는 줄은 제외
        if (line and 
            not line.isdigit() and 
            not re.match(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', line)):
            subtitle_lines.append(line)
    
    # 결과를 파일로 저장
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write('\n'.join(subtitle_lines))
    
    print(f"방법 1: 추출된 자막이 '{output_file_path}'에 저장되었습니다.")

def extract_subtitles_method2(srt_file_path, output_file_path):
    """
    방법 2: 줄별 분석을 통한 추출
    """
    with open(srt_file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    subtitle_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 숫자로 시작하는 줄 (자막 번호)
        if line.isdigit():
            i += 1
            # 다음 줄은 시간 정보이므로 건너뛰기
            if i < len(lines):
                i += 1
            # 그 다음 줄부터 자막 텍스트
            while i < len(lines) and lines[i].strip():
                subtitle_text = lines[i].strip()
                if subtitle_text:
                    subtitle_lines.append(subtitle_text)
                i += 1
        else:
            i += 1
    
    # 결과를 파일로 저장
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write('\n'.join(subtitle_lines))
    
    print(f"방법 2: 추출된 자막이 '{output_file_path}'에 저장되었습니다.")

def extract_subtitles_simple(srt_file_path, output_file_path):
    """
    방법 3: 가장 간단한 방법
    """
    with open(srt_file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    subtitle_lines = []
    
    for line in lines:
        line = line.strip()
        # 빈 줄, 숫자만 있는 줄, 시간 정보가 있는 줄 제외
        if (line and 
            not line.isdigit() and 
            '-->' not in line):
            subtitle_lines.append(line)
    
    # 결과를 파일로 저장
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write('\n'.join(subtitle_lines))
    
    print(f"방법 3: 추출된 자막이 '{output_file_path}'에 저장되었습니다.")

def srt_to_text(input_file, output_file, method='simple'):
    """
    SRT 파일을 텍스트로 변환하는 간단한 함수
    
    Args:
        input_file (str): 입력 SRT 파일 경로
        output_file (str): 출력 텍스트 파일 경로
        method (str): 추출 방법 ('simple', 'regex', 'parsing')
    
    Returns:
        bool: 성공시 True, 실패시 False
    """
    if not os.path.exists(input_file):
        print(f"오류: 입력 파일 '{input_file}'을 찾을 수 없습니다.")
        return False
    
    try:
        if method == 'simple':
            extract_subtitles_simple(input_file, output_file)
        elif method == 'regex':
            extract_subtitles_method1(input_file, output_file)
        elif method == 'parsing':
            extract_subtitles_method2(input_file, output_file)
        else:
            print(f"알 수 없는 방법: {method}")
            return False
        
        return True
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
        return False

# 메인 실행 부분
def main():
    # 명령행 인자 파서 설정
    parser = argparse.ArgumentParser(description='SRT 자막 파일에서 순수 텍스트만 추출합니다.')
    parser.add_argument('input_file', help='입력 SRT 파일 경로')
    parser.add_argument('output_file', help='출력 텍스트 파일 경로')
    parser.add_argument('-m', '--method', choices=['simple', 'regex', 'parsing'], 
                       default='simple', help='추출 방법 선택 (기본값: simple)')
    
    # 인자가 없으면 도움말 출력
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    args = parser.parse_args()
    
    # 파일이 존재하는지 확인
    if not os.path.exists(args.input_file):
        print(f"오류: 입력 파일 '{args.input_file}'을 찾을 수 없습니다.")
        return
    
    print(f"SRT 자막 텍스트 추출을 시작합니다...")
    print(f"입력 파일: {args.input_file}")
    print(f"출력 파일: {args.output_file}")
    print(f"사용 방법: {args.method}")
    
    try:
        # 선택된 방법으로 추출
        if args.method == 'simple':
            extract_subtitles_simple(args.input_file, args.output_file)
        elif args.method == 'regex':
            extract_subtitles_method1(args.input_file, args.output_file)
        elif args.method == 'parsing':
            extract_subtitles_method2(args.input_file, args.output_file)
        
        print("추출이 완료되었습니다!")
        
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()

# 테스트를 위한 샘플 SRT 내용 생성 함수
def create_sample_srt():
    """
    테스트용 샘플 SRT 파일 생성
    """
    sample_content = """1
00:00:00,000 --> 00:00:18,000
자 안녕하십니까 데이터베이스 개념 수업에 오신 것을 환영합니다.

2
00:00:18,000 --> 00:00:25,000
먼저 저는 컴퓨터공학과의 정민포 교수입니다.

3
00:00:25,000 --> 00:00:37,000
오늘 여러분을 만나게 되어 정말 기쁘고 함께 데이터베이스를 공부하게 되어 기대가 됩니다.
"""
    
    with open("sample.srt", "w", encoding="utf-8") as f:
        f.write(sample_content)
    
    print("샘플 SRT 파일 'sample.srt'가 생성되었습니다.")

# 샘플 파일로 테스트하려면 아래 주석을 해제하세요
# create_sample_srt()
# extract_subtitles_simple("sample.srt", "sample_output.txt")

"""
사용법:
python srt_extractor.py input.srt output.txt
python srt_extractor.py input.srt output.txt -m simple
python srt_extractor.py input.srt output.txt --method regex
python srt_extractor.py "경로/파일명.srt" "출력경로/결과.txt"

예시:
python srt_extractor.py lecture.srt lecture_text.txt
python srt_extractor.py "C:/Videos/subtitle.srt" "C:/Text/subtitle_only.txt"
"""