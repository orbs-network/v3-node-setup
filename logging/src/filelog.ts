import { createReadStream } from "fs";
import { open } from "fs/promises";
import { Readable } from "stream";

/**
 * Serves the log files of the components that are not containers.
 *
 * `control`, `updater` and `recovery` run on the host, not in Docker, so there is no
 * Docker log stream to ask for. nginx used to serve their files directly with an `alias`,
 * which meant the query parameters were silently ignored and a request for the last 300
 * lines returned the entire file - 239,838 lines of it in control's case. Routing them
 * through here instead gives them the same URL and the same `tail`.
 */

const CHUNK_SIZE = 64 * 1024;
const NEWLINE = 0x0a;

/** The only names that may be read from disk. Not a path, so no traversal is possible. */
export const FILE_BACKED_COMPONENTS = ["control", "updater", "recovery"] as const;

export function isFileBacked(name: string): boolean {
  return (FILE_BACKED_COMPONENTS as readonly string[]).includes(name);
}

export function logFilePath(root: string, name: string): string {
  if (!isFileBacked(name)) {
    throw new Error(`'${name}' is not a file-backed component`);
  }
  return `${root}/${name}/log.txt`;
}

/**
 * The byte offset where the last `lines` lines begin.
 *
 * Reads backwards from the end in chunks rather than loading the file. These logs rotate
 * at 10MB, so reading one to return 300 lines from it would mean holding the whole thing
 * in memory to throw nearly all of it away.
 */
export async function tailOffset(path: string, lines: number): Promise<number> {
  const handle = await open(path, "r");

  try {
    const { size } = await handle.stat();
    if (size === 0 || lines <= 0) {
      return size;
    }

    const buffer = Buffer.alloc(CHUNK_SIZE);
    let position = size;
    let newlines = 0;

    while (position > 0) {
      const length = Math.min(CHUNK_SIZE, position);
      position -= length;
      await handle.read(buffer, 0, length, position);

      for (let i = length - 1; i >= 0; i -= 1) {
        if (buffer[i] !== NEWLINE) {
          continue;
        }
        // A newline in the final byte terminates the last line rather than starting
        // another one, so counting it would return one line fewer than asked for.
        if (position + i === size - 1) {
          continue;
        }
        newlines += 1;
        if (newlines === lines) {
          return position + i + 1;
        }
      }
    }

    // Fewer lines in the file than asked for, so return all of it. A short answer is the
    // right answer here, not an error.
    return 0;
  } finally {
    await handle.close();
  }
}

/**
 * Streams a component's log, optionally only its last `tail` lines.
 *
 * Only the live file is read, never the rotated `log.txt.1` beside it, so a `tail` larger
 * than the current file returns everything it holds rather than reaching back into the
 * previous one.
 */
export async function readLogFile(path: string, tail: number | "all"): Promise<Readable> {
  const start = tail === "all" ? 0 : await tailOffset(path, tail);
  return createReadStream(path, { start });
}
