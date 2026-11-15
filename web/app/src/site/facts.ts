// The build-time facts of the landing page (plugins/facts.ts), typed.
import raw from "virtual:lsn-facts";
import type { Facts } from "../../plugins/facts";

export type { Facts };
export type CardRow = Facts["card"]["rows"][number];
export type FailedCheck = Facts["card"]["failedRows"][number];
export type Site = Facts["sites"][number];

const facts = raw as Facts;
export default facts;
