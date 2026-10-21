package more.attune.automotive;

import android.car.Car;
import android.car.drivingstate.CarUxRestrictions;
import android.car.drivingstate.CarUxRestrictionsManager;
import android.content.Context;
import android.os.Handler;

/** Uses display UX restrictions, never speed/gear as a substitute for Android policy. */
public final class CarRestrictionSource {
    public interface Listener { void onRestrictions(GatePolicy.Platform restrictions); }
    // Keep this facade free of Car-typed fields and method signatures. ART can
    // load it even if a broken/non-AAOS platform has no android.car classes.
    private interface Connection { void start(Listener listener); void stop(); }
    private final Context context;
    private final Handler main;
    private Connection connection;
    private int generation;

    public CarRestrictionSource(Context context, Handler main) { this.context = context; this.main = main; }

    public void start(Listener listener) {
        stop();
        final int epoch = ++generation;
        listener.onRestrictions(GatePolicy.Platform.UNKNOWN);
        try {
            connection = new PlatformConnection(context, main);
            connection.start(value -> {
                if (epoch == generation) listener.onRestrictions(value);
            });
        } catch (RuntimeException | LinkageError error) {
            stop();
            listener.onRestrictions(GatePolicy.Platform.UNKNOWN);
        }
    }

    public void stop() {
        generation++;
        Connection previous = connection;
        connection = null;
        if (previous != null) {
            try { previous.stop(); } catch (RuntimeException | LinkageError ignored) { }
        }
    }

    /** Loaded only inside the guarded start path; still uses the public Car APIs. */
    private static final class PlatformConnection implements Connection {
        private final Context context;
        private final Handler main;
        private Car car;
        private CarUxRestrictionsManager manager;
        private int generation;
        private int connectionGeneration;

        PlatformConnection(Context context, Handler main) { this.context = context; this.main = main; }

        @Override public void start(Listener listener) {
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
                    } catch (RuntimeException | LinkageError error) { listener.onRestrictions(GatePolicy.Platform.UNKNOWN); }
                });
            } catch (RuntimeException | LinkageError error) { listener.onRestrictions(GatePolicy.Platform.UNKNOWN); }
        }

        private static GatePolicy.Platform convert(CarUxRestrictions value) {
            if (value == null) return GatePolicy.Platform.UNKNOWN;
            try {
                return value.isRequiresDistractionOptimization()
                    ? GatePolicy.Platform.RESTRICTED : GatePolicy.Platform.UNRESTRICTED;
            } catch (RuntimeException | LinkageError error) { return GatePolicy.Platform.UNKNOWN; }
        }

        @Override public void stop() {
            generation++;
            connectionGeneration++;
            if (manager != null) {
                try { manager.unregisterListener(); } catch (RuntimeException | LinkageError ignored) { }
                manager = null;
            }
            if (car != null) {
                try { car.disconnect(); } catch (RuntimeException | LinkageError ignored) { }
                car = null;
            }
        }
    }
}
