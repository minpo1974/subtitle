# Whisper Video Processing System

## Overview
An integrated video processing system that uses OpenAI Whisper for automatic subtitle extraction and provides various video enhancement features.

## Features
- **Automatic Subtitle Extraction**: Using OpenAI Whisper model for speech-to-text
- **Long Video Support**: Chunked processing for videos longer than 1 hour
- **Multi-language Support**: Korean, English, Japanese, Chinese and more
- **Subtitle Translation**: Built-in translation capabilities
- **Hardsubbing**: Embed subtitles directly into videos
- **Font Customization**: Select system fonts with preview
- **GUI Interface**: User-friendly interface built with CustomTkinter

## Main Components

### Core Files
- `whis.py`: Main video processor with Whisper integration
- `whis_interface.py`: GUI application for easy interaction
- `font_selector.py`: Font selection dialog with preview
- `srt_converter.py`: SRT file format conversion utilities
- `srt_extract_ment.py`: SRT subtitle extraction utilities

### Required Dependencies
- **ffmpeg**: Video processing (includes ffmpeg.exe, ffplay.exe, ffprobe.exe)
- **Python Libraries**:
  - `whisper`: OpenAI Whisper model
  - `customtkinter`: Modern GUI framework
  - `tkinter`: Base GUI components
  - `asyncio`: Asynchronous processing
  - `pydub`: Audio processing (optional)
  - `googletrans`: Google translation (optional)
  - `argostranslate`: Offline translation (optional)
  - `edge_tts`: Text-to-speech (optional)

## Installation

### Prerequisites
1. Python 3.8 or higher
2. FFmpeg binaries (included in the project)

### Python Dependencies
```bash
pip install openai-whisper
pip install customtkinter
pip install pydub
pip install googletrans==4.0.0-rc1
pip install argostranslate
pip install edge-tts
```

## Usage

### GUI Mode
Run the interface application:
```bash
python whis_interface.py
```

### Features in GUI
1. **Video Selection**: Browse and select video files
2. **Subtitle Options**:
   - Extract new subtitles using Whisper
   - Use existing SRT files
   - Enable chunked processing for long videos
3. **Processing Options**:
   - Choose Whisper model size (tiny, base, small, medium, large)
   - Select language for detection
   - Set chunk duration for long videos
4. **Enhancement Options**:
   - Translate subtitles to different languages
   - Embed subtitles as hardsubs
   - Customize font, size, and color
5. **Output**:
   - Saves processed videos with appropriate suffixes
   - Keeps intermediate files optionally

### Command Line Mode
```bash
python whis.py --video input.mp4 --model medium --language ko
```

## Project Structure
```
whisper/
├── whis.py                 # Core video processor
├── whis_interface.py       # GUI application
├── font_selector.py        # Font selection utility
├── srt_converter.py        # SRT conversion utilities
├── srt_extract_ment.py     # SRT extraction utilities
├── ffmpeg.exe             # FFmpeg executable
├── ffplay.exe             # FFplay executable
├── ffprobe.exe            # FFprobe executable
├── backup/                # Backup versions of code
└── whis_interface/        # Interface resources
```

## Key Features Explained

### Chunked Processing
For videos longer than 1 hour, the system can split the video into smaller chunks to avoid Whisper's repetition issues with long content. Each chunk is processed separately and then merged.

### Font Selection
The font selector provides:
- System font detection
- Real-time preview
- Favorite fonts management
- Font size adjustment
- Multiple language support verification

### Special Character Handling
The system automatically handles special characters in filenames that might cause issues with FFmpeg processing, converting them to safe alternatives.

## Output Files
The system generates files with descriptive suffixes:
- `_whisper_subtitles.srt`: Extracted subtitles
- `_translated_[lang].srt`: Translated subtitles
- `_hardsub.mp4`: Video with embedded subtitles
- `_final.mp4`: Final processed video

## Notes
- The system is optimized for Windows but can work on other platforms with appropriate FFmpeg installation
- Long video processing may take considerable time depending on the model size
- GPU acceleration is used when available for Whisper processing

## License
This project uses various open-source components. Please refer to individual library licenses.

---

## 한국어 강의 영상 제작 워크플로우

### 0) 출판사 PPT로부터 한국어 대본 준비 (claude, genspark 등 이용)

#### 0-1) 필자는 실제 강의를 하는 것이기 때문에, powerpoint 1p 씩 강의를 진행함
   - 교재에서는 1.1, 1.2와 같은 절 단위로 강의영상 촬영
   - 교재의 1.1 section을 vFlat Scan을 교재 이미지를 얻고
   - 이 이미지를 ocr하여 텍스트를 인식시킴 (alpdf 활용)
   - [1주-2p] 교재_OCR.pdf

#### 0-2) 해당 page에 대해, 출판사 ppt를 보강하거나 그대로 사용
   - 교재를 읽고, PPT를 검토
   - 표에 있는 기관, 정보시스템과 데이터베이스명 퀴즈 활동 추가
  
#### 0-3) claude에서 해당 강의 PPT, 강의교재를 넣고 한글강의록 멘트 작성
(제공 : 해당 강의 PPT, 해당 강의 교재 내용)

아래의 prompt는 claude에서 실행함
```
prompt : 초급 학습자가 PPT 내용을 충분히 이해할 수 있도록, 교수자가 실제 강의를 하듯 슬라이드별 한글 강의록을 생성한다.
지침:
초급 학습자가 PPT 내용을 충분히 이해할 수 있도록, 교수자가 실제 강의를 하듯 슬라이드별 한글 강의록을 생성한다. 지침: 슬라이드별 형식으로 작성할 것. 각 슬라이드는 아래 네 구역을 포함한다. [슬라이더 주제] — 슬라이드 제목 또는 핵심 주제 [슬라이더 강의 멘트] — 학생에게 말하듯 자연스러운 완전한 문장으로 설명 (충분한 설명, 필요하다면 예제 포함) [슬라이더 핵심키워드] — 해당 슬라이드의 핵심 용어·개념 3-5개 문장은 쉬운 표현과 친절한 어조로 작성하되, 내용은 충분히 구체적으로. 원본 PPT의 용어·구조를 최대한 반영하되, 이해를 돕기 위해 예시나 비유를 적절히 추가해도 무방하다. 첨부된 한글 문서는 강의PT 원본이다. 데이터베이스 전공자로서 관련된 내용으로 채워줘. 첨부된 pdf는 해당 강의 내용과 관련된 교재의 내용이다. 강의 멘트에 충분히 반영되어야 한다. 마지막에는 퀴즈 활동 추가를 해줘. 활동 3개 추가

내용의 양은 충분히 많이 설명을 포함. 오랫동안 생각.
```

결과 : claude에서 답변한 강의록을 검토하고, [1주-2p]한글자막.txt에 저장 (추후 한글강의록 제출할 수 있음)
[1주-2p]한글자막-강의영상촬영멘트.txt를 이용하여 영상촬영함

#### 0-4) 0-3에서 얻은 한글 강의록으로 genspark ai slider에서 PT 재구성
제공 자료 : [1주-2p]한글자막-강의영상촬영멘트.txt, 한글 PPT, 한글 교재내용

- genspark ai slider 또는 gamma에서 해당 페이지 재구성(재구성을 위해, 교재의 내용을 입력)
- 영어강의 PT를 만들어내야 하기 때문에
- 영어 PT 생성을 요청해야 한다.

```
prompt : 첨부된 한글강의록 ([1주-2p]한글자막-강의영상촬영멘트.txt)으로 수업을 진행한다. 참고자료들을 참고하여 슬라이더를 구성해줘. 슬라이더는 영어로 작성되어야 한다. 영어로 작성한 뒤, 연속해서 똑같은 내용으로 한글로도 제시해줘.
```

위의 멘트로 잘 만들지 못할 때:
```
영어로 강의를 해야 한다. 강의멘트는 [2주-1p]한글자막-강의영상촬영멘트.txt이다. 주어진 ppt인 CH02_데이터베이스시스템 - 복사본-복사.pptx를 중심으로 강의를 한다. 영어버전과 한글버전의 slider를 충실하게 제시해줘. 해당 2장전체교재_OCR.pdf는 pptx에 대한 충분한 설명이다. a4 사이즈 크기로 자료를 제시해줘. 다운 받을 수 있는 포맷으로 제시해줘
```

또는:
```
영어로 강의를 해야 한다. 강의멘트는 [2주-1p]한글자막-강의영상촬영멘트.txt이다. 주어진 ppt인 CH02_데이터베이스시스템 - 복사본-복사.pptx를 중심으로 강의를 한다. 영어버전 slider를 먼저제시하고 같은 내용으로 그대로 한글버전의 slider를 충실하게 제시해줘. 해당 2장 전체교재_OCR.pdf는 pptx에 대한 충분한 설명이다. 일반 powerpoint slider  사이즈 크기로 자료를 제시해줘. 다운 받을 수 있는 포맷으로 제시해줘
```

---

## 유사한 기능을 캡컷으로 한다면?

1. doc zoom으로 영상 촬영(한국어) - 한국어 대본 준비
2. capcut에서 자동 자막 생성(한국어)
3. 생성된 자동 자막을 읽어가면서, 오타 수정 (텍스트->자동캡션, pro기능), 그 이후 자막트랙을 선택하고, 오른쪽 위에 캡션 메뉴 선택하면 자막이 나온다. 여기에서 수정함
4. 내보내기에서 동영상 체크해제, 오디어 체크, srt 선택
5. 이중언어 캡션을 선택해봤지만, 번역 자체가 마음에 안든다.
6. 그래서 srt를 시간을 고려해서 claude에서 영어자막을 수정하려고 한다.
7. claude prompt:
```
srt 내의 영상 시간을 고려해서 영어자막으로 수정하려고 한다. 첨부된 srt 문서형식으로 영어자막을 제시해줘. 너무 쪼개어진 내용은 적절히 시간을 조정해서 작성해줘. 그리고, 이 영어 자막은 사용자의 언어가 현재 한국어인데, 이를 영어로 더빙하려고 한다. sync를 잘 맞추어서 작성해줘.답변은 입력형식인 srt형식이다.

번역을 할때, 의미도 파악해서 말이 되게 해줘. (데이터베이스전문가, 교육자, 교수가 강의함). 직역도 좋지만, 문맥에 맞지 않게 번역만 하는 것은 안된다.
```

### 추천 명령어:
```
srt 형식을 유지해야 한다.
전공영어로 쉬운영어로 번역해줘.
가급적이면 타이밍을 잘 맞추어 영어가 나와야 한다.
화면에서 지시하는 내용과 자막과 일치하도록 노력해야 한다.
말이되지 않는 한글 오번역이 있는 경우, 가급적 맥락에 맞춰 수정해야 한다.
영어로 번역하기 전에, 비속어 예를 들어, "어", "음", "그게..." 등의 실제 강의 내용과 상관없는 내용은 정리를 해줘.
```

8. 이를 eng.srt로 저장한다.
9. 이제 원본 영상을 복사한 뒤, 사본 영상에서 소리를 모두는 작업을 시작한다.
10. capcut에서 새 프로젝트를 만든다.
11. 영어 영상을 불러온다.
12. 오디오 트랙 분리 (트랙선택 -> 오디오 -> 음성분리 & 노이즈 제거), 오디오분리 메뉴가 더 확실함
13. 텍스트->로컬자막->파읽가져오기
14. 텍스트 클립을 선택 -> 우측상단의 텍스트에서 음성으로 메뉴
15. 음성 선택
16. 내보내기 (유료)