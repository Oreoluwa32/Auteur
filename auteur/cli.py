"""Command-line interface for Auteur."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from auteur.config import settings
from auteur.models import FilmProject, ProjectStatus

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="auteur",
        description="Director agent — turns a logline into a finished short film.",
    )
    sub = p.add_subparsers(dest="command")

    # --- run ---
    run_p = sub.add_parser("run", help="Start a new film from a logline.")
    run_p.add_argument("logline", help="One-sentence story premise.")
    run_p.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility.")
    run_p.add_argument("--project-dir", default=settings.project_dir)
    run_p.add_argument("--output-dir", default=settings.output_dir)

    # --- resume ---
    res_p = sub.add_parser("resume", help="Resume a previously started project.")
    res_p.add_argument("project_id", help="Project UUID to resume.")
    res_p.add_argument("--project-dir", default=settings.project_dir)
    res_p.add_argument("--output-dir", default=settings.output_dir)

    # --- status ---
    stat_p = sub.add_parser("status", help="Print the current status of a project.")
    stat_p.add_argument("project_id")
    stat_p.add_argument("--project-dir", default=settings.project_dir)

    # Legacy: `python -m auteur "logline"` with no subcommand
    p.add_argument("logline", nargs="?", help=argparse.SUPPRESS)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--project-dir", default=settings.project_dir)
    p.add_argument("--output-dir", default=settings.output_dir)

    return p


async def _run(logline: str, seed: int | None, project_dir: str, output_dir: str) -> FilmProject:
    _override_dirs(project_dir, output_dir)
    project = FilmProject(logline=logline, seed=seed)
    print(f"[auteur] project id: {project.id}")
    print(f"[auteur] logline:    {logline}")
    return await _execute(project)


async def _resume(project_id: str, project_dir: str, output_dir: str) -> FilmProject:
    _override_dirs(project_dir, output_dir)
    project = FilmProject.load(project_dir, project_id)
    print(f"[auteur] resuming project {project_id} (status: {project.status.value})")
    return await _execute(project)


async def _execute(project: FilmProject) -> FilmProject:
    from auteur.runner import run

    _print_status(project)

    try:
        project = await run(project)
    except KeyboardInterrupt:
        print("\n[auteur] interrupted — project state saved, resume with:")
        print(f"         python -m auteur resume {project.id}")
        sys.exit(1)
    except Exception as exc:
        logger.error("pipeline error: %s", exc)
        print(f"[auteur] ✗ pipeline failed: {exc}")
        sys.exit(1)

    _print_summary(project)
    return project


def _print_status(project: FilmProject) -> None:
    print(f"[auteur] status: {project.status.value}")


def _print_summary(project: FilmProject) -> None:
    c = project.cost
    print("\n[auteur] ── run complete ──────────────────────────────────")
    print(f"  film:          {project.final_film_path or '(none)'}")
    print(f"  shots:         {len(project.shots)}")
    print(f"  input tokens:  {c.input_tokens:,}")
    print(f"  output tokens: {c.output_tokens:,}")
    print(f"  images:        {c.image_count}")
    print(f"  video seconds: {c.video_seconds:.1f}s")
    print("──────────────────────────────────────────────────")


def _status(project_id: str, project_dir: str) -> None:
    try:
        project = FilmProject.load(project_dir, project_id)
    except FileNotFoundError:
        print(f"[auteur] project {project_id} not found in {project_dir}")
        sys.exit(1)

    print(f"id:       {project.id}")
    print(f"logline:  {project.logline}")
    print(f"status:   {project.status.value}")
    print(f"shots:    {len(project.shots)}")
    for s in project.shots:
        score = f"{s.critic_score:.2f}" if s.critic_score is not None else "—"
        print(f"  shot {s.index:02d}  {s.status.value:12s}  score={score}  attempts={s.attempts}")
    cost = project.cost
    print(f"cost:     {cost.input_tokens:,} in / {cost.output_tokens:,} out tokens, "
          f"{cost.image_count} images, {cost.video_seconds:.1f}s video")


def _override_dirs(project_dir: str, output_dir: str) -> None:
    """Push CLI-supplied paths into settings so all modules see them."""
    settings.project_dir = project_dir
    settings.output_dir = output_dir


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s — %(message)s",
    )

    parser = _build_parser()
    args = parser.parse_args()

    # Legacy bare invocation: `python -m auteur "logline"` or `auteur "logline"`
    if args.command is None:
        if args.logline:
            asyncio.run(_run(args.logline, args.seed, args.project_dir, args.output_dir))
        else:
            parser.print_help()
        return

    if args.command == "run":
        asyncio.run(_run(args.logline, args.seed, args.project_dir, args.output_dir))
    elif args.command == "resume":
        asyncio.run(_resume(args.project_id, args.project_dir, args.output_dir))
    elif args.command == "status":
        _status(args.project_id, args.project_dir)
