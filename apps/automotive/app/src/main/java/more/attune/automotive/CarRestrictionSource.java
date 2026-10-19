package more.attune.automotive;

import android.car.Car;
import android.car.drivingstate.CarUxRestrictions;
import android.car.drivingstate.CarUxRestrictionsManager;
import android.content.Context;
import android.os.Handler;

/** Uses display UX restrictions, never speed/gear as a substitute for Android policy. */
public final class CarRestrictionSource {
    public interface Listener { void onRestrictions(GatePolicy.Platform restrictions); }
    private final Context context;
    private final Handler main;
    private Car car;
    private CarUxRestrictionsManager manager;
    private int generation;
    private int connectionGeneration;

    public CarRestrictionSource(Context context, Handler main) { this.context = context; this.main = main; }

    public void start(Listener listener) {
        stop();
        final int epoch = ++generation;
        listener.onRestrictions(GatePolicy.Platform.UNKNOWN);
        try {
            car = Car.createCar(context, main, Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT, (connected, ready) -> {
                if (epoch != generation) return;
                final int connectionEpoch = ++connectionGeneration;
                if (!ready) {
                    manager = null;
                    listener.onRestrictions(GatePolicy.Platform.UNKNOWN);
                    return;
                }
                try {
                    manager = (CarUxRestrictionsManager) connected.getCarManager(Car.CAR_UX_RESTRICTION_SERVICE);
                    if (manager == null) { listener.onRestrictions(GatePolicy.Platform.UNKNOWN); return; }
                    manager.registerListener(restrictions -> {
                        if (epoch == generation && connectionEpoch == connectionGeneration) {
                            listener.onRestrictions(convert(restrictions));
                        }
                    });
                    listener.onRestrictions(convert(manager.getCurrentCarUxRestrictions()));
                } catch (RuntimeException error) { listener.onRestrictions(GatePolicy.Platform.UNKNOWN); }
            });
        } catch (RuntimeException error) { listener.onRestrictions(GatePolicy.Platform.UNKNOWN); }
    }

    private static GatePolicy.Platform convert(CarUxRestrictions value) {
        if (value == null) return GatePolicy.Platform.UNKNOWN;
        return value.isRequiresDistractionOptimization()
            ? GatePolicy.Platform.RESTRICTED : GatePolicy.Platform.UNRESTRICTED;
    }

    public void stop() {
        generation++;
        connectionGeneration++;
        if (manager != null) {
            try { manager.unregisterListener(); } catch (RuntimeException ignored) { }
            manager = null;
        }
        if (car != null) { car.disconnect(); car = null; }
    }
}
