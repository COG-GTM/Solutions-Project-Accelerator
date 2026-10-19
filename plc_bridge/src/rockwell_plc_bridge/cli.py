"""Command-line dispatcher for the sidecar exe.

All subcommands emit JSON-line events on stdout (see
:mod:`rockwell_plc_bridge.events`) and exit 0 on success, nonzero on
failure. On failure the terminal line is an ``error`` event with a
``type`` field the main app maps back to a specific exception class.
"""

from __future__ import annotations

import argparse
import sys

from rockwell_plc_bridge import __version__, events


def _sdk_version(module_name: str) -> str | None:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover — importlib.metadata is stdlib on 3.12
        return None
    try:
        return version(module_name)
    except PackageNotFoundError:
        return None


def _cmd_version() -> int:
    """Emit ``{"event":"result","data":{"version":..., "logix_designer_sdk":..., "ftecho_sdk":...}}``."""
    events.result({
        "version": __version__,
        "logix_designer_sdk": _sdk_version("logix_designer_sdk"),
        "ftecho_sdk": _sdk_version("ftecho_sdk"),
    })
    return 0


def _cmd_probe(sdk: str) -> int:
    """Attempt to import the requested SDK. Emit ``result`` on success
    or ``error`` on failure so the shim can distinguish "sidecar
    missing" from "SDK missing inside sidecar"."""
    if sdk == "designer":
        try:
            from rockwell_plc_bridge.designer import _require_sdk
            _require_sdk()
        except Exception as ex:  # noqa: BLE001 — reported to caller
            events.error(ex)
            return 2
    elif sdk == "echo":
        try:
            from rockwell_plc_bridge.echo import _require_sdk
            _require_sdk()
        except Exception as ex:  # noqa: BLE001 — reported to caller
            events.error(ex)
            return 2
    else:  # argparse choices should prevent this
        events.error(ValueError("Unknown --sdk value: " + sdk))
        return 2

    events.result({"sdk": sdk, "available": True})
    return 0


def _cmd_designer_convert(args: argparse.Namespace) -> int:
    from rockwell_plc_bridge.designer import convert_l5x_to_acd
    try:
        acd = convert_l5x_to_acd(args.l5x_path, args.acd_path)
    except Exception as ex:  # noqa: BLE001 — reported to caller
        events.error(ex)
        return 2
    events.result({"acd_path": acd})
    return 0


def _cmd_echo_push(args: argparse.Namespace) -> int:
    from rockwell_plc_bridge.echo import push_acd_to_logix_echo
    try:
        controller_guid = push_acd_to_logix_echo(
            args.acd_path,
            chassis_name=args.chassis_name,
            ip1=args.ip1, m1=args.m1,
            ip2=args.ip2, m2=args.m2,
        )
    except Exception as ex:  # noqa: BLE001 — reported to caller
        events.error(ex)
        return 2
    events.result({"controller_guid": controller_guid})
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rockwell_plc_bridge",
        description=(
            "Rockwell PLC SDK sidecar. All output is JSON-line events on "
            "stdout — see plc_bridge/README.md."
        ),
    )
    parser.add_argument(
        "--version", action="store_true",
        help="Emit sidecar + SDK version JSON and exit.",
    )
    sub = parser.add_subparsers(dest="command")

    # probe --sdk {designer,echo}
    p_probe = sub.add_parser("probe", help="Check whether an SDK is importable.")
    p_probe.add_argument("--sdk", required=True, choices=("designer", "echo"))

    # designer <sub>
    p_designer = sub.add_parser("designer", help="Logix Designer SDK operations.")
    d_sub = p_designer.add_subparsers(dest="designer_command")
    p_conv = d_sub.add_parser(
        "convert-l5x-to-acd",
        help="Open an .L5X and save it as an .ACD via LogixProject.")
    p_conv.add_argument("--l5x-path", required=True)
    p_conv.add_argument("--acd-path", required=True)

    # echo <sub>
    p_echo = sub.add_parser("echo", help="FactoryTalk Logix Echo SDK operations.")
    e_sub = p_echo.add_subparsers(dest="echo_command")
    p_push = e_sub.add_parser(
        "push-acd",
        help="Create a controller from an ACD and download to it.")
    p_push.add_argument("--acd-path", required=True)
    p_push.add_argument("--chassis-name", default=None)
    p_push.add_argument("--ip1", default=None)
    p_push.add_argument("--m1", default=None)
    p_push.add_argument("--ip2", default=None)
    p_push.add_argument("--m2", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.version:
        return _cmd_version()

    if args.command == "probe":
        return _cmd_probe(args.sdk)

    if args.command == "designer":
        if args.designer_command == "convert-l5x-to-acd":
            return _cmd_designer_convert(args)
        parser.error("designer: missing subcommand")

    if args.command == "echo":
        if args.echo_command == "push-acd":
            return _cmd_echo_push(args)
        parser.error("echo: missing subcommand")

    parser.print_help(sys.stderr)
    return 1
