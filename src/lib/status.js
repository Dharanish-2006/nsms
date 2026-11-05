import { config } from "../config";

/** "on", "off", or "unknown" when the machine has not reported recently. */
export const statusOf = (m, now) =>
  now - m.updatedAt > config.staleAfterMs ? "unknown" : m.on ? "on" : "off";
