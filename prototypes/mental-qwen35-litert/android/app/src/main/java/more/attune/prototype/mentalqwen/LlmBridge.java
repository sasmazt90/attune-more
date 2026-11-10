package more.attune.prototype.mentalqwen;

import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import com.google.ai.edge.litertlm.Backend;
import com.google.ai.edge.litertlm.Content;
import com.google.ai.edge.litertlm.Contents;
import com.google.ai.edge.litertlm.Conversation;
import com.google.ai.edge.litertlm.ConversationConfig;
import com.google.ai.edge.litertlm.Engine;
import com.google.ai.edge.litertlm.EngineConfig;
import com.google.ai.edge.litertlm.Message;
import com.google.ai.edge.litertlm.MessageCallback;
import com.google.ai.edge.litertlm.SamplerConfig;

import org.json.JSONObject;

import java.io.File;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * On-device Qwen3.5-2B through LiteRT-LM Android (CPU backend, as the model card recommends for Android).
 * One fresh Engine per conversation: a Conversation on an Engine that already ran another conversation keeps that
 * conversation's state (model card; LiteRT-LM #3165; reproduced on host in results/raw/leak_host.json).
 * JS API (window.AttuneLlm): open, send, cancel, close; results come back through window.__attuneLlmCallback.
 */
final class LlmBridge {
    private static final String TAG = "AttuneQwen";
    private final WebView web;
    private final File modelFile;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private Engine engine;
    private Conversation conversation;
    private String sessionId;

    LlmBridge(WebView web, File modelFile) { this.web = web; this.modelFile = modelFile; }

    private void reply(String callbackId, JSONObject result) {
        String js = "window.__attuneLlmCallback && window.__attuneLlmCallback(" + JSONObject.quote(callbackId) + "," + result + ")";
        main.post(() -> web.evaluateJavascript(js, null));
    }
    private static JSONObject obj(Object... kv) {
        JSONObject o = new JSONObject();
        try { for (int i = 0; i < kv.length; i += 2) o.put((String) kv[i], kv[i + 1]); } catch (Exception ignored) { }
        return o;
    }
    private void closeCurrent() {
        if (conversation != null) { try { conversation.close(); } catch (RuntimeException ignored) { } conversation = null; }
        if (engine != null) { try { engine.close(); } catch (RuntimeException ignored) { } engine = null; }
        sessionId = null;
    }

    @JavascriptInterface public String info() {
        Runtime rt = Runtime.getRuntime();
        return obj("platform", "AAOS-native-LiteRT-LM", "runtime", "litertlm-android 0.19.1", "backend", "CPU",
            "model", modelFile.getAbsolutePath(), "modelBytes", modelFile.length(),
            "javaHeapMaxMb", rt.maxMemory() / 1048576).toString();
    }

    @JavascriptInterface public void open(String callbackId, String systemPrompt) {
        worker.execute(() -> {
            closeCurrent();
            long t0 = SystemClock.elapsedRealtime();
            try {
                engine = new Engine(new EngineConfig(modelFile.getAbsolutePath(), new Backend.CPU(4, null)));
                engine.initialize();
                long t1 = SystemClock.elapsedRealtime();
                conversation = engine.createConversation(new ConversationConfig(Contents.Companion.of(systemPrompt),
                    Collections.emptyList(), Collections.emptyList(), new SamplerConfig(1, 1.0, 0.0, 1), true,
                    null, Collections.emptyMap(), null, false, null));
                sessionId = UUID.randomUUID().toString();
                reply(callbackId, obj("ok", true, "sessionId", sessionId, "engineCreateMs", t1 - t0));
            } catch (Throwable e) {
                Log.e(TAG, "open failed", e);
                closeCurrent();
                reply(callbackId, obj("ok", false, "error", String.valueOf(e)));
            }
        });
    }

    @JavascriptInterface public void send(String callbackId, String id, String text, int maxTokens) {
        worker.execute(() -> {
            if (conversation == null || !id.equals(sessionId)) { reply(callbackId, obj("ok", false, "error", "session closed")); return; }
            final long t0 = SystemClock.elapsedRealtime();
            final long[] first = {-1};
            final StringBuilder out = new StringBuilder();
            final Object done = new Object();
            final boolean[] finished = {false};
            final String[] error = {null};
            conversation.sendMessageAsync(text, new MessageCallback() {
                @Override public void onMessage(Message m) {
                    for (Content c : m.getContents().getContents()) if (c instanceof Content.Text) {
                        if (first[0] < 0) first[0] = SystemClock.elapsedRealtime() - t0;
                        out.append(((Content.Text) c).getText());
                    }
                }
                @Override public void onDone() { synchronized (done) { finished[0] = true; done.notifyAll(); } }
                @Override public void onError(Throwable e) { synchronized (done) { error[0] = String.valueOf(e); finished[0] = true; done.notifyAll(); } }
            }, Collections.emptyMap(), null, null, null, maxTokens, null);
            synchronized (done) { while (!finished[0]) { try { done.wait(); } catch (InterruptedException ignored) { } } }
            long total = SystemClock.elapsedRealtime() - t0;
            boolean cancelled = error[0] != null && error[0].toLowerCase().contains("cancel");
            int tokens = -1;
            try { tokens = conversation.getTokenCount(); } catch (RuntimeException ignored) { }
            reply(callbackId, obj("ok", error[0] == null || cancelled, "text", out.toString(), "firstTokenMs", first[0], "totalMs", total,
                "cancelled", cancelled, "error", error[0] == null ? JSONObject.NULL : error[0], "contextTokens", tokens));
        });
    }

    /** Called from any thread: stops generation now; the JS core's epoch check discards whatever was produced. */
    @JavascriptInterface public void cancel(String id) {
        Conversation c = conversation;
        if (c != null && id != null && id.equals(sessionId)) { try { c.cancelProcess(); } catch (RuntimeException ignored) { } }
    }

    @JavascriptInterface public void close(String callbackId, String id) {
        worker.execute(() -> { if (id != null && id.equals(sessionId)) closeCurrent(); reply(callbackId, obj("ok", true)); });
    }

    void shutdown() { cancel(sessionId); worker.execute(this::closeCurrent); worker.shutdown(); }
}
