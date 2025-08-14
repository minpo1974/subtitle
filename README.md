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