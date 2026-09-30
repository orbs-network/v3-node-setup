/**
 * Translates our HTTP query parameters into a Docker log API query string.
 *
 * We deliberately speak Docker's vocabulary rather than inventing our own, so
 * anyone who knows `docker logs` already knows this endpoint. Everything here
 * is a passthrough to the daemon except the validation, which exists so that a
 * typo comes back as an error naming the parameter instead of being silently
 * dropped or handed to the daemon unchecked.
 */

/** A parameter we understand but whose value is wrong. Answered with 400. */
export class QueryError extends Error {}

/** A parameter we understand but do not implement yet. Answered with 501. */
export class UnsupportedQueryError extends Error {}

const TRUE_VALUES = new Set(["1", "true", "yes", "on"]);
const FALSE_VALUES = new Set(["0", "false", "no", "off"]);

const RELATIVE_AGE = /^(\d+)(s|m|h|d|w)$/;
const SECONDS_PER_UNIT: Record<string, number> = {
  s: 1,
  m: 60,
  h: 60 * 60,
  d: 24 * 60 * 60,
  w: 7 * 24 * 60 * 60,
};

/**
 * Express gives us `string | string[] | ParsedQs` per key. Anything but a
 * single string means the caller repeated the parameter or nested it, and we
 * would have to guess which one they meant.
 */
function scalar(name: string, raw: unknown): string | undefined {
  if (raw === undefined) {
    return undefined;
  }
  if (typeof raw !== "string") {
    throw new QueryError(`'${name}' must be given exactly once, as a plain value`);
  }
  const trimmed = raw.trim();
  if (trimmed === "") {
    throw new QueryError(`'${name}' was given with an empty value`);
  }
  return trimmed;
}

function boolean(name: string, raw: unknown, fallback: boolean): boolean {
  const value = scalar(name, raw);
  if (value === undefined) {
    return fallback;
  }
  const lowered = value.toLowerCase();
  if (TRUE_VALUES.has(lowered)) {
    return true;
  }
  if (FALSE_VALUES.has(lowered)) {
    return false;
  }
  throw new QueryError(`'${name}' must be one of 1/0/true/false, got '${value}'`);
}

function wholeNumber(name: string, value: string): number {
  if (!/^\d+$/.test(value)) {
    throw new QueryError(`'${name}' must be a non-negative whole number, got '${value}'`);
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) {
    throw new QueryError(`'${name}' is too large: '${value}'`);
  }
  return parsed;
}

function tailValue(raw: unknown): string {
  const value = scalar("tail", raw);
  if (value === undefined) {
    return "all";
  }
  if (value.toLowerCase() === "all") {
    return "all";
  }
  if (!/^\d+$/.test(value)) {
    throw new QueryError(`'tail' must be a non-negative whole number or 'all', got '${value}'`);
  }
  return String(wholeNumber("tail", value));
}

/**
 * Accepts a unix timestamp in seconds, an RFC3339 timestamp, or a relative age
 * such as `15m`. Relative ages are the reason this endpoint is usable by hand:
 * `?since=15m` beats working out a unix timestamp every time. Everything is
 * normalised to unix seconds so we do not depend on how a particular daemon
 * version parses date strings.
 */
function timestamp(name: string, raw: unknown, nowMillis: number): string | undefined {
  const value = scalar(name, raw);
  if (value === undefined) {
    return undefined;
  }

  const relative = RELATIVE_AGE.exec(value.toLowerCase());
  if (relative) {
    const seconds = wholeNumber(name, relative[1]) * SECONDS_PER_UNIT[relative[2]];
    if (!Number.isSafeInteger(seconds)) {
      throw new QueryError(`'${name}' is too large: '${value}'`);
    }
    return String(Math.max(0, Math.floor(nowMillis / 1000) - seconds));
  }

  if (/^\d+$/.test(value)) {
    return String(wholeNumber(name, value));
  }

  if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
    const parsed = Date.parse(value);
    if (Number.isNaN(parsed)) {
      throw new QueryError(`'${name}' is not a valid RFC3339 timestamp: '${value}'`);
    }
    return String(Math.floor(parsed / 1000));
  }

  throw new QueryError(
    `'${name}' must be a unix timestamp, an RFC3339 timestamp, ` +
      `or a relative age such as '15m' or '2h', got '${value}'`
  );
}

export function buildDockerLogQuery(
  query: Record<string, unknown>,
  nowMillis: number = Date.now()
): string {
  // Streaming is in place, but nginx still buffers this location, so a followed
  // stream would sit in nginx and never reach the client. Better to say so than
  // to hand the caller a request that hangs forever.
  if (query.follow !== undefined) {
    throw new UnsupportedQueryError(
      "'follow' is not supported yet: nginx buffers this endpoint, so a followed " +
        "stream would never reach you. Tracked in issue #69."
    );
  }

  const stdout = boolean("stdout", query.stdout, true);
  const stderr = boolean("stderr", query.stderr, true);
  if (!stdout && !stderr) {
    throw new QueryError(
      "'stdout' and 'stderr' cannot both be disabled: there would be nothing to return"
    );
  }

  const params = new URLSearchParams();
  params.set("stdout", stdout ? "1" : "0");
  params.set("stderr", stderr ? "1" : "0");
  params.set("tail", tailValue(query.tail));

  if (boolean("timestamps", query.timestamps, false)) {
    params.set("timestamps", "1");
  }

  const since = timestamp("since", query.since, nowMillis);
  if (since !== undefined) {
    params.set("since", since);
  }

  const until = timestamp("until", query.until, nowMillis);
  if (until !== undefined) {
    params.set("until", until);
  }

  return params.toString();
}
