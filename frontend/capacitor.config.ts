import type { CapacitorConfig } from "@capacitor/cli";

/**
 * AttendAI Android app. The React UI from `dist/` is bundled into the APK and talks to the
 * AttendAI server chosen in the app (default from VITE_DEFAULT_SERVER_URL at build time).
 */
const config: CapacitorConfig = {
  appId: "com.attendai.app",
  appName: "AttendAI",
  webDir: "dist",
  android: {
    // WebView origin is https://localhost (listed in the API's MOBILE_APP_ORIGINS).
    allowMixedContent: false,
    backgroundColor: "#0f2440",
  },
  plugins: {
    SystemBars: {
      insetsHandling: "css",
      initialViewportFitValueHint: "cover",
      style: "DARK",
    },
  },
};

export default config;
