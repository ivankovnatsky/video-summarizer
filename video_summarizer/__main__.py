import sys
from pathlib import Path
import tempfile
import shutil
from typing import Optional
import click

from video_summarizer.download import youtube
from video_summarizer.transcribe import whisper
from video_summarizer.constants import (
    DEFAULT_WHISPER_MODEL,
    DEFAULT_LLAMA_MODEL,
    DEFAULT_LANGUAGE,
    MODEL_MAPPING,
)
from video_summarizer.logger import logger
from .providers import get_provider


@click.command()
@click.option(
    "--url",
    help="URL of the video to summarize",
    type=str,
    default=None,
)
@click.option(
    "--file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to local video file",
    default=None,
)
@click.option(
    "--transcript",
    type=click.Path(exists=True, path_type=Path),
    help="Path to existing transcript file",
    default=None,
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("/tmp"),
    help="Output directory for summary files",
)
@click.option(
    "--whisper-model",
    default=DEFAULT_WHISPER_MODEL,
    help=f"Whisper model to use (default: {DEFAULT_WHISPER_MODEL})",
)
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "ollama"]),
    default="ollama",
    help="AI provider to use for summarization",
)
# FIXME: Handle provider/model mapping correctly.
@click.option(
    "--model",
    help="Model to use for summarization",
    default=DEFAULT_LLAMA_MODEL,
)
@click.option(
    "--language",
    default=DEFAULT_LANGUAGE,
    help="Language of the video",
)
@click.option(
    "--show-transcript",
    is_flag=True,
    help="Show transcript in output",
)
def main(
    url: Optional[str],
    file: Optional[Path],
    transcript: Optional[Path],
    output: Path,
    whisper_model: str,
    provider: str,
    model: str,
    language: str,
    show_transcript: bool,
) -> None:
    """Generate summaries of video content"""

    # Validate input parameters
    if sum(bool(x) for x in [url, file, transcript]) != 1:
        raise click.UsageError(
            "Exactly one of --url, --file, or --transcript must be provided"
        )

    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        audio_path: Optional[Path] = None

        # Handle input sources
        if transcript:
            transcript_path = transcript
        else:
            if url:
                audio_path = youtube.download_audio(url, temp_path)
            elif file:
                audio_path = temp_path / file.name
                shutil.copy2(str(file), str(audio_path))

            if not audio_path:
                raise click.UsageError("Failed to get audio file")

            transcript_path = whisper.transcribe(
                audio_path=audio_path,
                output_dir=temp_path,
                language=language,
                model_name=whisper_model,
            )

            # Save transcript to output directory
            transcript_output_path = output / f"{audio_path.stem}_transcript.txt"
            shutil.copy2(transcript_path, transcript_output_path)
            logger.info(f"Transcript saved to: {transcript_output_path}")

        # Generate summary
        ai_provider = get_provider(provider, MODEL_MAPPING.get(provider, model))
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript_text = f.read()

            if show_transcript:
                logger.info("\nTranscript:")
                logger.info("-" * 80)
                logger.info(transcript_text)
                logger.info("-" * 80)

        summary = ai_provider.summarize(transcript_text)

        # Prepare output
        output_file = output / f"{transcript_path.stem}_summary.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(summary)

        logger.info(f"Summary written to {output_file}")


if __name__ == "__main__":
    sys.exit(main())
