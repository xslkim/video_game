package com.changan.lanterns;

import android.app.Activity;
import android.content.res.AssetFileDescriptor;
import android.graphics.SurfaceTexture;
import android.media.MediaPlayer;
import android.util.Log;
import android.view.Surface;
import android.view.TextureView;
import android.webkit.JavascriptInterface;

/** Play directly from the APK on televisions whose WebView cannot advance an inline video. */
public final class LegacyFilm implements TextureView.SurfaceTextureListener {
    private final Activity activity;
    private MediaPlayer player;
    private Surface surface;
    private String source;
    private int offset;
    private float gain = 1;
    private volatile int position;
    private volatile int state; // 0 preparing, 1 playing, 2 paused, 3 ended, -1 failed
    private boolean wantPlay = true;

    LegacyFilm(Activity activity, TextureView texture) {
        this.activity = activity;
        texture.setSurfaceTextureListener(this);
    }
    private void releasePlayer() {
        if (player != null) {
            player.release();
            player = null;
        }
    }
    private void prepare() {
        releasePlayer();
        if (surface == null || source == null) return;
        MediaPlayer next = new MediaPlayer();
        player = next;
        try (AssetFileDescriptor fd = activity.getAssets().openFd(source)) {
            next.setSurface(surface);
            next.setDataSource(fd.getFileDescriptor(), fd.getStartOffset(), fd.getLength());
            next.setVolume(gain, gain);
            next.setOnErrorListener((mp, what, extra) -> {
                if (mp == player) state = -1;
                Log.e("ChanganGame", "Native decoder " + what + "/" + extra + " " + source);
                return true;
            });
            next.setOnCompletionListener(mp -> {
                if (mp == player) { position = mp.getDuration(); state = 3; }
            });
            next.setOnPreparedListener(mp -> {
                if (mp != player) return;
                if (offset > 0) {
                    mp.setOnSeekCompleteListener(seeked -> { if (seeked == player) beginPlayback(); });
                    mp.seekTo(offset);
                } else beginPlayback();
            });
            next.prepareAsync();
        } catch (Exception e) {
            Log.e("ChanganGame", "Cannot open " + source, e);
            state = -1;
        }
    }
    private void beginPlayback() {
        if (wantPlay) player.start();
        state = wantPlay ? 1 : 2;
    }
    @JavascriptInterface public void open(String path, int ms) {
        if (!path.matches("media/video-[0-9a-f]+\\.mp4")) throw new IllegalArgumentException("Invalid film");
        state = 0;
        position = ms;
        activity.runOnUiThread(() -> {
            source = path;
            offset = ms;
            wantPlay = true;
            prepare();
        });
    }
    @JavascriptInterface public int status() { return state; }
    @JavascriptInterface public int milliseconds() { return position; }
    @JavascriptInterface public void playing(boolean on) {
        activity.runOnUiThread(() -> {
            wantPlay = on;
            if (player == null) return;
            if (on && state == 2) beginPlayback();
            else if (!on && state == 1) { player.pause(); state = 2; }
        });
    }
    @JavascriptInterface public void volume(float value) {
        activity.runOnUiThread(() -> {
            gain = Math.max(0, Math.min(value, 1));
            if (player != null && state > 0) player.setVolume(gain, gain);
        });
    }
    @Override public void onSurfaceTextureAvailable(SurfaceTexture t, int w, int h) {
        surface = new Surface(t);
        prepare();
    }
    @Override public void onSurfaceTextureUpdated(SurfaceTexture t) {
        if (player != null && state == 1) position = player.getCurrentPosition();
    }
    @Override public void onSurfaceTextureSizeChanged(SurfaceTexture t, int w, int h) {}
    @Override public boolean onSurfaceTextureDestroyed(SurfaceTexture t) {
        close();
        return true;
    }
    void close() {
        releasePlayer();
        if (surface != null) { surface.release(); surface = null; }
    }
}
