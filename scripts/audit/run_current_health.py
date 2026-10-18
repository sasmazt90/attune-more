"""Run an existing production check into a fresh evidence directory.
No prior proof copied; only output paths change. Physical/controlled claims stay
with the original check. No mental-provider script is admitted here.
"""
import ast,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ALLOWED={'current_skin_contract','current_skin_photo_history','current_skin_photo_wipe_success','current_dental_capture','current_dental_negative','current_dental_history','current_hearing_positive','current_hearing_tone','current_care_contract','current_guidance','current_audio_focus','current_health_responsive','current_vision_negative','vision_feedback','vision_answer_memory_followup','vision_frame_size_followup','vision_transform_pixels','vision_motion_pixels'}
name=sys.argv[1];assert name in ALLOWED
suffix=sys.argv[2] if len(sys.argv)>2 else name
assert all(c.isalnum() or c in '-_' for c in suffix)
destination=ROOT/'audit-results/all-health-20261010/e2e'
if name!='current_dental_negative':destination=destination/suffix
destination.mkdir(parents=True,exist_ok=True)
source=ROOT/'tests/e2e'/f'{name}.py';tree=ast.parse(source.read_text('utf8'))
class OutputPaths(ast.NodeTransformer):
 def visit_Assign(self,node):
  if any(isinstance(t,ast.Name) and t.id in ('OUT','out') for t in node.targets):
   node.value=ast.Call(func=ast.Name(id='Path',ctx=ast.Load()),args=[ast.Constant(str(destination))],keywords=[])
  return node
# Output variables inside functions must retain their original meaning.
tree.body=[OutputPaths().visit(node) if isinstance(node,ast.Assign) else node for node in tree.body]
tree=ast.fix_missing_locations(tree)
sys.path.insert(0,str(ROOT/'tests/e2e'));sys.argv=[str(source)]
os.environ['SKIN_RESULT_AUDIT_DIR']=str(destination)
exec(compile(tree,str(source),'exec'),{'__name__':'__main__','__file__':str(source)})
