/**
 * Self-hosted workflow guard (n8n/hindsight_workflow.json).
 * Validates that every Code-node body parses (would have caught the broken
 * email-HTML concatenation) and that the spec-required outputs are wired:
 * §8.2 email subject, and §3.1/§4-Step-6 JSON + Markdown writes to output_docs/.
 */
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const wfPath = join(__dirname, '..', '..', 'hindsight_workflow.json');
const wf = JSON.parse(readFileSync(wfPath, 'utf8'));

let pass = 0;
const failures = [];
const ok = (name, cond, detail = '') => (cond ? pass++ : failures.push(name + (detail ? ' :: ' + detail : '')));

const codeNodes = wf.nodes.filter((n) => n.type === 'n8n-nodes-base.code');
ok('selfhosted.has_code_nodes', codeNodes.length >= 6, 'count=' + codeNodes.length);

// Every Code-node body must parse (n8n globals injected so refs don't trip parsing).
for (const n of codeNodes) {
  try {
    new Function('$input', '$', '$json', 'Buffer', 'require', n.parameters.jsCode);
    pass++;
  } catch (e) {
    failures.push('syntax:' + n.name + ' :: ' + e.message);
  }
}

const compose = codeNodes.find((n) => n.name === 'Compose record + outputs');
ok('selfhosted.compose_present', !!compose);
if (compose) {
  const src = compose.parameters.jsCode;
  // §8.2 exact subject pattern.
  ok('selfhosted.subject_8_2', src.includes("] New document processed: ") && src.includes("'['+classification+'"));
  // §3.1 / §4 Step 6: both JSON and Markdown written to output_docs/.
  ok('selfhosted.md_output_path', src.includes('/data/output_docs/${e.document_id}.md'));
  ok('selfhosted.json_output_path', src.includes('/data/output_docs/${e.document_id}.json'));
  // §8.2 body fields present.
  for (const field of ['Classification', 'Sentiment', 'Department', 'Sensitivity', 'Routing tag']) {
    ok('selfhosted.email_field_' + field.replace(/\s/g, '_'), src.includes(field));
  }
}

// Two file writers (markdown + json) must exist.
const writers = wf.nodes.filter((n) => n.type === 'n8n-nodes-base.readWriteFile');
ok('selfhosted.two_writers', writers.length >= 2, 'count=' + writers.length);

// Gemini retry (BON-4) on the self-hosted HTTP node.
const gemini = wf.nodes.find((n) => n.name === '🧠 Gemini — extract incident');
ok('selfhosted.gemini_retry', !!gemini && gemini.retryOnFail === true && gemini.maxTries === 5);

const total = pass + failures.length;
console.log(`\nHINDSIGHT self-hosted workflow tests: ${pass}/${total} passed`);
if (failures.length) {
  console.log('FAILURES:');
  failures.forEach((f) => console.log('  ✗ ' + f));
  process.exit(1);
}
console.log('All self-hosted workflow tests passed ✔');
