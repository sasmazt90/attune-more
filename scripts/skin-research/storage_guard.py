"""Local storage safety only; never alters labels, sampling, loss or acceptance."""
import os, shutil
from pathlib import Path

DEFAULT_RESERVE_BYTES = 2 * 1024**3

def checkpoint_storage_pause(folder):
    reserve = max(DEFAULT_RESERVE_BYTES, int(os.environ.get('TOGG_CHECKPOINT_RESERVE_BYTES', str(DEFAULT_RESERVE_BYTES))))
    free = shutil.disk_usage(folder).free
    requested = (Path(folder) / 'STORAGE_PAUSE').exists() or (Path(folder).parent / 'STORAGE_PAUSE').exists()
    if free >= reserve and not requested:
        return None
    return dict(actualFreeBytes=free, requiredReserveBytes=reserve, storagePauseRequested=requested, disk=str(Path(folder).resolve().anchor))
