#!/usr/bin/env python3
"""Native PARK and DRIVE gates on the Android 15 emulator. Backend simulation and emulated VHAL, not a vehicle.

Writes /var/lib/attune/evidence/native-gates.json. Run as root on the AAOS host with the attune venv.
"""
import subprocess,json,time,pathlib,urllib.request
from playwright.sync_api import sync_playwright
adb='/opt/android-sdk/platform-tools/adb';pkg='more.attune.automotive.prototype.clouddemo';component=pkg+'/more.attune.automotive.MainActivity'
r={'scope':'Actual Android 15 native app; backend simulation and emulated VHAL, not a physical vehicle','checks':[]}
def shell(*a):return subprocess.check_output([adb,'-s','emulator-5554','shell',*a],text=True,timeout=30).strip()
def dump():shell('uiautomator','dump','/sdcard/attune-qa-window.xml');return shell('cat','/sdcard/attune-qa-window.xml')
def wait(web,seconds=20):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  xml=dump()
  if ('android.webkit.WebView' in xml)==web:return True
  time.sleep(1)
 return False
def check(name,value):r['checks'].append({'name':name,'pass':bool(value)});print(json.dumps(r['checks'][-1]),flush=True)
def speed(n):
 req=urllib.request.Request('http://127.0.0.1:3000/api/vehicle/speed',data=json.dumps({'speedKmH':n}).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=10) as f:return json.load(f)
try:
 r['runtime']={'sdk':shell('getprop','ro.build.version.sdk'),'memory':shell('cat','/proc/meminfo').splitlines()[0],'display':shell('wm','size')}
 check('Initial PARK has native WebView',wait(True))
 speed(75);check('Backend DRIVE destroys native WebView',wait(False,15))
 speed(0);check('Backend PARK restores native WebView',wait(True,25))
 shell('input','keyevent','KEYCODE_HOME');time.sleep(2);check('HOME backgrounds activity',pkg not in shell('dumpsys','activity','top').split('ACTIVITY ')[-1][:200])
 shell('am','start','-W','--user','current','-n',component);check('Foreground reopens gated WebView',wait(True,25))
 shell('cmd','car_service','inject-vhal-event','GEAR_SELECTION','8');shell('cmd','car_service','inject-vhal-event','PARKING_BRAKE_ON','false');shell('cmd','car_service','inject-vhal-event','PERF_VEHICLE_SPEED','12.0');check('Native emulated VHAL driving blocks WebView',wait(False,15))
finally:
 shell('cmd','car_service','inject-vhal-event','PERF_VEHICLE_SPEED','0.0');shell('cmd','car_service','inject-vhal-event','GEAR_SELECTION','4');shell('cmd','car_service','inject-vhal-event','PARKING_BRAKE_ON','true');speed(0)
 shell('am','start','-W','--user','current','-n',component);check('Native PARK restores after VHAL driving',wait(True,25))
 pid=shell('pidof',pkg).split()[0];subprocess.run([adb,'-s','emulator-5554','forward','tcp:9222','localabstract:webview_devtools_remote_'+pid],check=True)
 r['status']='PASS' if all(x['pass'] for x in r['checks']) else 'PARTIAL';pathlib.Path('/var/lib/attune/evidence/native-gates.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
