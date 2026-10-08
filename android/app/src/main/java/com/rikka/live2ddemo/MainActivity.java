package com.rikka.live2ddemo;

import android.Manifest;
import android.app.Activity;
import android.content.pm.ActivityInfo;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.provider.MediaStore;
import android.content.res.Configuration;
import android.content.res.AssetManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.PointF;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.media.FaceDetector;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Base64;
import android.util.Log;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.ByteArrayInputStream;
import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.URL;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.json.JSONArray;
import org.json.JSONObject;

public class MainActivity extends Activity {
    private static final String TAG = "RikkaLive2D";
    private static final String ASSET_HOST = "appassets.local";
    private static final String ASSET_HOME = "https://" + ASSET_HOST + "/index.html";
    private static final int CAMERA_REQUEST = 1001;
    private static final int AUDIO_REQUEST = 1002;
    private static final int PHOTO_REQUEST = 1003;

    private WebView webView;
    private AssetServer assetServer;
    private boolean pageLoaded = false;
    private boolean fallbackAttempted = false;
    private SpeechRecognizer speechRecognizer;
    private boolean speechContinuous = false;
    private boolean speechPermissionPending = false;
    private ExecutorService apiExecutor;
    private Handler mainHandler;
    private TextToSpeech localTts;
    private boolean localTtsReady = false;

    private static final String GSV_REF_TEXT = "視界不良でも全てを見渡せる";
    private static final int GSV_LANG_JA = 1;
    private long gsvHandle = 0;
    private boolean gsvReady = false;
    private boolean gsvInitializing = false;
    private AudioTrack gsvAudioTrack;
    private ExecutorService gsvExecutor;
    private UdpDiscovery udpDiscovery;
    private volatile boolean localVoiceEnabled = true;
    private volatile float voiceSpeed = 1.0f;
    private volatile float voiceVolume = 1.0f;
    private volatile int voicePitch = 0;
    private volatile float voiceDeElect = 0f;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.TRANSPARENT);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.TRANSPARENT);
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
        setContentView(webView);

        WebView.setWebContentsDebuggingEnabled(true);
        webView.addJavascriptInterface(new NativeFaceBridge(this), "NativeFaceBridge");
        webView.addJavascriptInterface(new NativeSpeechBridge(this), "NativeSpeech");
        webView.addJavascriptInterface(new NativePhotoBridge(this), "NativePhoto");
        webView.addJavascriptInterface(new NativeApiBridge(this), "NativeApi");
        webView.addJavascriptInterface(new NativeTtsBridge(this), "NativeTts");
        webView.addJavascriptInterface(new NativeClipboardBridge(this), "NativeClipboard");
        webView.addJavascriptInterface(new NativeDiscoveryBridge(this), "NativeDiscovery");
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN) {
            settings.setAllowFileAccessFromFileURLs(true);
            settings.setAllowUniversalAccessFromFileURLs(true);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                if (request == null || request.getUrl() == null) return null;
                String host = request.getUrl().getHost();
                if (!ASSET_HOST.equalsIgnoreCase(host)) return null;
                return openAsset(request.getUrl().getPath());
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request == null || !request.isForMainFrame()) return;
                String description = error == null ? "unknown" : String.valueOf(error.getDescription());
                Log.e(TAG, "Main frame error: " + request.getUrl() + " - " + description);
                if (!fallbackAttempted && ASSET_HOST.equalsIgnoreCase(request.getUrl().getHost())) {
                    fallbackAttempted = true;
                    loadWithLocalServer();
                } else {
                    showFatal("页面加载失败：" + description);
                }
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse errorResponse) {
                if (request == null || !request.isForMainFrame()) return;
                int status = errorResponse == null ? 0 : errorResponse.getStatusCode();
                Log.e(TAG, "Main frame HTTP error: " + status + " " + request.getUrl());
                if (!fallbackAttempted && ASSET_HOST.equalsIgnoreCase(request.getUrl().getHost())) {
                    fallbackAttempted = true;
                    loadWithLocalServer();
                } else {
                    showFatal("页面资源返回错误：" + status);
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                Log.i(TAG, "Page finished: " + url);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage message) {
                if (message != null) {
                    Log.i(TAG, "JS " + message.messageLevel() + ": " + message.message()
                            + " @" + message.sourceId() + ":" + message.lineNumber());
                }
                return true;
            }

            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        for (String resource : request.getResources()) {
                            if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource)) {
                                request.grant(new String[]{resource});
                                return;
                            }
                        }
                        request.deny();
                    }
                });
            }
        });

        apiExecutor = Executors.newCachedThreadPool();
        gsvExecutor = Executors.newSingleThreadExecutor();
        mainHandler = new Handler(Looper.getMainLooper());
        initLocalTts();
        initGsvTts();
        udpDiscovery = new UdpDiscovery();
        udpDiscovery.start();
        ensureCameraAndLoad();
    }

    private WebResourceResponse openAsset(String rawPath) {
        String path = rawPath == null || rawPath.isEmpty() ? "/index.html" : rawPath;
        if (path.contains("..")) {
            return new WebResourceResponse("text/plain", "utf-8", 403, "Forbidden", null,
                    new ByteArrayInputStream(new byte[0]));
        }
        try {
            InputStream input = getAssets().open("web" + path);
            String mime = mimeType(path);
            String encoding = textEncoding(path);
            return new WebResourceResponse(mime, encoding, 200, "OK", null, input);
        } catch (IOException e) {
            return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", null,
                    new ByteArrayInputStream(("Not found: " + path).getBytes(StandardCharsets.UTF_8)));
        }
    }

    private void ensureCameraAndLoad() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_REQUEST);
                return;
            }
        }
        loadPage();
    }

    private void loadPage() {
        if (pageLoaded) return;
        pageLoaded = true;
        Log.i(TAG, "Loading " + ASSET_HOME);
        webView.loadUrl(ASSET_HOME);
    }

    private void loadWithLocalServer() {
        try {
            Log.w(TAG, "Asset interception failed; using localhost fallback");
            if (assetServer == null) {
                assetServer = new AssetServer(getAssets());
                assetServer.start();
            }
            webView.loadUrl("http://127.0.0.1:" + assetServer.getPort() + "/index.html");
        } catch (IOException e) {
            showFatal("本地资源服务启动失败: " + e.getMessage());
        }
    }

    private void showFatal(String message) {
        Log.e(TAG, message);
        String safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
        String html = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "</head><body style='background:#111;color:#fff;font-family:sans-serif;padding:24px'>"
                + "<h3>六花 Demo 启动失败</h3><p>" + safe + "</p>"
                + "<p style='color:#aaa'>请把这段文字截图发给开发者。</p></body></html>";
        webView.loadData(html, "text/html; charset=utf-8", "UTF-8");
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == AUDIO_REQUEST) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                if (speechPermissionPending) {
                    speechPermissionPending = false;
                    startSpeechRecognition();
                }
            } else {
                speechPermissionPending = false;
                sendSpeechEvent("onNativeSpeechError", "需要麦克风权限才能语音输入");
            }
        } else if (requestCode == CAMERA_REQUEST) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                loadPage();
            } else {
                showFatal("需要摄像头权限才能进行人脸追踪");
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != PHOTO_REQUEST) return;
        if (resultCode == RESULT_OK && data != null) {
            try {
                Bitmap bitmap = data.getParcelableExtra("data");
                if (bitmap == null) {
                    sendPhotoEvent("onNativePhotoError", "没有获取到照片");
                } else {
                    ByteArrayOutputStream output = new ByteArrayOutputStream();
                    bitmap.compress(Bitmap.CompressFormat.JPEG, 85, output);
                    String base64 = Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP);
                    sendPhotoEvent("onNativePhotoCaptured", base64);
                }
            } catch (Exception error) {
                sendPhotoEvent("onNativePhotoError", error == null ? "unknown" : error.toString());
            }
        } else {
            sendPhotoEvent("onNativePhotoError", "未拍照");
        }
        sendPhotoEvent("onNativePhotoReturned", "");
    }
    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        if (webView != null) {
            webView.post(new Runnable() {
                @Override
                public void run() {
                    webView.evaluateJavascript("window.dispatchEvent(new Event('resize'));", null);
                }
            });
            webView.postDelayed(new Runnable() {
                @Override
                public void run() {
                    webView.evaluateJavascript("window.dispatchEvent(new Event('resize'));", null);
                }
            }, 260L);
        }
    }

    @Override
    protected void onDestroy() {
        if (localTts != null) {
            localTts.stop();
            localTts.shutdown();
            localTts = null;
        }
        if (apiExecutor != null) {
            apiExecutor.shutdownNow();
            apiExecutor = null;
        }
        if (speechRecognizer != null) {
            speechRecognizer.destroy();
            speechRecognizer = null;
        }
        if (assetServer != null) {
            assetServer.stop();
            assetServer = null;
        }
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        stopGsvAudioTrack();
        synchronized (this) {
            if (gsvHandle != 0) {
                try { com.example.gpt_sovits_demo.MainActivity.freeModel(gsvHandle); } catch (Throwable ignored) {}
                gsvHandle = 0;
            }
        }
        if (gsvExecutor != null) {
            gsvExecutor.shutdownNow();
            gsvExecutor = null;
        }
        super.onDestroy();
    }
    private static String textEncoding(String path) {
        String lower = path.toLowerCase(Locale.US);
        if (lower.endsWith(".html") || lower.endsWith(".js") || lower.endsWith(".css")
                || lower.endsWith(".json") || lower.endsWith(".xml")) {
            return "utf-8";
        }
        return null;
    }

    private static String mimeType(String path) {
        String lower = path.toLowerCase(Locale.US);
        if (lower.endsWith(".html")) return "text/html";
        if (lower.endsWith(".js")) return "application/javascript";
        if (lower.endsWith(".css")) return "text/css";
        if (lower.endsWith(".json")) return "application/json";
        if (lower.endsWith(".png")) return "image/png";
        if (lower.endsWith(".moc3")) return "application/octet-stream";
        if (lower.endsWith(".xml")) return "application/xml";
        if (lower.endsWith(".wasm")) return "application/wasm";
        return "application/octet-stream";
    }


    private void initLocalTts() {
        localTts = new TextToSpeech(this, new TextToSpeech.OnInitListener() {
            @Override
            public void onInit(int status) {
                if (status == TextToSpeech.SUCCESS && localTts != null) {
                    int language = localTts.setLanguage(Locale.JAPANESE);
                    localTtsReady = language != TextToSpeech.LANG_MISSING_DATA
                            && language != TextToSpeech.LANG_NOT_SUPPORTED;
                    localTts.setSpeechRate(0.95f);
                    localTts.setPitch(1.05f);
                    localTts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                        @Override
                        public void onStart(String utteranceId) {
                            sendTtsState("start");
                        }

                        @Override
                        public void onDone(String utteranceId) {
                            sendTtsState("done");
                        }

                        @Override
                        public void onError(String utteranceId) {
                            sendTtsState("error");
                        }
                    });
                } else {
                    localTtsReady = false;
                }
            }
        });
    }

    private void sendGsvStatus(String status, String detail) {
        if (webView == null) return;
        final String script = "if (typeof window.onNativeGsvStatus === 'function') { window.onNativeGsvStatus("
                + JSONObject.quote(status == null ? "" : status) + ","
                + JSONObject.quote(detail == null ? "" : detail) + "); }";
        webView.post(new Runnable() {
            @Override
            public void run() {
                if (webView != null) webView.evaluateJavascript(script, null);
            }
        });
    }

    public void onBridgeDiscovered(final String ip, final int port) {
        if (webView == null) return;
        final String script = "if (typeof window.onNativeBridgeDiscovered === 'function') { window.onNativeBridgeDiscovered("
                + JSONObject.quote(ip == null ? "" : ip) + "," + port + "); }";
        webView.post(new Runnable() {
            @Override
            public void run() {
                if (webView != null) webView.evaluateJavascript(script, null);
            }
        });
    }

    public void onProgress(final int percent) {
        if (webView == null) return;
        final int p = Math.max(0, Math.min(100, percent));
        final String script = "if (typeof window.onNativeTtsProgress === 'function') { window.onNativeTtsProgress(" + p + "); }";
        webView.post(new Runnable() {
            @Override
            public void run() {
                if (webView != null) webView.evaluateJavascript(script, null);
            }
        });
    }

    private void initGsvTts() {
        if (gsvInitializing || gsvReady) return;
        gsvInitializing = true;
        sendGsvStatus("loading", "");
        gsvExecutor.execute(new Runnable() {
            @Override
            public void run() {
                try {
                    File modelDir = copyGsvAssets();
                    String vits = new File(modelDir, "vits.onnx").getAbsolutePath();
                    String ssl = new File(modelDir, "ssl.onnx").getAbsolutePath();
                    String enc = new File(modelDir, "t2s_encoder.onnx").getAbsolutePath();
                    String fsdec = new File(modelDir, "t2s_fs_decoder.onnx").getAbsolutePath();
                    String sdec = new File(modelDir, "t2s_s_decoder.onnx").getAbsolutePath();
                    String ref = new File(modelDir, "ref.wav").getAbsolutePath();
                    long h = com.example.gpt_sovits_demo.MainActivity.initModel("", vits, ssl, enc, fsdec, sdec, "", 24);
                    if (h == 0) throw new RuntimeException("model init failed");
                    boolean ok = com.example.gpt_sovits_demo.MainActivity.processReferenceSync(h, ref, GSV_REF_TEXT, GSV_LANG_JA);
                    if (!ok) throw new RuntimeException("reference processing failed");
                    com.example.gpt_sovits_demo.MainActivity.setProgressCallback(h, MainActivity.this);
                    synchronized (MainActivity.this) {
                        gsvHandle = h;
                        gsvReady = true;
                    }
                    Log.i(TAG, "GSV TTS ready");
                    sendGsvStatus("ready", "");
                } catch (Throwable t) {
                    Log.e(TAG, "GSV TTS init failed", t);
                    gsvInitializing = false;
                    sendGsvStatus("error", String.valueOf(t.getMessage()));
                }
            }
        });
    }

    private File copyGsvAssets() throws IOException {
        File dest = new File(getFilesDir(), "tts");
        if (!dest.exists() && !dest.mkdirs()) throw new IOException("mkdir failed");
        String[] files = getAssets().list("tts");
        for (String f : files) {
            File out = new File(dest, f);
            if (out.exists() && out.length() > 0) continue;
            sendGsvStatus("copying", f);
            InputStream in = getAssets().open("tts/" + f);
            FileOutputStream fos = new FileOutputStream(out);
            try {
                byte[] buf = new byte[1 << 20];
                int n;
                while ((n = in.read(buf)) > 0) fos.write(buf, 0, n);
            } finally {
                fos.close();
                in.close();
            }
        }
        return dest;
    }

    private void speakGsvTts(final String text) {
        final long handle;
        synchronized (MainActivity.this) {
            handle = gsvHandle;
        }
        if (handle == 0) {
            speakLocalTts(text);
            return;
        }
        sendTtsState("synthesizing");
        gsvExecutor.execute(new Runnable() {
            @Override
            public void run() {
                try {
                    float[] samples = com.example.gpt_sovits_demo.MainActivity.runInferenceSync(handle, text.trim(), GSV_LANG_JA);
                    if (samples == null || samples.length == 0) {
                        sendTtsState("error");
                        return;
                    }
                    playGsvAudio(samples);
                } catch (Throwable t) {
                    Log.e(TAG, "GSV synth failed", t);
                    sendTtsState("error");
                }
            }
        });
    }

    private void applyVoiceConfig(String json) {
        try {
            JSONObject o = new JSONObject(json);
            if (o.has("localVoice")) localVoiceEnabled = o.optBoolean("localVoice", true);
            if (o.has("speed")) voiceSpeed = Math.max(0.5f, Math.min(2.0f, (float) o.optDouble("speed", 1.0)));
            if (o.has("volume")) voiceVolume = Math.max(0f, Math.min(1f, (float) o.optDouble("volume", 1.0)));
            if (o.has("pitch")) voicePitch = Math.max(-12, Math.min(12, o.optInt("pitch", 0)));
            if (o.has("deElect")) voiceDeElect = Math.max(0f, Math.min(1f, (float) o.optDouble("deElect", 0.0)));
        } catch (Exception e) {
            Log.w(TAG, "voice config parse failed", e);
        }
    }

    private static float[] pitchShift(float[] x, int semitones) {
        double r = Math.pow(2.0, semitones / 12.0);
        if (Math.abs(r - 1.0) < 1e-6) return x;
        return resampleLinear(olaStretch(x, r), 1.0 / r);
    }

    private static float[] olaStretch(float[] x, double r) {
        int frame = 1024;
        int hopIn = 256;
        int hopOut = Math.max(1, (int) Math.round(hopIn * r));
        double[] window = new double[frame];
        for (int i = 0; i < frame; i++) {
            window[i] = 0.5 * (1.0 - Math.cos(2.0 * Math.PI * i / (frame - 1)));
        }
        double[] acc = new double[(int) (x.length * r) + frame + 1];
        int posIn = 0;
        int posOut = 0;
        while (posIn + frame <= x.length) {
            for (int i = 0; i < frame; i++) {
                int o = posOut + i;
                if (o < acc.length) acc[o] += x[posIn + i] * window[i];
            }
            posIn += hopIn;
            posOut += hopOut;
        }
        float[] out = new float[acc.length];
        for (int i = 0; i < out.length; i++) out[i] = (float) acc[i];
        return out;
    }

    private static float[] resampleLinear(float[] x, double factor) {
        int newLen = Math.max(1, (int) Math.round(x.length * factor));
        float[] y = new float[newLen];
        if (newLen == 1) { y[0] = x.length > 0 ? x[0] : 0f; return y; }
        for (int i = 0; i < newLen; i++) {
            double src = (double) i * (x.length - 1) / (newLen - 1);
            int i0 = (int) Math.floor(src);
            int i1 = Math.min(i0 + 1, x.length - 1);
            double frac = src - i0;
            y[i] = (float) (x[i0] * (1.0 - frac) + x[i1] * frac);
        }
        return y;
    }

    // 去电音：两阶一阶低通，strength 0~1，越大高频衰减越多。
    private static float[] deElectronic(float[] x, float strength) {
        if (strength <= 0.001f) return x;
        float fc = 11000f - strength * 7000f;
        float alpha = (float) (1.0 - Math.exp(-2.0 * Math.PI * fc / 32000.0));
        float[] y = new float[x.length];
        float p1 = 0f;
        float p2 = 0f;
        for (int i = 0; i < x.length; i++) {
            float v = alpha * x[i] + (1f - alpha) * p1;
            p1 = v;
            float v2 = alpha * v + (1f - alpha) * p2;
            p2 = v2;
            y[i] = v2;
        }
        return y;
    }
    private void playGsvAudio(final float[] samples) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    float[] playedSamples = voiceDeElect > 0.001f ? deElectronic(samples, voiceDeElect) : samples;
                    playedSamples = voicePitch != 0 ? pitchShift(playedSamples, voicePitch) : playedSamples;
                    stopGsvAudioTrack();
                    int buf = Math.max(
                            AudioTrack.getMinBufferSize(32000, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_FLOAT),
                            playedSamples.length * 4);
                    final AudioTrack track = new AudioTrack.Builder()
                            .setAudioAttributes(new AudioAttributes.Builder()
                                    .setUsage(AudioAttributes.USAGE_MEDIA)
                                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                                    .build())
                            .setAudioFormat(new AudioFormat.Builder()
                                    .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
                                    .setSampleRate(32000)
                                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                                    .build())
                            .setBufferSizeInBytes(buf)
                            .setTransferMode(AudioTrack.MODE_STATIC)
                            .build();
                    gsvAudioTrack = track;
                    track.write(playedSamples, 0, playedSamples.length, AudioTrack.WRITE_BLOCKING);
                    track.setPlaybackRate((int) (32000 * voiceSpeed));
                    track.setVolume(voiceVolume);
                    track.setNotificationMarkerPosition(playedSamples.length);
                    track.setPlaybackPositionUpdateListener(new AudioTrack.OnPlaybackPositionUpdateListener() {
                        @Override
                        public void onMarkerReached(AudioTrack t) {
                            sendTtsState("done");
                        }
                        @Override
                        public void onPeriodicNotification(AudioTrack t) {}
                    });
                    track.play();
                    sendTtsState("start");
                } catch (Throwable t) {
                    Log.e(TAG, "GSV playback failed", t);
                    sendTtsState("error");
                }
            }
        });
    }

    private void stopGsvAudioTrack() {
        if (gsvAudioTrack != null) {
            try {
                gsvAudioTrack.stop();
                gsvAudioTrack.release();
            } catch (Throwable ignored) {}
            gsvAudioTrack = null;
        }
    }

    private void stopGsvTts() {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                stopGsvAudioTrack();
                sendTtsState("done");
            }
        });
    }
    private void speak(String text) {
        if (localVoiceEnabled && gsvReady) {
            speakGsvTts(text);
        } else {
            speakLocalTts(text);
        }
    }

    private void speakLocalTts(String text) {
        if (localTts == null || text == null || text.trim().isEmpty()) {
            sendTtsState("error");
            return;
        }
        try {
            localTts.setSpeechRate(0.95f * voiceSpeed);
            localTts.setPitch(1.05f + voicePitch / 24.0f);
        } catch (Throwable ignored) {}
        localTts.speak(text.trim(), TextToSpeech.QUEUE_FLUSH, null, "rikka-local-tts");
    }

    private void stopTts() {
        stopGsvTts();
        stopLocalTts();
    }

    private void stopLocalTts() {
        if (localTts != null) localTts.stop();
        sendTtsState("done");
    }

    private void sendTtsState(String state) {
        if (webView == null) return;
        final String script = "window.onNativeTtsState(" + JSONObject.quote(state) + ");";
        webView.post(new Runnable() {
            @Override
            public void run() {
                if (webView != null) webView.evaluateJavascript(script, null);
            }
        });
    }

    private void performApiChat(String payloadJson) {
        String requestId = "";
        try {
            JSONObject request = new JSONObject(payloadJson);
            requestId = request.optString("requestId", "");
            String apiKey = request.optString("apiKey", "").trim();
            String baseUrl = request.optString("baseUrl", "https://api.deepseek.com").trim();
            String model = request.optString("model", "deepseek-chat").trim();
            JSONArray messages = request.optJSONArray("messages");
            if (apiKey.isEmpty()) throw new IOException("缺少 API Key");
            if (messages == null) throw new IOException("缺少 messages");

            String endpoint = baseUrl.replaceAll("/+$", "");
            if (!endpoint.endsWith("/chat/completions")) endpoint += "/chat/completions";

            JSONObject body = new JSONObject();
            body.put("model", model);
            body.put("messages", messages);
            body.put("temperature", 0.9);
            body.put("max_tokens", 512);
            body.put("stream", false);

            HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(20000);
            connection.setReadTimeout(120000);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("Authorization", "Bearer " + apiKey);
            OutputStreamWriter writer = new OutputStreamWriter(connection.getOutputStream(), StandardCharsets.UTF_8);
            writer.write(body.toString());
            writer.flush();
            writer.close();

            int status = connection.getResponseCode();
            InputStream input = status >= 200 && status < 300 ? connection.getInputStream() : connection.getErrorStream();
            BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8));
            StringBuilder responseText = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) responseText.append(line);
            reader.close();
            connection.disconnect();

            if (status < 200 || status >= 300) {
                throw new IOException("HTTP " + status + ": " + responseText);
            }
            JSONObject response = new JSONObject(responseText.toString());
            JSONArray choices = response.optJSONArray("choices");
            JSONObject message = choices == null || choices.length() == 0
                    ? null : choices.optJSONObject(0).optJSONObject("message");
            String reply = message == null ? "" : message.optString("content", "");
            if (reply.trim().isEmpty()) throw new IOException("API 返回空回复");

            JSONObject result = new JSONObject();
            result.put("ok", true);
            result.put("reply", reply.trim());
            sendApiResult(requestId, result.toString());
        } catch (Exception error) {
            try {
                JSONObject result = new JSONObject();
                result.put("ok", false);
                result.put("error", error == null ? "unknown" : error.toString());
                sendApiResult(requestId, result.toString());
            } catch (Exception ignored) {}
        }
    }

    private void sendApiResult(String requestId, String resultJson) {
        if (webView == null) return;
        final String script = "window.onNativeApiResult("
                + JSONObject.quote(requestId == null ? "" : requestId) + ","
                + JSONObject.quote(resultJson == null ? "{}" : resultJson) + ");";
        webView.post(new Runnable() {
            @Override
            public void run() {
                if (webView != null) webView.evaluateJavascript(script, null);
            }
        });
    }

    private static class NativeApiBridge {
        private final MainActivity activity;

        NativeApiBridge(MainActivity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public void chat(String payloadJson) {
            activity.apiExecutor.execute(new Runnable() {
                @Override
                public void run() {
                    activity.performApiChat(payloadJson);
                }
            });
        }
    }

    private static class NativeTtsBridge {
        private final MainActivity activity;

        NativeTtsBridge(MainActivity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public void speak(final String text) {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    activity.speak(text);
                }
            });
        }

        @JavascriptInterface
        public void stop() {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    activity.stopTts();
                }
            });
        }

        @JavascriptInterface
        public void setVoiceConfig(final String json) {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    activity.applyVoiceConfig(json);
                }
            });
        }
    }

    private static class NativeClipboardBridge {
        private final MainActivity activity;

        NativeClipboardBridge(MainActivity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public String readText() {
            try {
                android.content.ClipboardManager cm = (android.content.ClipboardManager)
                        activity.getSystemService(android.content.Context.CLIPBOARD_SERVICE);
                if (cm != null && cm.hasPrimaryClip()) {
                    android.content.ClipData clip = cm.getPrimaryClip();
                    if (clip != null && clip.getItemCount() > 0) {
                        CharSequence text = clip.getItemAt(0).coerceToText(activity);
                        return text == null ? "" : text.toString();
                    }
                }
            } catch (Throwable ignored) {}
            return "";
        }
    }
    private static class NativeDiscoveryBridge {
        private final MainActivity activity;

        NativeDiscoveryBridge(MainActivity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public void start() {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    if (activity.udpDiscovery != null) activity.udpDiscovery.start();
                }
            });
        }
    }

    private class UdpDiscovery {
        private DatagramSocket socket;
        private Thread thread;
        private volatile boolean running = false;

        void start() {
            if (thread != null) return;
            running = true;
            thread = new Thread(new Runnable() {
                @Override
                public void run() {
                    loop();
                }
            }, "rikka-udp-discovery");
            thread.setDaemon(true);
            thread.start();
        }

        private void loop() {
            try {
                socket = new DatagramSocket(null);
                socket.setReuseAddress(true);
                socket.setBroadcast(true);
                socket.bind(new InetSocketAddress(8766));
                socket.setSoTimeout(1000);
                byte[] buf = new byte[1024];
                while (running) {
                    try {
                        DatagramPacket p = new DatagramPacket(buf, buf.length);
                        socket.receive(p);
                        String json = new String(p.getData(), 0, p.getLength(), StandardCharsets.UTF_8);
                        JSONObject o = new JSONObject(json);
                        if ("petforge-phone-bridge".equals(o.optString("service"))) {
                            int port = o.optInt("port", 8765);
                            String ip = p.getAddress().getHostAddress();
                            onBridgeDiscovered(ip, port);
                        }
                    } catch (SocketTimeoutException e) {
                        // keep listening
                    } catch (Exception e) {
                        // ignore malformed packet
                    }
                }
            } catch (Exception e) {
                Log.w(TAG, "UDP discovery failed", e);
            } finally {
                if (socket != null) {
                    try { socket.close(); } catch (Exception ignored) {}
                    socket = null;
                }
            }
        }

        void stop() {
            running = false;
            if (socket != null) {
                try { socket.close(); } catch (Exception ignored) {}
                socket = null;
            }
        }
    }

    private String speechErrorMessage(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_AUDIO: return "录音错误";
            case SpeechRecognizer.ERROR_CLIENT: return "客户端错误";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS: return "麦克风权限不足";
            case SpeechRecognizer.ERROR_NETWORK: return "网络错误";
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT: return "网络超时";
            case SpeechRecognizer.ERROR_NO_MATCH: return "未识别到声音";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY: return "识别服务忙";
            case SpeechRecognizer.ERROR_SERVER: return "服务器错误";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT: return "语音超时";
            default: return "识别错误(" + error + ")";
        }
    }
    private void startSpeechRecognition() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                && checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            speechPermissionPending = true;
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, AUDIO_REQUEST);
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            sendSpeechEvent("onNativeSpeechError", "当前设备不支持语音识别");
            return;
        }
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (speechRecognizer == null) {
                    speechRecognizer = SpeechRecognizer.createSpeechRecognizer(MainActivity.this);
                    speechRecognizer.setRecognitionListener(new RecognitionListener() {
                        @Override
                        public void onReadyForSpeech(Bundle params) {}

                        @Override
                        public void onBeginningOfSpeech() {}

                        @Override
                        public void onRmsChanged(float rmsdB) {
                            float level = Math.max(0f, Math.min(1f, (rmsdB + 40f) / 40f));
                            sendSpeechEvent("onNativeSpeechLevel", String.valueOf(level));
                        }

                        @Override
                        public void onBufferReceived(byte[] buffer) {}

                        @Override
                        public void onEndOfSpeech() {
                            sendSpeechEvent("onNativeSpeechEnd", "");
                        }

                        @Override
                        public void onError(int error) {
                            String message = speechErrorMessage(error);
                            sendSpeechEvent("onNativeSpeechError", message);
                        }

                        @Override
                        public void onResults(Bundle results) {
                            ArrayList<String> values = results == null
                                    ? null : results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                            String text = values == null || values.isEmpty() ? "" : values.get(0);
                            sendSpeechEvent("onNativeSpeechFinal", text);
                        }

                        @Override
                        public void onPartialResults(Bundle partialResults) {
                            ArrayList<String> values = partialResults == null
                                    ? null : partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                            String text = values == null || values.isEmpty() ? "" : values.get(0);
                            sendSpeechEvent("onNativeSpeechPartial", text);
                        }

                        @Override
                        public void onEvent(int eventType, Bundle params) {}
                    });
                }
                Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN");
                intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
                intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
                intent.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 320L);
                intent.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 900L);
                intent.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 200L);
                speechRecognizer.startListening(intent);
            }
        });
    }

    private void setSpeechContinuous(boolean enabled) {
        speechContinuous = enabled;
    }

    private void stopSpeechRecognition() {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (speechRecognizer != null) {
                    try {
                        speechRecognizer.cancel();
                    } catch (Exception ignored) {}
                }
            }
        });
    }
    private void scheduleSpeechRestart() {
        webView.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (speechContinuous) startSpeechRecognition();
            }
        }, 350L);
    }
    private void sendPhotoEvent(String function, String base64) {
        if (webView == null) return;
        final String script = "window." + function + "(" + JSONObject.quote(base64 == null ? "" : base64) + ");";
        webView.post(new Runnable() {
            @Override
            public void run() {
                if (webView != null) webView.evaluateJavascript(script, null);
            }
        });
    }

    private static class NativePhotoBridge {
        private final MainActivity activity;

        NativePhotoBridge(MainActivity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public void capturePhoto() {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                        activity.startActivityForResult(intent, PHOTO_REQUEST);
                    } catch (Exception error) {
                        activity.sendPhotoEvent("onNativePhotoError", "无法打开相机：" + error.toString());
                    }
                }
            });
        }
    }
    private void sendSpeechEvent(String function, String value) {
        if (webView == null) return;
        final String script = "window." + function + "(" + JSONObject.quote(value == null ? "" : value) + ");";
        webView.post(new Runnable() {
            @Override
            public void run() {
                if (webView != null) webView.evaluateJavascript(script, null);
            }
        });
    }

    private static class NativeSpeechBridge {
        private final MainActivity activity;

        NativeSpeechBridge(MainActivity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public void startListening() {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    activity.startSpeechRecognition();
                }
            });
        }

        @JavascriptInterface
        public void stopListening() {
            activity.stopSpeechRecognition();
        }

        @JavascriptInterface
        public void setContinuous(boolean enabled) {
            activity.setSpeechContinuous(enabled);
        }
    }
    private static class NativeFaceBridge {
        private final Activity activity;

        NativeFaceBridge(Activity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public void setOrientation(final String mode) {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    activity.setRequestedOrientation(
                            "landscape".equals(mode)
                                    ? ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
                                    : ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
                }
            });
        }
        @JavascriptInterface
        public String detect(String jpegBase64) {
            Bitmap source = null;
            Bitmap rgb565 = null;
            try {
                if (jpegBase64 == null || jpegBase64.isEmpty()) {
                    return "{\"found\":false}";
                }
                int comma = jpegBase64.indexOf(',');
                String payload = comma >= 0 ? jpegBase64.substring(comma + 1) : jpegBase64;
                byte[] bytes = Base64.decode(payload, Base64.DEFAULT);
                source = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                if (source == null) {
                    return "{\"found\":false}";
                }
                rgb565 = source.copy(Bitmap.Config.RGB_565, false);
                source.recycle();
                source = null;
                if (rgb565 == null) {
                    return "{\"found\":false}";
                }
                int width = rgb565.getWidth();
                int height = rgb565.getHeight();
                FaceDetector detector = new FaceDetector(width, height, 1);
                FaceDetector.Face[] faces = new FaceDetector.Face[1];
                int count = detector.findFaces(rgb565, faces);
                if (count <= 0 || faces[0] == null) {
                    return "{\"found\":false}";
                }
                PointF midpoint = new PointF();
                faces[0].getMidPoint(midpoint);
                float eyesDistance = faces[0].eyesDistance();
                JSONObject result = new JSONObject();
                result.put("found", true);
                result.put("x", Math.max(0.0f, Math.min(1.0f, midpoint.x / width)));
                result.put("y", Math.max(0.0f, Math.min(1.0f, midpoint.y / height)));
                result.put("size", Math.max(0.03f, Math.min(1.0f, eyesDistance * 2.0f / width)));
                return result.toString();
            } catch (Throwable error) {
                Log.w(TAG, "Native face detector failed", error);
                return "{\"found\":false}";
            } finally {
                if (source != null) source.recycle();
                if (rgb565 != null) rgb565.recycle();
            }
        }
    }

    private static class AssetServer {
        private final AssetManager assets;
        private ServerSocket serverSocket;
        private Thread thread;
        private volatile boolean running;

        AssetServer(AssetManager assets) {
            this.assets = assets;
        }

        void start() throws IOException {
            serverSocket = new ServerSocket(0, 64, InetAddress.getByName("127.0.0.1"));
            running = true;
            thread = new Thread(new Runnable() {
                @Override
                public void run() {
                    loop();
                }
            }, "rikka-asset-server");
            thread.setDaemon(true);
            thread.start();
        }

        int getPort() {
            return serverSocket.getLocalPort();
        }

        void stop() {
            running = false;
            try {
                if (serverSocket != null) serverSocket.close();
            } catch (IOException ignored) {
            }
            serverSocket = null;
        }

        private void loop() {
            while (running) {
                try {
                    Socket socket = serverSocket.accept();
                    handle(socket);
                } catch (IOException e) {
                    if (running) e.printStackTrace();
                }
            }
        }

        private void handle(Socket socket) {
            try {
                InputStream raw = socket.getInputStream();
                ByteArrayOutputStream headerBytes = new ByteArrayOutputStream(2048);
                int previous = -1;
                int current;
                while ((current = raw.read()) != -1) {
                    headerBytes.write(current);
                    if (previous == '\r' && current == '\n') {
                        byte[] bytes = headerBytes.toByteArray();
                        int size = bytes.length;
                        if (size >= 4 && bytes[size - 4] == '\r' && bytes[size - 3] == '\n'
                                && bytes[size - 2] == '\r' && bytes[size - 1] == '\n') {
                            break;
                        }
                    }
                    previous = current;
                }
                String headers = new String(headerBytes.toByteArray(), StandardCharsets.US_ASCII);
                String firstLine = headers.split("\\r?\\n", 2)[0];
                String[] parts = firstLine.split(" ");
                if (parts.length < 2) {
                    send(socket, 400, "text/plain", "Bad Request".getBytes(StandardCharsets.UTF_8));
                    return;
                }
                String path = parts[1];
                int query = path.indexOf('?');
                if (query >= 0) path = path.substring(0, query);
                path = URLDecoder.decode(path, "UTF-8");
                if (path.equals("/")) path = "/index.html";
                if (path.contains("..")) {
                    send(socket, 403, "text/plain", "Forbidden".getBytes(StandardCharsets.UTF_8));
                    return;
                }
                InputStream input = null;
                try {
                    input = assets.open("web" + path);
                    send(socket, 200, serverMimeType(path), readAll(input));
                } catch (IOException e) {
                    send(socket, 404, "text/plain", "Not Found".getBytes(StandardCharsets.UTF_8));
                } finally {
                    if (input != null) try { input.close(); } catch (IOException ignored) {}
                }
            } catch (Exception e) {
                e.printStackTrace();
            } finally {
                try { socket.close(); } catch (IOException ignored) {}
            }
        }

        private byte[] readAll(InputStream input) throws IOException {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) != -1) output.write(buffer, 0, read);
            return output.toByteArray();
        }

        private void send(Socket socket, int status, String contentType, byte[] body) throws IOException {
            String reason = status == 200 ? "OK" : status == 404 ? "Not Found" : status == 403 ? "Forbidden" : "Bad Request";
            String header = "HTTP/1.1 " + status + " " + reason + "\r\n"
                    + "Content-Type: " + contentType + "\r\n"
                    + "Content-Length: " + body.length + "\r\n"
                    + "Access-Control-Allow-Origin: *\r\n"
                    + "Cache-Control: no-store\r\n"
                    + "Connection: close\r\n\r\n";
            OutputStream output = socket.getOutputStream();
            output.write(header.getBytes(StandardCharsets.US_ASCII));
            output.write(body);
            output.flush();
        }

        private static String serverMimeType(String path) {
            String mime = mimeType(path);
            String encoding = textEncoding(path);
            return encoding == null ? mime : mime + "; charset=" + encoding;
        }
    }
}



