# MeetingRec

MeetingRec is an AI-powered meeting recorder and transcription tool for macOS that I created because I needed a lightweight solution to capture and analyze my meetings.

I found that existing solutions were either expensive subscriptions or required running resource-intensive local LLM models that bogged down my computer. My approach was different - build a simple tool that records meetings, transcribes the audio, and generates a clean markdown file that I can then feed into any LLM I already have access to (like ChatGPT, Claude, or DeepSeek).

This way, I can chat about my meetings and extract insights without paying for yet another AI subscription - I just use the accounts I already have!

MeetingRec lives in your menu bar, making it easy to start/stop recordings and capture screenshots with a single click. The OpenAI-powered transcription creates comprehensive markdown reports that you can use anywhere.

Feel free to fork this project and adapt it to your needs, or simply run it as-is for a cost-effective alternative to commercial meeting assistants. While it may have fewer bells and whistles than paid apps (for now!), it gets the job done without the ongoing costs.

If you're interested in helping build a free, open-source meeting AI assistant, I'd love your contributions - pull requests are welcome!

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

### Feature Enhancements

#### Speaker Identification

- Identify and label different speakers in meeting transcriptions
- Add speaker profile management
- Implement AI-based speaker diarization
- Allow manual speaker labeling for corrections

#### Alternative AI Models

- Add support for open-source AI models beyond OpenAI
- Implement local transcription using models like Whisper locally
- Provide options for different AI providers
- Allow custom API endpoints for self-hosted models

### Technical Improvements

#### Component Decoupling

- Refactor AudioRecorder, ScreenshotCapture, and TranscriptionService to use interface-based design
- Implement a plugin architecture to allow extending with new recording or transcription methods
- Move file handling logic to dedicated file management service
- Separate UI logic from core application functions

#### Configuration Management

- Establish a single source of truth for default configuration values
- Improve separation between config storage and config access
- Implement configuration validation
- Add support for environment variables and command-line overrides

#### Testing Infrastructure

- Add unit tests for core modules with proper dependency injection
- Implement integration tests for the complete recording pipeline
- Create mocks for OpenAI API and audio devices in test environments
- Add CI/CD pipeline for automated testing
- Develop test fixtures for common testing scenarios

#### Error Handling Strategy

- Develop a consistent approach to error handling across the codebase
- Separate error detection from error reporting
- Improve user-facing error messages and recovery options
- Add detailed logging for debugging purposes

## License

This software is released under the GNU General Public License (GPL), which guarantees your freedom to share and change this software. For more details, see the [GNU GPL](https://www.gnu.org/licenses/gpl-3.0.en.html).
