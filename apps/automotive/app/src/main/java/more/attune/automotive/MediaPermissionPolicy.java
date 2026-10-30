package more.attune.automotive;

public final class MediaPermissionPolicy {
    public static final String VIDEO = "android.webkit.resource.VIDEO_CAPTURE";
    public static final String AUDIO = "android.webkit.resource.AUDIO_CAPTURE";
    private MediaPermissionPolicy() {}

    /** Retention is not a grant. The caller must still recheck foreground,
     * origin, hardware and Android permissions before granting any resource. */
    public static boolean retainForSystemPrompt(boolean runtimeRequestInFlight,
                                                boolean pendingWebRequest, boolean vehicleAndPlatformReady) {
        return runtimeRequestInFlight && pendingWebRequest && vehicleAndPlatformReady;
    }

    public static boolean eligible(String[] resources, boolean trustedOrigin, boolean gateReady,
                                   boolean cameraPresent, boolean microphonePresent) {
        if (!trustedOrigin || !gateReady || resources == null || resources.length == 0) return false;
        for (String resource : resources) {
            if (VIDEO.equals(resource)) { if (!cameraPresent) return false; }
            else if (AUDIO.equals(resource)) { if (!microphonePresent) return false; }
            else return false;
        }
        return true;
    }
}
