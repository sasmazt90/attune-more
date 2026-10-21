package more.attune.automotive;

/** Future authorized adapters supply fresh observations; no writable vehicle API is exposed. */
public interface VehicleDataProvider {
    interface Listener { void onObservation(VehicleSnapshot observation); }
    void start(Listener listener);
    void stop();
    String label();
}
