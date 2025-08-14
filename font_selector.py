import tkinter as tk
from tkinter import ttk, font
import json
import os
from datetime import datetime
import platform

class FontSelector:
    def __init__(self, root):
        self.root = root
        self.root.title("자막 폰트 선택기")
        self.root.geometry("800x600")
        
        # 폰트 캐시 파일 경로
        self.cache_file = "font_cache.json"
        
        # 자막용 추천 폰트 목록
        self.recommended_fonts = [
            "맑은 고딕", "Malgun Gothic", "나눔고딕", "NanumGothic",
            "나눔바른고딕", "NanumBarunGothic", "돋움", "Dotum",
            "굴림", "Gulim", "바탕", "Batang", "궁서", "Gungsuh",
            "Arial", "Helvetica", "Times New Roman", "Verdana",
            "Tahoma", "Calibri", "Segoe UI", "Comic Sans MS"
        ]
        
        # 선택된 폰트 정보
        self.selected_font = None
        
        # UI 초기화
        self.setup_ui()
        
        # 폰트 목록 로드
        self.load_fonts()
        
    def setup_ui(self):
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 폰트 목록 프레임
        list_frame = ttk.LabelFrame(main_frame, text="폰트 목록", padding="5")
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 스크롤바가 있는 리스트박스
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.font_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=15)
        self.font_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.font_listbox.yview)
        
        # 리스트박스 이벤트 바인딩
        self.font_listbox.bind('<<ListboxSelect>>', self.on_font_select)
        
        # 미리보기 프레임
        preview_frame = ttk.LabelFrame(main_frame, text="폰트 미리보기", padding="10")
        preview_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 폰트 정보 레이블
        self.font_info_label = ttk.Label(preview_frame, text="폰트를 선택하세요")
        self.font_info_label.pack(pady=5)
        
        # 영문 샘플
        self.english_sample = tk.Text(preview_frame, height=3, width=40, wrap=tk.WORD)
        self.english_sample.pack(pady=5)
        self.english_sample.insert(tk.END, "ABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz\n0123456789")
        self.english_sample.config(state=tk.DISABLED)
        
        # 한글 샘플
        self.korean_sample = tk.Text(preview_frame, height=3, width=40, wrap=tk.WORD)
        self.korean_sample.pack(pady=5)
        self.korean_sample.insert(tk.END, "가나다라마바사아자차카타파하\n동해물과 백두산이 마르고 닳도록\n하느님이 보우하사 우리나라 만세")
        self.korean_sample.config(state=tk.DISABLED)
        
        # 폰트 크기 조절
        size_frame = ttk.Frame(preview_frame)
        size_frame.pack(pady=10)
        
        ttk.Label(size_frame, text="폰트 크기:").pack(side=tk.LEFT, padx=5)
        self.size_var = tk.IntVar(value=12)
        self.size_spinbox = ttk.Spinbox(size_frame, from_=8, to=72, textvariable=self.size_var, width=10)
        self.size_spinbox.pack(side=tk.LEFT, padx=5)
        self.size_spinbox.bind('<Return>', lambda e: self.update_preview())
        
        ttk.Button(size_frame, text="적용", command=self.update_preview).pack(side=tk.LEFT, padx=5)
        
        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="폰트 캐시 새로고침", command=self.refresh_font_cache).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="선택", command=self.select_font).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="취소", command=self.root.quit).pack(side=tk.LEFT, padx=5)
        
        # 그리드 가중치 설정
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
    def load_fonts(self):
        """폰트 목록을 로드합니다."""
        if os.path.exists(self.cache_file):
            # 캐시 파일에서 폰트 목록 로드
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    font_list = cache_data.get('fonts', [])
                    cache_date = cache_data.get('date', 'Unknown')
                    print(f"폰트 캐시 로드됨 (생성일: {cache_date})")
            except Exception as e:
                print(f"캐시 파일 로드 실패: {e}")
                font_list = self.get_system_fonts()
                self.save_font_cache(font_list)
        else:
            # 시스템에서 폰트 목록 가져오기
            font_list = self.get_system_fonts()
            self.save_font_cache(font_list)
        
        # 폰트 목록을 리스트박스에 추가
        self.populate_font_list(font_list)
        
    def get_system_fonts(self):
        """시스템에 설치된 폰트 목록을 가져옵니다."""
        print("시스템 폰트 목록을 가져오는 중...")
        font_families = list(font.families())
        
        # 중복 제거 및 정렬
        font_families = sorted(list(set(font_families)))
        
        # 빈 문자열이나 시스템 폰트 제외
        font_families = [f for f in font_families if f and not f.startswith('@')]
        
        return font_families
        
    def save_font_cache(self, font_list):
        """폰트 목록을 캐시 파일에 저장합니다."""
        cache_data = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'fonts': font_list
        }
        
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print(f"폰트 캐시 저장됨: {len(font_list)}개 폰트")
        except Exception as e:
            print(f"캐시 파일 저장 실패: {e}")
            
    def populate_font_list(self, font_list):
        """폰트 목록을 리스트박스에 추가합니다."""
        self.font_listbox.delete(0, tk.END)
        
        # 추천 폰트를 먼저 추가
        added_fonts = set()
        
        # 추천 폰트 섹션
        self.font_listbox.insert(tk.END, "=== 자막용 추천 폰트 ===")
        self.font_listbox.itemconfig(tk.END, {'bg': '#e0e0e0'})
        
        for rec_font in self.recommended_fonts:
            if rec_font in font_list:
                self.font_listbox.insert(tk.END, f"★ {rec_font}")
                added_fonts.add(rec_font)
        
        # 구분선
        self.font_listbox.insert(tk.END, "")
        self.font_listbox.insert(tk.END, "=== 모든 폰트 ===")
        self.font_listbox.itemconfig(tk.END, {'bg': '#e0e0e0'})
        
        # 나머지 폰트 추가
        for font_name in font_list:
            if font_name not in added_fonts:
                self.font_listbox.insert(tk.END, font_name)
                
    def on_font_select(self, event):
        """폰트 선택 이벤트 처리"""
        selection = self.font_listbox.curselection()
        if selection:
            index = selection[0]
            font_name = self.font_listbox.get(index)
            
            # 구분선이나 헤더가 아닌 경우만 처리
            if not font_name.startswith("===") and font_name.strip():
                # 추천 폰트 표시 제거
                if font_name.startswith("★ "):
                    font_name = font_name[2:]
                
                self.selected_font = font_name
                self.update_preview()
                
    def update_preview(self):
        """폰트 미리보기 업데이트"""
        if not self.selected_font:
            return
            
        try:
            font_size = self.size_var.get()
            preview_font = (self.selected_font, font_size)
            
            # 폰트 정보 업데이트
            self.font_info_label.config(text=f"선택된 폰트: {self.selected_font} ({font_size}pt)")
            
            # 영문 샘플 업데이트
            self.english_sample.config(state=tk.NORMAL)
            self.english_sample.tag_configure("font_tag", font=preview_font)
            self.english_sample.tag_add("font_tag", "1.0", tk.END)
            self.english_sample.config(state=tk.DISABLED)
            
            # 한글 샘플 업데이트
            self.korean_sample.config(state=tk.NORMAL)
            self.korean_sample.tag_configure("font_tag", font=preview_font)
            self.korean_sample.tag_add("font_tag", "1.0", tk.END)
            self.korean_sample.config(state=tk.DISABLED)
            
        except Exception as e:
            print(f"폰트 미리보기 오류: {e}")
            
    def refresh_font_cache(self):
        """폰트 캐시를 새로고침합니다."""
        font_list = self.get_system_fonts()
        self.save_font_cache(font_list)
        self.populate_font_list(font_list)
        tk.messagebox.showinfo("완료", "폰트 캐시가 새로고침되었습니다.")
        
    def select_font(self):
        """선택된 폰트 정보를 반환합니다."""
        if self.selected_font:
            font_info = {
                'name': self.selected_font,
                'size': self.size_var.get()
            }
            print(f"선택된 폰트: {font_info}")
            # 여기서 선택된 폰트 정보를 사용하거나 반환할 수 있습니다
            tk.messagebox.showinfo("선택 완료", f"폰트: {font_info['name']}\n크기: {font_info['size']}pt")
        else:
            tk.messagebox.showwarning("경고", "폰트를 선택해주세요.")

def main():
    root = tk.Tk()
    app = FontSelector(root)
    root.mainloop()

if __name__ == "__main__":
    # tkinter messagebox import
    from tkinter import messagebox
    main()
