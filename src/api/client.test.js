import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, request, setUnauthorizedHandler } from "./client";
import { tokenStore } from "./token";

const reply = (status, body) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: body === undefined ? {} : { "content-type": "application/json" },
  });

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.clear();
  setUnauthorizedHandler(() => {});
});

describe("api client", () => {
  it("sends the token and builds the URL from the base path and query", async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    tokenStore.set("abc");

    const data = await request("/machines", { query: { plant: "Plant 1", empty: "" } });

    expect(data).toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("http://localhost/api/machines?plant=Plant+1");
    expect(init.headers.Authorization).toBe("Bearer abc");
  });

  it("returns null for 204 responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(204)));
    expect(await request("/x", { method: "DELETE" })).toBeNull();
  });

  it("turns server errors into ApiError carrying the server's message", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(reply(422, { message: "Bad limits", code: "validation" })),
    );
    await expect(
      request("/thresholds", { method: "POST", body: {} }),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      code: "validation",
      message: "Bad limits",
    });
  });

  it("does not leak raw server error text for 5xx responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(500)));
    const err = await request("/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe("Something went wrong on the server.");
  });

  it("clears the token and signs out on 401, except for login itself", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(401, { message: "Expired" })));
    tokenStore.set("old");

    await expect(request("/machines")).rejects.toThrow("Expired");
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(tokenStore.get()).toBeNull();

    await expect(
      request("/auth/login", { method: "POST", auth: false }),
    ).rejects.toThrow();
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("reports an unreachable server in plain words", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(request("/x")).rejects.toMatchObject({
      code: "network",
      message: "Cannot reach the server. Check your connection.",
    });
  });
});
