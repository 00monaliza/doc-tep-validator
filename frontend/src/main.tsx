import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { Providers } from "./app/providers";
import { routes } from "./app/router";
import "./design/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Providers><RouterProvider router={createBrowserRouter(routes)} /></Providers>
  </StrictMode>,
);
