import { USE_MOCK } from "../config";
import { httpApi } from "./http";
import { mockApi } from "./mock";

export { ApiError, setUnauthorizedHandler } from "./client";
export { tokenStore } from "./token";

// USE_MOCK is a build-time constant, so a production build drops the demo data
// and fake accounts from the bundle entirely.
export const api = USE_MOCK ? mockApi : httpApi;
