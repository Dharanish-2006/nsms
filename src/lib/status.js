import { config } from "../config";

export const statusOf = (m, now) =>
  now - m.updatedAt > config.staleAfterMs ? "unknown" : m.on ? "on" : "off";
