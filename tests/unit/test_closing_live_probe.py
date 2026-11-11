"""Live closing probe (scripts/mental_closing_abc/closing_live_probe.py): which closings may be measured. A process whose
start-up warm-up did not finish successfully for every required profile is blocked; its closings never run and never
enter the cold, prepared or warm numbers. No servers are started here."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/mental_closing_abc'))
from closing_live_probe import build_plan, warm_gate  # noqa: E402

OK = {'profile': 'default', 'ok': True, 'start': 'cold', 'seconds': 14.2}
FEMALE = {'profile': 'female-calm-v1', 'ok': True, 'start': 'warm', 'seconds': 13.1}


@pytest.mark.parametrize('result,profiles,expected', [
    ({'rows': [OK, FEMALE], 'waitedSeconds': 30}, ['default', 'female-calm-v1'], (True, None)),
    ({'rows': [OK], 'waitedSeconds': 12}, ['default'], (True, None)),
    ({'rows': [OK], 'waitedSeconds': 300, 'timeout': True}, ['default', 'female-calm-v1'], (False, 'warm-up-timeout')),
    ({'rows': [OK, {**FEMALE, 'ok': False}]}, ['default', 'female-calm-v1'], (False, 'warm-up-failed:female-calm-v1')),
    ({'rows': [{**OK, 'ok': False}]}, ['default', 'female-calm-v1'], (False, 'warm-up-failed:default')),
    ({'rows': [OK]}, ['default', 'female-calm-v1'], (False, 'warm-up-missing:female-calm-v1')),
    ({'rows': []}, ['default'], (False, 'warm-up-missing:default')),
    ({}, ['default'], (False, 'warm-up-missing:default')),
])
def test_closings_are_measured_only_after_every_required_warm_up_succeeded(result, profiles, expected):
    assert warm_gate(result, profiles) == expected


def test_plan_requires_the_closing_voice_only_for_prepared_processes_and_puts_warm_runs_last():
    plan = build_plan(['tr', 'en'], 3, 3, 8)
    tr = [p for p in plan if p['language'] == 'tr']
    assert [p['kind'] for p in tr] == ['cold'] * 3 + ['prepared'] * 3
    assert all(p['required'] == ['default'] for p in tr if p['kind'] == 'cold')
    assert all(p['required'] == ['default', 'female-calm-v1'] for p in tr if p['kind'] == 'prepared')
    assert [len(p['closings']) for p in tr] == [1, 1, 1, 1, 1, 9]
    assert [kind for _, kind in tr[-1]['closings']] == ['prepared'] + ['warm'] * 8
    assert len([c for p in plan for c in p['closings']]) == 2 * (3 + 3 + 8)
