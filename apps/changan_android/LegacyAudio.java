package com.changan.lanterns;

import android.app.Activity;
import android.content.res.AssetFileDescriptor;
import android.media.MediaPlayer;
import android.os.SystemClock;
import android.webkit.JavascriptInterface;
import android.util.Log;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/** Avoid the WebView 39 audio decoder. Keep native players only for currently sounding channels. */
public final class LegacyAudio {
    private final Activity activity;
    private final AtomicInteger sequence = new AtomicInteger();
    private final ConcurrentHashMap<Integer, Track> active = new ConcurrentHashMap<>();
    private static final class Track {
        MediaPlayer player;
        final int offset;
        volatile long began;
        float volume;
        Track(int offset, float volume) { this.offset = offset; this.volume = volume; }
    }
    LegacyAudio(Activity activity) { this.activity = activity; }
    private void dispose(int id) {
        Track track = active.remove(id);
        if (track != null && track.player != null) track.player.release();
    }
    @JavascriptInterface public int start(String path, int milliseconds, boolean loop, float volume) {
        if (!path.matches("media/audio-[0-9a-f]+\\.m4a") || active.size() >= 18) return 0;
        int id = sequence.incrementAndGet();
        Track track = new Track(Math.max(0, milliseconds), volume);
        active.put(id, track);
        activity.runOnUiThread(() -> {
            if (!active.containsKey(id)) return;
            MediaPlayer mp = new MediaPlayer();
            track.player = mp;
            try (AssetFileDescriptor fd = activity.getAssets().openFd(path)) {
                mp.setDataSource(fd.getFileDescriptor(), fd.getStartOffset(), fd.getLength());
                mp.setLooping(loop);
                mp.setOnCompletionListener(p -> dispose(id));
                mp.setOnErrorListener((p, what, extra) -> {
                    Log.w("ChanganGame", "Audio decode " + what + "/" + extra + " " + path);
                    dispose(id); return true;
                });
                mp.setOnPreparedListener(p -> {
                    if (!active.containsKey(id)) return;
                    p.setVolume(track.volume, track.volume);
                    if (track.offset > 0) {
                        p.setOnSeekCompleteListener(seeked -> {
                            if (active.containsKey(id)) { track.began = SystemClock.elapsedRealtime(); seeked.start(); }
                        });
                        p.seekTo(track.offset % Math.max(1, p.getDuration()));
                    } else { track.began = SystemClock.elapsedRealtime(); p.start(); }
                });
                mp.prepareAsync();
            } catch (Exception e) {
                Log.w("ChanganGame", "Cannot play " + path, e);
                dispose(id);
            }
        });
        return id;
    }
    @JavascriptInterface public boolean active(int id) { return active.containsKey(id); }
    @JavascriptInterface public int position(int id) {
        Track t = active.get(id);
        return t == null ? 0 : t.offset + (t.began == 0 ? 0 : (int)(SystemClock.elapsedRealtime() - t.began));
    }
    @JavascriptInterface public void volume(int id, float gain) {
        activity.runOnUiThread(() -> {
            Track t = active.get(id);
            if (t == null) return;
            t.volume = gain;
            if (t.player != null && t.began > 0) t.player.setVolume(gain, gain);
        });
    }
    @JavascriptInterface public void stop(int id) { activity.runOnUiThread(() -> dispose(id)); }
    void close() { for (int id : active.keySet()) dispose(id); }
}
