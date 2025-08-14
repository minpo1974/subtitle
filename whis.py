import whisper
import os
import subprocess
from datetime import timedelta
import argparse
import re
import time
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Callable
import json
import math

# 번역 라이브러리들
try:
    from googletrans import Translator as GoogleTranslator
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    import argostranslate.package
    import argostranslate.translate
    ARGOS_AVAILABLE = True
except ImportError:
    ARGOS_AVAILABLE = False

try:
    import edge_tts
    from pydub import AudioSegment
    from pydub.silence import split_on_silence
    TTS_AVAILABLE = True
    AUDIO_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    AUDIO_AVAILABLE = False

class IntegratedVideoProcessor:
    """통합 영상 처리 시스템"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.temp_files = []  # 임시 파일 추적용
        self.progress_callback: Optional[Callable] = None
        self.current_stage = ""
        
    def set_progress_callback(self, callback: Callable):
        """진행률 콜백 설정"""
        self.progress_callback = callback
        
    def report_progress(self, progress: float):
        """진행률 보고"""
        if self.progress_callback:
            self.progress_callback(self.current_stage, progress)
            
    def cleanup_temp_files(self):
        """임시 파일들 정리"""
        for file_path in self.temp_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"임시 파일 삭제: {file_path}")
                except:
                    pass
        self.temp_files.clear()
        
    def sanitize_filename(self, filename: str) -> str:
        """파일명에서 문제가 되는 특수문자 제거 또는 변경"""
        # 파일 경로에서 디렉토리와 파일명 분리
        dir_path = os.path.dirname(filename)
        base_name = os.path.basename(filename)
        
        # 파일명과 확장자 분리
        name_without_ext = os.path.splitext(base_name)[0]
        ext = os.path.splitext(base_name)[1]
        
        # 문제가 되는 특수문자들을 안전한 문자로 변경
        # ffmpeg에서 문제가 되는 문자들: [ ] ( ) ' " & $ ! ` ; | * ? < >
        replacements = {
            '[': '［',  # 전각 대괄호로 변경
            ']': '］',
            '(': '（',  # 전각 괄호로 변경
            ')': '）',
            "'": '＇',  # 전각 작은따옴표
            '"': '＂',  # 전각 큰따옴표
            '&': '＆',  # 전각 앰퍼샌드
            '$': '＄',  # 전각 달러
            '!': '！',  # 전각 느낌표
            '`': '｀',  # 전각 백틱
            ';': '；',  # 전각 세미콜론
            '|': '｜',  # 전각 파이프
            '*': '＊',  # 전각 별표
            '?': '？',  # 전각 물음표
            '<': '＜',  # 전각 부등호
            '>': '＞',  # 전각 부등호
            ':': '：',  # 전각 콜론 (Windows 경로에서 문제가 될 수 있음)
            '\\': '＼', # 전각 백슬래시
            '/': '／',  # 전각 슬래시 (경로 구분자가 아닌 경우)
        }
        
        # Windows에서 경로 구분자는 유지
        if os.name == 'nt' and ':' in name_without_ext[1:]:  # 드라이브 문자 다음의 콜론만 변경
            parts = name_without_ext.split(':', 1)
            if len(parts) > 1:
                name_without_ext = parts[0] + '：' + parts[1]
        
        # 특수문자 치환
        for old_char, new_char in replacements.items():
            name_without_ext = name_without_ext.replace(old_char, new_char)
        
        # 안전한 파일명 생성
        safe_filename = name_without_ext + ext
        
        # 전체 경로 재구성
        if dir_path:
            return os.path.join(dir_path, safe_filename)
        else:
            return safe_filename
            
    def get_safe_base_name(self, video_path: str) -> str:
        """비디오 경로에서 안전한 기본 이름 추출"""
        # 원본 경로의 디렉토리와 파일명 분리
        dir_path = os.path.dirname(video_path)
        filename = os.path.basename(video_path)
        
        # 안전한 파일명 생성
        safe_filename = self.sanitize_filename(filename)
        safe_base_name = os.path.splitext(safe_filename)[0]
        
        # 디렉토리 경로와 결합
        if dir_path:
            return os.path.join(dir_path, safe_base_name)
        else:
            return safe_base_name
        
    def extract_audio_from_video(self, video_path: str, audio_path: str) -> bool:
        """영상에서 오디오 추출 (수정됨: 인코딩 처리 개선)"""
        try:
            command = [
                'ffmpeg', '-i', video_path,
                '-ab', '160k',
                '-ac', '2',
                '-ar', '44100',
                '-vn', audio_path,
                '-y'
            ]
            
            # subprocess 실행 시 인코딩 명시
            result = subprocess.run(
                command, 
                check=True, 
                capture_output=True,
                encoding='utf-8',
                errors='replace'
            )
            
            print(f"✅ 오디오 추출 완료: {audio_path}")
            self.temp_files.append(audio_path)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ 오디오 추출 실패: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                print(f"   STDERR: {e.stderr}")
            return False
            
    def format_timestamp(self, seconds: float) -> str:
        """초를 SRT 형식 타임스탬프로 변환"""
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        milliseconds = int((td.total_seconds() - total_seconds) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
        
    def create_srt_file(self, segments: List[dict], output_path: str):
        """Whisper 결과를 SRT 파일로 저장 (수정됨: 인코딩 명시)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                start_time = self.format_timestamp(segment['start'])
                end_time = self.format_timestamp(segment['end'])
                text = segment['text'].strip()
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
                
        print(f"✅ SRT 파일 생성 완료: {output_path}")

    def split_audio_by_time(self, audio_path: str, chunk_duration_minutes: int = 10) -> List[str]:
        """오디오를 시간 기반으로 분할"""
        if not AUDIO_AVAILABLE:
            print("❌ pydub가 설치되지 않았습니다. 분할 처리를 사용할 수 없습니다.")
            return []
            
        try:
            print(f"🔄 오디오 분할 시작 ({chunk_duration_minutes}분 단위)")
            
            # 오디오 로드
            audio = AudioSegment.from_file(audio_path)
            total_duration = len(audio) / 1000  # 초 단위
            chunk_duration_ms = chunk_duration_minutes * 60 * 1000  # 밀리초 단위
            
            print(f"   전체 길이: {total_duration:.1f}초 ({total_duration/60:.1f}분)")
            print(f"   분할 단위: {chunk_duration_minutes}분")
            
            chunks = []
            chunk_files = []
            
            # 오디오를 청크로 분할
            for i in range(0, len(audio), chunk_duration_ms):
                chunk = audio[i:i + chunk_duration_ms]
                chunks.append(chunk)
                
                # 청크를 파일로 저장
                base_name = os.path.splitext(audio_path)[0]
                chunk_file = f"{base_name}_chunk_{len(chunks):03d}.wav"
                chunk.export(chunk_file, format="wav")
                chunk_files.append(chunk_file)
                self.temp_files.append(chunk_file)
                
                chunk_duration_sec = len(chunk) / 1000
                start_time = i / 1000
                print(f"   청크 {len(chunks)}: {start_time:.1f}s ~ {start_time + chunk_duration_sec:.1f}s ({chunk_duration_sec:.1f}초)")
                
            print(f"✅ 오디오 분할 완료: {len(chunk_files)}개 청크 생성")
            return chunk_files
            
        except Exception as e:
            print(f"❌ 오디오 분할 실패: {e}")
            return []

    def extract_subtitles_with_chunks(self, video_path: str, model_size: str = "medium", 
                                    language: str = "auto", chunk_duration: int = 10) -> str:
        """청크 단위로 자막 추출"""
        self.current_stage = "Whisper 자막 추출 (분할 처리)"
        print(f"\n🎯 1단계: Whisper로 자막 추출 - 분할 처리 (모델: {model_size}, 언어: {language}, 청크: {chunk_duration}분)")
        
        base_name = self.get_safe_base_name(video_path)
        audio_path = base_name + "_temp_audio.wav"
        srt_path = base_name + "_whisper_subtitles.srt"
        
        # 중간 결과 저장용 폴더
        partial_results_dir = base_name + "_partial_chunks"
        os.makedirs(partial_results_dir, exist_ok=True)
        
        try:
            # 1. 오디오 추출
            print("   📁 1-1단계: 오디오 추출 중...")
            self.report_progress(0.05)
            if not self.extract_audio_from_video(video_path, audio_path):
                return None
                
            # 2. 오디오 분할
            print(f"   ✂️  1-2단계: 오디오 분할 중 ({chunk_duration}분 단위)...")
            self.report_progress(0.1)
            chunk_files = self.split_audio_by_time(audio_path, chunk_duration)
            
            if not chunk_files:
                print("❌ 오디오 분할 실패, 일반 처리로 전환합니다.")
                return self.extract_subtitles_with_whisper(video_path, model_size, language)
                
            # 3. Whisper 모델 로드
            print(f"   🧠 1-3단계: Whisper 모델 ({model_size}) 로딩 중...")
            self.report_progress(0.15)
            model = whisper.load_model(model_size)
            
            # 4. 청크별 음성 인식
            print(f"   🎤 1-4단계: 청크별 음성 인식 시작 ({len(chunk_files)}개 청크)")
            print(f"   ⏱️  예상 처리 시간: 약 {len(chunk_files) * 2}~{len(chunk_files) * 5}분")
            all_segments = []
            
            import time
            total_start_time = time.time()
            
            for i, chunk_file in enumerate(chunk_files):
                chunk_start_time_processing = time.time()
                chunk_progress = 0.15 + (0.75 * i / len(chunk_files))
                self.report_progress(chunk_progress)
                
                print(f"\n      📝 청크 {i+1}/{len(chunk_files)} 처리 시작")
                print(f"         파일: {os.path.basename(chunk_file)}")
                print(f"         크기: {os.path.getsize(chunk_file) / 1024 / 1024:.1f}MB")
                
                try:
                    # 청크의 시작 시간 계산 (분할 단위로)
                    chunk_start_time = i * chunk_duration * 60  # 초 단위
                    
                    print(f"         🔄 Whisper 처리 중... (청크 {i+1})")
                    print(f"         ⏰ 처리 시작 시간: {time.strftime('%H:%M:%S')}")
                    
                    # Whisper로 청크 처리 (timeout 포함)
                    import signal
                    import threading
                    
                    result = None
                    exception_occurred = None
                    
                    def whisper_process():
                        nonlocal result, exception_occurred
                        try:
                            if language and language != "auto":
                                result = model.transcribe(chunk_file, language=language, verbose=False)
                            else:
                                result = model.transcribe(chunk_file, verbose=False)
                        except Exception as e:
                            exception_occurred = e
                    
                    # 별도 스레드에서 Whisper 실행
                    whisper_thread = threading.Thread(target=whisper_process)
                    whisper_thread.daemon = True
                    whisper_thread.start()
                    
                    # 진행 상황 모니터링 (30초마다 상태 출력)
                    timeout_minutes = max(5, chunk_duration * 2)  # 최소 5분, 또는 청크 길이의 2배
                    timeout_seconds = timeout_minutes * 60
                    
                    for wait_time in range(0, timeout_seconds, 30):
                        whisper_thread.join(timeout=30)
                        if not whisper_thread.is_alive():
                            break
                        elapsed = wait_time + 30
                        print(f"         ⏳ Whisper 처리 중... ({elapsed//60}분 {elapsed%60}초 경과)")
                        print(f"            💡 긴 청크는 처리에 시간이 오래 걸릴 수 있습니다.")
                        if elapsed >= 300:  # 5분 이상
                            print(f"            📊 예상 완료 시간: {timeout_minutes}분 이내")
                    
                    # timeout 확인
                    if whisper_thread.is_alive():
                        print(f"         ⚠️ timeout ({timeout_minutes}분) 발생!")
                        print(f"         🔄 다음 청크로 건너뜁니다...")
                        continue
                    
                    if exception_occurred:
                        raise exception_occurred
                    
                    if result is None:
                        print(f"         ❌ Whisper 처리 결과가 없습니다.")
                        continue
                    
                    chunk_processing_time = time.time() - chunk_start_time_processing
                    
                    # 세그먼트에 오프셋 적용
                    chunk_segments = []
                    for segment in result['segments']:
                        adjusted_segment = {
                            'start': segment['start'] + chunk_start_time,
                            'end': segment['end'] + chunk_start_time,
                            'text': segment['text']
                        }
                        all_segments.append(adjusted_segment)
                        chunk_segments.append(adjusted_segment)
                    
                    # 중간 결과 저장
                    chunk_srt_path = os.path.join(partial_results_dir, f"chunk_{i+1:03d}.srt")
                    self.create_srt_file(chunk_segments, chunk_srt_path)
                    
                    # 현재까지의 전체 결과도 저장
                    current_total_srt = os.path.join(partial_results_dir, f"current_total_{i+1:03d}.srt")
                    self.create_srt_file(all_segments, current_total_srt)
                    
                    elapsed_total = time.time() - total_start_time
                    estimated_remaining = (elapsed_total / (i + 1)) * (len(chunk_files) - i - 1)
                    
                    print(f"         ✅ 청크 {i+1} 완료!")
                    print(f"         📊 세그먼트: {len(result['segments'])}개")
                    print(f"         ⏱️  처리시간: {chunk_processing_time:.1f}초")
                    print(f"         📄 텍스트: {result['text'][:80]}...")
                    print(f"         💾 중간저장: {chunk_srt_path}")
                    print(f"         📈 전체진행: {i+1}/{len(chunk_files)} ({((i+1)/len(chunk_files)*100):.1f}%)")
                    print(f"         ⏳ 예상남은시간: {estimated_remaining/60:.1f}분")
                    
                    if 'language' in result:
                        print(f"         🌍 감지언어: {result['language']}")
                    
                except Exception as e:
                    print(f"         ❌ 청크 {i+1} 처리 실패: {e}")
                    print(f"         🔄 다음 청크로 계속 진행...")
                    continue
                    
            # 5. 통합된 SRT 파일 생성
            print("\n   🔗 1-5단계: 분할된 자막 통합 중...")
            self.report_progress(0.95)
            
            if all_segments:
                self.create_srt_file(all_segments, srt_path)
                
                total_processing_time = time.time() - total_start_time
                
                print(f"\n   📊 통합 결과:")
                print(f"      - 총 세그먼트: {len(all_segments)}개")
                print(f"      - 처리 청크: {len(chunk_files)}개")
                print(f"      - 총 처리시간: {total_processing_time/60:.1f}분")
                print(f"      - 평균 청크처리: {total_processing_time/len(chunk_files):.1f}초")
                
                # 전체 텍스트 미리보기
                total_text = ' '.join([seg['text'] for seg in all_segments[:5]])  # 처음 5개만
                print(f"   📄 전체 텍스트 미리보기: {total_text[:200]}...")
                
                # 중간 파일들 정리 여부 알림
                print(f"\n   📁 중간 결과물:")
                print(f"      - 폴더: {partial_results_dir}")
                print(f"      - 청크별 SRT: chunk_001.srt ~ chunk_{len(chunk_files):03d}.srt")
                print(f"      - 진행상황 SRT: current_total_001.srt ~ current_total_{len(chunk_files):03d}.srt")
                
            else:
                print("   ❌ 추출된 세그먼트가 없습니다.")
                return None
                
            self.report_progress(1.0)
            print(f"\n✅ 분할 처리를 통한 자막 추출 완료!")
            print(f"   📁 최종 파일: {srt_path}")
            print(f"   📊 총 세그먼트 수: {len(all_segments)}")
            print(f"   💾 중간 결과: {partial_results_dir} 폴더")
            
            return srt_path
            
        except Exception as e:
            print(f"❌ 분할 자막 추출 실패: {e}")
            print("   일반 처리로 전환을 시도합니다...")
            return self.extract_subtitles_with_whisper(video_path, model_size, language)
        
    def extract_subtitles_with_whisper(self, video_path: str, model_size: str = "medium", 
                                     language: str = "auto") -> str:
        """Whisper로 자막 추출"""
        self.current_stage = "Whisper 자막 추출"
        print(f"\n🎯 1단계: Whisper로 자막 추출 (모델: {model_size}, 언어: {language})")
        
        base_name = self.get_safe_base_name(video_path)
        audio_path = base_name + "_temp_audio.wav"
        srt_path = base_name + "_whisper_subtitles.srt"
        
        try:
            # 1. 오디오 추출
            print("   오디오 추출 중...")
            self.report_progress(0.1)
            if not self.extract_audio_from_video(video_path, audio_path):
                return None
                
            # 2. Whisper 모델 로드
            print(f"   Whisper 모델 ({model_size}) 로딩 중...")
            self.report_progress(0.3)
            model = whisper.load_model(model_size)
            
            # 3. 음성 인식
            print("   음성 인식 중... (시간이 오래 걸릴 수 있습니다)")
            self.report_progress(0.5)
            
            if language and language != "auto":
                result = model.transcribe(audio_path, language=language, verbose=False)
            else:
                result = model.transcribe(audio_path, verbose=False)
                
            # 4. SRT 파일 생성
            self.report_progress(0.9)
            self.create_srt_file(result['segments'], srt_path)
            
            if 'language' in result:
                print(f"   감지된 언어: {result['language']}")
                
            self.report_progress(1.0)
            return srt_path
            
        except Exception as e:
            print(f"❌ Whisper 자막 추출 실패: {e}")
            return None
            
    async def improve_subtitles_with_claude(self, srt_path: str, improvement_type: str = "grammar") -> str:
        """Claude를 사용해서 자막 개선 (현재는 비활성화)"""
        self.current_stage = "Claude 자막 개선"
        print(f"\n🤖 2단계: Claude로 자막 개선 ({improvement_type}) - 추후 추가 예정")
        
        # Claude API 연동 전까지는 원본 반환
        print("   ⚠️  Claude 기능은 추후 추가 예정입니다.")
        return srt_path
        
    def translate_srt(self, srt_path: str, source_lang: str = "auto", 
                     target_lang: str = "ko", translator: str = "google") -> str:
        """SRT 자막 번역"""
        self.current_stage = "자막 번역"
        print(f"\n🌐 3단계: 자막 번역 ({source_lang} → {target_lang})")
        
        if not GOOGLE_AVAILABLE and translator == "google":
            print("❌ Google Translate가 설치되지 않았습니다.")
            return srt_path
            
        try:
            # SRT 파일 파싱
            self.report_progress(0.1)
            subtitles = self.parse_srt_file(srt_path)
            
            if not subtitles:
                return srt_path
                
            # 번역 실행
            translator_service = GoogleTranslator()
            original_texts = [sub['text'] for sub in subtitles]
            
            print(f"   {len(original_texts)}개 자막 번역 중...")
            translated_texts = []
            
            for i, text in enumerate(original_texts):
                try:
                    progress = 0.1 + (0.8 * i / len(original_texts))
                    self.report_progress(progress)
                    print(f"   번역 중: {i+1}/{len(original_texts)} - {text[:30]}...")
                    result = translator_service.translate(text, src=source_lang, dest=target_lang)
                    translated_texts.append(result.text)
                    time.sleep(0.1)  # API 제한 방지
                except:
                    translated_texts.append(text)
                    
            # 번역 결과 적용
            for i, translated in enumerate(translated_texts):
                subtitles[i]['text'] = translated
                
            # 번역된 SRT 저장
            base_name = os.path.splitext(srt_path)[0]
            translated_srt_path = f"{base_name}_{target_lang}.srt"
            
            self.create_translated_srt(subtitles, translated_srt_path)
            
            self.report_progress(1.0)
            print(f"✅ 자막 번역 완료: {translated_srt_path}")
            return translated_srt_path
            
        except Exception as e:
            print(f"❌ 자막 번역 실패: {e}")
            return srt_path
            
    def parse_srt_file(self, srt_path: str) -> List[Dict]:
        """SRT 파일 파싱 (수정됨: 인코딩 명시)"""
        subtitles = []
        
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        blocks = re.split(r'\n\s*\n', content)
        
        for block in blocks:
            if not block.strip():
                continue
                
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
                
            try:
                index = int(lines[0])
            except ValueError:
                continue
                
            time_line = lines[1]
            time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', time_line)
            
            if time_match:
                start_time = time_match.group(1)
                end_time = time_match.group(2)
                text = '\n'.join(lines[2:]).strip()
                
                subtitles.append({
                    'index': index,
                    'start': start_time,
                    'end': end_time,
                    'text': text
                })
                
        return subtitles
        
    def create_translated_srt(self, subtitles: List[Dict], output_path: str):
        """번역된 자막을 SRT 파일로 저장 (수정됨: 인코딩 명시)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for subtitle in subtitles:
                f.write(f"{subtitle['index']}\n")
                f.write(f"{subtitle['start']} --> {subtitle['end']}\n")
                f.write(f"{subtitle['text']}\n\n")
                
    def embed_subtitles_to_video(self, video_path: str, srt_path: str, 
                               font_size: int = 24, font_color: str = 'white',
                               background_color: str = 'black@0.5', 
                               font_name: str = 'NanumGothic') -> str:
        """자막을 영상에 하드서브로 합성 (수정됨: 인코딩 처리 개선)"""
        self.current_stage = "하드서브 생성"
        print(f"\n📹 4단계: 자막을 영상에 합성")
        
        base_name = Path(video_path).stem
        safe_base_name = self.sanitize_filename(base_name)
        video_ext = Path(video_path).suffix
        output_dir = os.path.dirname(video_path)
        output_path = os.path.join(output_dir, f"{safe_base_name}_with_subtitles{video_ext}")
        
        try:
            self.report_progress(0.1)
            
            # Windows에서 경로 처리
            if os.name == 'nt':  # Windows
                srt_path_normalized = srt_path.replace('\\', '/')
                srt_path_normalized = srt_path_normalized.replace(':', '\\:')
            else:
                srt_path_normalized = srt_path
                
            # 색상 변환
            hex_color = self.color_to_hex(font_color)
            
            command = [
                'ffmpeg',
                '-i', video_path,
                '-vf', f"subtitles='{srt_path_normalized}':force_style='FontSize={font_size},PrimaryColour=&H{hex_color}&,OutlineColour=&H000000&,BorderStyle=1,Outline=2,Shadow=1,MarginV=20,FontName={font_name}'",
                '-c:a', 'copy',
                '-y',
                output_path
            ]
            
            print("   자막 합성 중...")
            print(f"   폰트: {font_name}, 크기: {font_size}, 색상: {font_color}")
            self.report_progress(0.5)
            
            # subprocess 실행 시 인코딩 명시
            result = subprocess.run(
                command, 
                check=True, 
                capture_output=True,
                encoding='utf-8',
                errors='replace'
            )
            
            self.report_progress(1.0)
            print(f"✅ 자막 합성 완료: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 자막 합성 실패: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                print(f"   STDERR: {e.stderr}")
            return video_path
            
    def color_to_hex(self, color: str) -> str:
        """색상을 hex로 변환 (BGR 형식으로)"""
        color_map = {
            'white': '00FFFFFF',
            'black': '00000000',
            'red': '000000FF',
            'green': '0000FF00',
            'blue': '00FF0000',
            'yellow': '0000FFFF',
            'cyan': '00FFFF00',
            'magenta': '00FF00FF',
            'black@0.5': '80000000'
        }
        return color_map.get(color.lower(), '00FFFFFF')
        
    async def create_voice_dubbing(self, srt_path: str, voice_type: str = 'auto') -> str:
        """자막 기반 음성 더빙 생성"""
        self.current_stage = "더빙 생성"
        print(f"\n🎤 5단계: 음성 더빙 생성 ({voice_type})")
        
        if not TTS_AVAILABLE:
            print("❌ TTS 라이브러리가 설치되지 않았습니다. (edge-tts, pydub)")
            return None
            
        try:
            self.report_progress(0.1)
            
            # SRT 파일 파싱
            subtitles = self.parse_srt_with_time(srt_path)
            
            if not subtitles:
                return None
                
            base_name = Path(srt_path).stem
            safe_base_name = self.sanitize_filename(base_name)
            output_dir = os.path.dirname(srt_path)
            audio_output_path = os.path.join(output_dir, f"{safe_base_name}_dubbed_audio.wav")
            
            # 전체 오디오 길이 계산
            total_duration = max(sub['end'] for sub in subtitles)
            silence = AudioSegment.silent(duration=int(total_duration * 1000))
            
            temp_dir = tempfile.mkdtemp()
            
            for i, subtitle in enumerate(subtitles):
                progress = 0.1 + (0.8 * i / len(subtitles))
                self.report_progress(progress)
                print(f"   음성 생성: {i+1}/{len(subtitles)} - {subtitle['text'][:30]}...")
                
                # 언어 감지
                language, gender = self.detect_language_and_gender(subtitle['text'])
                if voice_type != 'auto':
                    parts = voice_type.split('_')
                    language = parts[0]
                    gender = parts[1] if len(parts) > 1 else 'female'
                    
                # 음성 생성
                temp_audio_file = os.path.join(temp_dir, f"segment_{i}.wav")
                success = await self.generate_audio_segment(
                    subtitle['text'], language, gender, temp_audio_file
                )
                
                if success and os.path.exists(temp_audio_file):
                    segment_audio = AudioSegment.from_file(temp_audio_file)
                    start_ms = int(subtitle['start'] * 1000)
                    end_ms = int(subtitle['end'] * 1000)
                    available_duration = end_ms - start_ms
                    
                    if len(segment_audio) > available_duration:
                        segment_audio = segment_audio[:available_duration]
                        
                    silence = silence.overlay(segment_audio, position=start_ms)
                    
            # 최종 오디오 저장
            silence.export(audio_output_path, format="wav")
            
            # 임시 파일 정리
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            self.report_progress(1.0)
            print(f"✅ 더빙 오디오 생성 완료: {audio_output_path}")
            return audio_output_path
            
        except Exception as e:
            print(f"❌ 음성 더빙 생성 실패: {e}")
            return None
            
    def parse_srt_with_time(self, srt_path: str) -> List[Dict]:
        """시간 정보를 포함하여 SRT 파싱 (수정됨: 인코딩 명시)"""
        subtitles = []
        
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        blocks = re.split(r'\n\s*\n', content)
        
        for block in blocks:
            if not block.strip():
                continue
                
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
                
            time_line = lines[1]
            time_match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})', time_line)
            
            if time_match:
                start_h, start_m, start_s, start_ms = map(int, time_match.groups()[:4])
                end_h, end_m, end_s, end_ms = map(int, time_match.groups()[4:])
                
                start_time = start_h * 3600 + start_m * 60 + start_s + start_ms / 1000
                end_time = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000
                
                text = ' '.join(lines[2:]).strip()
                
                subtitles.append({
                    'start': start_time,
                    'end': end_time,
                    'text': text
                })
                
        return subtitles
        
    def detect_language_and_gender(self, text: str) -> tuple:
        """언어와 성별 감지"""
        if re.search(r'[가-힣]', text):
            return 'ko', 'female'
        else:
            return 'en', 'female'
            
    async def generate_audio_segment(self, text: str, language: str, gender: str, output_path: str) -> bool:
        """음성 세그먼트 생성"""
        voices = {
            'ko_female': 'ko-KR-SunHiNeural',
            'ko_male': 'ko-KR-InJoonNeural',
            'en_female': 'en-US-JennyNeural',
            'en_male': 'en-US-GuyNeural'
        }
        
        voice_key = f"{language}_{gender}"
        voice = voices.get(voice_key, voices['en_female'])
        
        try:
            temp_mp3_path = output_path.replace('.wav', '.mp3')
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(temp_mp3_path)
            
            if os.path.exists(temp_mp3_path):
                audio = AudioSegment.from_mp3(temp_mp3_path)
                audio.export(output_path, format="wav")
                os.remove(temp_mp3_path)
                return True
                
            return False
            
        except Exception as e:
            print(f"음성 생성 실패: {e}")
            return False
            
    def remove_original_audio(self, video_path: str) -> str:
        """영상에서 원본 오디오를 제거합니다 (수정됨: 인코딩 처리 개선)"""
        print(f"\n🔇 5-2단계: 원본 오디오 제거")
        print(f"   입력 파일: {video_path}")
        
        # 파일 존재 확인
        if not os.path.exists(video_path):
            print(f"❌ 입력 영상 파일이 없습니다: {video_path}")
            return None
            
        base_name = Path(video_path).stem
        safe_base_name = self.sanitize_filename(base_name)
        ext = Path(video_path).suffix
        output_dir = os.path.dirname(video_path)
        output_path = os.path.join(output_dir, f"{safe_base_name}_no_audio{ext}")
        
        print(f"   출력 파일: {output_path}")
        
        try:
            command = [
                'ffmpeg',
                '-i', video_path,
                '-an',          # 오디오 제거
                '-c:v', 'copy', # 비디오는 그대로 복사
                '-y',           # 덮어쓰기
                output_path
            ]
            
            print(f"   FFmpeg 명령어: {' '.join(command)}")
            print("   원본 오디오 제거 중...")
            
            # 실시간 로그로 진행 상황 확인 (수정됨: 인코딩 명시)
            result = subprocess.run(
                command, 
                check=False, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                if os.path.exists(output_path):
                    print(f"✅ 원본 오디오 제거 완료: {output_path}")
                    print(f"   파일 크기: {os.path.getsize(output_path)} bytes")
                    return output_path
                else:
                    print(f"❌ 출력 파일이 생성되지 않음: {output_path}")
                    return None
            else:
                print(f"❌ FFmpeg 실행 실패 (코드: {result.returncode})")
                print(f"   STDOUT: {result.stdout}")
                print(f"   STDERR: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"❌ 오디오 제거 중 예외 발생: {e}")
            return None
            
    def add_audio_to_video(self, video_path: str, audio_path: str) -> str:
        """무음 영상에 새로운 오디오를 추가합니다 (수정됨: 인코딩 처리 개선)"""
        print(f"\n🎬 5-3단계: 더빙 오디오를 무음 영상에 합성")
        print(f"   무음 영상: {video_path}")
        print(f"   더빙 오디오: {audio_path}")
        
        # 파일 존재 확인
        if not os.path.exists(video_path):
            print(f"❌ 무음 영상 파일이 없습니다: {video_path}")
            return None
            
        if not os.path.exists(audio_path):
            print(f"❌ 더빙 오디오 파일이 없습니다: {audio_path}")
            return None
            
        base_name = Path(video_path).stem.replace('_no_audio', '')
        safe_base_name = self.sanitize_filename(base_name)
        ext = Path(video_path).suffix
        output_dir = os.path.dirname(video_path)
        output_path = os.path.join(output_dir, f"{safe_base_name}_final_dubbed{ext}")
        
        print(f"   출력 파일: {output_path}")
        
        try:
            command = [
                'ffmpeg',
                '-i', video_path,   # 무음 영상
                '-i', audio_path,   # 더빙 오디오
                '-c:v', 'copy',     # 비디오는 그대로 복사
                '-c:a', 'aac',      # 오디오는 AAC로 인코딩
                '-shortest',        # 짧은 쪽에 맞춤
                '-y',              # 덮어쓰기
                output_path
            ]
            
            print(f"   FFmpeg 명령어: {' '.join(command)}")
            print("   더빙 오디오 합성 중...")
            
            # subprocess 실행 시 인코딩 명시
            result = subprocess.run(
                command, 
                check=False, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                if os.path.exists(output_path):
                    print(f"✅ 더빙 합성 완료: {output_path}")
                    print(f"   파일 크기: {os.path.getsize(output_path)} bytes")
                    return output_path
                else:
                    print(f"❌ 출력 파일이 생성되지 않음: {output_path}")
                    return None
            else:
                print(f"❌ FFmpeg 실행 실패 (코드: {result.returncode})")
                print(f"   STDOUT: {result.stdout}")
                print(f"   STDERR: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"❌ 오디오 합성 중 예외 발생: {e}")
            return None
            
    async def create_full_dubbing_process(self, video_path: str, srt_path: str, 
                                        voice_type: str = 'auto', 
                                        keep_temp_files: bool = False) -> str:
        """전체 더빙 프로세스"""
        print(f"\n🎤 5단계: 음성 더빙 생성 및 합성 시작")
        print(f"   입력 영상: {video_path}")
        print(f"   SRT 파일: {srt_path}")
        print(f"   음성 타입: {voice_type}")
        
        dubbed_audio = None
        no_audio_video = None
        final_video = None
        
        try:
            # 5-1. 더빙 오디오 생성
            print("\n🎤 5-1단계: 더빙 오디오 생성 시도...")
            try:
                dubbed_audio = await self.create_voice_dubbing(srt_path, voice_type)
                if dubbed_audio and os.path.exists(dubbed_audio):
                    print(f"✅ 5-1단계 성공: {dubbed_audio}")
                    print(f"   파일 크기: {os.path.getsize(dubbed_audio)} bytes")
                else:
                    print("❌ 5-1단계 실패: 더빙 오디오 생성 실패")
                    dubbed_audio = None
            except Exception as e:
                print(f"❌ 5-1단계 예외: {e}")
                dubbed_audio = None
                
            # 5-2. 원본 영상에서 오디오 제거
            print("\n🔇 5-2단계: 원본 오디오 제거 (항상 실행)")
            try:
                no_audio_video = self.remove_original_audio(video_path)
                if no_audio_video and os.path.exists(no_audio_video):
                    print(f"✅ 5-2단계 성공: {no_audio_video}")
                    print(f"   파일 크기: {os.path.getsize(no_audio_video)} bytes")
                else:
                    print("❌ 5-2단계 실패: 원본 오디오 제거 실패")
                    return None
            except Exception as e:
                print(f"❌ 5-2단계 예외: {e}")
                return None
                
            # 5-3. 무음 영상에 새 오디오 추가
            if dubbed_audio and no_audio_video:
                print("\n🎬 5-3단계: 더빙 오디오 합성")
                try:
                    final_video = self.add_audio_to_video(no_audio_video, dubbed_audio)
                    if final_video and os.path.exists(final_video):
                        print(f"✅ 5-3단계 성공: {final_video}")
                        print(f"   파일 크기: {os.path.getsize(final_video)} bytes")
                    else:
                        print("❌ 5-3단계 실패: 더빙 오디오 합성 실패")
                        final_video = no_audio_video
                except Exception as e:
                    print(f"❌ 5-3단계 예외: {e}")
                    final_video = no_audio_video
            else:
                print("\n⏭️  5-3단계 건너뜀: 더빙 오디오가 없음")
                final_video = no_audio_video
                
            # 5-4. 임시 파일 정리
            print("\n🧹 5-4단계: 임시 파일 정리")
            if not keep_temp_files:
                files_to_delete = []
                if no_audio_video and final_video != no_audio_video:
                    files_to_delete.append(no_audio_video)
                if dubbed_audio and not keep_temp_files:
                    files_to_delete.append(dubbed_audio)
                    
                for file_path in files_to_delete:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            print(f"   삭제: {file_path}")
                        except:
                            print(f"   삭제 실패: {file_path}")
            else:
                print("   임시 파일 보관됨")
                
            # 결과 요약
            print("\n🎉 더빙 프로세스 완료!")
            print("   ✅ 5-1단계: 더빙 오디오 생성", "완료" if dubbed_audio else "실패")
            print("   ✅ 5-2단계: 원본 오디오 제거", "완료" if no_audio_video else "실패")
            print("   ✅ 5-3단계: 더빙 오디오 합성", "완료" if (final_video and dubbed_audio) else "건너뜀")
            print("   ✅ 5-4단계: 임시 파일 정리 완료")
            print(f"🎬 최종 결과: {final_video}")
            
            return final_video
            
        except Exception as e:
            print(f"❌ 더빙 프로세스 중 예상치 못한 예외: {e}")
            import traceback
            traceback.print_exc()
            
            # 부분적으로라도 성공한 파일 반환
            if final_video:
                return final_video
            elif no_audio_video:
                return no_audio_video
            else:
                return None
                
    async def process_video_complete(self, video_path: str, config: dict) -> dict:
        """전체 비디오 처리 프로세스"""
        print("=" * 60)
        print("🚀 통합 영상 처리 시스템 시작")
        print("=" * 60)
        print(f"입력 영상: {video_path}")
        print(f"설정: {json.dumps(config, ensure_ascii=False, indent=2)}")
        print()
        
        results = {
            "input_video": video_path,
            "whisper_srt": None,
            "improved_srt": None,
            "translated_srt": None,
            "hardsub_video": None,
            "dubbed_audio": None,
            "final_video": None,
            "config": config
        }
        
        try:
            # 1. Whisper 자막 추출
            print(f"\n🔍 DEBUG: extract_subtitles = {config.get('extract_subtitles')}")
            print(f"🔍 DEBUG: existing_srt = {config.get('existing_srt')}")
            print(f"🔍 DEBUG: use_chunked_processing = {config.get('use_chunked_processing')}")
            
            if config.get("extract_subtitles", True):
                print("📍 1단계: Whisper 자막 추출 실행")
                
                # 분할 처리 옵션 확인
                if config.get("use_chunked_processing", False):
                    print("   🔄 분할 처리 모드로 자막 추출")
                    whisper_srt = self.extract_subtitles_with_chunks(
                        video_path,
                        config.get("whisper_model", "medium"),
                        config.get("whisper_language", "auto"),
                        config.get("chunk_duration", 10)
                    )
                else:
                    print("   📄 일반 모드로 자막 추출")
                    whisper_srt = self.extract_subtitles_with_whisper(
                        video_path,
                        config.get("whisper_model", "medium"),
                        config.get("whisper_language", "auto")
                    )
                    
                results["whisper_srt"] = whisper_srt
                
                if not whisper_srt:
                    print("❌ Whisper 자막 추출 실패. 프로세스 중단.")
                    return results
                    
                current_srt = whisper_srt
            else:
                print("📍 1단계: 기존 SRT 파일 사용")
                current_srt = config.get("existing_srt")
                if not current_srt or not os.path.exists(current_srt):
                    print("❌ 기존 SRT 파일이 없습니다.")
                    return results
                print(f"✅ 기존 SRT 파일 확인: {current_srt}")
                
            # 2. Claude 자막 개선
            print(f"\n🔍 DEBUG: improve_with_claude = {config.get('improve_with_claude')}")
            if config.get("improve_with_claude", False):
                print("📍 2단계: Claude 자막 개선 실행")
                improved_srt = await self.improve_subtitles_with_claude(
                    current_srt,
                    config.get("improvement_type", "grammar")
                )
                results["improved_srt"] = improved_srt
                current_srt = improved_srt
            else:
                print("📍 2단계: Claude 자막 개선 건너뜀")
                
            # 3. 자막 번역
            print(f"\n🔍 DEBUG: translate_subtitles = {config.get('translate_subtitles')}")
            if config.get("translate_subtitles", False):
                print("📍 3단계: 자막 번역 실행")
                translated_srt = self.translate_srt(
                    current_srt,
                    config.get("source_language", "auto"),
                    config.get("target_language", "ko"),
                    config.get("translator", "google")
                )
                results["translated_srt"] = translated_srt
                current_srt = translated_srt
            else:
                print("📍 3단계: 자막 번역 건너뜀")
                
            print(f"\n🔍 DEBUG: 현재 사용할 SRT = {current_srt}")
            
            # 4. 하드서브 영상 생성
            current_video = video_path
            print(f"\n🔍 DEBUG: embed_subtitles = {config.get('embed_subtitles')}")
            if config.get("embed_subtitles", False):
                print("📍 4단계: 하드서브 영상 생성 실행")
                hardsub_video = self.embed_subtitles_to_video(
                    video_path,
                    current_srt,
                    config.get("font_size", 24),
                    config.get("font_color", "white"),
                    config.get("background_color", "black@0.5"),
                    config.get("font_name", "NanumGothic")
                )
                results["hardsub_video"] = hardsub_video
                current_video = hardsub_video
                print(f"✅ 하드서브 영상 생성 완료: {current_video}")
            else:
                print("📍 4단계: 하드서브 영상 생성 건너뜀")
                
            print(f"\n🔍 DEBUG: 현재 사용할 영상 = {current_video}")
            
            # 5. 음성 더빙 생성 및 합성
            print(f"\n🔍 DEBUG: create_dubbing = {config.get('create_dubbing')}")
            if config.get("create_dubbing", False):
                print("📍 5단계: 더빙 프로세스 실행 시작")
                print(f"   입력 영상: {current_video}")
                print(f"   입력 SRT: {current_srt}")
                print(f"   음성 타입: {config.get('voice_type', 'auto')}")
                
                try:
                    final_video = await self.create_full_dubbing_process(
                        current_video,
                        current_srt,
                        config.get("voice_type", "auto"),
                        config.get("keep_temp_files", False)
                    )
                    
                    if final_video:
                        results["final_video"] = final_video
                        print(f"✅ 더빙 프로세스 성공: {final_video}")
                    else:
                        print("❌ 더빙 프로세스 실패 - None 반환")
                        
                except Exception as e:
                    print(f"❌ 더빙 프로세스 중 예외 발생: {e}")
                    import traceback
                    traceback.print_exc()
                    
            else:
                print("📍 5단계: 더빙 프로세스 건너뜀")
                # 더빙 없이 하드서브만 생성한 경우 final_video 설정
                if config.get("embed_subtitles", False):
                    results["final_video"] = current_video
                    
            print("\n" + "="*60)
            print("🎉 전체 처리 완료!")
            print("="*60)
            
            # 결과 요약
            print("📋 처리 결과:")
            for key, value in results.items():
                if value and key != "config":
                    print(f"   {key}: {value}")
                    
            return results
            
        except Exception as e:
            print(f"❌ 전체 처리 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return results
            
        finally:
            # 임시 파일 정리
            if not config.get("keep_temp_files", False):
                self.cleanup_temp_files()

def main():
    """명령줄 인터페이스"""
    parser = argparse.ArgumentParser(description='통합 영상 처리 시스템')
    parser.add_argument('video_path', help='입력 영상 파일 경로')
    
    # Whisper 설정
    parser.add_argument('--whisper-model', default='medium',
                       choices=['tiny', 'base', 'small', 'medium', 'large'],
                       help='Whisper 모델 크기')
    parser.add_argument('--whisper-language', default='auto',
                       help='Whisper 언어 설정')
    
    # 처리 옵션
    parser.add_argument('--extract-subtitles', action='store_true', default=True,
                       help='Whisper로 자막 추출')
    parser.add_argument('--existing-srt', help='기존 SRT 파일 사용')
    parser.add_argument('--use-chunked-processing', action='store_true',
                       help='긴 영상 분할 처리')
    parser.add_argument('--chunk-duration', type=int, default=10,
                       help='분할 길이 (분 단위)')
    parser.add_argument('--improve-claude', action='store_true',
                       help='Claude로 자막 개선')
    parser.add_argument('--improvement-type', default='grammar',
                       choices=['grammar', 'translation', 'summary'],
                       help='개선 타입')
    parser.add_argument('--translate', action='store_true',
                       help='자막 번역')
    parser.add_argument('--target-language', default='ko',
                       help='번역 대상 언어')
    parser.add_argument('--embed-subtitles', action='store_true',
                       help='자막을 영상에 합성')
    parser.add_argument('--create-dubbing', action='store_true',
                       help='음성 더빙 생성')
    parser.add_argument('--voice-type', default='auto',
                       help='음성 타입')
    
    # 자막 스타일
    parser.add_argument('--font-size', type=int, default=24,
                       help='폰트 크기')
    parser.add_argument('--font-color', default='white',
                       help='폰트 색상')
    parser.add_argument('--background-color', default='black@0.5',
                       help='배경 색상')
    parser.add_argument('--font-name', default='NanumGothic',
                       help='폰트 이름')
    
    # 기타
    parser.add_argument('--keep-temp', action='store_true',
                       help='임시 파일 보관')
    
    args = parser.parse_args()
    
    # 설정 구성
    config = {
        "extract_subtitles": args.extract_subtitles and not args.existing_srt,
        "existing_srt": args.existing_srt,
        "use_chunked_processing": args.use_chunked_processing,
        "chunk_duration": args.chunk_duration,
        "whisper_model": args.whisper_model,
        "whisper_language": args.whisper_language,
        "improve_with_claude": args.improve_claude,
        "improvement_type": args.improvement_type,
        "translate_subtitles": args.translate,
        "target_language": args.target_language,
        "embed_subtitles": args.embed_subtitles,
        "create_dubbing": args.create_dubbing,
        "voice_type": args.voice_type,
        "font_size": args.font_size,
        "font_color": args.font_color,
        "background_color": args.background_color,
        "font_name": args.font_name,
        "keep_temp_files": args.keep_temp
    }
    
    # 처리 실행
    processor = IntegratedVideoProcessor()
    results = asyncio.run(processor.process_video_complete(args.video_path, config))
    
    # 결과 출력
    print(f"\n최종 결과: {json.dumps(results, ensure_ascii=False, indent=2)}")

if __name__ == "__main__":
    main()
