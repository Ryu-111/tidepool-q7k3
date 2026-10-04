package dev.ryu.jevprobe;

import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.os.Build;
import java.io.ByteArrayOutputStream;
import java.util.Timer;
import java.util.TimerTask;
import java.util.UUID;
import java.util.function.Consumer;

/** Dummy probe only: one-shot adb channel, no argv, clipboard, file or log containing the key. */
final class EmulatorKey {
    static boolean receive(Consumer<String> ready) {
        if (!"ranchu".equals(Build.HARDWARE)) return false;
        Timer timer = new Timer(true);
        LocalServerSocket server = null;
        try {
            String name = "jevprobe-key-" + UUID.randomUUID().toString().replace("-", "");
            server = new LocalServerSocket(name);
            final LocalServerSocket listener = server;
            timer.schedule(new TimerTask() {
                public void run() { try { listener.close(); } catch (Exception ignored) { } }
            }, 30000);
            ready.accept(name); // Publish only after binding: no other app can squat this name.
            try (LocalSocket socket = server.accept()) {
                int uid = socket.getPeerCredentials().getUid();
                if (uid != 2000 && uid != 0) return false; // adb shell / rooted emulator adbd only
                socket.setSoTimeout(3000);
                ByteArrayOutputStream buffer = new ByteArrayOutputStream();
                int c;
                while ((c = socket.getInputStream().read()) != '\n') {
                    if (c < 33 || c > 126 || c == '\'' || c == '"' || buffer.size() >= 4096)
                        return false;
                    buffer.write(c);
                }
                if (buffer.size() == 0) return false;
                if (!MainActivity.setKey(buffer.toString("US-ASCII"))) return false;
                socket.getOutputStream().write(new byte[]{'O', 'K', '\n'});
                return true;
            }
        } catch (Exception ignored) {
            return false; // Never expose exception details from a credential channel.
        } finally {
            timer.cancel();
            if (server != null) try { server.close(); } catch (Exception ignored) { }
        }
    }
}
