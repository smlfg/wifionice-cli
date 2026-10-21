"""Structured CLI errors and top-level handling (no tracebacks on expected failures)."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any

from wifionice_cli import exit_codes as ec
from wifionice_cli.json_util import dumps


@dataclass
class CliError(Exception):
    """Expected failure; maps to a documented exit code."""

    message: str
    code: int = ec.INPUT
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def error_payload(err: CliError | BaseException, *, interrupted: bool = False) -> dict[str, Any]:
    if interrupted:
        return {"ok": False, "error": {"code": ec.ABORT, "message": "interrupted"}}
    if isinstance(err, CliError):
        payload: dict[str, Any] = {
            "ok": False,
            "error": {"code": err.code, "message": err.message},
        }
        if err.details:
            payload["error"]["details"] = err.details
        return payload
    return {
        "ok": False,
        "error": {"code": ec.INPUT, "message": str(err) or "unexpected error"},
    }


def emit_error(
    err: CliError | BaseException,
    *,
    json_mode: bool,
    interrupted: bool = False,
) -> None:
    if json_mode:
        sys.stdout.write(dumps(error_payload(err, interrupted=interrupted)) + "\n")
    else:
        if interrupted:
            print("interrupted", file=sys.stderr)
        elif isinstance(err, CliError):
            print(err.message, file=sys.stderr)
        else:
            print(str(err) or "unexpected error", file=sys.stderr)


def run_main(main_fn, argv: list[str] | None = None) -> int:
    """Wrap ``main_fn(argv) -> int`` with CliError / KeyboardInterrupt / EOF handling."""
    arglist = argv if argv is not None else sys.argv[1:]
    json_mode = "--json" in arglist
    try:
        return main_fn(arglist if argv is not None else None)
    except CliError as e:
        emit_error(e, json_mode=json_mode)
        return e.code
    except KeyboardInterrupt:
        emit_error(CliError("interrupted", code=ec.ABORT), json_mode=json_mode, interrupted=True)
        return ec.ABORT
    except EOFError:
        emit_error(
            CliError("end of input", code=ec.ABORT),
            json_mode=json_mode,
            interrupted=True,
        )
        return ec.ABORT


class ArgumentParser(argparse.ArgumentParser):
    """argparse parser that exits with :data:`~wifionice_cli.exit_codes.INPUT`."""

    def add_subparsers(self, *args, **kwargs):
        action = super().add_subparsers(*args, **kwargs)
        parent_json = self.json_mode
        orig_add_parser = action.add_parser

        def add_parser(name, **kwargs):
            sub = orig_add_parser(name, **kwargs)
            sub.set_json_mode(parent_json)
            return sub

        action.add_parser = add_parser
        return action

    def exit(self, status: int = 0, message: str | None = None) -> None:
        code = ec.map_argparse_exit(status)
        if message:
            if self.json_mode:
                sys.stdout.write(
                    dumps(
                        {
                            "ok": False,
                            "error": {"code": code, "message": message.strip()},
                        }
                    )
                    + "\n"
                )
            else:
                self._print_message(message, sys.stderr)
        raise SystemExit(code)

    def error(self, message: str) -> None:
        self.exit(ec.INPUT, message)

    @property
    def json_mode(self) -> bool:
        return getattr(self, "_json_mode", False)

    def set_json_mode(self, enabled: bool) -> None:
        self._json_mode = enabled
