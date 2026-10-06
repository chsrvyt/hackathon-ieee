package com.attendai.app;

import android.os.Bundle;
import androidx.activity.EdgeToEdge;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Capacitor switches from the launch theme to AppTheme.NoActionBar in super.onCreate.
        // Enabling edge-to-edge first would build the window with the launch theme, which shows
        // an action bar painted with the splash image on some devices.
        super.onCreate(savedInstanceState);
        // Draw behind the system bars; the web UI pads itself with the injected safe-area insets.
        EdgeToEdge.enable(this);
    }
}
