/// <reference types="vite/client" />

declare module "virtual:lsn-facts" {
  const facts: unknown;
  export const digest: string;
  export default facts;
}
