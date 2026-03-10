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

  const { version, toolTemplates, roles, defaults } = parsed;

  if (!version) throw new Error('missing required key: version');
  if (!toolTemplates) throw new Error('missing required key: toolTemplates');
  if (!roles) throw new Error('missing required key: roles');
  if (!defaults) throw new Error('missing required key: defaults');

  assertNonEmptyString(version, 'version');
  assertObject(toolTemplates, 'toolTemplates');
  assertObject(roles, 'roles');
  assertObject(defaults, 'defaults');

  if (!Object.prototype.hasOwnProperty.call(defaults, 'cwd')) {
    throw new Error('missing required key: defaults.cwd');
  }
  if (!Object.prototype.hasOwnProperty.call(defaults, 'model')) {
    throw new Error('missing required key: defaults.model');
  }
  assertNonEmptyString(defaults.cwd, 'defaults.cwd');
  assertNonEmptyString(defaults.model, 'defaults.model');

  // Normalize templates
  const normalizedToolTemplates = {};
  for (const [name, tpl] of Object.entries(toolTemplates)) {
    assertObject(tpl, `toolTemplates.${name}`);

    const normalized = {
      allowedTools: Array.isArray(tpl.allowedTools) ? tpl.allowedTools.slice() : undefined,
      disallowedTools: Array.isArray(tpl.disallowedTools) ? tpl.disallowedTools.slice() : undefined
    };

    normalizedToolTemplates[name] = normalized;
  }

  // Normalize roles
  const normalizedRoles = {};
  for (const [roleName, roleDef] of Object.entries(roles)) {
    assertObject(roleDef, `roles.${roleName}`);

    if (!Object.prototype.hasOwnProperty.call(roleDef, 'description')) {
      throw new Error(`missing required key: roles.${roleName}.description`);
    }
    if (!Object.prototype.hasOwnProperty.call(roleDef, 'model')) {
      throw new Error(`missing required key: roles.${roleName}.model`);
    }
    if (!Object.prototype.hasOwnProperty.call(roleDef, 'toolTemplateRefs')) {
      throw new Error(`missing required key: roles.${roleName}.toolTemplateRefs`);
    }

    assertNonEmptyString(roleDef.description, `roles.${roleName}.description`);
    assertNonEmptyString(roleDef.model, `roles.${roleName}.model`);
    if (!Array.isArray(roleDef.toolTemplateRefs)) {
      throw new Error(`roles.${roleName}.toolTemplateRefs must be a list/array`);
    }

    normalizedRoles[roleName] = {
      description: roleDef.description,
      model: roleDef.model,
      toolTemplateRefs: roleDef.toolTemplateRefs.slice()
    };
  }

  return {
    version,
    toolTemplates: normalizedToolTemplates,
    roles: normalizedRoles,
    defaults: {
      cwd: defaults.cwd,
      model: defaults.model
    },
    meta: {
      path: absolutePath
    }
  };
}
