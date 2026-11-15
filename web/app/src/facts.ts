// The build-time facts of the landing page (see plugins/facts.ts), typed.
import raw from "virtual:lsn-facts";
import type { Facts } from "../plugins/facts";

const facts = raw as Facts;
export default facts;
