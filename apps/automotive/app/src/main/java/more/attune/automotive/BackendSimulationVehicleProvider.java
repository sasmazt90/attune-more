package more.attune.automotive;

import android.os.Handler;
import android.os.SystemClock;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/** Reuses GET /api/vehicle/state and POST /api/vehicle/speed; no second simulation model. */
public final class BackendSimulationVehicleProvider implements VehicleDataProvider {
    private final String apiOrigin;
    private final Handler main;
    private final AtomicInteger generation = new AtomicInteger();
    private final AtomicInteger revision = new AtomicInteger();
    private final AtomicBoolean updating = new AtomicBoolean();
    private ScheduledExecutorService executor;
    private volatile HttpURLConnection inFlight;

    public BackendSimulationVehicleProvider(String apiOrigin, Handler main) {
        new OriginPolicy(apiOrigin, true);
        this.apiOrigin = apiOrigin;
        this.main = main;
    }

    @Override public void start(Listener listener) {
        stop();
        int epoch = generation.incrementAndGet();
        executor = Executors.newSingleThreadScheduledExecutor();
        listener.onObservation(null);
        executor.scheduleWithFixedDelay(() -> {
            if (epoch != generation.get() || updating.get()) return;
            int requestRevision = revision.get();
            VehicleSnapshot snapshot;
            try { snapshot = request("GET", "/api/vehicle/state", null); }
            catch (Exception error) { snapshot = null; }
            publish(listener, snapshot, epoch, requestRevision);
        }, 0, 1, TimeUnit.SECONDS);
        activeListener = listener;
    }

    private Listener activeListener;

    /** Debug UI only. Invalidates old reads before queuing the existing backend mutation. */
    public void setSpeed(double speed) {
        if (!BuildConfig.BACKEND_SIMULATION || !Double.isFinite(speed) || speed < 0
                || executor == null || !updating.compareAndSet(false, true)) return;
        int epoch = generation.get();
        int requestRevision = revision.incrementAndGet();
        Listener listener = activeListener;
        if (listener == null) { updating.set(false); return; }
        listener.onObservation(null);
        executor.execute(() -> {
            if (epoch != generation.get()) return;
            VehicleSnapshot snapshot;
            try { snapshot = request("POST", "/api/vehicle/speed", new JSONObject().put("speedKmH", speed)); }
            catch (Exception error) { snapshot = null; }
            if (epoch == generation.get()) updating.set(false);
            publish(listener, snapshot, epoch, requestRevision);
        });
    }

    public boolean isUpdating() { return updating.get(); }

    private void publish(Listener listener, VehicleSnapshot snapshot, int epoch, int requestRevision) {
        main.post(() -> {
            if (epoch == generation.get() && requestRevision == revision.get()) {
                listener.onObservation(snapshot);
            }
        });
    }

    private VehicleSnapshot request(String method, String path, JSONObject body) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(apiOrigin + path).openConnection();
        inFlight = connection;
        try {
            connection.setConnectTimeout(2000);
            connection.setReadTimeout(2000);
            connection.setInstanceFollowRedirects(false);
            connection.setUseCaches(false);
            connection.setRequestMethod(method);
            if (body != null) {
                byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setFixedLengthStreamingMode(bytes.length);
                try (java.io.OutputStream stream = connection.getOutputStream()) { stream.write(bytes); }
            }
            if (connection.getResponseCode() != 200) throw new IllegalStateException("Backend unavailable");
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream stream = connection.getInputStream()) {
                byte[] block = new byte[4096];
                int count;
                while ((count = stream.read(block)) != -1) {
                    if (bytes.size() + count > 65536) throw new IllegalStateException("Oversized observation");
                    bytes.write(block, 0, count);
                }
            }
            JSONObject value = new JSONObject(bytes.toString(StandardCharsets.UTF_8.name()));
            Object speed = value.get("currentSpeed"), moving = value.get("vehicleMoving"), parked = value.get("vehicleParked");
            if (!(speed instanceof Number) || !(moving instanceof Boolean) || !(parked instanceof Boolean)) {
                throw new IllegalArgumentException("Invalid observation types");
            }
            return new VehicleSnapshot(((Number) speed).doubleValue(), (Boolean) moving, (Boolean) parked,
                value.getString("gear"), SystemClock.elapsedRealtime());
        } finally {
            connection.disconnect();
            if (inFlight == connection) inFlight = null;
        }
    }

    @Override public void stop() {
        generation.incrementAndGet();
        revision.incrementAndGet();
        activeListener = null;
        updating.set(false);
        if (inFlight != null) inFlight.disconnect();
        if (executor != null) { executor.shutdownNow(); executor = null; }
    }

    @Override public String label() { return "Backend simülasyonu — gerçek araç sinyali değildir"; }
}
