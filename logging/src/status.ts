import {pruneTailLists} from './tail';
import {RotationState, State, Tailer} from './model/state';
import * as fs from 'fs';
import {writeFileSync} from 'fs';
import {exec} from 'child-process-promise';
import {ensureFileDirectoryExists, getCurrentClockTime, JsonResponse} from './helpers';
import {Configuration} from './config';

async function getOpenFilesCount() {
    const result = await exec('lsof -l | wc -l');
    return parseInt(result.stdout);
}

function renderTailProcessDesc(t: Tailer) {
    return {
        processId: t.childProcess.pid,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        status: `exit code: ${(t.childProcess as any).exitCode} signal: ${(t.childProcess as any).signalCode}`,
        start: t.start ? t.start.toISOString() : 'NA',
        end: t.end ? t.end.toISOString() : 'NA',
        url: t.url,
        headers: t.requestHeaders,
        bytesRead: t.bytesRead,
    };
}

function renderServices(services: { [p: string]: RotationState })  {
    const result : {[p: string]: {}} = {};
    for (const serviceName in services) {
        result[serviceName] = {
            'urls': {
                'manifest': `/logs/${serviceName}`,
                'tail': `/logs/${serviceName}/tail`,
            },
            ...services[serviceName]
        };
    }
    return result;
}

export async function generateStatusObj(err?: Error) {
    // include error field if found errors
    const errorText = getErrorText(state, config, err);
    const status: JsonResponse = {
        Status: errorText ? 'Error' : 'OK',
        Error: errorText,
        Timestamp: new Date().toISOString(),
        Payload: {
            Uptime: getCurrentClockTime() - state.ServiceLaunchTime,
            MemoryBytesUsed: process.memoryUsage().heapUsed,
            Version: {
                Semantic: state.CurrentVersion,
            },
            OpenFiles,
            Config: config,
            Services: renderServices(state.Services),
            TailsActive: state.ActiveTails.map(renderTailProcessDesc),
            TailsTerm: state.TerminatedTails.map(renderTailProcessDesc),
        },
    };

    return status;
}

export async function writeStatusToDisk(filePath: string, state: State, config: Configuration, err?: Error) {
    const status = await generateStatusObj(state, config, err);

    // do the actual writing to local file
    ensureFileDirectoryExists(filePath);
    const content = JSON.stringify(status, null, 2);
    writeFileSync(filePath, content);

    // log progress
    console.log(`Wrote status JSON to ${filePath} (${content.length} bytes).`);
}

// helpers

function getErrorText(state: State, config: Configuration, err?: Error) {
    const res = [];

    if (state.ServiceLaunchTime === 0) {
        // TODO replace with a meaning full inspection of the state
        res.push('Invalid launch time');
    }

    if (!fs.existsSync(config.LogsPath)) {
        res.push('Disk access error');
    }

    if (err) {
        res.push(`Error: ${err.message}.`);
    }
    return res.length ? res.join(',') : undefined;
}