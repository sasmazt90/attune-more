"""Approved spoken UI and actual camera replace guided rotary trials.
No injected transcript or fabricated score; positive voice acceptance is manual.
"""
import runpy
runpy.run_path('tests/e2e/continuous_vision_contract.py',run_name='__main__')
runpy.run_path('tests/e2e/vision_camera_followup.py',run_name='__main__')
