// Unzip a batch of .md/.txt incident logs (BON-7). Pure JS — no external deps.
const CRC32_TABLE = (function () {
  const t = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let j = 0; j < 8; j++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    t[i] = c >>> 0;
  }
  return t;
})();

function crc32(buf, init) {
  let c = init >>> 0;
  for (let i = 0; i < buf.length; i++) {
    c = CRC32_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  }
  return c >>> 0;
}

function inflateRaw(deflated) {
  try {
    const zlib = require("zlib");
    return zlib.inflateRawSync(deflated);
  } catch (e) {
    throw new Error("DEFLATE zip requires zlib (self-hosted only). Use ZIP_STORED on n8n Cloud.");
  }
}

function readU16(buf, off) { return buf[off] | (buf[off + 1] << 8); }
function readU32(buf, off) {
  return (buf[off] | (buf[off + 1] << 8) | (buf[off + 2] << 16) | (buf[off + 3] << 24)) >>> 0;
}

function unzipEntries(buf) {
  const entries = [];
  let eocd = buf.length;
  for (let i = buf.length - 22; i >= 0; i--) {
    if (readU32(buf, i) === 0x06054b50) { eocd = i; break; }
  }

  let offset = 0;
  while (offset + 30 < eocd) {
    if (readU32(buf, offset) !== 0x04034b50) break;
    const comp = readU16(buf, offset + 8);
    const compSize = readU32(buf, offset + 18);
    const nameLen = readU16(buf, offset + 26);
    const extraLen = readU16(buf, offset + 28);
    const name = buf.slice(offset + 30, offset + 30 + nameLen).toString("utf8");
    const dataStart = offset + 30 + nameLen + extraLen;
    const data = buf.slice(dataStart, dataStart + compSize);
    offset = dataStart + compSize;

    if (name.endsWith("/")) continue;
    const ext = name.indexOf(".") >= 0 ? name.split(".").pop().toLowerCase() : "";
    if (ext !== "md" && ext !== "txt" && ext !== "markdown") continue;

    let raw;
    if (comp === 0) raw = data;
    else if (comp === 8) raw = inflateRaw(data);
    else continue;

    entries.push({
      filename: name.split("/").pop(),
      file_type: ext,
      extracted_text: raw.toString("utf8"),
      char_count: raw.length,
      ok: true,
    });
    if (entries.length >= 25) break;
  }
  return entries;
}

const items = $input.all();
const out = [];
for (let idx = 0; idx < items.length; idx++) {
  const item = items[idx];
  const bin = item.binary || {};
  const keys = Object.keys(bin);
  if (!keys.length) continue;
  const key = keys[0];
  let buf;
  try {
    buf = await this.helpers.getBinaryDataBuffer(idx, key);
  } catch (e) {
    buf = Buffer.from((bin[key].data || ""), "base64");
  }
  const entries = unzipEntries(buf);
  if (!entries.length) throw new Error("ZIP contained no supported .md/.txt files");
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    out.push({
      json: {
        sourceFilename: e.filename,
        batchIndex: i,
        batchTotal: entries.length,
        documentText: e.extracted_text,
        mimeType: "text/plain",
        isPdf: false,
        isBatchItem: true,
      },
    });
  }
}
return out;
