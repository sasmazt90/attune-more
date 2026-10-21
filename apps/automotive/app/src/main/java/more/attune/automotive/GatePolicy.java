package more.attune.automotive;

/** Android's display-specific restrictions and the existing application gate are independent. */
public final class GatePolicy {
    public enum Platform { UNKNOWN, RESTRICTED, UNRESTRICTED }
    public enum Reason { BACKGROUND, PLATFORM_UNKNOWN, PLATFORM_RESTRICTED,
        VEHICLE_UNKNOWN, VEHICLE_STALE, VEHICLE_MOVING, NOT_PARKED, READY }
    public static final long MAX_OBSERVATION_AGE_MS = 2500;

    private GatePolicy() {}

    public static Reason evaluate(boolean foreground, Platform platform,
                                  VehicleSnapshot vehicle, long nowMillis) {
        if (!foreground) return Reason.BACKGROUND;
        if (platform == null || platform == Platform.UNKNOWN) return Reason.PLATFORM_UNKNOWN;
        if (platform == Platform.RESTRICTED) return Reason.PLATFORM_RESTRICTED;
        if (vehicle == null) return Reason.VEHICLE_UNKNOWN;
        if (nowMillis < vehicle.observedAtMillis
                || nowMillis - vehicle.observedAtMillis > MAX_OBSERVATION_AGE_MS) {
            return Reason.VEHICLE_STALE;
        }
        if (vehicle.moving || vehicle.speedKmh > 0) return Reason.VEHICLE_MOVING;
        if (!vehicle.parked || !"P".equals(vehicle.gear)) return Reason.NOT_PARKED;
        return Reason.READY;
    }
}
