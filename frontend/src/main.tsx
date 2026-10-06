import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { ApiError } from "./api/client";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { initNativeShell, isNative } from "./native";
import "./styles.css";

if (isNative()) {
  document.documentElement.classList.add("native-app");
  void initNativeShell(
    () => window.history.back(),
    () => window.history.length > 1 && !["/me", "/dashboard", "/login"].includes(window.location.pathname),
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Retry network blips and server errors once; never retry 4xx (auth/validation won't fix itself).
      retry: (count, error) => count < 1 && (!(error instanceof ApiError) || error.status === 0 || error.status >= 500),
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
