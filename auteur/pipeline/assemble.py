"""Stage 6 — Assemble: stitch clips, add audio, titles → final MP4."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from auteur.models import FilmProject, ShotStatus

logger = logging.getLogger(__name__)


def _total_duration(project: FilmProject) -> float:
    return sum(s.duration for s in project.shots if s.status == ShotStatus.ACCEPTED)


def _clip_list_file(project: FilmProject, tmp_dir: Path) -> Path:
    """Write an ffmpeg concat list for accepted shots (or their keyframes as stills)."""
    list_path = tmp_dir / "concat.txt"
    lines = []
    for shot in project.shots:
        if shot.status != ShotStatus.ACCEPTED:
            continue

        if shot.clip_path and Path(shot.clip_path).exists():
            src = shot.clip_path
        elif shot.keyframe_path and Path(shot.keyframe_path).exists():
            # Fall back to keyframe as a still image loop
            still = tmp_dir / f"still_{shot.index}.mp4"
            _image_to_video(Path(shot.keyframe_path), still, duration=shot.duration)
            src = str(still)
        else:
            logger.warning("shot %d: no clip or keyframe, skipping", shot.index)
            continue

        lines.append(f"file '{src}'")
        lines.append(f"duration {shot.duration}")

    list_path.write_text("\n".join(lines))
    return list_path


def _image_to_video(image: Path, dest: Path, duration: float) -> None:
    """Loop a still image into a short video clip."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image),
            "-t", str(duration),
            "-vf", "scale=1920:1080",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(dest),
        ],
        check=True,
        capture_output=True,
    )


def assemble(project: FilmProject, output_dir: Path) -> FilmProject:
    """Concatenate shots, mix audio, add title card → final MP4.

    Synchronous — runs ffmpeg as subprocesses. Called from an async context
    via asyncio.to_thread.
    """
    final_dir = output_dir / project.id
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / "film.mp4"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # 1. Concatenate clips
        raw_concat = tmp_dir / "concat_raw.mp4"
        list_file = _clip_list_file(project, tmp_dir)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                str(raw_concat),
            ],
            check=True,
            capture_output=True,
        )

        # 2. Build audio mix command inputs
        audio_inputs: list[str] = []
        filter_parts: list[str] = []

        if project.narrator_audio_path and Path(project.narrator_audio_path).exists():
            audio_inputs += ["-i", project.narrator_audio_path]
            n = len(audio_inputs) // 2
            filter_parts.append(f"[{n}:a]volume=1.0[narr]")

        if project.music_path and Path(project.music_path).exists():
            audio_inputs += ["-i", project.music_path]
            m = len(audio_inputs) // 2
            total = _total_duration(project)
            filter_parts.append(f"[{m}:a]aloop=loop=-1:size=44100,atrim=duration={total},volume=0.25[music]")

        # 3. Add title card (2s black with text)
        title_clip = tmp_dir / "title.mp4"
        _make_title_card(project.logline[:80], title_clip)

        # 4. Final compose
        cmd = ["ffmpeg", "-y", "-i", str(title_clip), "-i", str(raw_concat)]
        cmd += audio_inputs

        filter_complex = "[0:v][1:v]concat=n=2:v=1[vid]"
        if "narr" in " ".join(filter_parts) and "music" in " ".join(filter_parts):
            filter_parts.append("[narr][music]amix=inputs=2[aud]")
            filter_complex += ";" + ";".join(filter_parts)
            cmd += ["-filter_complex", filter_complex, "-map", "[vid]", "-map", "[aud]"]
        elif filter_parts:
            label = "narr" if "narr" in filter_parts[0] else "music"
            filter_complex += ";" + filter_parts[0]
            cmd += ["-filter_complex", filter_complex, "-map", "[vid]", "-map", f"[{label}]"]
        else:
            cmd += ["-filter_complex", filter_complex, "-map", "[vid]"]

        cmd += ["-c:v", "libx264", "-c:a", "aac", "-shortest", str(final_path)]

        logger.info("assembling final film")
        subprocess.run(cmd, check=True, capture_output=True)

    project.final_film_path = str(final_path)
    logger.info("film assembled: %s", final_path)
    return project


def _make_title_card(text: str, dest: Path) -> None:
    """Render a 2-second black title card with white text."""
    safe_text = text.replace("'", "\\'").replace(":", "\\:")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:d=2",
            "-vf", (
                f"drawtext=text='{safe_text}'"
                ":fontcolor=white:fontsize=48"
                ":x=(w-text_w)/2:y=(h-text_h)/2"
            ),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(dest),
        ],
        check=True,
        capture_output=True,
    )
