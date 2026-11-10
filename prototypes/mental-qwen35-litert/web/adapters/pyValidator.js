// On-device product validator: services/core-api/mental_analysis.py (unchanged copy, generated/product/SOURCES.sha256)
// executed by Pyodide in the page. pydantic is only needed by the module's analysis models, not by
// validate_spoken_summary, so a minimal stand-in module is installed for the import.
const FILES = ['services/core-api/mental_analysis.py', 'services/core-api/mental_themes.py', 'shared/localization/mental-themes.json', 'shared/localization/messages.json'];
const PYDANTIC_STUB = `
class BaseModel: pass
def Field(*a, **k): return None
def field_validator(*a, **k): return lambda f: f
ConfigDict = dict
StrictBool = bool
`;
export async function createPyValidator({base = '/generated/product/', pyodideBase = '/node_modules/pyodide/'} = {}) {
  const t0 = performance.now();
  const {loadPyodide} = await import(pyodideBase + 'pyodide.mjs');
  const py = await loadPyodide({indexURL: pyodideBase});
  py.FS.mkdirTree('/repo/services/core-api'); py.FS.mkdirTree('/repo/shared/localization'); py.FS.mkdirTree('/stub');
  for (const f of FILES) py.FS.writeFile('/repo/' + f, await (await fetch(base + f)).text());
  py.FS.writeFile('/stub/pydantic.py', PYDANTIC_STUB);
  py.runPython(`import sys; sys.path[:0] = ['/stub', '/repo/services/core-api']\nfrom mental_analysis import validate_spoken_summary`);
  const fn = py.globals.get('validate_spoken_summary');
  const loadMs = performance.now() - t0;
  return {
    loadMs,
    async validate(line, language, messages) {
      const r = fn(line, language, py.toPy(messages));
      const [value, status] = r.toJs(); r.destroy();
      return {line: value ?? null, status: status ?? null};
    },
  };
}
