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
    toolTemplates:
      standard:
        description: Standard access
        tools: [Read, Write]
    roles:
      principal:
        template: standard
    defaults:
      cwd: /tmp
  `;

  const result = await withTempFile(yaml, (p) => loadRoleToolTemplates(p));

  assert.equal(result.defaults.cwd, '/tmp');
  assert.equal(result.roles.principal.template, 'standard');
  assert.deepEqual(result.toolTemplates.standard.tools, ['Read', 'Write']);
  assert.equal(result.meta.path.startsWith('/'), true);
});

test('loadRoleToolTemplates: requires absolute path', async () => {
  await assert.rejects(() => loadRoleToolTemplates('relative.yaml'), {
    message: /must be absolute/
  });
});

test('loadRoleToolTemplates: validates required keys', async () => {
  const yamlMissing = `defaults: { cwd: /tmp }`;
  await withTempFile(yamlMissing, async (p) => {
    await assert.rejects(() => loadRoleToolTemplates(p), {
      message: /missing required key: toolTemplates/
    });
  });
});

test('loadRoleToolTemplates: validates defaults.cwd', async () => {
  const yamlBad = `
    toolTemplates: {}
    roles: {}
    defaults: { cwd: "" }
  `;

  await withTempFile(yamlBad, async (p) => {
    await assert.rejects(() => loadRoleToolTemplates(p), {
      message: /defaults\.cwd must be a non-empty string/
    });
  });
});
