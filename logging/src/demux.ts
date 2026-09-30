import { Transform, TransformCallback } from "stream";

/**
 * Strips Docker's stream multiplexing framing.
 *
 * A non-TTY container's log stream is a sequence of frames, each an 8 byte
 * header (byte 0 is the stream id, bytes 4-7 a big endian payload length)
 * followed by that many payload bytes.
 *
 * The framing does not respect socket chunk boundaries: a header can be split
 * across two `data` events, and a payload routinely is. Decoding each chunk
 * independently — which is what this service used to do — therefore produced
 * garbage for anything larger than a single chunk, because every chunk after
 * the first was read as though it started on a header. Hence a Transform that
 * carries the leftovers across chunks.
 *
 * Payload bytes are passed through as bytes, never decoded to a string here, so
 * a multi-byte UTF-8 character split across two frames still reassembles
 * correctly downstream.
 */
const HEADER_SIZE = 8;
const PAYLOAD_LENGTH_OFFSET = 4;

export class DockerLogDemuxer extends Transform {
  /** Bytes received but not yet consumed: a partial header or a partial payload. */
  private pending: Buffer = Buffer.alloc(0);

  /** Payload bytes still owed to the frame currently being read. */
  private owed = 0;

  _transform(chunk: Buffer, _encoding: BufferEncoding, done: TransformCallback): void {
    this.pending = this.pending.length === 0 ? chunk : Buffer.concat([this.pending, chunk]);

    for (;;) {
      if (this.owed > 0) {
        if (this.pending.length === 0) {
          break;
        }
        const take = Math.min(this.owed, this.pending.length);
        this.push(this.pending.subarray(0, take));
        this.pending = this.pending.subarray(take);
        this.owed -= take;
        continue;
      }

      if (this.pending.length < HEADER_SIZE) {
        break;
      }
      this.owed = this.pending.readUInt32BE(PAYLOAD_LENGTH_OFFSET);
      this.pending = this.pending.subarray(HEADER_SIZE);
    }

    done();
  }

  _flush(done: TransformCallback): void {
    // A truncated final frame means the daemon or the connection cut out
    // mid-payload. Emit what arrived rather than dropping it; losing the tail of
    // a log is exactly when you most want to see how far it got.
    if (this.owed > 0 && this.pending.length > 0) {
      this.push(this.pending);
    }
    this.pending = Buffer.alloc(0);
    this.owed = 0;
    done();
  }
}
