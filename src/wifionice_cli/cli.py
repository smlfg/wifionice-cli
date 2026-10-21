"""wifionice — WIFIonICE (wifi.bahn.de) captive-portal CLI."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from wifionice_cli import __version__
from wifionice_cli import exit_codes as ec
from wifionice_cli.config import resolve_config
from wifionice_cli.errors import ArgumentParser, CliError, run_main
from wifionice_cli.json_util import dumps
from wifionice_cli.portal import PortalClient
from wifionice_cli.state import load_state, save_state
from wifionice_cli.url_util import join_preserve_base_path
from wifionice_cli.validation import reject_nan_in_json_tree, require_finite_number


def _emit(data: dict, *, json_mode: bool) -> None:
    reject_nan_in_json_tree(data)
    if json_mode:
        sys.stdout.write(dumps({"ok": True, **data}) + "\n")
    else:
        for key, value in data.items():
            print(f"{key}: {value}")


def build_parser(json_mode: bool) -> ArgumentParser:
    parser = ArgumentParser(prog="wifionice", description=__doc__)
    parser.set_json_mode(json_mode)
    global_flags = ArgumentParser(add_help=False)
    global_flags.add_argument("--json", action="store_true", help="machine-readable JSON on stdout")
    global_flags.add_argument(
        "--dry-run",
        action="store_true",
        help="simulate: no network requests, no state writes",
    )
    config_flags = ArgumentParser(add_help=False)
    config_flags.add_argument(
        "--config",
        type=Path,
        default=None,
        help="config JSON file (default: ~/.config/wifionice/config.json)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", parents=[global_flags], help="print package version")

    sub.add_parser(
        "config",
        parents=[global_flags, config_flags],
        help="show resolved configuration (env > file > defaults)",
    )

    p_checkin = sub.add_parser(
        "checkin",
        parents=[global_flags, config_flags],
        help="log in to the portal (confirms the portal terms of use)",
    )
    p_checkin.add_argument(
        "--accept-terms",
        action="store_true",
        help="explicitly accept the WIFIonICE terms of use (required for a real checkin)",
    )

    sub.add_parser(
        "status",
        parents=[global_flags, config_flags],
        help="portal reachable? session active? (CNA API, legacy fallback)",
    )

    p_speed = sub.add_parser(
        "speed",
        parents=[global_flags, config_flags],
        help="train speed in km/h from the onboard ICE portal (not a bandwidth test)",
        description=(
            "Report the train's current speed from GET {iceportal}/api1/rs/status. "
            "This is onboard telemetry in km/h, not a download/upload bandwidth measurement."
        ),
    )
    p_speed.add_argument(
        "--bandwidth",
        action="store_true",
        help="not supported: speed is train speed (km/h), not link bandwidth",
    )

    sub.add_parser(
        "logout",
        parents=[global_flags, config_flags],
        help="delete the local session state (does not log the device off the portal)",
    )

    return parser


def _checkin_plan(cfg) -> dict:
    return {
        "base_url": cfg.base_url,
        "state_path": str(cfg.state_path),
        "accept_terms": True,
        "requests": [
            {
                "method": "POST",
                "url": join_preserve_base_path(cfg.base_url, "cna/logon"),
                "headers": {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Csrf-Token": "csrf",
                },
                "json": {},
            },
            {
                "fallback_on_http_404": True,
                "method": "POST",
                "url": join_preserve_base_path(cfg.base_url, "de") + "/",
                "form": {"login": "true", "CSRFToken": "<csrf from cookie>"},
            },
        ],
    }


def _cmd_checkin(args, cfg, *, json_mode: bool, dry_run: bool) -> int:
    if not args.accept_terms and not dry_run:
        raise CliError(
            "checkin requires --accept-terms "
            "(the portal login confirms the WIFIonICE terms of use)",
            code=ec.INPUT,
        )
    if dry_run:
        _emit({"command": "checkin", "dry_run": True, **_checkin_plan(cfg)}, json_mode=json_mode)
        return ec.OK

    client = PortalClient(cfg.base_url, iceportal_url=cfg.iceportal_url, timeout=cfg.timeout)
    result = client.checkin()
    state = {
        "portal_base_url": cfg.base_url,
        "method": result["method"],
        "authenticated": True,
        "checked_in_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_state(cfg.state_path, state)
    _emit(
        {
            "command": "checkin",
            "checked_in": True,
            "method": result["method"],
            "state_path": str(cfg.state_path),
        },
        json_mode=json_mode,
    )
    return ec.OK


def _cmd_status(args, cfg, *, json_mode: bool) -> int:
    client = PortalClient(cfg.base_url, iceportal_url=cfg.iceportal_url, timeout=cfg.timeout)
    info = client.status()
    out: dict = {
        "command": "status",
        "portal_base_url": cfg.base_url,
        "portal_reachable": True,
        "authenticated": info.authenticated,
        "method": info.method,
    }
    if info.session:
        out["session"] = info.session
    local = load_state(cfg.state_path)
    if local is not None:
        out["local"] = {
            "state_path": str(cfg.state_path),
            "checked_in_at": local.get("checked_in_at"),
            "method": local.get("method"),
        }
    _emit(out, json_mode=json_mode)
    return ec.OK


def _cmd_speed(args, cfg, *, json_mode: bool) -> int:
    if args.bandwidth:
        raise CliError(
            "speed reports train speed (km/h) from the onboard ICE portal, not a bandwidth test; "
            "optional bandwidth measurement is not implemented",
            code=ec.INPUT,
        )
    client = PortalClient(cfg.base_url, iceportal_url=cfg.iceportal_url, timeout=cfg.timeout)
    payload = client.iceportal_status()
    if "speed" not in payload:
        raise CliError(
            "onboard ICE portal response has no speed field",
            code=ec.PARSE,
            details={"keys": sorted(payload.keys())},
        )
    speed = require_finite_number(payload["speed"], name="speed")
    out = {
        "command": "speed",
        "iceportal_url": cfg.iceportal_url,
        "measurement": "train_speed_kmh",
        "train_speed_kmh": speed,
        "servicelevel": payload.get("servicelevel"),
        "connection": payload.get("connection"),
        "note": "train speed from the onboard ICE portal, not a bandwidth measurement",
    }
    _emit(out, json_mode=json_mode)
    return ec.OK


def _portal_logoff_best_effort(cfg) -> tuple[bool, str | None]:
    client = PortalClient(cfg.base_url, iceportal_url=cfg.iceportal_url, timeout=cfg.timeout)
    return client.cna_logoff()


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def _cmd_logout(args, cfg, *, json_mode: bool, dry_run: bool) -> int:
    local = load_state(cfg.state_path)
    if local is None:
        portal_logoff = False
        if not dry_run:
            portal_logoff, warning = _portal_logoff_best_effort(cfg)
            if warning:
                _warn(warning)
        _emit(
            {
                "command": "logout",
                "removed": False,
                "portal_logoff": portal_logoff,
                "state_path": str(cfg.state_path),
                "detail": "no local session state found",
            },
            json_mode=json_mode,
        )
        return ec.OK
    if dry_run:
        _emit(
            {
                "command": "logout",
                "dry_run": True,
                "removed": False,
                "state_path": str(cfg.state_path),
                "detail": "would delete the local session state",
            },
            json_mode=json_mode,
        )
        return ec.OK
    portal_logoff, warning = _portal_logoff_best_effort(cfg)
    if warning:
        _warn(warning)
    try:
        cfg.state_path.unlink()
    except OSError as e:
        raise CliError(
            f"cannot delete state: {cfg.state_path}",
            code=ec.PARSE,
            details={"reason": str(e)},
        ) from e
    detail = (
        "local state deleted; portal logoff succeeded"
        if portal_logoff
        else "local state deleted; portal logoff failed or unavailable"
    )
    _emit(
        {
            "command": "logout",
            "removed": True,
            "portal_logoff": portal_logoff,
            "state_path": str(cfg.state_path),
            "detail": detail,
        },
        json_mode=json_mode,
    )
    return ec.OK


def _main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else sys.argv[1:]
    json_mode = "--json" in args_list
    parser = build_parser(json_mode)
    args = parser.parse_args(args_list)
    json_mode = args.json or json_mode
    dry_run = args.dry_run

    if args.command == "version":
        if json_mode:
            sys.stdout.write(dumps({"ok": True, "version": __version__}) + "\n")
        else:
            print(__version__)
        return ec.OK

    cfg = resolve_config(config_path=args.config)

    if args.command == "config":
        _emit(
            {
                "command": "config",
                "base_url": cfg.base_url,
                "iceportal_url": cfg.iceportal_url,
                "state_path": str(cfg.state_path),
                "timeout": cfg.timeout,
                "sources": cfg.sources,
            },
            json_mode=json_mode,
        )
        return ec.OK

    if args.command == "checkin":
        return _cmd_checkin(args, cfg, json_mode=json_mode, dry_run=dry_run)
    if args.command == "status":
        if dry_run:
            raise CliError("status does not support --dry-run", code=ec.INPUT)
        return _cmd_status(args, cfg, json_mode=json_mode)
    if args.command == "speed":
        if dry_run:
            raise CliError("speed does not support --dry-run", code=ec.INPUT)
        return _cmd_speed(args, cfg, json_mode=json_mode)
    if args.command == "logout":
        return _cmd_logout(args, cfg, json_mode=json_mode, dry_run=dry_run)

    raise CliError(f"unknown command: {args.command}", code=ec.INPUT)


def main() -> None:
    sys.exit(run_main(_main))


if __name__ == "__main__":
    main()
