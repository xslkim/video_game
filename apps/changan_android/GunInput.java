package com.changan.lanterns;

import android.os.SystemClock;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.BindException;
import java.io.IOException;
import android.util.Log;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;

final class GunInput {
    interface Listener {
        void event(String command, double x, double y);
    }
    private final Listener listener;
    private DatagramSocket game, discovery;
    private InetAddress peer;
    private String session;
    private long seen, aimTime, lastAim = -1, lastLost = -1, floor = -1;
    private double x, y;
    private boolean locked;
    private final Set<Long> shots = new HashSet<>();
    private final Set<String> retired = new HashSet<>();
    GunInput(Listener listener) { this.listener = listener; }

    private static DatagramSocket bind(int port) throws IOException {
        DatagramSocket socket = new DatagramSocket(null);
        try {
            socket.setReuseAddress(true);
            socket.bind(new InetSocketAddress(port));
            return socket;
        } catch (IOException e) {
            socket.close();
            throw e;
        }
    }

    synchronized boolean enable(boolean yes) {
        if (yes && game != null && !game.isClosed())
            return true;
        if (game != null)
            game.close();
        if (discovery != null)
            discovery.close();
        game = discovery = null;
        peer = null;
        session = null;
        locked = false;
        retired.clear();
        shots.clear();
        lastAim = lastLost = floor = -1;
        if (!yes)
            return true;
        try {
            try {
                game = bind(9000);
            } catch (BindException occupied) {
                game = bind(0);
            }
            discovery = bind(8001);
            game.setSoTimeout(150);
            listen(game, false);
            listen(discovery, true);
            Log.i("ChanganGame", "TVGun discovery 8001, input " + game.getLocalPort());
            return true;
        } catch (Exception e) {
            Log.w("ChanganGame", "TVGun socket unavailable", e);
            enable(false);
            return false;
        }
    }

    private void listen(final DatagramSocket socket, final boolean announce) {
        Thread worker = new Thread(() -> {
            byte[] buf = new byte[192];
            while (!socket.isClosed()) {
                DatagramPacket packet = new DatagramPacket(buf, buf.length);
                try {
                    socket.receive(packet);
                    String msg = new String(buf, 0, packet.getLength(), StandardCharsets.UTF_8).trim();
                    String reply = announce ? ("TVGUN_DISCOVER".equals(msg) && game != null
                                                   ? "TVGUN_HERE " + game.getLocalPort()
                                                   : null)
                                            : accept(msg, packet.getAddress());
                    if (reply != null) {
                        byte[] bytes = reply.getBytes(StandardCharsets.UTF_8);
                        socket.send(
                            new DatagramPacket(bytes, bytes.length, packet.getAddress(), packet.getPort()));
                    }
                } catch (SocketTimeoutException ignored) {
                    synchronized (this) {
                        if (game == socket && locked && SystemClock.elapsedRealtime() - aimTime > 600)
                            lost();
                    }
                } catch (Exception ignored) {
                    if (socket.isClosed())
                        return;
                }
            }
        }, "Changan TVGun");
        worker.setDaemon(true);
        worker.start();
    }

    private void lost() {
        locked = false;
        lastLost = lastAim;
        listener.event("lost", 0, 0);
    }
    private synchronized String accept(String msg, InetAddress sender) {
        long now = SystemClock.elapsedRealtime();
        if (peer != null && !peer.equals(sender) && now - seen < 2000)
            return null;
        if (msg.startsWith("HELLO ")) {
            String id = msg.substring(6);
            if (id.length() < 8 || retired.contains(id))
                return null;
            if (!id.equals(session) || !sender.equals(peer)) {
                if (locked)
                    lost();
                if (session != null) {
                    if (retired.size() > 64)
                        retired.clear();
                    retired.add(session);
                }
                peer = sender;
                session = id;
                shots.clear();
                lastAim = lastLost = floor = -1;
            }
            seen = now;
            return "FRAME 24,48";
        }
        if (!sender.equals(peer))
            return null;
        seen = now;
        if (msg.equals("START") || msg.equals("COIN"))
            listener.event("start", 0, 0);
        else if (msg.equals("EXIT"))
            listener.event("exit", 0, 0);
        else if (msg.equals("RELOAD"))
            listener.event("reload", 0, 0);
        else if (msg.equals("SPECIAL")) {
            if (locked && now - aimTime <= 600)
                listener.event("special", x, y);
        } else if (msg.equals("SHOT")) {
            if (locked && now - aimTime <= 100)
                listener.event("shoot", x, y);
        } else if (msg.startsWith("LOST,")) {
            long seq = Long.parseLong(msg.substring(5));
            if (seq > lastAim) {
                lastAim = seq;
                lost();
            }
        } else {
            boolean shot = msg.startsWith("SHOT ");
            String[] a = (shot ? msg.substring(5) : msg).split(",");
            if (a.length != (shot ? 3 : 4))
                return null;
            double px = Double.parseDouble(a[0]), py = Double.parseDouble(a[1]);
            if (Double.isInfinite(px) || Double.isNaN(px) || Double.isInfinite(py) || Double.isNaN(py))
                return null;
            long seq = Long.parseLong(a[a.length - 1]);
            if (shot) {
                if (locked && now - aimTime <= 600 && seq > lastLost && seq > floor && shots.add(seq)) {
                    listener.event("shoot", px, py);
                    if (shots.size() > 512) {
                        floor = java.util.Collections.min(shots);
                        shots.remove(floor);
                    }
                }
            } else {
                int grade = Integer.parseInt(a[2]);
                if (grade >= 1 && grade <= 4 && seq > lastAim) {
                    x = px;
                    y = py;
                    lastAim = seq;
                    aimTime = now;
                    locked = true;
                    listener.event("aim", x, y);
                }
            }
        }
        return null;
    }
}
