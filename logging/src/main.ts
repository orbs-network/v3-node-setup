import express, { Express, NextFunction, Request, Response } from "express";
import { request, ClientRequest, RequestOptions, IncomingMessage } from "http";

const app: Express = express();
const port: number = 80;

// TODO: This can happen at the nginx level
const validNameRegex = /^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/;

app.use((_: Request, res: Response, next: NextFunction) => {
  res.setHeader("Content-Disposition", "inline");
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  next();
});

/**
 * Remove non-text data from Docker logs
 * Needed to prevent client browser from trying to download logs instead of displaying them
 * */
const decodeDockerLogs = (data: Buffer): string => {
  let str = "";
  let i = 0;
  while (i < data.length) {
    const len = data.readUInt32BE(i + 4);
    str += data.toString("utf8", i + 8, i + 8 + len);
    i += 8 + len;
  }
  return str;
};

app.get("/service/:name/logs", (req: Request, res: Response) => {
  const containerName: string = req.params.name;

  if (!validNameRegex.test(containerName)) {
    return res.status(400).send("Invalid container name");
  }

  const options: RequestOptions = {
    socketPath: "/var/run/docker.sock",
    path: `/containers/${containerName}/logs?stdout=1&stderr=1`,
    method: "GET",
  };

  const clientRequest: ClientRequest = request(
    options,
    (resp: IncomingMessage) => {
      if (resp.statusCode === 404) {
        // TODO: add proper logger
        console.log(
          `User ${req.ip} requested logs for non-existent service ${containerName}`
        );
        res.status(404).send("Service not found");
      } else if (resp.statusCode !== 200) {
        console.error("500 error: ", resp);
        res.status(500).send("An internal error occurred. Try again later");
      } else {
        console.log("BACK TO SQUARE THREE!!!");
        let data = "";
        // Log will be max 10MB due to log rotation
        resp.on("data", (chunk: Buffer) => {
          const logs = decodeDockerLogs(chunk);
          data += logs;
        });
        resp.on("end", () => {
          res.send(data);
        });
      }
    }
  );

  clientRequest.on("error", (e: Error) => {
    console.error("onError: ", e);
    res.status(500).send("An unexpected error occurred. Try again later");
  });

  clientRequest.end();
});

app.listen(port, () => {
  console.log(`Logging service listening at http://localhost:${port}`);
});
