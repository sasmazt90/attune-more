package more.attune.automotive;

import android.Manifest;
import android.app.Activity;
import android.content.res.Configuration;
import android.content.res.Resources;
import java.util.Locale;
import java.util.LinkedHashMap;
import java.util.Map;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import org.json.JSONObject;

/** Sideloadable AAOS parked prototype; contains no health algorithms or vehicle credentials. */
public final class MainActivity extends Activity {
    private final Handler main = new Handler(Looper.getMainLooper());
    private final OriginPolicy webOrigin = new OriginPolicy(BuildConfig.WEB_ORIGIN, BuildConfig.DEBUG);
    private final OriginPolicy apiOrigin = new OriginPolicy(BuildConfig.API_ORIGIN, BuildConfig.DEBUG);
    private VehicleDataProvider vehicleProvider;
    private CarRestrictionSource carRestrictions;
    private VehicleSnapshot observation;
    private GatePolicy.Platform platform = GatePolicy.Platform.UNKNOWN;
    private boolean foreground, pageFailed, destroyed;
    private FrameLayout frame;
    private TextView status, placeholder;
    private Button back, home, simulation;
    private WebView web;
    private PermissionRequest pendingPermission;
    private String[] pendingResources;
    private static final int MEDIA_PERMISSION = 31;

    private Resources localizedResources;
    private String uiLanguage = "tr";
    private boolean localeReadPending;
    private final Map<Button,Integer> toolbarLabels = new LinkedHashMap<>();

    private String localizedString(int id, Object... args) {
        return (localizedResources == null ? getResources() : localizedResources).getString(id,args);
    }

    private void applyLanguage(String language, boolean persist) {
        if (!("tr".equals(language) || "en".equals(language) || "de".equals(language))) return;
        if (localizedResources != null && uiLanguage.equals(language)) return;
        uiLanguage = language;
        Configuration config = new Configuration(getResources().getConfiguration());
        config.setLocale(Locale.forLanguageTag(language.equals("en") ? "en-US" : language.equals("de") ? "de-DE" : "tr-TR"));
        localizedResources = createConfigurationContext(config).getResources();
        for (Map.Entry<Button,Integer> label : toolbarLabels.entrySet()) label.getKey().setText(localizedString(label.getValue()));
        if (persist) getPreferences(MODE_PRIVATE).edit().putString("attune.language.v1",language).apply();
    }

    /** One-way, allowlisted preference read from the trusted foreground WebView.
     * No JS interface, navigation, vehicle mutation or policy override is exposed. */
    private void synchronizeLanguage() {
        if (!ready() || web == null || localeReadPending || !webOrigin.contains(web.getUrl())) return;
        final WebView source = web;
        localeReadPending = true;
        try { source.evaluateJavascript("(function(){try{var l=localStorage.getItem('attune.language.v1');return ['tr','en','de'].indexOf(l)>=0?l:'tr';}catch(e){return 'tr';}})()", value -> {
            localeReadPending = false;
            if (source != web || !ready() || !webOrigin.contains(source.getUrl())) return;
            try {
                Object decoded = new org.json.JSONTokener(value).nextValue();
                if (decoded instanceof String) { applyLanguage((String) decoded,true); render(); }
            } catch (org.json.JSONException ignored) { }
        }); } catch (RuntimeException ignored) { localeReadPending = false; }
    }

    private final Runnable watchdog = new Runnable() {
        @Override public void run() { render(); synchronizeLanguage(); main.postDelayed(this, 500); }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        applyLanguage(getPreferences(MODE_PRIVATE).getString("attune.language.v1","tr"),false);
        vehicleProvider = BuildConfig.BACKEND_SIMULATION
            ? new BackendSimulationVehicleProvider(BuildConfig.API_ORIGIN, main) : new UnavailableVehicleProvider();
        carRestrictions = new CarRestrictionSource(this, main);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(6, 11, 18));
        // Normal system insets/cutouts remain under OS control; no immersive or forced landscape mode.
        root.setFitsSystemWindows(true);
        HorizontalScrollView scroll = new HorizontalScrollView(this);
        LinearLayout toolbar = new LinearLayout(this);
        back = button(R.string.back, () -> { if (ready() && web != null && web.canGoBack()) web.goBack(); });
        home = button(R.string.home, () -> { if (ready() && web != null) web.loadUrl(BuildConfig.WEB_ORIGIN + "/"); });
        toolbar.addView(back); toolbar.addView(home);
        toolbar.addView(button(R.string.retry, () -> {
            pageFailed = false;
            destroyWeb();
            observation = null;
            vehicleProvider.start(value -> { observation = value; render(); });
            render();
        }));
        simulation = button(R.string.simulation, () -> {
            if (foreground && platform == GatePolicy.Platform.UNRESTRICTED
                    && vehicleProvider instanceof BackendSimulationVehicleProvider) {
                ((BackendSimulationVehicleProvider) vehicleProvider).setSpeed(
                    observation != null && observation.parked ? 75 : 0);
            }
        });
        if (BuildConfig.BACKEND_SIMULATION) toolbar.addView(simulation);
        scroll.addView(toolbar);
        root.addView(scroll);
        status = new TextView(this);
        status.setTextColor(Color.rgb(226, 232, 240));
        status.setTextSize(14);
        status.setPadding(dp(12), dp(4), dp(12), dp(8));
        root.addView(status);
        frame = new FrameLayout(this);
        placeholder = new TextView(this);
        placeholder.setTextColor(Color.WHITE);
        placeholder.setTextSize(20);
        placeholder.setPadding(dp(24), dp(24), dp(24), dp(24));
        frame.addView(placeholder);
        root.addView(frame, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private Button button(int text, Runnable action) {
        Button button = new Button(this);
        toolbarLabels.put(button,text); button.setText(localizedString(text)); button.setTextSize(16); button.setAllCaps(false);
        button.setMinHeight(dp(64)); button.setMinWidth(dp(80));
        button.setOnClickListener(view -> action.run());
        return button;
    }

    @Override public void onStart() {
        super.onStart();
        observation = null;
        carRestrictions.start(value -> { platform = value; render(); });
        vehicleProvider.start(value -> { observation = value; render(); });
        main.post(watchdog);
    }
    @Override public void onResume() { super.onResume(); foreground = true; render(); }
    @Override public void onPause() {
        foreground = false;
        destroyWeb(); // Stop capture, JS, media, recognition and unsaved in-flight sessions.
        super.onPause();
    }
    @Override public void onStop() {
        main.removeCallbacks(watchdog);
        vehicleProvider.stop(); carRestrictions.stop(); observation = null; platform = GatePolicy.Platform.UNKNOWN;
        super.onStop();
    }
    @Override public void onDestroy() {
        destroyed = true; main.removeCallbacks(watchdog); destroyWeb(); super.onDestroy();
    }
    private GatePolicy.Reason reason() { return GatePolicy.evaluate(foreground, platform, observation, SystemClock.elapsedRealtime()); }
    private boolean ready() { return !destroyed && reason() == GatePolicy.Reason.READY; }

    private void render() {
        if (frame == null || destroyed) return;
        GatePolicy.Reason reason = reason();
        int platformText = platform == GatePolicy.Platform.UNRESTRICTED ? R.string.platform_clear
            : platform == GatePolicy.Platform.RESTRICTED ? R.string.platform_restricted : R.string.platform_unknown;
        status.setText(localizedString(R.string.status_line, localizedString(BuildConfig.BACKEND_SIMULATION ? R.string.provider_simulation : R.string.provider_unavailable), localizedString(platformText),
            localizedString(messageFor(reason)), localizedString(cameraPresent() ? R.string.present : R.string.absent),
            localizedString(microphonePresent() ? R.string.present : R.string.absent)));
        boolean allowed = reason == GatePolicy.Reason.READY;
        back.setEnabled(allowed); home.setEnabled(allowed);
        simulation.setEnabled(foreground && platform == GatePolicy.Platform.UNRESTRICTED
            && (!(vehicleProvider instanceof BackendSimulationVehicleProvider)
                || !((BackendSimulationVehicleProvider) vehicleProvider).isUpdating()));
        simulation.setText(localizedString(observation != null && observation.parked ? R.string.simulate_driving : R.string.simulate_parked));
        if (!allowed) {
            destroyWeb();
            placeholder.setVisibility(View.VISIBLE);
            placeholder.setText(localizedString(R.string.locked, localizedString(messageFor(reason))));
        } else if (pageFailed) {
            placeholder.setVisibility(View.VISIBLE);
            placeholder.setText(localizedString(R.string.page_failed));
        } else if (web == null) openWeb();
    }

    private int messageFor(GatePolicy.Reason reason) {
        switch (reason) {
            case BACKGROUND: return R.string.gate_background;
            case PLATFORM_UNKNOWN: return R.string.gate_platform_unknown;
            case PLATFORM_RESTRICTED: return R.string.gate_platform_restricted;
            case VEHICLE_UNKNOWN: return R.string.gate_vehicle_unknown;
            case VEHICLE_STALE: return R.string.gate_stale;
            case VEHICLE_MOVING: return R.string.gate_moving;
            case NOT_PARKED: return R.string.gate_not_parked;
            case READY: return R.string.gate_ready;
            default: return R.string.gate_vehicle_unknown;
        }
    }

    private void openWeb() {
        if (!ready() || !getPackageManager().hasSystemFeature(PackageManager.FEATURE_WEBVIEW)) return;
        WebView view;
        try { view = new WebView(this); }
        catch (RuntimeException error) { pageFailed = true; render(); return; }
        web = view;
        view.resumeTimers(); view.onResume();
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false); settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false); settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(false); settings.setSupportMultipleWindows(false);
        settings.setGeolocationEnabled(false); settings.setSafeBrowsingEnabled(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(view, false);
        view.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView source, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (ready() && webOrigin.contains(url)) return false;
                if (request.isForMainFrame() && request.hasGesture() && ready() && OriginPolicy.isHttps(url)) {
                    new AlertDialog.Builder(MainActivity.this).setTitle(localizedString(R.string.external_title))
                        .setMessage(localizedString(R.string.external_message))
                        .setNegativeButton(localizedString(R.string.cancel), null).setPositiveButton(localizedString(R.string.open_browser), (dialog, which) -> {
                            if (!ready()) return;
                            try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
                            catch (android.content.ActivityNotFoundException error) { notice(R.string.no_browser); }
                        }).show();
                }
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView source, WebResourceRequest request) {
                String url = request.getUrl().toString();
                String scheme = request.getUrl().getScheme();
                // Existing consented photo previews and audio use in-memory URLs.
                // These are subresources only, never top-level navigation or native bridges.
                if (!request.isForMainFrame() && ("data".equals(scheme) || "blob".equals(scheme))) return null;
                if (OriginPolicy.isHttps(url) || (BuildConfig.DEBUG && (webOrigin.contains(url) || apiOrigin.contains(url)))) return null;
                return new WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", java.util.Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
            }
            @Override public void onPageFinished(WebView source, String url) {
                if (source != web || !ready() || !webOrigin.contains(url)) return;
                try (java.io.InputStream stream = getAssets().open("automotive.css")) {
                    ByteArrayOutputStreamCompat css = new ByteArrayOutputStreamCompat(stream);
                    source.evaluateJavascript("(()=>{let s=document.getElementById('attune-automotive-style');if(!s){s=document.createElement('style');s.id='attune-automotive-style';document.head.appendChild(s)}s.textContent="
                        + JSONObject.quote(css.text) + ";})()", null);
                } catch (java.io.IOException error) { pageFailed = true; destroyWeb(); render(); }
            }
            @Override public void onReceivedError(WebView source, WebResourceRequest request, WebResourceError error) {
                if (source == web && request.isForMainFrame()) { pageFailed = true; destroyWeb(); render(); }
            }
            @Override public void onReceivedSslError(WebView source, SslErrorHandler handler, SslError error) {
                handler.cancel();
                if (source == web) { pageFailed = true; destroyWeb(); render(); }
            }
            @Override public boolean onRenderProcessGone(WebView source, RenderProcessGoneDetail detail) {
                if (source == web) { pageFailed = true; destroyWeb(); render(); }
                return true;
            }
        });
        view.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) { handlePermission(request); }
            @Override public void onPermissionRequestCanceled(PermissionRequest request) {
                if (pendingPermission == request) { pendingPermission = null; pendingResources = null; }
            }
            @Override public boolean onShowFileChooser(WebView source, android.webkit.ValueCallback<Uri[]> callback, FileChooserParams params) {
                // An external picker pauses the Activity. Do not promise a result after destroying
                // its initiating WebView; a future in-Activity picker needs separate acceptance.
                callback.onReceiveValue(null);
                notice(R.string.no_picker);
                return true;
            }
        });
        frame.addView(view, new FrameLayout.LayoutParams(-1, -1));
        placeholder.setVisibility(View.GONE);
        view.loadUrl(BuildConfig.WEB_ORIGIN + "/");
    }

    private boolean cameraPresent() { return getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY); }
    private boolean microphonePresent() { return getPackageManager().hasSystemFeature(PackageManager.FEATURE_MICROPHONE); }
    private boolean permissionEligible(PermissionRequest request, String[] resources) {
        return web != null && webOrigin.contains(web.getUrl()) && MediaPermissionPolicy.eligible(resources,
            webOrigin.contains(request.getOrigin().toString()), ready(), cameraPresent(), microphonePresent());
    }
    private void handlePermission(PermissionRequest request) {
        String[] resources = request.getResources();
        if (pendingPermission != null || !permissionEligible(request, resources)) { request.deny(); notice(R.string.media_unavailable); return; }
        ArrayList<String> permissions = new ArrayList<>();
        for (String resource : resources) {
            String permission = MediaPermissionPolicy.VIDEO.equals(resource) ? Manifest.permission.CAMERA : Manifest.permission.RECORD_AUDIO;
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED && !permissions.contains(permission)) permissions.add(permission);
        }
        pendingPermission = request; pendingResources = resources.clone();
        if (permissions.isEmpty()) completePermission();
        else requestPermissions(permissions.toArray(new String[0]), MEDIA_PERMISSION);
    }
    private void completePermission() {
        PermissionRequest request = pendingPermission;
        String[] resources = pendingResources;
        pendingPermission = null; pendingResources = null;
        if (request == null) return;
        if (!permissionEligible(request, resources)) { request.deny(); return; }
        for (String resource : resources) {
            String permission = MediaPermissionPolicy.VIDEO.equals(resource) ? Manifest.permission.CAMERA : Manifest.permission.RECORD_AUDIO;
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) { request.deny(); return; }
        }
        request.grant(resources); // Only the explicitly validated video/audio whitelist, never unknown resources.
    }
    @Override public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code == MEDIA_PERMISSION) completePermission();
    }
    @Override public void onBackPressed() { if (ready() && web != null && web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    private void notice(int message) { Toast.makeText(this, localizedString(message), Toast.LENGTH_SHORT).show(); }
    private void destroyWeb() {
        localeReadPending = false;
        if (pendingPermission != null) { pendingPermission.deny(); pendingPermission = null; pendingResources = null; }
        WebView old = web; web = null;
        if (old != null) {
            old.stopLoading(); old.onPause(); old.pauseTimers(); frame.removeView(old); old.removeAllViews(); old.destroy();
        }
    }

    private static final class ByteArrayOutputStreamCompat {
        final String text;
        ByteArrayOutputStreamCompat(java.io.InputStream stream) throws java.io.IOException {
            java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
            byte[] block = new byte[4096]; int count;
            while ((count = stream.read(block)) != -1) bytes.write(block, 0, count);
            text = bytes.toString(StandardCharsets.UTF_8.name());
        }
    }
}
