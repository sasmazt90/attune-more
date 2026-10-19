package more.attune.validation;

import android.app.Instrumentation;
import android.car.Car;
import android.car.drivingstate.CarUxRestrictions;
import android.car.drivingstate.CarUxRestrictionsManager;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Test-only observer of real Car APIs. No VHAL writes or restriction overrides. */
public final class RestrictionProbe extends Instrumentation {
    @Override public void onCreate(Bundle args) { super.onCreate(args); start(); }

    @Override public void onStart() {
        Bundle result = new Bundle();
        CountDownLatch done = new CountDownLatch(1);
        Car car = null;
        try {
            PackageManager pm = getContext().getPackageManager();
            result.putString("automotive", Boolean.toString(pm.hasSystemFeature("android.hardware.type.automotive")));
            result.putString("camera", Boolean.toString(pm.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)));
            result.putString("microphone", Boolean.toString(pm.hasSystemFeature(PackageManager.FEATURE_MICROPHONE)));
            String target = "more.attune.automotive.prototype.debug";
            result.putString("cameraPermission", pm.checkPermission("android.permission.CAMERA", target)
                == PackageManager.PERMISSION_GRANTED ? "granted" : "denied");
            result.putString("microphonePermission", pm.checkPermission("android.permission.RECORD_AUDIO", target)
                == PackageManager.PERMISSION_GRANTED ? "granted" : "denied");
            car = Car.createCar(getContext(), new Handler(Looper.getMainLooper()),
                Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT, (connected, ready) -> {
                    if (!ready) { result.putString("error", "Car service unavailable"); done.countDown(); return; }
                    try {
                        CarUxRestrictionsManager manager = (CarUxRestrictionsManager) connected.getCarManager(Car.CAR_UX_RESTRICTION_SERVICE);
                        CarUxRestrictions ux = manager.getCurrentCarUxRestrictions();
                        if (ux == null) result.putString("error", "No UX restriction observation");
                        else {
                            result.putString("doRequired", Boolean.toString(ux.isRequiresDistractionOptimization()));
                            result.putString("restrictionFlags", Integer.toString(ux.getActiveRestrictions()));
                        }
                    } catch (RuntimeException error) { result.putString("error", error.toString()); }
                    finally { done.countDown(); }
                });
            if (!done.await(10, TimeUnit.SECONDS)) result.putString("error", "Car service timeout");
        } catch (Exception error) { result.putString("error", error.toString()); }
        finally {
            if (car != null) car.disconnect();
            finish(result.containsKey("error") ? 0 : -1, result);
        }
    }
}
