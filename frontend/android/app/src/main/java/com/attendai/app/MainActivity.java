package com.attendai.app;

import android.os.Bundle;
import androidx.activity.EdgeToEdge;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Draw behind the system bars; the web UI pads itself with the injected safe-area insets.
        EdgeToEdge.enable(this);
        super.onCreate(savedInstanceState);
    }
}
