/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PROFILE_SERVICE_URL?: string;
  readonly VITE_RECIPE_SERVICE_URL?: string;
  readonly VITE_PLANNER_SERVICE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

