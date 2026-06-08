import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/ingestor-service')))

from services import calculate_severity

@pytest.mark.parametrize("kp_value, expected_severity", [
    (0, "low"),
    (4, "low"),
    (5, "moderate"),
    (7, "moderate")
])
def test_rn1_severity_low_and_moderate(kp_value, expected_severity):
    event_flat = {"kpIndex": kp_value}
    sev, emerg = calculate_severity(event_flat)
    assert sev == expected_severity
    assert emerg is False
    
@pytest.mark.parametrize("kp_value", [8, 9])
def test_rn1_severity_severe(kp_value):
    event_nested = {"allKpIndex": [{"kpIndex": 1}, {"kpIndex": kp_value}]}
    sev, emerg = calculate_severity(event_nested)
    assert sev == "severe"
    assert emerg is True