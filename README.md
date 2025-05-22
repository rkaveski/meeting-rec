# MeetingRec

MeetingRec is an AI-powered meeting recorder and transcription tool for macOS. It lives in your menu bar, allowing you to easily record meetings, capture screenshots, and generate transcriptions using OpenAI.

## Features

- **System Audio Recording**: Capture both your microphone and system audio for complete meeting recordings
- **Screenshot Capture**: Take screenshots during meetings with a single click
- **AI Transcription**: Automatically transcribe audio using OpenAI's Whisper model
- **Markdown Reports**: Generate comprehensive markdown reports with embedded audio, screenshots, and transcriptions
- **Menu Bar App**: Convenient access from your macOS menu bar

## Module Overview

- **menu_bar_app.py**: Main application entry point, implements the menu bar UI and core application logic
- **audio_recorder.py**: Handles audio recording with both microphone and system audio capture
- **screenshot_capture.py**: Manages screenshot functionality with window detection
- **markdown_exporter.py**: Generates formatted markdown reports from meeting data
- **config_manager.py**: Manages application configuration via YAML files
- **error_manager.py**: Provides centralized error handling and notification system
- **transcription_service.py**: Interfaces with OpenAI's API for audio transcription
- **menu_manager.py**: Handles menu creation and state management

## Setup

### Requirements

- macOS 10.14 or newer
- Python 3.8 or newer
- OpenAI API key (for transcription features)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/meetingrec.git
cd meetingrec
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app in development mode:

```bash
python -m meetingrec.menu_bar_app
```

4. On first run, you'll be prompted to set up your OpenAI API key in the configuration file.

## Development Mode

To run MeetingRec in development mode:

1. Ensure you have all dependencies installed:

```bash
pip install -r requirements.txt
```

2. Run the application directly:

```bash
python run.py
```

3. For rapid development, you can also run specific modules:

```bash
# Run only the menu bar app
python -m meetingrec.menu_bar_app

# Test audio recording
python -m meetingrec.audio_recorder
```

4. Configure development settings in `~/.meetingrec/config.yaml`

## Building the Application

To build a standalone macOS application:

1. Run the build script:

```bash
python build_app.py
```

2. The built application will be in the `dist` folder

## Configuration

MeetingRec stores its configuration in `~/.meetingrec/config.yaml`. You can edit this file directly or through the app's "Open Config" menu option.

Key configuration options:

- OpenAI API key for transcription
- Output directory for meeting recordings
- Audio format and quality settings
- AI model settings

## To-Do & Future Enhancements

### Speaker Identification

- Identify and label different speakers in meeting transcriptions
- Add speaker profile management
- Implement AI-based speaker diarization
- Allow manual speaker labeling for corrections

### Testing Infrastructure

- Add unit tests for core modules
- Implement integration tests for the complete recording pipeline
- Create mocks for OpenAI API in test environments
- Add CI/CD pipeline for automated testing

### Alternative AI Models

- Add support for open-source AI models beyond OpenAI
- Implement local transcription using models like Whisper locally
- Provide options for different AI providers
- Allow custom API endpoints for self-hosted models

## License

This software is released under the GNU General Public License (GPL), which guarantees your freedom to share and change this software. For more details, see the [GNU GPL](https://www.gnu.org/licenses/gpl-3.0.en.html).
