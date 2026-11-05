"""Optional local audio playback and recording helpers.

Playback prefers mpv, then ffplay. Recording prefers arecord, then ffmpeg
with ALSA input. MUKI remains usable when none of these tools is installed.
"""
from pathlib import Path
import shutil
import subprocess


def playback_command(path: str | Path) -> list[str] | None:
    file_path = str(path)
    if shutil.which("mpv"):
        return ["mpv", "--no-video", "--really-quiet", file_path]
    if shutil.which("ffplay"):
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", file_path]
    return None


def play(path: str | Path) -> subprocess.Popen:
    command = playback_command(path)
    if not command:
        raise RuntimeError("Audio playback needs mpv or ffplay. Install mpv for the lightest supported setup.")
    if not Path(path).is_file():
        raise FileNotFoundError(path)
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def recording_command(path: str | Path, seconds: int = 8) -> list[str] | None:
    seconds = max(1, min(int(seconds), 60))
    target = str(path)
    if shutil.which("arecord"):
        return ["arecord", "-q", "-f", "S16_LE", "-r", "44100", "-c", "1", "-d", str(seconds), target]
    if shutil.which("ffmpeg"):
        return ["ffmpeg", "-nostdin", "-y", "-f", "alsa", "-i", "default",
                "-t", str(seconds), "-ac", "1", "-ar", "44100", target]
    return None


def record(path: str | Path, seconds: int = 8) -> subprocess.Popen:
    command = recording_command(path, seconds)
    if not command:
        raise RuntimeError("Recording needs arecord (alsa-utils) or ffmpeg with ALSA support.")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
