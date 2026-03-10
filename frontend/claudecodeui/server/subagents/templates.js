import fs from 'node:fs/promises';
import YAML from 'yaml';

const DEFAULT_TEMPLATES_PATH =
  '/root/claudeagent/scientific_agent/.claude/teams/role_tool_templates.yaml';

function assertObject(value, label) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} must be a mapping/object`);
  }
}

function assertNonEmptyString(value, label) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`${label} must be a non-empty string`);
  }
}

export async function loadRoleToolTemplates(absolutePath = DEFAULT_TEMPLATES_PATH) {
  if (!absolutePath || typeof absolutePath !== 'string') {
    throw new Error('templates path must be a string');
  }
  if (!absolutePath.startsWith('/')) {
    throw new Error(
      `templates path must be absolute: received "${absolutePath}"`
    );
  }

  let raw;
  try {
    raw = await fs.readFile(absolutePath, 'utf8');
  } catch (err) {
    throw new Error(
      `failed to read role/tool templates file at ${absolutePath}: ${err.message}`
    );
  }

  let parsed;
  try {
    parsed = YAML.parse(raw);
  } catch (err) {
    throw new Error(
      `failed to parse YAML in role/tool templates file at ${absolutePath}: ${err.message}`
    );
  }

  assertObject(parsed, 'root');

  const { toolTemplates, roles, defaults } = parsed;

  if (!toolTemplates) throw new Error('missing required key: toolTemplates');
  if (!roles) throw new Error('missing required key: roles');
  if (!defaults) throw new Error('missing required key: defaults');

  assertObject(toolTemplates, 'toolTemplates');
  assertObject(roles, 'roles');
  assertObject(defaults, 'defaults');

  if (!Object.prototype.hasOwnProperty.call(defaults, 'cwd')) {
    throw new Error('missing required key: defaults.cwd');
  }
  assertNonEmptyString(defaults.cwd, 'defaults.cwd');

  // Normalize templates
  const normalizedToolTemplates = {};
  for (const [name, tpl] of Object.entries(toolTemplates)) {
    assertObject(tpl, `toolTemplates.${name}`);

    const normalized = {
      description:
        typeof tpl.description === 'string' ? tpl.description : undefined,
      tools: Array.isArray(tpl.tools) ? tpl.tools.slice() : undefined
    };

    normalizedToolTemplates[name] = normalized;
  }

  // Normalize roles
  const normalizedRoles = {};
  for (const [roleName, roleDef] of Object.entries(roles)) {
    assertObject(roleDef, `roles.${roleName}`);
    if (!Object.prototype.hasOwnProperty.call(roleDef, 'template')) {
      throw new Error(`missing required key: roles.${roleName}.template`);
    }
    assertNonEmptyString(roleDef.template, `roles.${roleName}.template`);

    normalizedRoles[roleName] = {
      template: roleDef.template,
      ...roleDef
    };
  }

  return {
    toolTemplates: normalizedToolTemplates,
    roles: normalizedRoles,
    defaults: {
      cwd: defaults.cwd
    },
    meta: {
      path: absolutePath
    }
  };
}
