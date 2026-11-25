"""Non-secret process-scoped runtime settings; no credential-file reads."""
from contextlib import contextmanager
import json
import os
from pathlib import Path

RUNTIME_KEYS = {'version', 'python_executable', 'ossutil_executable',
                'ossutil_config', 'ossutil_endpoint'}
ENV_KEYS = {'ossutil_executable': 'PAPERTRACE_OSSUTIL_EXECUTABLE',
            'ossutil_config': 'PAPERTRACE_OSSUTIL_CONFIG',
            'ossutil_endpoint': 'PAPERTRACE_OSSUTIL_ENDPOINT'}


class RuntimeConfigurationError(ValueError):
    pass


def load_runtime(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if (not isinstance(value, dict) or set(value) != RUNTIME_KEYS
            or type(value.get('version')) is not int or value['version'] != 1):
        raise ValueError('daily_runtime_schema_invalid')
    for key in RUNTIME_KEYS - {'version'}:
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError('daily_runtime_field_invalid')
    for key in ('python_executable', 'ossutil_executable', 'ossutil_config'):
        if not Path(value[key]).is_absolute() or not Path(value[key]).is_file():
            raise ValueError('daily_runtime_path_unavailable:' + key)
    return value


@contextmanager
def runtime_scope(path=None):
    if path is None:
        yield
        return
    try:
        settings = load_runtime(path)
    except (OSError, ValueError) as exc:
        raise RuntimeConfigurationError(type(exc).__name__) from None
    previous = {name: os.environ.get(name) for name in ENV_KEYS.values()}
    try:
        for key, name in ENV_KEYS.items():
            os.environ[name] = settings[key]
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
