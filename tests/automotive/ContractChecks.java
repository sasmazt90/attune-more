package more.attune.automotive;

/** Host-JVM behavioral checks: no Android SDK, emulator, vehicle, media or network needed. */
public final class ContractChecks {
    private static int checks;
    private static void check(boolean value, String description) {
        checks++;
        if (!value) throw new AssertionError(description);
    }
    private static VehicleSnapshot parked(long time) { return new VehicleSnapshot(0, false, true, "P", time); }
    private static GatePolicy.Reason gate(boolean foreground, GatePolicy.Platform platform, VehicleSnapshot state, long now) {
        return GatePolicy.evaluate(foreground, platform, state, now);
    }
    private static void invalid(Runnable action, String description) {
        boolean rejected = false;
        try { action.run(); } catch (IllegalArgumentException error) { rejected = true; }
        check(rejected, description);
    }

    public static void main(String[] args) {
        GatePolicy.Platform clear = GatePolicy.Platform.UNRESTRICTED;
        check(gate(true, clear, parked(100), 100) == GatePolicy.Reason.READY, "fresh parked observation");
        check(gate(false, clear, parked(100), 100) == GatePolicy.Reason.BACKGROUND, "background always locks");
        check(gate(true, null, parked(100), 100) == GatePolicy.Reason.PLATFORM_UNKNOWN, "missing platform is not a parked signal");
        check(gate(true, GatePolicy.Platform.UNKNOWN, parked(100), 100) == GatePolicy.Reason.PLATFORM_UNKNOWN, "no car service");
        check(gate(true, GatePolicy.Platform.RESTRICTED, parked(100), 100) == GatePolicy.Reason.PLATFORM_RESTRICTED, "platform overrides backend simulation");
        check(gate(true, clear, null, 100) == GatePolicy.Reason.VEHICLE_UNKNOWN, "network disconnect/invalid sample");
        check(gate(true, clear, parked(100), 2600) == GatePolicy.Reason.READY, "TTL boundary");
        check(gate(true, clear, parked(100), 2601) == GatePolicy.Reason.VEHICLE_STALE, "stale parked snapshot cannot unlock");
        check(gate(true, clear, parked(100), 99) == GatePolicy.Reason.VEHICLE_STALE, "clock reversal");
        check(gate(true, clear, new VehicleSnapshot(0, false, true, "N", 100), 100) == GatePolicy.Reason.NOT_PARKED, "stopped in neutral is not Park");
        for (double speed : new double[]{0.001, 1, 75, 250}) {
            check(gate(true, clear, new VehicleSnapshot(speed, true, false, "D", 100), 100) == GatePolicy.Reason.VEHICLE_MOVING, "positive speed locks " + speed);
        }
        for (double speed : new double[]{-1, Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY}) {
            invalid(() -> new VehicleSnapshot(speed, false, true, "P", 100), "reject invalid speed");
        }
        invalid(() -> new VehicleSnapshot(1, false, true, "P", 100), "reject inconsistent moving flag");
        invalid(() -> new VehicleSnapshot(0, false, false, "P", 100), "reject conflicting parked flag");
        invalid(() -> new VehicleSnapshot(0, false, true, "?", 100), "reject unknown gear");
        invalid(() -> new VehicleSnapshot(0, false, true, "P", -1), "reject invalid monotonic time");
        // Park -> moving -> Park restores eligibility only after a new positive observation.
        for (double speed : new double[]{0, 75, 0}) {
            VehicleSnapshot snapshot = new VehicleSnapshot(speed, speed > 0, speed == 0, speed > 0 ? "D" : "P", 100);
            check((gate(true, clear, snapshot, 100) == GatePolicy.Reason.READY) == (speed == 0), "transition follows observation");
            check(gate(true, clear, null, 100) != GatePolicy.Reason.READY, "mutation/restart invalidates prior state");
        }
        OriginPolicy secure = new OriginPolicy("https://app.example", false);
        for (String url : new String[]{"https://app.example/skin", "https://APP.EXAMPLE:443/profile?from=skin", "https://app.example/"}) {
            check(secure.contains(url), "same origin " + url);
        }
        for (String url : new String[]{null, "http://app.example/", "https://app.example:444/", "https://app.example.evil/", "https://evil/app.example", "https://user@app.example/", "https://app.example@evil/", "//app.example/", "file:///data/private", "content://private", "javascript:alert(1)", "data:text/html,test", "https://app.example:0/", "https://app.example:65536/"}) {
            check(!secure.contains(url), "reject untrusted origin " + url);
        }
        for (String origin : new String[]{"http://localhost:3000", "https://user@app.example", "https://app.example/path", "https://app.example?next=bad", "https://app.example#fragment", "https://app.example:0"}) {
            invalid(() -> new OriginPolicy(origin, false), "invalid release origin " + origin);
        }
        OriginPolicy debug = new OriginPolicy("http://localhost:3000", true);
        check(debug.contains("http://localhost:3000/mental"), "explicit debug loopback");
        check(!debug.contains("http://127.0.0.1:3000/"), "no implicit alias trust");
        check(!debug.contains("http://localhost:8000/"), "API is not a media permission origin");
        invalid(() -> new OriginPolicy("http://10.0.2.2:3000", true), "no LAN/emulator cleartext exception");
        check(!OriginPolicy.isHttps("https://user@evil.example"), "no credentialed handoff");
        check(OriginPolicy.isHttps("https://example.org/appointment"), "explicit HTTPS handoff candidate");
        String[] video = {MediaPermissionPolicy.VIDEO}, audio = {MediaPermissionPolicy.AUDIO};
        check(MediaPermissionPolicy.eligible(video, true, true, true, false), "camera-only hardware");
        check(MediaPermissionPolicy.eligible(audio, true, true, false, true), "microphone-only hardware");
        check(!MediaPermissionPolicy.eligible(video, true, true, false, true), "missing camera");
        check(!MediaPermissionPolicy.eligible(audio, true, true, true, false), "missing microphone");
        check(!MediaPermissionPolicy.eligible(video, false, true, true, true), "untrusted permission origin");
        check(!MediaPermissionPolicy.eligible(video, true, false, true, true), "moving/background permission denial");
        check(!MediaPermissionPolicy.eligible(new String[]{MediaPermissionPolicy.VIDEO, "NEW_PRIVILEGE"}, true, true, true, true), "deny unknown future WebView resources");
        check(!MediaPermissionPolicy.eligible(new String[]{MediaPermissionPolicy.VIDEO, MediaPermissionPolicy.AUDIO}, true, true, true, false), "deny unsupported combined request");
        check(!MediaPermissionPolicy.eligible(new String[0], true, true, true, true), "deny empty request");
        check(!MediaPermissionPolicy.eligible(null, true, true, true, true), "deny null request");
        check(MediaPermissionPolicy.retainForSystemPrompt(true, true, true), "system prompt retains its initiating page");
        check(!MediaPermissionPolicy.retainForSystemPrompt(false, true, true), "ordinary pause cannot retain page");
        check(!MediaPermissionPolicy.retainForSystemPrompt(true, false, true), "cancelled request cannot retain page");
        for (GatePolicy.Platform p : GatePolicy.Platform.values()) {
            for (VehicleSnapshot s : new VehicleSnapshot[]{null, parked(100), parked(0), new VehicleSnapshot(10, true, false, "D", 100)}) {
                boolean safe = gate(true, p, s, 2600) == GatePolicy.Reason.READY;
                check(MediaPermissionPolicy.retainForSystemPrompt(true, true, safe) == safe,
                    "permission prompt still follows platform, stale and moving gates");
                check(!MediaPermissionPolicy.eligible(audio, true, false, false, true),
                    "retaining prompt never permits a background media grant");
            }
        }
        VehicleDataProvider provider = new UnavailableVehicleProvider();
        final boolean[] notified = {false};
        provider.start(value -> { notified[0] = true; check(value == null, "release never fabricates vehicle state"); });
        check(notified[0], "release provider explicitly reports unavailable");
        provider.stop();
        System.out.println("PASS " + checks + " automotive policy checks (host JVM; not Android runtime validation)");
    }
}
