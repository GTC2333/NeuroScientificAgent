import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import { loadRoleToolTemplates } from '../templates.js';

async function withTempFile(contents, fn) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'role-tool-templates-'));
  const filePath = path.join(dir, 'templates.yaml');
  await fs.writeFile(filePath, contents, 'utf8');
  try {
    return await fn(filePath);
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
}

test('loadRoleToolTemplates: loads and normalizes YAML', async () => {
  const yaml = `
    version: "1"
    defaults:
      cwd: /tmp
      model: claude-sonnet-4-20250514
    toolTemplates:
      standard:
        allowedTools: [Read, Write]
    roles:
      principal:
        description: Team lead
        model: claude-sonnet-4-20250514
        toolTemplateRefs: [standard]
  `;

  const result = await withTempFile(yaml, (p) => loadRoleToolTemplates(p));

  assert.equal(result.version, '1');
  assert.equal(result.defaults.cwd, '/tmp');
  assert.equal(result.defaults.model, 'claude-sonnet-4-20250514');
  assert.deepEqual(result.roles.principal.toolTemplateRefs, ['standard']);
  assert.deepEqual(result.toolTemplates.standard.allowedTools, ['Read', 'Write']);
  assert.equal(result.meta.path.startsWith('/'), true);
});

test('loadRoleToolTemplates: requires absolute path', async () => {
  await assert.rejects(() => loadRoleToolTemplates('relative.yaml'), {
    message: /must be absolute/
  });
});

test('loadRoleToolTemplates: validates required keys', async () => {
  const yamlMissing = `defaults: { cwd: /tmp, model: x }`;
  await withTempFile(yamlMissing, async (p) => {
    await assert.rejects(() => loadRoleToolTemplates(p), {
      message: /missing required key: version/
    });
  });
});

test('loadRoleToolTemplates: validates defaults.cwd', async () => {
  const yamlBad = `
    version: "1"
    toolTemplates: {}
    roles: {}
    defaults: { cwd: "", model: x }
  `;

  await withTempFile(yamlBad, async (p) => {
    await assert.rejects(() => loadRoleToolTemplates(p), {
      message: /defaults\.cwd must be a non-empty string/
    });
  });
});
