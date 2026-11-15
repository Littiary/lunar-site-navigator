/// <reference types="vite/client" />

// Modules made at build time by the plugins in ../plugins.
declare module "virtual:lsn-facts" {
  const facts: unknown;
  export const digest: string;
  export default facts;
}

declare module "virtual:lsn-classic" {
  export const paneTemplate: string;
}
