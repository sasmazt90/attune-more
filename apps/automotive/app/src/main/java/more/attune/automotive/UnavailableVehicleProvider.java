package more.attune.automotive;

/** Production placeholder: never promotes the backend demo to a real vehicle signal. */
public final class UnavailableVehicleProvider implements VehicleDataProvider {
    @Override public void start(Listener listener) { listener.onObservation(null); }
    @Override public void stop() {}
    @Override public String label() { return "Yetkili araç sağlayıcısı entegre değil"; }
}
