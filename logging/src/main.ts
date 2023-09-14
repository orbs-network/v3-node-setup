import express, { Express, NextFunction, Request, Response } from "express";
import { request, ClientRequest, RequestOptions, IncomingMessage } from "http";
import {writeStatusToDisk} from "./status";

const app: Express = express();
const port: number = 80;

const serviceLaunchTime = Date.now();
const statusFilePath = process.env.STATUS_FILE_PATH || "/opt/orbs/status/status.json";

let error = '';

setInterval( function() { writeStatusToDisk(statusFilePath, serviceLaunchTime, error); }, 5*60*1000 );

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
    error = "Invalid container name";
    return res.status(400).send(error);
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
          error = "Service not found";
          res.status(404).send(error);
        } else if (resp.statusCode !== 200) {
          error = resp;
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
    error = e.message;
    console.error("onError: ", e);
    res.status(500).send("An unexpected error occurred. Try again later");
  });

  clientRequest.end();
});

app.listen(port, () => {
  console.log(`Logging service listening at http://localhost:${port}`);
});
