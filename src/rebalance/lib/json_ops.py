import json
from typing import Any

def _json_dumps(value: Any) -> str:
    """Returns a deterministic, sorted, ensure_ascii=False JSON string."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
