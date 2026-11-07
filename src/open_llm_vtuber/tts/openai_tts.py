# src/open_llm_vtuber/tts/openai_tts.py
import base64
import json
import os
import sys
from pathlib import Path

from loguru import logger
from openai import OpenAI  # Use the official OpenAI library

from .tts_interface import TTSInterface

# Add the current directory to sys.path for relative imports if needed
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)


class TTSEngine(TTSInterface):
    """
    Uses an OpenAI-compatible TTS API endpoint to generate speech.
    Connects to a server specified by `base_url`.
    API Reference: https://platform.openai.com/docs/api-reference/audio/createSpeech (for standard parameters)
    """

    def __init__(
        self,
        model="kokoro",  # Default model based on user example
        voice="af_sky+af_bella",  # Default voice based on user example
        api_key="not-needed",  # Default for local/compatible servers that don't require auth
        base_url="http://localhost:8880/v1",  # Default to the specified endpoint
        file_extension: str = "mp3",  # Configurable file extension
        **kwargs,  # Allow passing additional args to OpenAI client
    ):
        """
        Initializes the OpenAI TTS engine.

        Args:
            model (str): The TTS model to use (e.g., 'tts-1', 'tts-1-hd').
            voice (str): The voice to use (e.g., 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer').
            api_key (str, optional): API key for the TTS service. Defaults to "not-needed".
            base_url (str, optional): Base URL of the OpenAI-compatible TTS endpoint. Defaults to "http://localhost:8880/v1".
        """
        self.model = model
        self.voice = voice
        self.file_extension = file_extension.lower()  # Use configured extension
        if self.file_extension not in ["mp3", "wav"]:
            logger.warning(
                f"Unsupported file extension '{self.file_extension}' configured for OpenAI TTS. Defaulting to 'mp3'."
            )
            self.file_extension = "mp3"
        self.new_audio_dir = "cache"
        self.temp_audio_file = "temp_openai"  # Use a different temp name

        # Optional BreezeTTS2 / Qwen3-Base voice-clone conditioning. The
        # reference is read once at startup and cached as a data URL so every
        # sentence reuses the same voice without re-reading the file.
        self.ref_text = os.environ.get("VTUBER_TTS_REF_TEXT", "").strip()
        self.ref_data_url = None
        ref_audio_path = os.environ.get("VTUBER_TTS_REF_AUDIO", "").strip()
        if ref_audio_path:
            try:
                with open(ref_audio_path, "rb") as ref_file:
                    encoded = base64.b64encode(ref_file.read()).decode("ascii")
                self.ref_data_url = f"data:audio/wav;base64,{encoded}"
                logger.info(
                    f"Loaded TTS reference audio: {ref_audio_path} "
                    f"({len(encoded) // 1024} KiB base64)"
                )
            except OSError as exc:
                logger.error(f"Failed to load TTS reference audio {ref_audio_path}: {exc}")
        self.sample_rate = os.environ.get("VTUBER_TTS_SAMPLE_RATE", "").strip()
        raw_extra = os.environ.get("VTUBER_TTS_EXTRA_PARAMS", "").strip()
        try:
            self.extra_params = json.loads(raw_extra) if raw_extra else {}
        except json.JSONDecodeError as exc:
            logger.error(f"Invalid VTUBER_TTS_EXTRA_PARAMS JSON: {exc}")
            self.extra_params = {}

        if not os.path.exists(self.new_audio_dir):
            os.makedirs(self.new_audio_dir)

        try:
            # Initialize OpenAI client
            self.client = OpenAI(api_key=api_key, base_url=base_url, **kwargs)
            logger.info(
                f"OpenAI-compatible TTS Engine initialized, targeting endpoint: {base_url}"
            )
        except Exception as e:
            logger.critical(f"Failed to initialize OpenAI client: {e}")
            self.client = None  # Ensure client is None if init fails

    def generate_audio(self, text, file_name_no_ext=None, speed=1.0):
        """
        Generate speech audio file using OpenAI TTS.

        Args:
            text (str): The text to synthesize.
            file_name_no_ext (str, optional): Name of the file without extension. Defaults to a generated name.
            speed (float): The speed of the speech (0.25 to 4.0). Defaults to 1.0.

        Returns:
            str: The path to the generated audio file, or None if generation failed.
        """
        if not self.client:
            logger.error("OpenAI client not initialized. Cannot generate audio.")
            return None

        # Use the configured file extension
        file_name = self.generate_cache_file_name(file_name_no_ext, self.file_extension)
        speech_file_path = Path(file_name)

        # Formatting for speech is the upstream LLM's responsibility. Do not
        # rewrite numbers, URLs, IPs or acronyms here; the only cleanup before
        # this engine is tts_filter (Markdown/symbols) and the sentence
        # divider's period protection, both of which avoid corrupting text.

        try:
            logger.debug(
                f"Generating audio via {self.client.base_url} for text: '{text[:50]}...' with voice '{self.voice}' model '{self.model}'"
            )
            # Qwen3-TTS CustomVoice accepts a natural-language style prompt
            # (`instructions`) plus a `seed`. BreezeTTS2 uses the same fields
            # plus `ref_audio` / `ref_text` for voice cloning, and
            # `sample_rate` / `extra_params` for model-specific options.
            extra_body = {}
            instructions = os.environ.get(
                "VTUBER_TTS_INSTRUCTIONS",
                "语气自然平稳，像日常说话。",
            ).strip()
            if instructions:
                extra_body["instructions"] = instructions

            seed = os.environ.get("VTUBER_TTS_SEED", "42").strip()
            if seed:
                extra_body["seed"] = int(seed)

            if self.ref_data_url:
                extra_body["ref_audio"] = self.ref_data_url
                if self.ref_text:
                    extra_body["ref_text"] = self.ref_text

            if self.sample_rate:
                extra_body["sample_rate"] = int(self.sample_rate)

            extra_body.update(self.extra_params)

            create_kwargs = {
                "model": self.model,
                # The OpenAI SDK requires voice even when the server would
                # accept it omitted. BreezeTTS2 clone mode takes the identity
                # from ref_audio; S0 is its default checkpoint tag.
                "voice": self.voice or "S0",
                "input": text,
                "response_format": self.file_extension,
                "speed": speed,
                "extra_body": extra_body,
            }

            # Use with_streaming_response for potentially better handling of large audio files or network issues
            with self.client.audio.speech.with_streaming_response.create(
                **create_kwargs
            ) as response:
                # Stream the audio content to the file
                response.stream_to_file(speech_file_path)

            logger.info(
                f"Successfully generated audio file via compatible endpoint: {speech_file_path}"
            )

        except Exception as e:
            logger.critical(f"Error: OpenAI TTS unable to generate audio: {e}")
            # Clean up potentially incomplete file
            if speech_file_path.exists():
                try:
                    os.remove(speech_file_path)
                except OSError as rm_err:
                    logger.error(
                        f"Could not remove incomplete file {speech_file_path}: {rm_err}"
                    )
            return None

        return str(speech_file_path)


# Example usage (optional, for testing with the compatible endpoint)
# if __name__ == '__main__':
#     # Configure TTSEngine to use the specific model and voice from the example
#     # The base_url and api_key will use the defaults set in __init__
#     tts_engine = TTSEngine(model="kokoro", voice="af_sky+af_bella")
#     test_text = "Hello world! This is a test using the compatible endpoint."
#     audio_path = tts_engine.generate_audio(test_text, "compatible_endpoint_test")
#     if audio_path:
#         print(f"Generated audio saved to: {audio_path}")
#     else:
#         print("Failed to generate audio.")
