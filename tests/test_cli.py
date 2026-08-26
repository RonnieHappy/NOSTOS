from pathlib import Path

from nostos.cli import build_parser


def test_cli_exposes_release_commands() -> None:
    parser = build_parser()
    for command in ("doctor", "analyze", "serve", "batch"):
        args = parser.parse_args([command, *({
            "analyze": ["image.png", "--output", "out"],
            "batch": ["manifest.json", "--output", "out.csv"],
        }.get(command, []))])
        assert args.command == command
        assert callable(args.func)


def test_analyze_defaults_are_cpu_first() -> None:
    args = build_parser().parse_args(["analyze", "image.png", "--output", "out"])
    assert args.stain == "SafO"
    assert args.pixel_size_um == 5.16
    assert args.learned_checkpoint is None


def test_server_binds_to_loopback_by_default() -> None:
    args = build_parser().parse_args(["serve", "--no-browser"])
    assert args.host == "127.0.0.1"
    assert args.port == 8765
