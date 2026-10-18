'use strict';

// Reproducible local-override installation; no package manager fallback.
if (process.version !== 'v22.20.0' || !/^npm\/10\.9\.3(?:\s|$)/.test(process.env.npm_config_user_agent || '')) {
  throw new Error('This lockfile requires Node 22.20.0 and npm 10.9.3');
}
