package more.attune.automotive;

/** Minimal read-only safety data. No driver identity, location, or health data. */
public final class VehicleSnapshot {
    public final double speedKmh;
    public final boolean moving;
    public final boolean parked;
    public final String gear;
    public final long observedAtMillis;

    public VehicleSnapshot(double speedKmh, boolean moving, boolean parked,
                           String gear, long observedAtMillis) {
        if (!Double.isFinite(speedKmh) || speedKmh < 0 || moving != (speedKmh > 0)
                || moving == parked || gear == null || !gear.matches("[PRND]")
                || observedAtMillis < 0) {
            throw new IllegalArgumentException("Invalid vehicle observation");
        }
        this.speedKmh = speedKmh;
        this.moving = moving;
        this.parked = parked;
        this.gear = gear;
        this.observedAtMillis = observedAtMillis;
    }
}
