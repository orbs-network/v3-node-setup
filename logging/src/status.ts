import * as fs from 'fs';
import {dirname} from "path";

export async function generateStatusObj(serviceLaunchTime: number, err?: string) {
    const status: any = {}
    if (err) {
        status['Status'] = 'Error';
        status['Error'] = err;
    }
    else {
        status['Status'] = 'OK';
    }
    Object.assign({
        Timestamp: new Date().toISOString(),
        Payload: {
            Uptime: Math.round(new Date().getTime() / 1000) - serviceLaunchTime,
            MemoryBytesUsed: process.memoryUsage().heapUsed,
            Version: {
                Semantic: getCurrentVersion(),
            },
        },
    }, status);
    return status;
}

export async function writeStatusToDisk(filePath: string, serviceLaunchTime: number, err?: string) {
    const status = await generateStatusObj(serviceLaunchTime, err);

    fs.mkdirSync(dirname(filePath), { recursive: true });
    const content = JSON.stringify(status, null, 2);
    fs.writeFileSync(filePath, content);

    console.log(`Wrote status JSON to ${filePath} (${content.length} bytes).`);
}

export function getCurrentVersion() { // TODO: need to update .version file during CI/CD
    try {
        return fs.readFileSync('./version').toString().trim();
    } catch (err) {
        console.error(`Could not find version: ${err.message}`);
    }
    return '';
}