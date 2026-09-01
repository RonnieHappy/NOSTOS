from pathlib import Path

from nostos.cli import build_parser


def test_cli_exposes_release_commands() -> None:
    parser = build_parser()
    for command in ("doctor", "analyze", "intraop-pshg", "serve", "batch"):
        args = parser.parse_args([command, *({
            "analyze": ["image.png", "--output", "out"],
            "intraop-pshg": ["case", "--output", "out"],
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


def test_intraop_pshg_defaults_to_cpu_profile_contract() -> None:
    args = build_parser().parse_args(["intraop-pshg", "case", "--output", "out"])
    assert args.pixel_size_um == 1.0
    assert args.profile is None
    assert args.include_reference_evaluation is False


def test_cli_exposes_separate_profile_compilation_and_confirmation_audit() -> None:
    parser = build_parser()
    compiled = parser.parse_args(
        [
            "compile-validity-profile",
            "development.jsonl",
            "--config",
            "protocol.json",
            "--output",
            "compiled",
        ]
    )
    audited = parser.parse_args(
        [
            "audit-validity-profile",
            "confirmation.jsonl",
            "--profile",
            "validity_profile.json",
            "--output",
            "audit",
        ]
    )
    assert callable(compiled.func)
    assert callable(audited.func)


def test_cli_exposes_hierarchical_conditional_support_workflow() -> None:
    parser = build_parser()
    compiled = parser.parse_args(
        [
            "compile-conditional-support",
            "development.jsonl",
            "--config",
            "protocol.json",
            "--base-profile",
            "base.json",
            "--output",
            "compiled",
        ]
    )
    audited = parser.parse_args(
        [
            "audit-conditional-support",
            "confirmation.jsonl",
            "--config",
            "protocol.json",
            "--base-profile",
            "base.json",
            "--conditional-profile",
            "conditional.json",
            "--output",
            "audit",
        ]
    )
    assert callable(compiled.func)
    assert callable(audited.func)
