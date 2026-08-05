from __future__ import annotations

import re
from pathlib import Path

_SVC = Path(__file__).parent.parent / "deploy" / "cloud-run-service.yaml"


def test_service_sets_max_scale():
    """Runaway-cost guard: the service must cap autoscaling (Cloud Run's
    default is 100). Guards against a silent revert of the maxScale annotation."""
    text = _SVC.read_text(encoding="utf-8")
    assert "autoscaling.knative.dev/maxScale" in text, "maxScale annotation missing"
    m = re.search(r'autoscaling\.knative\.dev/maxScale:\s*"?(\d+)"?', text)
    assert m and 1 <= int(m.group(1)) <= 10, (
        f"maxScale should be a small cap, got {m and m.group(1)}"
    )
