#!/usr/bin/env python
"""First frame of a controlled I420 y4m fixture as JPEG, for the injected AAOS test camera.

    python extract_y4m_jpeg.py fixture.y4m out.jpg
"""
import sys

import cv2
import numpy as np


def main():
    raw = open(sys.argv[1], 'rb').read()
    end = raw.index(b'\n')
    fields = raw[:end].split()
    width = int(next(f[1:] for f in fields if f.startswith(b'W')))
    height = int(next(f[1:] for f in fields if f.startswith(b'H')))
    start = raw.index(b'\n', end + 1) + 1
    size = width * height * 3 // 2
    i420 = np.frombuffer(raw, np.uint8, size, start).reshape(height * 3 // 2, width)
    image = cv2.cvtColor(i420, cv2.COLOR_YUV2BGR_I420)
    if not cv2.imwrite(sys.argv[2], image, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise SystemExit('JPEG write failed')
    print(width, height)


if __name__ == '__main__':
    main()
