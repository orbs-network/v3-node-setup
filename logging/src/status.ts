import * as fs from "fs";
import { dirname } from "path";

export function generateStatusObj(serviceLaunchTime: number, err?: string) {
  let status: any = {};
  if (err) {
    status["Status"] = "Error";
    status["Error"] = err;
  } else {
    status["Status"] = "OK";
  }
  status = Object.assign(
    {
      Timestamp: new Date().toISOString(),
      Payload: {
        Uptime: Math.round(new Date().getTime() / 1000) - serviceLaunchTime,
        MemoryBytesUsed: process.memoryUsage().heapUsed,
      },
    },
    status
  );
  return status;
}

export function writeStatusToDisk(
  filePath: string,
  serviceLaunchTime: number,
  err?: string
) {
  const status = generateStatusObj(serviceLaunchTime, err);

  fs.mkdirSync(dirname(filePath), { recursive: true });
  const content = JSON.stringify(status, null, 2);
  fs.writeFileSync(filePath, content);

  console.log(`Wrote status JSON to ${filePath} (${content.length} bytes).`);
}
