import os
import time
import wave
import threading
import pyaudio
import logging

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# Import CoreAudio related modules from pyobjc
import objc
from Foundation import NSArray
from CoreAudio import (
    AudioHardwareGetPropertyInfo,
    AudioHardwareGetProperty,
    AudioHardwareSetProperty,
    AudioDeviceGetProperty,
    kAudioHardwarePropertyDevices,
    kAudioDevicePropertyDeviceName,
    kAudioDevicePropertyStreamConfiguration,
    kAudioHardwarePropertyDefaultInputDevice,
    kAudioHardwarePropertyDefaultOutputDevice
)

from meetingrec.config_manager import ConfigManager
from meetingrec.error_manager import error_manager, safe_execute, RecordingError, DependencyError
from meetingrec.transcription_service import TranscriptionService

logger = logging.getLogger("meetingrec.audio_recorder")

class CoreAudioManager:
    """Manages macOS CoreAudio devices and routing for system audio recording."""
    
    def __init__(self):
        """Initialize the CoreAudio manager."""
        self.original_output_device = None
        self.original_input_device = None
        self.temp_device_created = False
        
    def get_audio_devices(self) -> List[Dict[str, Any]]:
        """Get a list of available audio devices using CoreAudio.
        
        Returns:
            List of dictionaries containing device information
        """
        try:
            # Get all audio devices
            property_size = objc.sizeof(objc.c_void_p)
            property_address = objc.malloc(property_size, objc.c_void_p)
            
            status, devices_size = AudioHardwareGetPropertyInfo(
                kAudioHardwarePropertyDevices, 
                property_size, 
                property_address
            )
            
            if status != 0:
                logger.error(f"Failed to get audio devices info: {status}")
                return []
                
            devices_buffer = objc.malloc(devices_size)
            status, _ = AudioHardwareGetProperty(
                kAudioHardwarePropertyDevices,
                devices_size,
                devices_buffer
            )
            
            if status != 0:
                logger.error(f"Failed to get audio devices: {status}")
                return []
                
            device_array = NSArray.arrayWithArray_(devices_buffer)
            
            # Get info for each device
            devices = []
            for i, device_id in enumerate(device_array):
                # Get device name
                property_size = objc.sizeof(objc.c_char * 128)
                buffer = objc.malloc(property_size)
                
                status, size = AudioDeviceGetProperty(
                    device_id,
                    0,
                    False,
                    kAudioDevicePropertyDeviceName,
                    property_size,
                    buffer
                )
                
                if status != 0:
                    continue
                    
                device_name = str(buffer)
                
                # Check if device is input or output capable
                input_channels = self._get_device_channel_count(device_id, True)
                output_channels = self._get_device_channel_count(device_id, False)
                
                devices.append({
                    'id': device_id,
                    'name': device_name,
                    'index': i,
                    'input_channels': input_channels,
                    'output_channels': output_channels,
                    'is_input': input_channels > 0,
                    'is_output': output_channels > 0
                })
                
            return devices
            
        except Exception as e:
            logger.error(f"Error getting audio devices: {e}")
            return []
            
    def _get_device_channel_count(self, device_id: int, is_input: bool) -> int:
        """Get the number of channels for a device.
        
        Args:
            device_id: The CoreAudio device ID
            is_input: True for input channels, False for output
            
        Returns:
            Number of channels
        """
        try:
            property_size = objc.sizeof(objc.c_uint32)
            buffer = objc.malloc(property_size)
            
            status, size = AudioDeviceGetProperty(
                device_id,
                0,
                is_input,
                kAudioDevicePropertyStreamConfiguration,
                property_size,
                buffer
            )
            
            if status != 0:
                return 0
                
            return int(buffer[0])
        except Exception:
            return 0
            
    def get_default_devices(self) -> Tuple[int, int]:
        """Get the default input and output device IDs.
        
        Returns:
            Tuple of (input_device_id, output_device_id)
        """
        try:
            # Get default output device
            property_size = objc.sizeof(objc.c_uint32)
            buffer = objc.malloc(property_size)
            
            status, _ = AudioHardwareGetProperty(
                kAudioHardwarePropertyDefaultOutputDevice,
                property_size,
                buffer
            )
            
            if status != 0:
                logger.error(f"Failed to get default output device: {status}")
                output_device = 0
            else:
                output_device = int(buffer[0])
                
            # Get default input device
            status, _ = AudioHardwareGetProperty(
                kAudioHardwarePropertyDefaultInputDevice,
                property_size,
                buffer
            )
            
            if status != 0:
                logger.error(f"Failed to get default input device: {status}")
                input_device = 0
            else:
                input_device = int(buffer[0])
                
            return (input_device, output_device)
        except Exception as e:
            logger.error(f"Error getting default devices: {e}")
            return (0, 0)
            
    def save_audio_config(self) -> Dict[str, Any]:
        """Save the current audio configuration.
        
        Returns:
            Dictionary with current audio configuration
        """
        try:
            input_device, output_device = self.get_default_devices()
            
            self.original_input_device = input_device
            self.original_output_device = output_device
            
            logger.info(f"Saved audio configuration: input={input_device}, output={output_device}")
            
            return {
                'input_device': input_device,
                'output_device': output_device
            }
        except Exception as e:
            logger.error(f"Error saving audio config: {e}")
            return {}
            
    def setup_recording_route(self) -> Optional[int]:
        """Set up audio routing for system audio recording.
        
        This method configures the audio system to enable recording system audio.
        It looks for a suitable device (like BlackHole) or creates a temporary
        aggregate device if needed.
        
        Returns:
            Device ID to use for recording, or None if setup failed
        """
        try:
            # First, look for BlackHole or similar loopback device
            devices = self.get_audio_devices()
            blackhole_device = next((d for d in devices if 'BlackHole' in d['name'] and d['is_input']), None)
            
            if blackhole_device:
                logger.info(f"Found BlackHole device: {blackhole_device['name']}")
                
                # Create aggregate device for output to both speakers and BlackHole
                # This is done using the Audio MIDI Setup tool via AppleScript
                # (simplified for this implementation)
                
                # For now, we'll just use BlackHole directly
                return blackhole_device['id']
            else:
                logger.warning("BlackHole device not found")
                return None
                
        except Exception as e:
            logger.error(f"Error setting up recording route: {e}")
            return None
            
    def restore_audio_config(self) -> bool:
        """Restore the original audio configuration.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.original_output_device or not self.original_input_device:
                logger.warning("No original audio config to restore")
                return False
                
            # Restore default output device
            property_size = objc.sizeof(objc.c_uint32)
            buffer = objc.malloc(property_size)
            buffer[0] = self.original_output_device
            
            status = AudioHardwareSetProperty(
                kAudioHardwarePropertyDefaultOutputDevice,
                property_size,
                buffer
            )
            
            if status != 0:
                logger.error(f"Failed to restore output device: {status}")
                return False
                
            # Restore default input device
            buffer[0] = self.original_input_device
            
            status = AudioHardwareSetProperty(
                kAudioHardwarePropertyDefaultInputDevice,
                property_size,
                buffer
            )
            
            if status != 0:
                logger.error(f"Failed to restore input device: {status}")
                return False
                
            logger.info("Restored original audio configuration")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring audio config: {e}")
            return False

class AudioRecorder:
    """Records system audio using PyAudio and CoreAudio for routing."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize the audio recorder with configuration."""
        self.config_manager = config_manager or ConfigManager()
        self.audio_config = self.config_manager.get_audio_config()
        
        self.output_dir = Path(self.config_manager.get_output_dir())
        self.is_recording = False
        self.current_meeting_path = None
        self.audio_thread = None
        self.pyaudio_instance = None
        self.stream = None
        self.frames = []
        
        # Initialize transcription service
        self.transcription_service = TranscriptionService(self.config_manager)
        
        # Initialize CoreAudio manager
        self.core_audio = CoreAudioManager()
        
        # Audio parameters
        self.format = pyaudio.paInt16
        self.channels = 2 if self.audio_config["channel"].lower() == "stereo" else 1
        self.rate = self.audio_config["sample_rate"]
        self.chunk = 1024
        self.audio_format = self.audio_config["format"].lower()
        
        # Check available audio devices
        self.available_devices = self.check_audio_devices()
    
    def check_audio_devices(self):
        """Check available audio devices and their capabilities."""
        try:
            p = pyaudio.PyAudio()
            info = []
            
            # Get info about audio devices
            for i in range(p.get_device_count()):
                device_info = p.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:  # Only input devices
                    info.append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels'],
                        'sample_rate': int(device_info['defaultSampleRate'])
                    })
            
            p.terminate()
            
            if not info:
                logger.warning("No audio input devices found!")
            else:
                logger.info(f"Found {len(info)} audio input devices:")
                for device in info:
                    logger.info(f"  - {device['name']}: {device['channels']} channels, {device['sample_rate']}Hz")
                    
            # Also check CoreAudio devices
            core_audio_devices = self.core_audio.get_audio_devices()
            logger.info(f"Found {len(core_audio_devices)} CoreAudio devices")
            
            # Look for BlackHole or similar device
            blackhole_device = next((d for d in info if 'BlackHole' in d['name']), None)
            if blackhole_device:
                logger.info(f"Found BlackHole device: {blackhole_device['name']}")
            else:
                logger.warning("BlackHole device not found in PyAudio devices")
                
            return info
        except Exception as e:
            logger.error(f"Error checking audio devices: {e}")
            return []
    
    def _setup_meeting_directory(self) -> Path:
        """Create a directory for the current meeting's data."""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        meeting_dir = self.output_dir / f"{timestamp}-meeting"
        
        try:
            # Create directory and subdirectories
            meeting_dir.mkdir(parents=True, exist_ok=True)
            (meeting_dir / "screenshots").mkdir(exist_ok=True)
            
            return meeting_dir
        except Exception as e:
            raise RecordingError(
                f"Failed to create meeting directory: {str(e)}",
                {"path": str(meeting_dir)}
            ) from e
    
    def _recording_worker(self):
        """Worker thread function that handles the actual recording."""
        try:
            # Initialize CoreAudio manager and save original config
            original_config = self.core_audio.save_audio_config()
            
            # Set up recording route
            recording_device_id = self.core_audio.setup_recording_route()
            
            # If we couldn't set up a CoreAudio route, fall back to default behavior
            if recording_device_id is None:
                logger.warning("Could not set up system audio recording route, falling back to microphone")
                self._legacy_recording_worker()
                return
                
            # Find the corresponding PyAudio device
            self.pyaudio_instance = pyaudio.PyAudio()
            blackhole_device_index = None
            
            # Look for the BlackHole device in PyAudio devices
            for i in range(self.pyaudio_instance.get_device_count()):
                device_info = self.pyaudio_instance.get_device_info_by_index(i)
                if 'BlackHole' in device_info['name']:
                    blackhole_device_index = i
                    logger.info(f"Found BlackHole device in PyAudio: index={i}")
                    break
            
            if blackhole_device_index is None:
                logger.warning("BlackHole device not found in PyAudio, falling back to default device")
                self._legacy_recording_worker()
                return
                
            # Open stream using the BlackHole device
            logger.info(f"Opening audio stream with BlackHole device (index={blackhole_device_index})")
            self.stream = self.pyaudio_instance.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=blackhole_device_index,
                frames_per_buffer=self.chunk
            )
            
            self.frames = []
            
            # Record audio in chunks until stopped
            logger.info("Starting system audio recording")
            while self.is_recording:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames.append(data)
                
        except Exception as e:
            logger.error(f"Error during recording: {e}")
            self.is_recording = False
        finally:
            # Clean up resources
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                
            # Restore original audio configuration
            self.core_audio.restore_audio_config()
            
    def _legacy_recording_worker(self):
        """Legacy recording worker that only captures microphone input."""
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            
            # Try with configured channels first
            try:
                logger.info(f"Attempting to open audio stream with {self.channels} channels")
                self.stream = self.pyaudio_instance.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    frames_per_buffer=self.chunk
                )
            except Exception as e:
                # If stereo fails, try mono
                if self.channels == 2:
                    logger.warning(f"Failed to open stream with stereo channels: {e}. Falling back to mono.")
                    self.channels = 1
                    self.stream = self.pyaudio_instance.open(
                        format=self.format,
                        channels=self.channels,
                        rate=self.rate,
                        input=True,
                        frames_per_buffer=self.chunk
                    )
                    logger.info("Successfully opened audio stream with mono channel")
                else:
                    # If already using mono, re-raise the error
                    raise
            
            self.frames = []
            
            # Record audio in chunks until stopped
            while self.is_recording:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames.append(data)
                
        except Exception as e:
            logger.error(f"Error during recording: {e}")
            self.is_recording = False
        finally:
            # Clean up resources
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
    
    @safe_execute
    def start_recording(self) -> Dict[str, Any]:
        """Start audio recording.
        
        Returns:
            Dict containing meeting information including path
        """
        if self.is_recording:
            return {"success": False, "message": "Already recording"}
        
        # Set up meeting directory
        self.current_meeting_path = self._setup_meeting_directory()
        
        # Start recording
        self.is_recording = True
        self.audio_thread = threading.Thread(target=self._recording_worker)
        self.audio_thread.daemon = True
        self.audio_thread.start()
        
        meeting_info = {
            "success": True,
            "message": "Recording started",
            "meeting_path": str(self.current_meeting_path),
            "timestamp": datetime.now().isoformat(),
        }
        
        # Save meeting info
        try:
            with open(self.current_meeting_path / "meeting_info.txt", "w") as f:
                f.write(f"Recording started at: {meeting_info['timestamp']}\n")
        except Exception as e:
            # Non-fatal error - log but continue
            error_manager.handle_error(
                RecordingError(f"Failed to save meeting info: {str(e)}",
                              {"path": str(self.current_meeting_path)}),
                show_notification=False
            )
        
        return meeting_info
    
    @safe_execute
    def stop_recording(self) -> Dict[str, Any]:
        """Stop audio recording and save the file.
        
        Returns:
            Dict containing recording information
        """
        if not self.is_recording:
            return {"success": False, "message": "Not recording"}
        
        try:
            # Stop the recording thread
            self.is_recording = False
            if self.audio_thread:
                self.audio_thread.join(timeout=2.0)
        
            # Generate output filename
            audio_path = self.current_meeting_path / f"meeting_audio.{self.audio_format}"
        
            # Save the audio file
            if self.audio_format == "wav":
                self._save_wav_file(audio_path)
            else:
                # For non-WAV formats, save as WAV first, then convert using ffmpeg
                wav_path = self.current_meeting_path / "meeting_audio_temp.wav"
                self._save_wav_file(wav_path)
                self._convert_to_format(wav_path, audio_path)
                # Remove the temporary WAV file
                os.remove(wav_path)
        
            recording_info = {
                "success": True,
                "message": "Recording stopped and saved",
                "audio_path": str(audio_path),
                "meeting_path": str(self.current_meeting_path),
                "duration": len(self.frames) * self.chunk / self.rate,
                "timestamp_end": datetime.now().isoformat()
            }
        
            # Update meeting info
            with open(self.current_meeting_path / "meeting_info.txt", "a") as f:
                f.write(f"Recording stopped at: {recording_info['timestamp_end']}\n")
                f.write(f"Duration: {recording_info['duration']:.2f} seconds\n")
        
            # IMPORTANT: Capture these values for the background thread
            # to avoid race conditions
            current_meeting_path = self.current_meeting_path
            config_manager = self.config_manager
        
            # Start transcription in a separate thread to not block the UI
            def transcribe_audio_async():
                logger.info("Starting transcription process...")
                try:
                    # Check if API key is configured
                    api_key = config_manager.get_openai_api_key()
                    if not api_key:
                        logger.warning("OpenAI API key not set. Skipping transcription.")
                        return
                
                    # Transcribe the audio
                    transcription_result = self.transcription_service.transcribe_audio(
                        audio_path,
                        current_meeting_path  # Use captured value instead of self.current_meeting_path
                    )
                
                    # Update meeting info with transcription results
                    with open(current_meeting_path / "meeting_info.txt", "a") as f:
                        if transcription_result.get("success", False):
                            f.write(f"Transcription completed at: {datetime.now().isoformat()}\n")
                            f.write(f"Transcript file: {transcription_result.get('transcript_path', 'unknown')}\n")
                        else:
                            f.write(f"Transcription failed: {transcription_result.get('message', 'unknown error')}\n")
                
                    logger.info(f"Transcription completed: {transcription_result.get('success', False)}")
                except Exception as e:
                    logger.error(f"Error in transcription thread: {e}")
        
            # Start transcription in background
            import threading
            transcription_thread = threading.Thread(target=transcribe_audio_async)
            transcription_thread.daemon = True
            transcription_thread.start()
        
            return recording_info
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to stop recording: {str(e)}"
            }
        finally:
            # Clear instance variables AFTER capturing what we need for the thread
            self.current_meeting_path = None
            self.frames = []
    
    def _save_wav_file(self, file_path: Path) -> bool:
        """Save recorded audio frames to a WAV file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with wave.open(str(file_path), 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.pyaudio_instance.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(self.frames))
            return True
        except Exception as e:
            error_manager.handle_error(
                RecordingError(f"Failed to save WAV file: {str(e)}",
                              {"path": str(file_path)}),
                show_notification=True
            )
            return False
    
    def _convert_to_format(self, input_path: Path, output_path: Path) -> bool:
        """Convert WAV file to MP3 format using lameenc.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # For MP3 format (the only format we need)
            if output_path.suffix.lower() == '.mp3':
                import wave
                import lameenc
                
                # Open the WAV file
                with wave.open(str(input_path), 'rb') as wav_file:
                    # Get WAV file properties
                    channels = wav_file.getnchannels()
                    sample_rate = wav_file.getframerate()
                    sample_width = wav_file.getsampwidth()
                    
                    # Create MP3 encoder
                    encoder = lameenc.Encoder()
                    encoder.set_channels(channels)
                    encoder.set_sample_rate(sample_rate)
                    
                    # Set quality (higher value = higher quality, 2-7 is typical range)
                    encoder.set_quality(2)  # High quality
                    
                    # Read WAV data and encode to MP3
                    wav_data = wav_file.readframes(wav_file.getnframes())
                    mp3_data = encoder.encode(wav_data)
                    mp3_data += encoder.flush()  # Get the last bit of MP3 data
                    
                    # Write MP3 file
                    with open(str(output_path), 'wb') as mp3_file:
                        mp3_file.write(mp3_data)
                    
                logger.info(f"Converted {input_path} to MP3 format using lameenc")
                return True
            else:
                # If it's not MP3, we don't support it without FFmpeg
                error_manager.handle_error(
                    RecordingError(f"Format not supported without FFmpeg: {output_path.suffix}",
                                  {"input": str(input_path), "output": str(output_path)}),
                    show_notification=True
                )
                return False
                
        except Exception as e:
            error_manager.handle_error(
                RecordingError(f"Error converting audio: {str(e)}",
                              {"input": str(input_path), "output": str(output_path)}),
                show_notification=True
            )
            return False
    
    def is_currently_recording(self) -> bool:
        """Check if recording is in progress."""
        return self.is_recording
    
    def get_current_meeting_path(self) -> Optional[Path]:
        """Get the path to the current meeting directory."""
        return self.current_meeting_path


if __name__ == "__main__":
    # Simple test code
    recorder = AudioRecorder()
    print("Starting recording (5 seconds)...")
    info = recorder.start_recording()
    print(f"Recording to: {info.get('meeting_path')}")
    
    # Record for 5 seconds
    time.sleep(5)
    
    print("Stopping recording...")
    result = recorder.stop_recording()
    print(f"Recording saved: {result.get('audio_path')}")
    print(f"Duration: {result.get('duration'):.2f} seconds")