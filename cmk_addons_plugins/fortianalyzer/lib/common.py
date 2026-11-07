"""
FortiAnalyzer: Shared section validation, numeric conversion and singleton discovery.
"""

import math

from cmk.agent_based.v2 import Service


def source(section, key):
    """
    Read a collected API section while preserving collection errors.

    Input:
        section: Parsed agent data for the registered section.
        key: Mapping key to look up.

    Output:
        (data, None) on success, or (None, error_message) on missing or failed data.

    """
    raw = section.get(key)
    if not isinstance(raw, dict):
        return None, 'Missing API section: ' + key
    if raw.get('error'):
        return None, str(raw['error'])
    data = raw.get('data')
    if not isinstance(data, dict):
        return None, 'Missing API data: ' + key
    return data, None


def number(value):
    """
    Convert a reported number to a finite floating-point value.

    Input:
        value: Raw value to validate or convert.

    Output:
        Finite float, or None for booleans, missing values or invalid numbers.

    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(str(value).strip().removesuffix('%'))
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def count(value):
    """
    Validate a non-negative integral count.

    Input:
        value: Raw value to validate or convert.

    Output:
        Integral float, or None when the value is not a valid count.

    """
    result = number(value)
    return result if result is not None and result >= 0 and result.is_integer() else None


def discover_single(section):
    """
    Discover the singleton service regardless of API collection status.

    Input:
        section: Parsed agent data for the registered section.

    Output:
        Yields exactly one Service without an item.

    """
    yield Service()


def discover_gui_single(section):
    """
    Discover GUI-dependent services only for Admin user authentication.
    """
    if section.get('authentication') != 'token':
        yield from discover_single(section)
