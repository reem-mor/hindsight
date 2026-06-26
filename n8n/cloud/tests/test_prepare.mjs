/**
 * prepare.js guardrail tests — no upload, zero-byte, allowlist, DOCX reject, zip fan-out.
 */
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const prepareSrc = readFileSync(join(__dirname, '..', 'nodes', 'prepare.js'), 'utf8');

const mkPrepare = () => new Function('$input', '$', 'helpers', `
  return (async () => { ${prepareSrc} }).call({ helpers });
`);

function itemFromBuffer(fileName, ext, buf, mimeType) {
  return {
    json: {},
    binary: {
      data: {
        fileName,
        fileExtension: ext,
        mimeType: mimeType || 'application/octet-stream',
        data: Buffer.from(buf).toString('base64'),
      },
    },
  };
}

async function runPrepare(items) {
  const helpers = {
    getBinaryDataBuffer: async (_idx, key) => {
      const meta = items[0].binary[key];
      return Buffer.from(meta.data || '', 'base64');
    },
  };
  const $input = { all: () => items };
  const $ = () => ({ all: () => [] });
  return mkPrepare()($input, $, helpers);
}

let pass = 0;
const failures = [];
const ok = (name, cond, detail = '') => (cond ? pass++ : failures.push(name + (detail ? ' :: ' + detail : '')));
async function throws(name, fn) {
  try {
    await fn();
    failures.push(name + ' :: expected an error, none thrown');
  } catch (_) {
    pass++;
  }
}

// minimal ZIP_STORED with one hello.md entry
function makeStoredZip(name, text) {
  const content = Buffer.from(text, 'utf8');
  const nameBuf = Buffer.from(name, 'utf8');
  const local = Buffer.alloc(30 + nameBuf.length + content.length);
  local.writeUInt32LE(0x04034b50, 0);
  local.writeUInt16LE(0, 4);
  local.writeUInt16LE(0, 6);
  local.writeUInt16LE(0, 8);
  local.writeUInt16LE(0, 10);
  local.writeUInt32LE(content.length, 14);
  local.writeUInt32LE(content.length, 18);
  local.writeUInt16LE(nameBuf.length, 26);
  local.writeUInt16LE(0, 28);
  nameBuf.copy(local, 30);
  content.copy(local, 30 + nameBuf.length);
  const central = Buffer.alloc(46 + nameBuf.length);
  central.writeUInt32LE(0x02014b50, 0);
  central.writeUInt16LE(0, 4);
  central.writeUInt16LE(0, 6);
  central.writeUInt16LE(0, 8);
  central.writeUInt16LE(0, 10);
  central.writeUInt16LE(0, 12);
  central.writeUInt32LE(content.length, 16);
  central.writeUInt32LE(content.length, 20);
  central.writeUInt16LE(nameBuf.length, 28);
  central.writeUInt16LE(0, 30);
  central.writeUInt16LE(0, 32);
  central.writeUInt16LE(0, 34);
  central.writeUInt32LE(0, 36);
  central.writeUInt32LE(0, 40);
  nameBuf.copy(central, 46);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(1, 8);
  end.writeUInt16LE(1, 10);
  end.writeUInt32LE(central.length, 12);
  end.writeUInt32LE(local.length, 16);
  end.writeUInt16LE(0, 20);
  return Buffer.concat([local, central, end]);
}

await throws('prepare.no_upload', () => runPrepare([{ json: {}, binary: {} }]));

await throws('prepare.zero_byte', () =>
  runPrepare([itemFromBuffer('empty.md', 'md', Buffer.alloc(0), 'text/markdown')]),
);

await throws('prepare.unsupported_exe', () =>
  runPrepare([itemFromBuffer('malware.exe', 'exe', Buffer.from('MZ'), 'application/octet-stream')]),
);

await throws('prepare.docx_rejected', () =>
  runPrepare([itemFromBuffer('report.docx', 'docx', Buffer.from('PK'), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')]),
);

const mdOut = await runPrepare([
  itemFromBuffer('incident.md', 'md', '# SIEM alert\nCredential stuffing detected.', 'application/pdf'),
]);
ok('prepare.md_ok', mdOut.length === 1 && mdOut[0].json.sourceFilename === 'incident.md');
ok('prepare.mime_mismatch_text', !mdOut[0].json.isPdf);

const zipBuf = makeStoredZip('batch/a.md', '# batch item');
const zipOut = await runPrepare([itemFromBuffer('batch.zip', 'zip', zipBuf, 'application/zip')]);
ok('prepare.zip_fanout', zipOut.length === 1 && zipOut[0].json.isBatchItem === true);

// BON-1 Vision: a .pdf is sent to Gemini as inline_data (mime application/pdf), not as text —
// the only data-path without prior unit coverage (flagged by the RC coverage audit).
const pdfOut = await runPrepare([
  itemFromBuffer('vuln_scan.pdf', 'pdf', Buffer.from('%PDF-1.4 minimal'), 'application/pdf'),
]);
let pdfBody = pdfOut[0].json.geminiBody;
if (typeof pdfBody === 'string') pdfBody = JSON.parse(pdfBody);
const pdfParts = (pdfBody && pdfBody.contents && pdfBody.contents[0] && pdfBody.contents[0].parts) || [];
ok('prepare.pdf_isPdf', pdfOut.length === 1 && pdfOut[0].json.isPdf === true);
ok(
  'prepare.pdf_vision_inline_data',
  pdfParts.some((p) => p.inline_data && p.inline_data.mime_type === 'application/pdf' && !!p.inline_data.data),
  'expected an inline_data application/pdf part for the PDF Vision branch',
);

const total = pass + failures.length;
console.log(`\nHINDSIGHT prepare node tests: ${pass}/${total} passed`);
if (failures.length) {
  console.log('FAILURES:');
  failures.forEach((f) => console.log('  ✗ ' + f));
  process.exit(1);
}
console.log('All prepare node tests passed ✔');
