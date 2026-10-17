"""Source-bound local MediaPipe expression support for lower face only."""
import math
VERSION='local-mediapipe-expression-support-v1'
GATE_VERSION='source-bound-lower-face-expression-v3-observed-pose'
REQUIRED=('jawOpen','mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','cheekPuff','mouthPressLeft','mouthPressRight','mouthPucker','mouthFunnel')

def validate(observation,photo_id):
    if observation is None:return None
    if not isinstance(observation,dict) or observation.get('version')!=VERSION or observation.get('photoId')!=photo_id:raise ValueError('EXPRESSION_SOURCE_OR_VERSION_MISMATCH')
    scores=observation.get('scores')
    if not isinstance(scores,dict) or not all(key in scores for key in REQUIRED):raise ValueError('EXPRESSION_FIELDS_MISSING')
    if not all(not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in scores.values()):raise ValueError('EXPRESSION_SCORE_INVALID')
    return scores

def reason(observation,photo_id,opening,smile,lip_width_ratio):
    scores=validate(observation,photo_id)
    if opening>.10 or scores is not None and scores['jawOpen']>.15:return 'EXPRESSION_OPEN_MOUTH'
    if scores is None:
        # Broad lips cannot waive a geometrically observed smile.
        return 'EXPRESSION_SMILE' if smile<-.07 else 'EXPRESSION_SUPPORT_UNAVAILABLE'
    for keys,label in [(('mouthSmileLeft','mouthSmileRight'),'SMILE'),(('mouthFrownLeft','mouthFrownRight'),'FROWN'),(('cheekPuff',),'CHEEK_PUFF'),(('mouthPressLeft','mouthPressRight'),'MOUTH_PRESS')]:
        if max(scores[k] for k in keys)>.5:return 'EXPRESSION_'+label
    if scores['mouthPucker']>.5 and (lip_width_ratio<.35 or scores['mouthFunnel']>.25):return 'EXPRESSION_PUCKER'
    return None


def pose_reason(pose,conditions):
    """Same capture-angle limits as matchesSkinAngle; no new fitted thresholds."""
    values=[conditions.get(k) for k in ('yaw','pitch','roll')]
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):return 'HEAD_ANGLE_UNSUPPORTED'
    yaw,pitch,roll=values
    if abs(pitch)>.22 or abs(roll)>.15:return 'HEAD_ANGLE_UNSUPPORTED'
    valid=abs(yaw)<=.20 if pose=='FRONT' else -.65<=yaw<=-.28 if pose=='RIGHT' else .28<=yaw<=.65 if pose=='LEFT' else False
    return None if valid else 'HEAD_ANGLE_UNSUPPORTED'
