package com.changan.lanterns;

import android.app.Activity;
import android.content.res.AssetFileDescriptor;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.ByteArrayInputStream;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

public final class GameActivity extends Activity {
    private WebView page;
    private LegacyFilm legacy;
    private LegacyAudio legacyAudio;
    private GunInput gun;
    private static final String ORIGIN = "https://lantern.local/";

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().getDecorView().setSystemUiVisibility(5894);
        getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        page = new WebView(this);
        page.setBackgroundColor(0xff101720);
        page.getSettings().setJavaScriptEnabled(true);
        page.getSettings().setDomStorageEnabled(true);
        page.getSettings().setMediaPlaybackRequiresUserGesture(false);
        page.getSettings().setAllowFileAccess(false);
        page.getSettings().setAllowContentAccess(false);
        page.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage msg) {
                Log.i("ChanganGame",
                      msg.messageLevel() + " " + msg.message() + " [" + msg.lineNumber() + "]");
                return true;
            }
        });
        page.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return !url.startsWith(ORIGIN);
            }
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !request.getUrl().toString().startsWith(ORIGIN);
            }
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return local(request);
            }
        });
        gun = new GunInput(
            (command, x,
             y) -> runOnUiThread(() -> script("window.gunEvent && window.gunEvent('" + command + "'," + x + "," + y + ")")));
        page.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public boolean gunMode(boolean enabled) {
                return gun.enable(enabled);
            }
        }, "LanternDevice");
        if (android.os.Build.VERSION.SDK_INT <= 23) {
            android.widget.FrameLayout frame = new android.widget.FrameLayout(this);
            android.view.TextureView video = new android.view.TextureView(this);
            frame.addView(video);
            frame.addView(page);
            frame.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> {
                int width = Math.min(r - l, (b - t) * 16 / 9);
                android.widget.FrameLayout.LayoutParams layout = new android.widget.FrameLayout.LayoutParams(
                    width, width * 9 / 16, android.view.Gravity.CENTER);
                if (video.getWidth() != layout.width || video.getHeight() != layout.height)
                    video.setLayoutParams(layout);
            });
            legacy = new LegacyFilm(this, video);
            page.addJavascriptInterface(legacy, "LanternFilm");
            legacyAudio = new LegacyAudio(this);
            page.addJavascriptInterface(legacyAudio, "LanternAudio");
            page.setBackgroundColor(android.graphics.Color.TRANSPARENT);
            setContentView(frame);
        } else setContentView(page);
        page.requestFocus();
        String qa = getIntent().getStringExtra("qa");
        page.loadUrl(ORIGIN + "index.html" +
                     ("full".equals(qa) || "resume".equals(qa) || "gun".equals(qa) || "codec".equals(qa)
                          ? "?qa=" + qa : ""));
    }

    private WebResourceResponse local(WebResourceRequest request) {
        String uri = request.getUrl().toString();
        String path = request.getUrl().getPath();
        if (!uri.startsWith(ORIGIN) || path == null || !path.matches("/[A-Za-z0-9_./-]+") ||
            path.contains(".."))
            return empty(403, "Forbidden");
        path = path.substring(1);
        String type = path.endsWith(".mp4")    ? "video/mp4"
                      : path.endsWith(".m4a")  ? "audio/mp4"
                      : path.endsWith(".js")   ? "application/javascript"
                      : path.endsWith(".json") ? "application/json"
                      : path.endsWith(".css")  ? "text/css"
                      : path.endsWith(".jpg")  ? "image/jpeg"
                      : path.endsWith(".webp") ? "image/webp"
                      : path.endsWith(".html") ? "text/html"
                                               : "application/octet-stream";
        try {
            if (!type.startsWith("video/") && !type.startsWith("audio/"))
                return new WebResourceResponse(type, null, getAssets().open(path));
            try (AssetFileDescriptor fd = getAssets().openFd(path)) {
                long length = fd.getLength(), start = 0, end = length - 1;
                String range = request.getRequestHeaders().get("Range");
                if (range == null)
                    range = request.getRequestHeaders().get("range");
                if (range != null) {
                    if (!range.matches("bytes=[0-9]+-[0-9]*"))
                        return empty(416, "Invalid range");
                    String[] bounds = range.substring(6).split("-", -1);
                    start = Long.parseLong(bounds[0]);
                    if (!bounds[1].isEmpty())
                        end = Math.min(end, Long.parseLong(bounds[1]));
                    if (start > end)
                        return empty(416, "Invalid range");
                }
                InputStream input = getAssets().open(path, android.content.res.AssetManager.ACCESS_RANDOM);
                long toSkip = start;
                while (toSkip > 0) {
                    long skipped = input.skip(toSkip);
                    if (skipped <= 0) {
                        input.close();
                        throw new IOException("Cannot seek to media range");
                    }
                    toSkip -= skipped;
                }
                final long span = end - start + 1;
                InputStream bounded = new FilterInputStream(input) {
                    long remaining = span;
                    @Override
                    public int read(byte[] b, int off, int len) throws IOException {
                        if (remaining == 0)
                            return -1;
                        int n = super.read(b, off, (int)Math.min(remaining, len));
                        if (n > 0)
                            remaining -= n;
                        return n;
                    }
                    @Override
                    public int read() throws IOException {
                        if (remaining == 0)
                            return -1;
                        int n = super.read();
                        if (n >= 0)
                            --remaining;
                        return n;
                    }
                };
                Map<String, String> headers = new HashMap<>();
                headers.put("Accept-Ranges", "bytes");
                headers.put("Content-Length", Long.toString(span));
                if (range != null)
                    headers.put("Content-Range", "bytes " + start + "-" + end + "/" + length);
                return new WebResourceResponse(type, null, range == null ? 200 : 206,
                                               range == null ? "OK" : "Partial Content", headers, bounded);
            }
        } catch (IOException | NumberFormatException e) {
            Log.w("ChanganGame", "Asset " + path + ": " + e.getMessage());
            return empty(404, "Not found");
        }
    }

    private static WebResourceResponse empty(int code, String message) {
        return new WebResourceResponse("text/plain", "utf-8", code, message, new HashMap<>(),
                                       new ByteArrayInputStream(new byte[0]));
    }
    private void script(String expression) {
        if (page != null)
            page.evaluateJavascript(expression, null);
    }
    @Override
    public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
        if ((event.getSource() & android.view.InputDevice.SOURCE_JOYSTICK) ==
            android.view.InputDevice.SOURCE_JOYSTICK) {
            float x = event.getAxisValue(android.view.MotionEvent.AXIS_X);
            float y = event.getAxisValue(android.view.MotionEvent.AXIS_Y);
            script("window.stickAim && window.stickAim(" + x + "," + y + ")");
            return true;
        }
        return super.dispatchGenericMotionEvent(event);
    }
    @Override
    public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        String action;
        switch (event.getKeyCode()) {
        case android.view.KeyEvent.KEYCODE_BUTTON_A:
        case android.view.KeyEvent.KEYCODE_BUTTON_R2:
            action = "shoot";
            break;
        case android.view.KeyEvent.KEYCODE_BUTTON_X:
            action = "reload";
            break;
        case android.view.KeyEvent.KEYCODE_BUTTON_Y:
            action = "special";
            break;
        case android.view.KeyEvent.KEYCODE_BUTTON_START:
            action = "start";
            break;
        default:
            return super.dispatchKeyEvent(event);
        }
        if (event.getAction() == android.view.KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0)
            script("window.padAction && window.padAction('" + action + "')");
        return true;
    }
    @Override
    public void onBackPressed() {
        script("window.togglePause && window.togglePause()");
    }
    @Override
    protected void onPause() {
        script("window.pauseGame && window.pauseGame()");
        page.onPause();
        super.onPause();
    }
    @Override
    protected void onResume() {
        super.onResume();
        if (page != null)
            page.onResume();
    }
    @Override
    protected void onDestroy() {
        if (legacy != null) legacy.close();
        if (legacyAudio != null) legacyAudio.close();
        if (gun != null)
            gun.enable(false);
        if (page != null) {
            page.removeJavascriptInterface("LanternDevice");
            page.destroy();
            page = null;
        }
        super.onDestroy();
    }
}
