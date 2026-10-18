"""Capture only the foreground Chrome window owned by this test profile."""
import base64, ctypes, os, subprocess
from ctypes import wintypes
from pathlib import Path
import psutil


def capture_owned_window(page, profile, destination, *, maximize=True):
    assert os.name == 'nt'
    user = ctypes.windll.user32
    user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    page.bring_to_front()
    owned = set()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() != 'chrome.exe':
                continue
            command = proc.cmdline()
            if any(str(profile) in arg for arg in command):
                owned.add(proc.pid)
                owned.update(child.pid for child in proc.children(recursive=True))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    assert owned, 'No owned browser process found'
    user.GetForegroundWindow.restype = wintypes.HWND
    handles = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(handle, _):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if pid.value in owned and user.IsWindowVisible(handle):
            name = ctypes.create_unicode_buffer(200)
            user.GetClassNameW(handle, name, 200)
            bounds = wintypes.RECT()
            user.GetWindowRect(handle, ctypes.byref(bounds))
            if name.value == 'Chrome_WidgetWin_1' and bounds.right-bounds.left > 400 and bounds.bottom-bounds.top > 400:
                handles.append(handle)
        return True
    user.EnumWindows(callback_type(visit), 0)
    assert len(handles) == 1, f'Ambiguous owned visible browser window: {len(handles)}'
    handle = handles[0]
    previous = user.GetForegroundWindow()
    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    foreground_thread = user.GetWindowThreadProcessId(previous, None)
    attached = user.AttachThreadInput(current_thread, foreground_thread, True)
    user.ShowWindow(handle, 3 if maximize else 1)
    user.SetForegroundWindow(handle)
    if attached:
        user.AttachThreadInput(current_thread, foreground_thread, False)
    page.wait_for_timeout(250)
    foreground = user.GetForegroundWindow() == handle
    if not foreground:
        # Windows may deny focus to a background automation process. Capture
        # this exact owned HWND instead of reading the foreground/desktop.
        from PIL import ImageGrab
        bounds = wintypes.RECT()
        assert user.GetWindowRect(handle, ctypes.byref(bounds))
        expected_sizes={(bounds.right-bounds.left, bounds.bottom-bounds.top)}
        visible_bounds=wintypes.RECT()
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(handle,9,ctypes.byref(visible_bounds),ctypes.sizeof(visible_bounds))==0:
            expected_sizes.add((visible_bounds.right-visible_bounds.left,visible_bounds.bottom-visible_bounds.top))
        # Chrome's compositor can briefly return a blank PrintWindow frame
        # after focus/scroll. Retry this same verified HWND; never substitute
        # a desktop or unrelated foreground-window capture.
        for attempt in range(5):
            image = ImageGrab.grab(window=handle)
            # Narrow windows are valid. If Windows exports mismatched bounds,
            # use the existing explicitly labelled compositor path below.
            if image.size in expected_sizes and any(hi-lo > 20 for lo, hi in image.getextrema()):
                break
            page.wait_for_timeout(500)
        else:
            # Browser compositor capture is the preferred browser-specific
            # evidence when Windows PrintWindow cannot render an occluded GPU
            # surface. This is still this running headed Chrome with its native
            # zoom preference; it is never labelled an OS/window screenshot.
            # Omit a clip: CDP/PW CSS clip coordinates can differ from native
            # browser-zoom coordinates after scrolling. Capture this page's
            # actual visible compositor surface without any resize/retouch.
            session = page.context.new_cdp_session(page)
            try:
                captured = session.send('Page.captureScreenshot', {
                    'format': 'png', 'fromSurface': True,
                    'captureBeyondViewport': False})
                Path(destination).write_bytes(base64.b64decode(captured['data']))
            finally:
                session.detach()
            from PIL import Image
            with Image.open(destination) as browser_image:
                assert any(hi-lo > 20 for lo, hi in browser_image.getextrema())
                dimensions = page.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,css:document.body.style.zoom||"1"})')
                assert dimensions['css'] == '1'
                # CDP screenshot export does not necessarily multiply native
                # browser zoom into its bitmap dimensions. Keep actual export
                # pixels distinct from HWND pixels and native DOM/DPR evidence.
                assert browser_image.width > 200 and browser_image.height > 200
                pixels = list(browser_image.size)
            return {'ownedWindow': True, 'ownedForeground': False,
                    'nativeWindowCapture': False, 'browserCompositorCapture': True,
                    'browserExportPixels': pixels, 'dimensions': dimensions,
                    'capture': 'Headed Chrome compositor at actual native zoom; Windows HWND was blank or had mismatched bounds',
                    'windowsExportPixels':list(image.size),'expectedHWNDPixels':[list(v) for v in expected_sizes],
                    'compositorRetries': 5}
        image.save(destination)
        return {'ownedWindow': True, 'ownedForeground': False,
                'windowPhysicalPixels': list(image.size),
                'capture': 'Windows exact owned HWND via Pillow ImageGrab; focus denied',
                'compositorRetries': attempt}
    rect = wintypes.RECT()
    assert user.GetClientRect(handle, ctypes.byref(rect))
    point = wintypes.POINT(0, 0)
    assert user.ClientToScreen(handle, ctypes.byref(point))
    region = f'{point.x},{point.y},{rect.right},{rect.bottom}'
    script = Path(os.environ['USERPROFILE']) / '.codex/skills/screenshot/scripts/take_screenshot.ps1'
    # Explicit physical client bounds exclude desktop, taskbar and unrelated apps.
    subprocess.run(['powershell.exe', '-NoProfile', '-File', str(script),
                    '-Region', region, '-Path', str(Path(destination).resolve())], check=True,
                   stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    from PIL import Image
    with Image.open(destination) as image:
        assert image.size == (rect.right, rect.bottom)
    return {'ownedForeground': True, 'clientPhysicalPixels': [rect.right, rect.bottom],
            'capture': 'Windows CopyFromScreen, owned Chrome client only'}
