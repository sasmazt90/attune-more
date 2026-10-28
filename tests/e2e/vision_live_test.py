"""Current Vision acceptance entrypoint: sequential speech turns.

The simultaneous-playback regression was superseded by the owner's sequential
voice requirement. See vision_conversation.py for evidence boundaries.
"""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('vision_conversation.py')),run_name='__main__')
