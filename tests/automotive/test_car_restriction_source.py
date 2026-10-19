"""Execute the real CarRestrictionSource with host fixtures, including no Car classes.

These tests prove Java failure paths and GatePolicy composition, not ART, Binder,
Android lifecycle or OEM compatibility. No SDK implementations are packaged.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
JAVA = ROOT / 'apps/automotive/app/src/main/java/more/attune/automotive'
FIXTURES = {
    'android/content/Context.java': 'package android.content; public class Context {}',
    'android/os/Handler.java': 'package android.os; public class Handler {}',
    'android/car/Car.java': '''package android.car;
import android.content.Context; import android.os.Handler;
import android.car.drivingstate.CarUxRestrictionsManager;
public class Car {
 public static final long CAR_WAIT_TIMEOUT_DO_NOT_WAIT=0;
 public static final String CAR_UX_RESTRICTION_SERVICE="ux";
 public interface CarServiceLifecycleListener { void onLifecycleChanged(Car car, boolean ready); }
 public static CarServiceLifecycleListener callback;
 public static Throwable createFailure, managerFailure, disconnectFailure;
 public static Car instance;
 public static CarUxRestrictionsManager manager;
 public static void fail(Throwable t) { if(t instanceof Error) throw (Error)t; if(t!=null) throw (RuntimeException)t; }
 public static Car createCar(Context c, Handler h, long timeout, CarServiceLifecycleListener listener) {
  fail(createFailure); callback=listener; return instance=new Car();
 }
 public Object getCarManager(String name) { fail(managerFailure); return manager; }
 public void disconnect() { fail(disconnectFailure); }
}''',
    'android/car/drivingstate/CarUxRestrictions.java': '''package android.car.drivingstate;
public class CarUxRestrictions {
 public static Throwable failure;
 private final boolean restricted;
 public CarUxRestrictions(boolean value) { restricted=value; }
 public boolean isRequiresDistractionOptimization() { android.car.Car.fail(failure); return restricted; }
}''',
    'android/car/drivingstate/CarUxRestrictionsManager.java': '''package android.car.drivingstate;
import android.car.Car;
public class CarUxRestrictionsManager {
 public interface OnUxRestrictionsChangedListener { void onUxRestrictionsChanged(CarUxRestrictions ux); }
 public OnUxRestrictionsChangedListener listener;
 public CarUxRestrictions current;
 public Throwable readFailure, registerFailure, unregisterFailure;
 public void registerListener(OnUxRestrictionsChangedListener l) { Car.fail(registerFailure); listener=l; }
 public void unregisterListener() { Car.fail(unregisterFailure); }
 public CarUxRestrictions getCurrentCarUxRestrictions() { Car.fail(readFailure); return current; }
}''',
    'more/attune/automotive/CarAbsentChecks.java': '''package more.attune.automotive;
import java.util.*;
public class CarAbsentChecks {
 public static void main(String[] args) throws Exception {
  try { Class.forName("android.car.Car"); throw new AssertionError("Car fixture unexpectedly present"); }
  catch (ClassNotFoundException expected) { }
  var source=new CarRestrictionSource(new android.content.Context(),new android.os.Handler());
  var states=new ArrayList<GatePolicy.Platform>();
  for(int i=0;i<2;i++) {
   source.start(states::add); source.stop();
  }
  if(states.isEmpty() || states.stream().anyMatch(s -> s!=GatePolicy.Platform.UNKNOWN))
   throw new AssertionError("Missing Car classes did not remain UNKNOWN: "+states);
  for(var state:states) {
   var reason=GatePolicy.evaluate(true,state,new VehicleSnapshot(0,false,true,"P",100),100);
   if(reason!=GatePolicy.Reason.PLATFORM_UNKNOWN) throw new AssertionError("Missing API unlocked gate");
   if(MediaPermissionPolicy.eligible(new String[]{MediaPermissionPolicy.AUDIO},true,
      reason==GatePolicy.Reason.READY,true,true)) throw new AssertionError("Missing API allowed media");
  }
  System.out.println("PASS: real source loads without any android.car classes; restart/stop remain UNKNOWN, gate/media locked");
 }
}''',
    'more/attune/automotive/CarSourceChecks.java': '''package more.attune.automotive;
import android.car.Car; import android.car.drivingstate.*; import java.util.*;
public class CarSourceChecks {
 static int checks;
 static void require(boolean ok,String why) { checks++; if(!ok) throw new AssertionError(why); }
 static GatePolicy.Platform last(List<GatePolicy.Platform> states) { return states.get(states.size()-1); }
 public static void main(String[] args) {
  var source=new CarRestrictionSource(new android.content.Context(),new android.os.Handler());
  var states=new ArrayList<GatePolicy.Platform>();
  for(Throwable failure:new Throwable[]{new SecurityException("denied"),new NoClassDefFoundError("no Car"),
      new NoSuchMethodError("old API"),new ExceptionInInitializerError("broken platform")}) {
   Car.createFailure=failure; source.start(states::add);
   require(last(states)==GatePolicy.Platform.UNKNOWN,"create failure must lock"); source.stop();
  }
  Car.createFailure=null; source.start(states::add);
  require(last(states)==GatePolicy.Platform.UNKNOWN,"no connection must lock");
  Car.callback.onLifecycleChanged(Car.instance,false);
  require(last(states)==GatePolicy.Platform.UNKNOWN,"not-ready must lock");
  Car.manager=null; Car.callback.onLifecycleChanged(Car.instance,true);
  require(last(states)==GatePolicy.Platform.UNKNOWN,"missing manager must lock");
  Car.manager=new CarUxRestrictionsManager();
  for(Throwable failure:new Throwable[]{new SecurityException("denied"),new NoSuchMethodError("old API")}) {
   Car.managerFailure=failure; Car.callback.onLifecycleChanged(Car.instance,true);
   require(last(states)==GatePolicy.Platform.UNKNOWN,"manager failure must lock");
   Car.managerFailure=null; Car.manager.registerFailure=failure;
   Car.callback.onLifecycleChanged(Car.instance,true);
   require(last(states)==GatePolicy.Platform.UNKNOWN,"registration failure must lock");
   Car.manager.registerFailure=null; Car.manager.readFailure=failure;
   Car.callback.onLifecycleChanged(Car.instance,true);
   require(last(states)==GatePolicy.Platform.UNKNOWN,"read failure must lock");
   Car.manager.readFailure=null;
  }
  Car.callback.onLifecycleChanged(Car.instance,true);
  require(last(states)==GatePolicy.Platform.UNKNOWN,"null restriction must lock");
  Car.manager.current=new CarUxRestrictions(false); Car.callback.onLifecycleChanged(Car.instance,true);
  require(last(states)==GatePolicy.Platform.UNRESTRICTED,"positive Car observation required");
  var listener=Car.manager.listener; var callback=Car.callback; var car=Car.instance;
  CarUxRestrictions.failure=new NoSuchMethodError("missing restriction method");
  listener.onUxRestrictionsChanged(new CarUxRestrictions(false));
  require(last(states)==GatePolicy.Platform.UNKNOWN,"asynchronous API failure must lock");
  CarUxRestrictions.failure=null;
  listener.onUxRestrictionsChanged(new CarUxRestrictions(true));
  require(last(states)==GatePolicy.Platform.RESTRICTED,"Car restriction must override Park");
  Car.callback.onLifecycleChanged(Car.instance,false);
  int count=states.size(); listener.onUxRestrictionsChanged(new CarUxRestrictions(false));
  require(states.size()==count && last(states)==GatePolicy.Platform.UNKNOWN,"stale connection cannot unlock");
  Car.manager.unregisterFailure=new SecurityException("cleanup denied");
  Car.disconnectFailure=new NoSuchMethodError("cleanup API absent"); source.stop();
  callback.onLifecycleChanged(car,true); listener.onUxRestrictionsChanged(new CarUxRestrictions(false));
  require(states.size()==count,"stop invalidates every callback despite cleanup failures");
  source.start(states::add); require(last(states)==GatePolicy.Platform.UNKNOWN,"restart begins unknown");
  for(var state:new GatePolicy.Platform[]{GatePolicy.Platform.UNKNOWN,GatePolicy.Platform.RESTRICTED}) {
   require(GatePolicy.evaluate(true,state,new VehicleSnapshot(0,false,true,"P",100),100)!=GatePolicy.Reason.READY,
    "backend Park cannot substitute for Car policy");
  }
  source.stop(); System.out.println("PASS "+checks+" real Car source failure, restriction, stale callback and restart checks (host fixtures)");
 }
}''',
}


@unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK compiler required')
class CarSourceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='attune-car-source-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        paths = []
        for name, content in FIXTURES.items():
            path = cls.root / 'src' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            paths.append(str(path))
        cls.classes = cls.root / 'classes'
        subprocess.run(['javac', '-source', '17', '-target', '17', '-Xlint:-options', '-d', str(cls.classes),
                        *(str(JAVA / (name + '.java')) for name in
                          ('CarRestrictionSource', 'GatePolicy', 'VehicleSnapshot', 'MediaPermissionPolicy')),
                        *paths], check=True, capture_output=True, text=True)

    def test_real_source_handles_failures_and_stale_callbacks(self):
        result = subprocess.run(['java', '-cp', str(self.classes), 'more.attune.automotive.CarSourceChecks'],
                                check=True, capture_output=True, text=True)
        self.assertIn('PASS ', result.stdout)
        print(result.stdout.strip())

    def test_real_source_loads_and_locks_with_all_car_classes_absent(self):
        absent = self.root / 'without-car'
        shutil.copytree(self.classes, absent)
        shutil.rmtree(absent / 'android/car')
        result = subprocess.run(['java', '-cp', str(absent), 'more.attune.automotive.CarAbsentChecks'],
                                check=True, capture_output=True, text=True)
        self.assertIn('without any android.car classes', result.stdout)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
