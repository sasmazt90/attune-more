package more.attune.prototype.mentalqwen;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.webkit.WebViewAssetLoader;

import java.io.File;

/** Hosts the KOL B web prototype from APK assets; models from the app's files directory; LLM natively. */
public final class MainActivity extends Activity {
    private static final String ORIGIN = "https://appassets.androidplatform.net";
    private WebView web;
    private LlmBridge llm;
    private final ParkGate gate = new ParkGate();

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        File models = new File(getFilesDir(), "models");
        // The page uses the same absolute paths as on WEB (/app, /core, /node_modules, ...): each maps to assets/web/<path>.
        WebViewAssetLoader.Builder builder = new WebViewAssetLoader.Builder()
            .addPathHandler("/models/", new WebViewAssetLoader.InternalStoragePathHandler(this, models));
        for (String prefix : new String[]{"app", "core", "adapters", "dist", "speech", "generated", "node_modules"}) {
            builder.addPathHandler("/" + prefix + "/", path -> {
                try {
                    String name = "web/" + prefix + "/" + path;
                    return new WebResourceResponse(mime(name), null, getAssets().open(name));
                } catch (java.io.IOException e) { return null; }
            });
        }
        WebViewAssetLoader loader = builder.build();
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(true);   // as in the product AAOS app
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (!ORIGIN.equals(u.getScheme() + "://" + u.getHost())) return new WebResourceResponse("text/plain", "utf-8", 403, "blocked", null, null);
                return loader.shouldInterceptRequest(u);
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) {
                boolean ours = ORIGIN.equals(request.getOrigin().getScheme() + "://" + request.getOrigin().getHost());
                if (ours && checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
                    request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                else request.deny();
            }
        });
        llm = new LlmBridge(web, new File(models, "qwen35-2b/Qwen3.5-2B_int8.litertlm"));
        web.addJavascriptInterface(llm, "AttuneLlm");
        setContentView(web);
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1);
        web.loadUrl(ORIGIN + "/app/index.html?llm=android");
        gate.start(this, new Handler(Looper.getMainLooper()), parked ->
            web.evaluateJavascript("window.__attuneParked && window.__attuneParked(" + parked + ")", null));
    }
    private static String mime(String name) {
        if (name.endsWith(".html")) return "text/html";
        if (name.endsWith(".js") || name.endsWith(".mjs")) return "text/javascript";
        if (name.endsWith(".wasm")) return "application/wasm";
        if (name.endsWith(".json")) return "application/json";
        if (name.endsWith(".zip")) return "application/zip";
        return "application/octet-stream";
    }
    @Override protected void onPause() { super.onPause(); web.evaluateJavascript("window.__attuneBackground && window.__attuneBackground()", null); }
    @Override protected void onDestroy() { gate.stop(); llm.shutdown(); web.destroy(); super.onDestroy(); }
}
