import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import asyncio
import threading
import json
import os
from pathlib import Path
import queue
from datetime import datetime
import sys
import io
import subprocess
import re

# 기존 whis.py의 IntegratedVideoProcessor import
from whis import IntegratedVideoProcessor

# 폰트 선택기 import
from font_selector import FontSelector

# 다크 모드 설정
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SafeIntVar(tk.IntVar):
    """안전한 IntVar 클래스 - 빈 문자열 처리"""
    def __init__(self, master=None, value=None, name=None):
        self._default_value = value if value is not None else 0
        super().__init__(master, value, name)
        
    def get(self):
        try:
            value = super().get()
            return value if value is not None else self._default_value
        except (tk.TclError, ValueError):
            return self._default_value
            
    def set(self, value):
        try:
            if value is None or value == "":
                super().set(self._default_value)
            else:
                super().set(int(value))
        except (tk.TclError, ValueError):
            super().set(self._default_value)

class SafeDoubleVar(tk.DoubleVar):
    """안전한 DoubleVar 클래스 - 빈 문자열 처리"""
    def __init__(self, master=None, value=None, name=None):
        self._default_value = value if value is not None else 0.0
        super().__init__(master, value, name)
        
    def get(self):
        try:
            value = super().get()
            return value if value is not None else self._default_value
        except (tk.TclError, ValueError):
            return self._default_value
            
    def set(self, value):
        try:
            if value is None or value == "":
                super().set(self._default_value)
            else:
                super().set(float(value))
        except (tk.TclError, ValueError):
            super().set(self._default_value)

class OutputRedirector:
    """print 출력을 GUI 로그로 리다이렉트"""
    def __init__(self, log_queue):
        self.log_queue = log_queue
        
    def write(self, text):
        if text.strip():  # 빈 줄 제외
            self.log_queue.put(text.strip())
            
    def flush(self):
        pass

class VideoProcessorGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("통합 영상 처리 시스템 v2.1")
        self.root.geometry("1200x800")
        
        # 처리기 인스턴스
        self.processor = IntegratedVideoProcessor()
        
        # 상태 변수들
        self.video_path = tk.StringVar()
        self.srt_path = tk.StringVar()
        self.processing = False
        self.log_queue = queue.Queue()
        
        # 처리 옵션 변수들
        self.extract_subtitles = tk.BooleanVar(value=True)
        self.use_existing_srt = tk.BooleanVar(value=False)
        self.use_chunked_processing = tk.BooleanVar(value=False)
        self.improve_claude = tk.BooleanVar(value=False)
        self.translate_subtitles = tk.BooleanVar(value=False)
        self.embed_subtitles = tk.BooleanVar(value=True)
        self.create_dubbing = tk.BooleanVar(value=False)
        self.keep_temp_files = tk.BooleanVar(value=False)
        
        # 설정 변수들 - 안전한 변수 클래스 사용
        self.whisper_model = tk.StringVar(value="medium")
        self.whisper_language = tk.StringVar(value="auto")
        self.chunk_duration = SafeIntVar(value=10)
        self.improvement_type = tk.StringVar(value="grammar")
        self.source_language = tk.StringVar(value="auto")
        self.target_language = tk.StringVar(value="ko")
        self.voice_type = tk.StringVar(value="auto")
        self.font_color = tk.StringVar(value="white")
        
        # 폰트 선택 관련 변수 - 안전한 변수 클래스 사용
        initial_font_size = 24
        self.font_size = SafeIntVar(value=initial_font_size)
        self.selected_font_name = tk.StringVar(value="NanumGothic")
        self.selected_font_size = SafeIntVar(value=initial_font_size)
        
        # 결과 저장용
        self.processing_results = {}
        
        # 진행률 추적
        self.current_stage = 0
        self.total_stages = 0
        
        # subprocess 관련 추가
        self.current_process = None
        
        self.setup_ui()
        self.start_log_updater()
        
    def setup_validation(self):
        """입력 검증 설정 - 더 안전한 방식"""
        def safe_validate_int(var, default_value):
            def validate(*args):
                try:
                    current_value = var.get()
                    # 현재 값이 유효한지 확인
                    if isinstance(current_value, int) and current_value > 0:
                        return
                except:
                    pass
                # 문제가 있으면 기본값으로 설정
                try:
                    var.set(default_value)
                except:
                    pass
            return validate
        
        # 안전한 검증 추가
        self.chunk_duration.trace_add("write", safe_validate_int(self.chunk_duration, 10))
        self.font_size.trace_add("write", safe_validate_int(self.font_size, 24))
        self.selected_font_size.trace_add("write", safe_validate_int(self.selected_font_size, 24))
        
    def check_special_chars(self, filename: str) -> bool:
        """파일명에 문제가 될 수 있는 특수문자가 있는지 확인"""
        # ffmpeg에서 문제가 되는 특수문자들
        problematic_chars = ['[', ']', '(', ')', "'", '"', '&', '$', '!', '`', ';', '|', '*', '?', '<', '>']
        
        base_name = os.path.basename(filename)
        for char in problematic_chars:
            if char in base_name:
                return True
        return False
        
    def warn_special_chars(self, filename: str, file_type: str = "영상"):
        """특수문자 경고 메시지 표시"""
        if self.check_special_chars(filename):
            base_name = os.path.basename(filename)
            self.log(f"⚠️ 경고: {file_type} 파일명에 특수문자가 포함되어 있습니다: {base_name}")
            self.log("   ffmpeg 처리 시 문제가 발생할 수 있으므로 자동으로 안전한 파일명으로 변환됩니다.")
            self.log("   원본 파일은 변경되지 않으며, 생성되는 파일만 안전한 이름을 사용합니다.")
            
            # 사용자에게 확인 받기
            response = messagebox.askquestion(
                "특수문자 감지",
                f"{file_type} 파일명에 특수문자가 포함되어 있습니다.\n\n"
                f"파일명: {base_name}\n\n"
                "처리 중 자동으로 안전한 파일명으로 변환됩니다.\n"
                "계속 진행하시겠습니까?",
                icon='warning'
            )
            return response == 'yes'
        return True
        
    def setup_ui(self):
        """UI 구성"""
        # 메인 컨테이너
        main_container = ctk.CTkFrame(self.root)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 좌측: 입력 및 옵션
        left_frame = ctk.CTkFrame(main_container)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # 우측: 로그 및 결과
        right_frame = ctk.CTkFrame(main_container)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        # === 좌측 패널 구성 ===
        self.setup_input_section(left_frame)
        self.setup_options_section(left_frame)
        self.setup_control_buttons(left_frame)
        
        # === 우측 패널 구성 ===
        self.setup_log_section(right_frame)
        self.setup_results_section(right_frame)
        
        # 검증 설정
        self.setup_validation()
        
    def setup_input_section(self, parent):
        """입력 파일 선택 섹션"""
        input_frame = ctk.CTkFrame(parent)
        input_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(input_frame, text="📁 입력 파일", 
                    font=("Arial", 16, "bold")).pack(anchor="w", pady=(5, 10))
        
        # 영상 파일 선택
        video_frame = ctk.CTkFrame(input_frame)
        video_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(video_frame, text="영상 파일:").pack(side="left", padx=(10, 5))
        ctk.CTkEntry(video_frame, textvariable=self.video_path, width=300).pack(side="left", padx=5)
        ctk.CTkButton(video_frame, text="찾아보기", 
                     command=self.browse_video, width=80).pack(side="left")
        
        # SRT 파일 선택 (옵션)
        srt_frame = ctk.CTkFrame(input_frame)
        srt_frame.pack(fill="x", pady=5)
        
        ctk.CTkCheckBox(srt_frame, text="기존 자막 사용", 
                       variable=self.use_existing_srt,
                       command=self.toggle_srt_input).pack(side="left", padx=(10, 5))
        
        self.srt_entry = ctk.CTkEntry(srt_frame, textvariable=self.srt_path, 
                                     width=220, state="disabled")
        self.srt_entry.pack(side="left", padx=5)
        
        self.srt_button = ctk.CTkButton(srt_frame, text="찾아보기", 
                                       command=self.browse_srt, width=80, state="disabled")
        self.srt_button.pack(side="left")
        
    def create_safe_entry(self, parent, textvariable, **kwargs):
        """안전한 Entry 위젯 생성"""
        def on_focus_out(event):
            try:
                current_value = event.widget.get()
                if current_value == "":
                    if isinstance(textvariable, (SafeIntVar, SafeDoubleVar)):
                        textvariable.set(textvariable._default_value)
                    event.widget.delete(0, tk.END)
                    event.widget.insert(0, str(textvariable.get()))
            except:
                pass
                
        entry = ctk.CTkEntry(parent, textvariable=textvariable, **kwargs)
        entry.bind("<FocusOut>", on_focus_out)
        return entry
        
    def setup_options_section(self, parent):
        """처리 옵션 섹션"""
        options_frame = ctk.CTkFrame(parent)
        options_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(options_frame, text="⚙️ 처리 옵션", 
                    font=("Arial", 16, "bold")).pack(anchor="w", pady=(5, 10))
        
        # 스크롤 가능한 옵션 영역
        scroll_frame = ctk.CTkScrollableFrame(options_frame, height=400)
        scroll_frame.pack(fill="both", expand=True)
        
        # 1. Whisper 옵션
        whisper_frame = ctk.CTkFrame(scroll_frame)
        whisper_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(whisper_frame, text="🎤 Whisper 설정", 
                    font=("Arial", 14, "bold")).pack(anchor="w", pady=5)
        
        ctk.CTkCheckBox(whisper_frame, text="자막 추출", 
                       variable=self.extract_subtitles).pack(anchor="w", padx=20)
        
        # 긴 영상 분할 처리 옵션 추가
        chunked_frame = ctk.CTkFrame(whisper_frame)
        chunked_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkCheckBox(chunked_frame, text="긴 영상 분할 처리 (1시간+ 영상 권장)", 
                       variable=self.use_chunked_processing,
                       command=self.toggle_chunked_processing).pack(anchor="w")
        
        # 분할 길이 설정 - 안전한 Entry 사용
        chunk_duration_frame = ctk.CTkFrame(whisper_frame)
        chunk_duration_frame.pack(fill="x", padx=40, pady=5)
        
        ctk.CTkLabel(chunk_duration_frame, text="분할 길이 (분):").pack(side="left", padx=(0, 10))
        self.chunk_duration_entry = self.create_safe_entry(chunk_duration_frame, 
                                                          textvariable=self.chunk_duration, 
                                                          width=60, state="disabled")
        self.chunk_duration_entry.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(chunk_duration_frame, text="(기본값: 10분, 권장: 5-15분)", 
                    text_color="gray", font=("Arial", 10)).pack(side="left")
        
        model_frame = ctk.CTkFrame(whisper_frame)
        model_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(model_frame, text="모델 크기:").pack(side="left", padx=(0, 10))
        ctk.CTkOptionMenu(model_frame, 
                         values=["tiny", "base", "small", "medium", "large"],
                         variable=self.whisper_model, width=120).pack(side="left")
        
        lang_frame = ctk.CTkFrame(whisper_frame)
        lang_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(lang_frame, text="언어:").pack(side="left", padx=(0, 10))
        
        # 다양한 언어 옵션 제공
        whisper_languages = [
            "auto", "ko", "en", "ja", "zh", "es", "fr", "de", 
            "ru", "ar", "hi", "pt", "it", "tr", "vi", "th"
        ]
        ctk.CTkOptionMenu(lang_frame,
                         values=whisper_languages,
                         variable=self.whisper_language, width=120).pack(side="left")
        
        # 2. Claude 개선 옵션 (추후 추가 예정 표시)
        claude_frame = ctk.CTkFrame(scroll_frame)
        claude_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(claude_frame, text="🤖 Claude 개선 (추후 추가 예정)", 
                    font=("Arial", 14, "bold"), text_color="gray").pack(anchor="w", pady=5)
        
        ctk.CTkCheckBox(claude_frame, text="자막 개선", 
                       variable=self.improve_claude, state="disabled").pack(anchor="w", padx=20)
        
        improve_frame = ctk.CTkFrame(claude_frame)
        improve_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(improve_frame, text="개선 타입:", text_color="gray").pack(side="left", padx=(0, 10))
        ctk.CTkOptionMenu(improve_frame, 
                         values=["grammar", "translation", "summary"],
                         variable=self.improvement_type, width=120, state="disabled").pack(side="left")
        
        # 3. 번역 옵션
        translate_frame = ctk.CTkFrame(scroll_frame)
        translate_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(translate_frame, text="🌐 번역 설정", 
                    font=("Arial", 14, "bold")).pack(anchor="w", pady=5)
        
        ctk.CTkCheckBox(translate_frame, text="자막 번역", 
                       variable=self.translate_subtitles).pack(anchor="w", padx=20)
        
        trans_lang_frame = ctk.CTkFrame(translate_frame)
        trans_lang_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(trans_lang_frame, text="원본 언어:").pack(side="left", padx=(0, 10))
        ctk.CTkEntry(trans_lang_frame, textvariable=self.source_language, 
                    width=80).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(trans_lang_frame, text="대상 언어:").pack(side="left", padx=(0, 10))
        
        # 번역 대상 언어 리스트
        target_languages = [
            ("한국어", "ko"),
            ("영어", "en"),
            ("일본어", "ja"),
            ("중국어(간체)", "zh-cn"),
            ("중국어(번체)", "zh-tw"),
            ("스페인어", "es"),
            ("프랑스어", "fr"),
            ("독일어", "de"),
            ("러시아어", "ru"),
            ("아랍어", "ar"),
            ("힌디어", "hi"),
            ("포르투갈어", "pt"),
            ("이탈리아어", "it"),
            ("터키어", "tr"),
            ("베트남어", "vi"),
            ("태국어", "th"),
            ("인도네시아어", "id"),
            ("말레이어", "ms")
        ]
        
        target_lang_values = [f"{name} ({code})" for name, code in target_languages]
        self.target_lang_menu = ctk.CTkOptionMenu(trans_lang_frame,
                                                 values=target_lang_values,
                                                 width=150,
                                                 command=self.on_target_language_change)
        self.target_lang_menu.pack(side="left")
        self.target_lang_menu.set("한국어 (ko)")
        
        # Claude 번역 프롬프트 추천 버튼
        claude_prompt_frame = ctk.CTkFrame(translate_frame)
        claude_prompt_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(claude_prompt_frame, text="🤖 Claude 번역 프롬프트 추천", 
                     command=self.show_claude_translation_prompt,
                     width=200, height=30).pack(side="left")
        
        # 4. 하드서브 옵션
        hardsub_frame = ctk.CTkFrame(scroll_frame)
        hardsub_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(hardsub_frame, text="📹 하드서브 설정", 
                    font=("Arial", 14, "bold")).pack(anchor="w", pady=5)
        
        ctk.CTkCheckBox(hardsub_frame, text="자막 영상에 합성", 
                       variable=self.embed_subtitles).pack(anchor="w", padx=20)
        
        # 폰트 선택 프레임
        font_selection_frame = ctk.CTkFrame(hardsub_frame)
        font_selection_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(font_selection_frame, text="폰트 선택:").pack(side="left", padx=(0, 10))
        
        # 선택된 폰트 표시 라벨
        self.font_display_label = ctk.CTkLabel(font_selection_frame, 
                                              text=f"{self.selected_font_name.get()} ({self.selected_font_size.get()}pt)",
                                              fg_color="gray20", corner_radius=5, width=200)
        self.font_display_label.pack(side="left", padx=(0, 10))
        
        # 폰트 선택 버튼
        ctk.CTkButton(font_selection_frame, text="🎨 폰트 선택", 
                     command=self.open_font_selector, width=100).pack(side="left", padx=(0, 10))
        
        # 기존 폰트 크기 및 색상 설정 - 안전한 Entry 사용
        font_frame = ctk.CTkFrame(hardsub_frame)
        font_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(font_frame, text="폰트 크기:").pack(side="left", padx=(0, 10))
        self.font_size_entry = self.create_safe_entry(font_frame, textvariable=self.font_size, 
                                                     width=60)
        self.font_size_entry.pack(side="left", padx=(0, 20))
        
        # 폰트 크기 변경 시 선택된 폰트 크기도 업데이트
        def on_font_size_change(*args):
            try:
                new_size = self.font_size.get()
                if new_size != self.selected_font_size.get():
                    self.selected_font_size.set(new_size)
                    self.update_font_display()
                    self.log(f"폰트 크기가 {new_size}pt로 변경되었습니다.")
            except:
                pass
        
        self.font_size.trace_add('write', on_font_size_change)
        
        ctk.CTkLabel(font_frame, text="폰트 색상:").pack(side="left", padx=(0, 10))
        
        # 폰트 색상 리스트
        font_colors = ["white", "yellow", "red", "green", "blue", "cyan", "magenta", "black"]
        ctk.CTkOptionMenu(font_frame,
                         values=font_colors,
                         variable=self.font_color, width=100).pack(side="left")
        
        # 5. 더빙 옵션
        dubbing_frame = ctk.CTkFrame(scroll_frame)
        dubbing_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(dubbing_frame, text="🎵 더빙 설정", 
                    font=("Arial", 14, "bold")).pack(anchor="w", pady=5)
        
        ctk.CTkCheckBox(dubbing_frame, text="음성 더빙 생성", 
                       variable=self.create_dubbing).pack(anchor="w", padx=20)
        
        voice_frame = ctk.CTkFrame(dubbing_frame)
        voice_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(voice_frame, text="음성 타입:").pack(side="left", padx=(0, 10))
        ctk.CTkOptionMenu(voice_frame, 
                         values=["auto", "ko_female", "ko_male", "en_female", "en_male"],
                         variable=self.voice_type, width=120).pack(side="left")
        
        # 6. 기타 옵션
        misc_frame = ctk.CTkFrame(scroll_frame)
        misc_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(misc_frame, text="🔧 기타 설정", 
                    font=("Arial", 14, "bold")).pack(anchor="w", pady=5)
        
        ctk.CTkCheckBox(misc_frame, text="임시 파일 보관", 
                       variable=self.keep_temp_files).pack(anchor="w", padx=20)
        
    def open_font_selector(self):
        """폰트 선택기 열기"""
        try:
            # 새 창 생성
            font_window = tk.Toplevel(self.root)
            font_window.transient(self.root)
            font_window.grab_set()
            
            # 폰트 선택기 인스턴스 생성
            font_selector = FontSelector(font_window)
            
            # 현재 선택된 폰트로 초기화
            current_font = self.selected_font_name.get()
            current_size = self.selected_font_size.get()
            
            # 폰트 선택기에 현재 폰트 설정
            font_selector.selected_font = current_font
            font_selector.size_var.set(current_size)
            
            # 리스트박스에서 해당 폰트 찾아서 선택
            try:
                for i in range(font_selector.font_listbox.size()):
                    item = font_selector.font_listbox.get(i)
                    if item == current_font or item == f"★ {current_font}":
                        font_selector.font_listbox.selection_set(i)
                        font_selector.font_listbox.see(i)
                        break
            except:
                pass
                
            # 미리보기 업데이트
            if hasattr(font_selector, 'update_preview'):
                font_selector.update_preview()
            
            # 폰트 선택기의 버튼들을 찾아서 기능 수정
            def find_and_modify_select_button(widget):
                """선택 버튼을 찾아서 기능 수정"""
                try:
                    # 버튼인지 확인하고 텍스트가 "선택"인지 확인
                    if hasattr(widget, 'cget') and hasattr(widget, 'configure'):
                        try:
                            if widget.cget('text') == '선택':
                                # 새로운 선택 함수 정의
                                def new_select_command():
                                    if font_selector.selected_font:
                                        # 폰트 정보 가져오기
                                        new_font_name = font_selector.selected_font
                                        new_font_size = font_selector.size_var.get()
                                        
                                        # 메인 인터페이스의 모든 관련 변수 업데이트
                                        self.selected_font_name.set(new_font_name)
                                        self.selected_font_size.set(new_font_size)
                                        self.font_size.set(new_font_size)
                                        
                                        # 폰트 크기 입력 필드도 직접 업데이트
                                        try:
                                            self.font_size_entry.delete(0, tk.END)
                                            self.font_size_entry.insert(0, str(new_font_size))
                                        except:
                                            pass
                                        
                                        # 디스플레이 업데이트
                                        self.update_font_display()
                                        
                                        # 로그 메시지
                                        self.log(f"✅ 폰트 선택 완료: {new_font_name} ({new_font_size}pt)")
                                        self.log(f"   하드서브 설정에 반영되었습니다.")
                                        
                                        # 성공 메시지 표시
                                        messagebox.showinfo("선택 완료", 
                                                          f"폰트: {new_font_name}\n크기: {new_font_size}pt\n\n하드서브 설정에 반영되었습니다.")
                                        
                                        # 창 닫기
                                        font_window.destroy()
                                    else:
                                        messagebox.showwarning("경고", "폰트를 선택해주세요.")
                                
                                # 버튼 command 변경
                                widget.configure(command=new_select_command)
                                return True
                        except:
                            pass
                except:
                    pass
                
                # 하위 위젯들도 검사
                for child in widget.winfo_children():
                    if find_and_modify_select_button(child):
                        return True
                
                return False
            
            # 취소 버튼 기능도 수정
            def find_and_modify_cancel_button(widget):
                """취소 버튼을 찾아서 기능 수정"""
                try:
                    if hasattr(widget, 'cget') and hasattr(widget, 'configure'):
                        try:
                            if widget.cget('text') == '취소':
                                widget.configure(command=font_window.destroy)
                                return True
                        except:
                            pass
                except:
                    pass
                
                for child in widget.winfo_children():
                    if find_and_modify_cancel_button(child):
                        return True
                
                return False
            
            # 약간의 지연 후 버튼 수정 (UI가 완전히 로드된 후)
            def modify_buttons_delayed():
                find_and_modify_select_button(font_window)
                find_and_modify_cancel_button(font_window)
            
            font_window.after(100, modify_buttons_delayed)
            
            # 창이 닫힐 때 현재 값 확인 (백업용)
            def on_window_close():
                try:
                    # 폰트 선택기에서 현재 값 읽기
                    if hasattr(font_selector, 'selected_font') and font_selector.selected_font:
                        self.selected_font_name.set(font_selector.selected_font)
                    if hasattr(font_selector, 'size_var'):
                        size_value = font_selector.size_var.get()
                        self.selected_font_size.set(size_value)
                        self.font_size.set(size_value)
                    
                    self.update_font_display()
                except:
                    pass
                finally:
                    font_window.destroy()
            
            font_window.protocol("WM_DELETE_WINDOW", on_window_close)
            
        except Exception as e:
            self.log(f"❌ 폰트 선택기 오류: {e}")
            messagebox.showerror("오류", f"폰트 선택기를 열 수 없습니다: {e}")
            
    def sync_font_settings(self):
        """폰트 설정 동기화"""
        # 선택된 폰트 정보를 하드서브 설정에 반영
        self.font_size.set(self.selected_font_size.get())
        self.update_font_display()
        
    def update_font_display(self):
        """폰트 표시 라벨 업데이트"""
        try:
            display_text = f"{self.selected_font_name.get()} ({self.selected_font_size.get()}pt)"
            self.font_display_label.configure(text=display_text)
        except:
            pass
        
    def toggle_chunked_processing(self):
        """분할 처리 옵션 활성화/비활성화"""
        if self.use_chunked_processing.get():
            self.chunk_duration_entry.configure(state="normal")
            self.log("📄 긴 영상 분할 처리가 활성화되었습니다.")
            self.log("   1시간 이상의 긴 영상에서 Whisper 반복 문제를 해결합니다.")
        else:
            self.chunk_duration_entry.configure(state="disabled")
            self.log("📄 일반 처리 모드로 설정되었습니다.")
            
    def on_target_language_change(self, value):
        """대상 언어 선택 시 언어 코드 추출"""
        # "한국어 (ko)" 형식에서 "ko" 추출
        code = value.split("(")[-1].rstrip(")")
        self.target_language.set(code)
        
    def show_claude_translation_prompt(self):
        """Claude 번역 프롬프트 추천 창 표시"""
        prompt_window = ctk.CTkToplevel(self.root)
        prompt_window.title("Claude 번역 프롬프트 추천")
        prompt_window.geometry("600x500")
        prompt_window.transient(self.root)
        prompt_window.grab_set()
        
        # 프롬프트 내용
        prompt_text = """SRT 형식을 유지해야 한다.

전공영어로 쉬운영어로 번역해줘.

가급적이면 타이밍을 잘 맞추어 영어가 나와야 한다.

화면에서 지시하는 내용과 자막과 일치하도록 노력해야 한다.

말이되지 않는 한글 오번역이 있는 경우, 가급적 맥락에 맞춰 수정해야 한다.

영어로 번역하기 전에, 비속어 예를 들어, "어", "음", "그게..." 등의 실제 강의 내용과 상관없는 내용은 정리를 해줘."""
        
        # 제목 라벨
        title_label = ctk.CTkLabel(prompt_window, 
                                  text="🤖 Claude 번역용 프롬프트 추천", 
                                  font=("Arial", 16, "bold"))
        title_label.pack(pady=(20, 10))
        
        # 설명 라벨
        desc_label = ctk.CTkLabel(prompt_window, 
                                 text="아래 내용을 Claude에게 SRT 파일과 함께 제공하면 좋은 번역 결과를 얻을 수 있습니다:",
                                 wraplength=550)
        desc_label.pack(pady=(0, 10))
        
        # 프롬프트 텍스트 표시
        text_frame = ctk.CTkFrame(prompt_window)
        text_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        text_widget = ctk.CTkTextbox(text_frame, 
                                    width=550, height=250,
                                    font=("Arial", 12))
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        text_widget.insert("1.0", prompt_text)
        
        # 버튼 프레임
        button_frame = ctk.CTkFrame(prompt_window)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # 복사 버튼
        def copy_to_clipboard():
            prompt_window.clipboard_clear()
            prompt_window.clipboard_append(prompt_text)
            copy_button.configure(text="✅ 복사됨!")
            prompt_window.after(2000, lambda: copy_button.configure(text="📋 클립보드에 복사"))
        
        copy_button = ctk.CTkButton(button_frame, 
                                   text="📋 클립보드에 복사",
                                   command=copy_to_clipboard,
                                   width=150)
        copy_button.pack(side="left", padx=(10, 5))
        
        # 닫기 버튼
        close_button = ctk.CTkButton(button_frame, 
                                    text="닫기",
                                    command=prompt_window.destroy,
                                    width=100)
        close_button.pack(side="right", padx=(5, 10))
        
    def setup_control_buttons(self, parent):
        """제어 버튼 섹션"""
        control_frame = ctk.CTkFrame(parent)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        self.process_button = ctk.CTkButton(control_frame, text="🚀 처리 시작", 
                                          command=self.start_processing,
                                          height=40, font=("Arial", 14, "bold"))
        self.process_button.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        self.stop_button = ctk.CTkButton(control_frame, text="⏹️ 중지", 
                                       command=self.stop_processing,
                                       height=40, state="disabled",
                                       fg_color="red", hover_color="darkred")
        self.stop_button.pack(side="left", expand=True, fill="x", padx=(5, 0))
        
    def setup_log_section(self, parent):
        """로그 표시 섹션"""
        log_frame = ctk.CTkFrame(parent)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        
        ctk.CTkLabel(log_frame, text="📝 처리 로그", 
                    font=("Arial", 16, "bold")).pack(anchor="w", pady=(5, 10))
        
        # 텍스트 위젯으로 로그 표시
        self.log_text = tk.Text(log_frame, wrap="word", height=15,
                               bg="#2b2b2b", fg="white", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True)
        
        # 스크롤바
        scrollbar = ctk.CTkScrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
    def setup_results_section(self, parent):
        """결과 표시 섹션"""
        results_frame = ctk.CTkFrame(parent)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(results_frame, text="📊 처리 결과", 
                    font=("Arial", 16, "bold")).pack(anchor="w", pady=(5, 10))
        
        # 결과 리스트
        self.results_frame = ctk.CTkScrollableFrame(results_frame, height=200)
        self.results_frame.pack(fill="both", expand=True)
        
        # 진행률 표시
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(results_frame, variable=self.progress_var)
        self.progress_bar.pack(fill="x", pady=(10, 5))
        
        self.progress_label = ctk.CTkLabel(results_frame, text="대기 중...")
        self.progress_label.pack()
        
    def toggle_srt_input(self):
        """SRT 입력 활성화/비활성화"""
        if self.use_existing_srt.get():
            self.srt_entry.configure(state="normal")
            self.srt_button.configure(state="normal")
            self.extract_subtitles.set(False)
        else:
            self.srt_entry.configure(state="disabled")
            self.srt_button.configure(state="disabled")
            self.extract_subtitles.set(True)
            
    def browse_video(self):
        """영상 파일 선택"""
        filename = filedialog.askopenfilename(
            title="영상 파일 선택",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if filename:
            self.video_path.set(filename)
            self.log(f"영상 파일 선택: {filename}")
            
            # 특수문자 경고
            if not self.warn_special_chars(filename, "영상"):
                self.video_path.set("")
                self.log("영상 파일 선택이 취소되었습니다.")
            
    def browse_srt(self):
        """SRT 파일 선택"""
        filename = filedialog.askopenfilename(
            title="자막 파일 선택",
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")]
        )
        if filename:
            self.srt_path.set(filename)
            self.log(f"자막 파일 선택: {filename}")
            
            # 특수문자 경고
            if not self.warn_special_chars(filename, "자막"):
                self.srt_path.set("")
                self.log("자막 파일 선택이 취소되었습니다.")
            
    def log(self, message):
        """로그 메시지 추가"""
        self.log_queue.put(message)
        
    def start_log_updater(self):
        """로그 업데이터 시작"""
        def update_log():
            try:
                while True:
                    message = self.log_queue.get_nowait()
                    self.log_text.insert("end", message + "\n")
                    self.log_text.see("end")
                    
                    # 진행률 업데이트 감지
                    if "%" in message and "진행" in message:
                        try:
                            # "50% 진행" 형식에서 숫자 추출
                            percent = int(message.split("%")[0].split()[-1])
                            self.update_progress(percent / 100, message)
                        except:
                            pass
                    
                    # 청크 처리 상태 업데이트
                    if "청크 " in message and "/" in message and "처리" in message:
                        try:
                            # "청크 3/13 처리 시작" 형식에서 정보 추출
                            if "시작" in message:
                                parts = message.split("청크 ")[1].split("/")
                                current = int(parts[0])
                                total = int(parts[1].split(" ")[0])
                                progress_text = f"청크 {current}/{total} 처리 중..."
                                self.update_progress(current / total * 0.8, progress_text)  # 80%까지만 청크 처리로 간주
                        except:
                            pass
                    
                    # 처리 완료 감지
                    if "✅ 청크" in message and "완료" in message:
                        try:
                            # 완료된 청크 번호 추출
                            chunk_num = int(message.split("청크 ")[1].split(" ")[0])
                            self.log(f"🎉 청크 {chunk_num} 처리 완료!")
                        except:
                            pass
                            
                    # 에러 상황 감지
                    if "❌ 청크" in message and "실패" in message:
                        self.log("⚠️ 청크 처리 중 오류가 발생했지만 계속 진행 중입니다.")
                        
            except queue.Empty:
                pass
            finally:
                self.root.after(100, update_log)
                
        self.root.after(100, update_log)
        
    def get_config(self):
        """현재 설정을 딕셔너리로 반환"""
        # 폰트 설정 동기화 확인
        try:
            if self.selected_font_size.get() != self.font_size.get():
                self.font_size.set(self.selected_font_size.get())
        except:
            pass
            
        config = {
            "extract_subtitles": self.extract_subtitles.get() and not self.use_existing_srt.get(),
            "existing_srt": self.srt_path.get() if self.use_existing_srt.get() else None,
            "use_chunked_processing": self.use_chunked_processing.get(),
            "chunk_duration": self.chunk_duration.get(),
            "whisper_model": self.whisper_model.get(),
            "whisper_language": self.whisper_language.get(),
            "improve_with_claude": self.improve_claude.get(),
            "improvement_type": self.improvement_type.get(),
            "translate_subtitles": self.translate_subtitles.get(),
            "source_language": self.source_language.get(),
            "target_language": self.target_language.get(),
            "embed_subtitles": self.embed_subtitles.get(),
            "create_dubbing": self.create_dubbing.get(),
            "voice_type": self.voice_type.get(),
            "font_size": self.selected_font_size.get(),  # 선택된 폰트 크기 사용
            "font_color": self.font_color.get(),
            "background_color": "black@0.5",
            "font_name": self.selected_font_name.get(),  # 선택된 폰트 이름 사용
            "keep_temp_files": self.keep_temp_files.get()
        }
        
        # 설정 로그에 폰트 정보 표시
        try:
            self.log(f"설정된 폰트: {config['font_name']} ({config['font_size']}pt)")
        except:
            pass
        
        return config
        
    def update_progress(self, value, message):
        """진행률 업데이트"""
        try:
            self.progress_var.set(value)
            self.progress_label.configure(text=message)
        except:
            pass
        
    def add_result(self, stage, file_path):
        """결과 파일 추가"""
        if not file_path or not os.path.exists(file_path):
            return
            
        result_frame = ctk.CTkFrame(self.results_frame)
        result_frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(result_frame, text=f"{stage}:").pack(side="left", padx=(10, 5))
        ctk.CTkLabel(result_frame, text=os.path.basename(file_path),
                    fg_color="gray20", corner_radius=5).pack(side="left", padx=5, expand=True, fill="x")
        
        # 플랫폼별 파일 열기
        def open_file():
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":  # macOS
                os.system(f"open '{file_path}'")
            else:  # Linux
                os.system(f"xdg-open '{file_path}'")
                
        def open_folder():
            folder = os.path.dirname(file_path)
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":  # macOS
                os.system(f"open '{folder}'")
            else:  # Linux
                os.system(f"xdg-open '{folder}'")
                
        ctk.CTkButton(result_frame, text="열기", width=60,
                     command=open_file).pack(side="left", padx=2)
        ctk.CTkButton(result_frame, text="폴더", width=60,
                     command=open_folder).pack(side="left", padx=2)
        
    async def process_video_async(self, video_path, config):
        """비동기 비디오 처리"""
        # stdout 리다이렉트 설정
        old_stdout = sys.stdout
        sys.stdout = OutputRedirector(self.log_queue)
        
        try:
            # 활성화된 단계 계산
            stages = []
            if config.get("extract_subtitles"):
                stages.append("Whisper 자막 추출")
            if config.get("improve_with_claude"):
                stages.append("Claude 자막 개선")
            if config.get("translate_subtitles"):
                stages.append("자막 번역")
            if config.get("embed_subtitles"):
                stages.append("하드서브 생성")
            if config.get("create_dubbing"):
                stages.append("더빙 생성")
                
            self.total_stages = len(stages)
            self.current_stage = 0
            
            # 진행률 콜백 설정
            def progress_callback(stage_name, progress):
                if self.total_stages > 0:
                    stage_progress = (self.current_stage + progress) / self.total_stages
                    percent = int(stage_progress * 100)
                    self.log(f"{percent}% 진행 - {stage_name}")
                    
            self.processor.set_progress_callback(progress_callback)
            
            # 실제 처리
            results = await self.processor.process_video_complete(video_path, config)
            
            # 결과 표시
            if results.get("whisper_srt"):
                self.add_result("Whisper 자막", results["whisper_srt"])
                
            if results.get("improved_srt"):
                self.add_result("개선된 자막", results["improved_srt"])
                
            if results.get("translated_srt"):
                self.add_result("번역된 자막", results["translated_srt"])
                
            if results.get("hardsub_video"):
                self.add_result("하드서브 영상", results["hardsub_video"])
                
            if results.get("final_video"):
                self.add_result("최종 영상", results["final_video"])
                
            self.update_progress(1.0, "100% 완료!")
            self.log("✅ 모든 처리가 완료되었습니다!")
            
            return results
            
        except Exception as e:
            self.log(f"❌ 오류 발생: {str(e)}")
            self.update_progress(0, "오류 발생")
            raise
        finally:
            # stdout 복원
            sys.stdout = old_stdout
            
    def start_processing(self):
        """처리 시작"""
        # 입력 확인
        if not self.video_path.get():
            messagebox.showerror("오류", "영상 파일을 선택해주세요.")
            return
            
        if self.use_existing_srt.get() and not self.srt_path.get():
            messagebox.showerror("오류", "자막 파일을 선택해주세요.")
            return
            
        # 특수문자 재확인
        video_file = self.video_path.get()
        if self.check_special_chars(video_file):
            base_name = os.path.basename(video_file)
            self.log("\n📌 파일명 특수문자 감지")
            self.log(f"   원본: {base_name}")
            self.log("   처리 중 안전한 파일명으로 자동 변환됩니다.")
            
        # UI 상태 변경
        self.processing = True
        self.process_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        
        # 결과 초기화
        for widget in self.results_frame.winfo_children():
            widget.destroy()
            
        # 설정 로그
        config = self.get_config()
        self.log("="*60)
        self.log("🚀 처리 시작")
        self.log(f"영상: {self.video_path.get()}")
        
        # 현재 폰트 설정 로그
        try:
            self.log(f"현재 폰트 설정: {self.selected_font_name.get()} ({self.selected_font_size.get()}pt)")
            self.log(f"폰트 색상: {self.font_color.get()}")
        except:
            pass
        
        # 분할 처리 정보 로그
        if config.get("use_chunked_processing"):
            self.log(f"🔄 분할 처리 모드: {config.get('chunk_duration')}분 단위")
            self.log("   긴 영상에서 Whisper 반복 문제를 해결합니다.")
            self.log("   💡 팁: 처리 중 언제든 중간 결과를 확인할 수 있습니다.")
            
            # 중간 결과 폴더 버튼 추가
            video_base = os.path.splitext(self.video_path.get())[0]
            # 안전한 파일명으로 변환
            safe_base = self.processor.sanitize_filename(video_base)
            partial_dir = safe_base + "_partial_chunks"
            self.add_partial_results_button(partial_dir)
            
        else:
            self.log("📄 일반 처리 모드")
            
        try:
            self.log(f"설정: {json.dumps(config, ensure_ascii=False, indent=2)}")
        except:
            self.log("설정 로그 출력 중 오류")
        self.log("="*60)
        
        # 비동기 처리 시작
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self.process_video_async(self.video_path.get(), config)
                )
                self.processing_results = results
            except Exception as e:
                self.log(f"❌ 처리 중 오류: {str(e)}")
            finally:
                loop.close()
                self.processing = False
                self.root.after(0, self.processing_finished)
                
        # 별도 스레드에서 실행
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        
    def add_partial_results_button(self, partial_dir):
        """중간 결과 폴더 접근 버튼 추가"""
        result_frame = ctk.CTkFrame(self.results_frame)
        result_frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(result_frame, text="중간 결과:").pack(side="left", padx=(10, 5))
        ctk.CTkLabel(result_frame, text="처리 진행 중...",
                    fg_color="orange", corner_radius=5).pack(side="left", padx=5, expand=True, fill="x")
        
        def open_partial_folder():
            if os.path.exists(partial_dir):
                if sys.platform == "win32":
                    os.startfile(partial_dir)
                elif sys.platform == "darwin":  # macOS
                    os.system(f"open '{partial_dir}'")
                else:  # Linux
                    os.system(f"xdg-open '{partial_dir}'")
            else:
                messagebox.showinfo("알림", "중간 결과 폴더가 아직 생성되지 않았습니다.")
                
        def refresh_partial_status():
            if os.path.exists(partial_dir):
                try:
                    chunk_files = [f for f in os.listdir(partial_dir) if f.startswith('chunk_') and f.endswith('.srt')]
                    current_files = [f for f in os.listdir(partial_dir) if f.startswith('current_total_') and f.endswith('.srt')]
                    
                    status_text = f"청크 {len(chunk_files)}개 완료"
                    if current_files:
                        latest_current = max(current_files)
                        status_text += f" (최신: {latest_current})"
                        
                    # 상태 레이블 업데이트
                    for widget in result_frame.winfo_children():
                        if isinstance(widget, ctk.CTkLabel) and widget.cget("text") in ["처리 진행 중...", status_text]:
                            widget.configure(text=status_text, fg_color="blue")
                            break
                except:
                    pass
            # 5초마다 갱신
            self.root.after(5000, refresh_partial_status)
            
        ctk.CTkButton(result_frame, text="폴더 열기", width=80,
                     command=open_partial_folder).pack(side="left", padx=2)
        ctk.CTkButton(result_frame, text="새로고침", width=80,
                     command=refresh_partial_status).pack(side="left", padx=2)
        
        # 자동 갱신 시작
        self.root.after(5000, refresh_partial_status)
        
    def stop_processing(self):
        """처리 중지"""
        self.processing = False
        
        # subprocess 종료 시도
        if hasattr(self, 'current_process') and self.current_process:
            try:
                self.current_process.terminate()
                self.log("⏹️ 프로세스 종료 신호를 보냈습니다.")
            except:
                pass
                
        self.log("⏹️ 사용자가 처리를 중지했습니다.")
        self.processing_finished()
        
    def processing_finished(self):
        """처리 완료 후 UI 복원"""
        self.process_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        
        if self.processing_results:
            messagebox.showinfo("완료", "모든 처리가 완료되었습니다!")
            
    def run(self):
        """GUI 실행"""
        self.root.mainloop()

def main():
    """메인 함수"""
    # 필요한 패키지 확인
    try:
        import customtkinter
    except ImportError:
        print("customtkinter가 설치되지 않았습니다.")
        print("다음 명령어로 설치해주세요: pip install customtkinter")
        return
        
    # GUI 실행
    app = VideoProcessorGUI()
    app.run()

if __name__ == "__main__":
    main()