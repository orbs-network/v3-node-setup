import express, { Express, NextFunction, Request, Response } from "express";
import { request, ClientRequest, IncomingMessage } from "http";
import { writeStatusToDisk } from "./status";
import { DockerLogDemuxer } from "./demux";
import { buildDockerLogQuery, buildFileLogOptions, QueryError, UnsupportedQueryError } from "./query";
import { isFileBacked, logFilePath, readLogFile } from "./filelog";

const app: Express = express();
const port: number = 80;

const serviceLaunchTime = Math.round(new Date().getTime() / 1000);
const statusFilePath =
  process.env.STATUS_FILE_PATH || "/opt/orbs/status/status.json";
const dockerSocketPath = process.env.DOCKER_SOCKET_PATH || "/var/run/docker.sock";
// Where .data is mounted, read-only, so the non-container components' log files can be
// read. docker-compose.yml maps ./.data here.
const logsRoot = process.env.LOGS_ROOT || "/opt/orbs/logs";

let error = "";

setInterval(
  (function status() {
    // setInterval that also run immediately
    writeStatusToDisk(statusFilePath, serviceLaunchTime, error);
    error = "";
    return status;
  })(),
  5 * 60 * 1000
);

// TODO: This can happen at the nginx level
const validNameRegex = /^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/;

app.use((_: Request, res: Response, next: NextFunction) => {
  res.setHeader("Content-Disposition", "inline");
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  next();
});

interface DockerResponse {
  clientRequest: ClientRequest;
  response: IncomingMessage;
}

function dockerGet(path: string): Promise<DockerResponse> {
  return new Promise((resolve, reject) => {
    const clientRequest: ClientRequest = request(
      { socketPath: dockerSocketPath, path, method: "GET" },
      (response: IncomingMessage) => resolve({ clientRequest, response })
    );
    clientRequest.on("error", reject);
    clientRequest.end();
  });
}

async function readBody(response: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of response) {
    chunks.push(chunk as Buffer);
  }
  return Buffer.concat(chunks).toString("utf8");
}

class ContainerNotFound extends Error {}

/**
 * A container started with a TTY gets an unframed log stream, so demultiplexing
 * it would mangle the output. None of ours use one today, but the cost of being
 * wrong is unreadable logs, and the daemon will tell us for free.
 *
 * This doubles as the existence check: if the container is gone we find out here,
 * before any bytes have been written to the response and while we can still set
 * a status code.
 */
async function containerUsesTty(name: string): Promise<boolean> {
  const { response } = await dockerGet(`/containers/${encodeURIComponent(name)}/json`);

  if (response.statusCode === 404) {
    response.resume();
    throw new ContainerNotFound(name);
  }
  if (response.statusCode !== 200) {
    response.resume();
    throw new Error(`Docker returned ${response.statusCode} inspecting '${name}'`);
  }

  const inspected = JSON.parse(await readBody(response));
  return inspected?.Config?.Tty === true;
}

function respondToQueryError(err: unknown, res: Response): void {
  if (err instanceof UnsupportedQueryError) {
    error = err.message;
    res.status(501).send(`${err.message}\n`);
    return;
  }
  if (err instanceof QueryError) {
    error = err.message;
    res.status(400).send(`${err.message}\n`);
    return;
  }
  error = err instanceof Error ? err.message : String(err);
  console.error("Query error: ", err);
  res.status(500).send("An unexpected error occurred. Try again later\n");
}

/**
 * Serves a component that runs on the host rather than in Docker, by reading its log file.
 * Only the live file, and only `tail` - see filelog.ts and buildFileLogOptions.
 */
async function serveFileLog(req: Request, res: Response, component: string): Promise<void> {
  let options: { tail: number | "all" };

  try {
    options = buildFileLogOptions(req.query, component);
  } catch (err) {
    respondToQueryError(err, res);
    return;
  }

  try {
    const logs = await readLogFile(logFilePath(logsRoot, component), options.tail);

    logs.on("error", (err: Error) => {
      error = err.message;
      console.error("Log file stream error: ", err);
      res.destroy();
    });

    res.on("close", () => logs.destroy());
    logs.pipe(res);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      // Expected for updater and recovery, which have routes but nothing writing them.
      console.log(`User ${req.ip} requested logs for ${component}, which has no log file`);
      error = `No log file for ${component}`;
      res.status(404).send(`${error}\n`);
      return;
    }
    error = err instanceof Error ? err.message : String(err);
    console.error("onError: ", err);
    res.status(500).send("An unexpected error occurred. Try again later\n");
  }
}

app.get("/service/:name/log", async (req: Request, res: Response) => {
  const containerName: string = req.params.name;

  if (!validNameRegex.test(containerName)) {
    error = "Invalid container name";
    res.status(400).send(`${error}\n`);
    return;
  }

  if (isFileBacked(containerName)) {
    await serveFileLog(req, res, containerName);
    return;
  }

  let dockerQuery: string;
  try {
    dockerQuery = buildDockerLogQuery(req.query);
  } catch (err) {
    respondToQueryError(err, res);
    return;
  }

  try {
    const tty = await containerUsesTty(containerName);
    const { clientRequest, response } = await dockerGet(
      `/containers/${encodeURIComponent(containerName)}/logs?${dockerQuery}`
    );

    if (response.statusCode === 404) {
      response.resume();
      throw new ContainerNotFound(containerName);
    }
    if (response.statusCode !== 200) {
      response.resume();
      throw new Error(`Docker returned ${response.statusCode} reading logs for '${containerName}'`);
    }

    // Piped rather than accumulated: the json-file driver keeps up to
    // max-size * max-file per container (150MB as configured in
    // docker-compose.yml), and the API reads across the rotated files, so an
    // unfiltered request would otherwise buffer all of it before sending a byte.
    const logs = tty ? response : response.pipe(new DockerLogDemuxer());
    logs.pipe(res);

    // A client that gives up halfway must not leave the daemon streaming the
    // rest of a 150MB log into a socket nobody is reading.
    res.on("close", () => {
      clientRequest.destroy();
      response.destroy();
    });

    response.on("error", (err: Error) => {
      error = err.message;
      console.error("Log stream error: ", err);
      res.destroy();
    });
  } catch (err) {
    if (err instanceof ContainerNotFound) {
      console.log(
        `User ${req.ip} requested logs for non-existent service ${containerName}`
      );
      error = "Service not found";
      res.status(404).send(`${error}\n`);
      return;
    }
    error = err instanceof Error ? err.message : String(err);
    console.error("onError: ", err);
    res.status(500).send("An unexpected error occurred. Try again later\n");
  }
});

app.listen(port, () => {
  console.log(`Logging service listening at http://localhost:${port}`);
});
