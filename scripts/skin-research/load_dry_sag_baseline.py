"""Load immutable initial methods in this audit process, never the live backend."""
import importlib.util,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASELINE='420d0e3814106a2ec77744a17e000ea1e8669cec'
def load_baseline():
 folder=ROOT/'.runtime/dry-sag-baseline-20261013';folder.mkdir(parents=True,exist_ok=True)
 saved={name:sys.modules.get(name) for name in ('instant_appearance','skin_general')};loaded={}
 for name in ('instant_appearance','skin_general','appearance_analysis'):
  file=folder/(name+'.py');content=subprocess.check_output(['git','show',BASELINE+':services/core-api/'+name+'.py'],cwd=ROOT)
  if file.exists():assert file.read_bytes()==content,'Immutable baseline drift'
  else:file.write_bytes(content)
  alias=name if name!='appearance_analysis' else 'dry_sag_frozen_appearance'
  spec=importlib.util.spec_from_file_location(alias,file);module=importlib.util.module_from_spec(spec);sys.modules[alias]=module;spec.loader.exec_module(module);loaded[name]=module
 for name,old in saved.items():
  if old is None:sys.modules.pop(name,None)
  else:sys.modules[name]=old
 return loaded['appearance_analysis'],loaded['instant_appearance'],loaded['skin_general']
