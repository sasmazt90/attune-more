package more.attune.prototype.mentalqwen;

import android.car.Car;
import android.car.drivingstate.CarUxRestrictions;
import android.car.drivingstate.CarUxRestrictionsManager;
import android.content.Context;
import android.os.Handler;

/** Same rule as the product AAOS app (CarRestrictionSource): parked only when the platform requires no distraction
 *  optimization; anything unknown counts as NOT parked. */
final class ParkGate {
    interface Listener { void onParked(boolean parked); }
    private Car car;
    private CarUxRestrictionsManager manager;

    void start(Context context, Handler main, Listener listener) {
        listener.onParked(false);
        try {
            car = Car.createCar(context, main, Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT, (connected, ready) -> {
                if (!ready) { listener.onParked(false); return; }
                try {
                    manager = (CarUxRestrictionsManager) connected.getCarManager(Car.CAR_UX_RESTRICTION_SERVICE);
                    if (manager == null) { listener.onParked(false); return; }
                    manager.registerListener(r -> listener.onParked(parked(r)));
                    listener.onParked(parked(manager.getCurrentCarUxRestrictions()));
                } catch (RuntimeException | LinkageError e) { listener.onParked(false); }
            });
        } catch (RuntimeException | LinkageError e) { listener.onParked(false); }
    }
    private static boolean parked(CarUxRestrictions r) {
        try { return r != null && !r.isRequiresDistractionOptimization(); } catch (RuntimeException | LinkageError e) { return false; }
    }
    void stop() {
        if (manager != null) { try { manager.unregisterListener(); } catch (RuntimeException | LinkageError ignored) { } manager = null; }
        if (car != null) { try { car.disconnect(); } catch (RuntimeException | LinkageError ignored) { } car = null; }
    }
}
