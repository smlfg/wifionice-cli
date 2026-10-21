import math

import pytest

from wifionice_cli import exit_codes as ec
from wifionice_cli.errors import CliError
from wifionice_cli.validation import (
    parse_date,
    reject_nan_in_json_tree,
    require_absolute_http_url,
    require_positive_int,
)


def test_require_absolute_http_url_rejects_schemeless():
    with pytest.raises(CliError) as e:
        require_absolute_http_url("not-a-url", name="base_url")
    assert e.value.code == ec.INPUT
    require_absolute_http_url("https://wifi.bahn.de", name="base_url")


def test_positive_int_rejects_zero_and_negative():
    with pytest.raises(CliError) as e:
        require_positive_int(0)
    assert e.value.code == ec.INPUT
    with pytest.raises(CliError):
        require_positive_int(-3)


def test_parse_date_invalid():
    with pytest.raises(CliError) as e:
        parse_date("not-a-date")
    assert e.value.code == ec.INPUT


def test_reject_nan_in_tree():
    with pytest.raises(CliError):
        reject_nan_in_json_tree({"x": float("nan")})
    with pytest.raises(CliError):
        reject_nan_in_json_tree([float("inf")])
    reject_nan_in_json_tree({"x": 1.0, "y": [2, 3]})
