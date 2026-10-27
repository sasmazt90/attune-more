set -e
S=/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad
python3 $S/cp/scripts/prep.py $S/$CP $S/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task > $S/rf/k5_prep.log 2>&1
cd $S/rf && CP=$CP BASE=$BASE TAG=$TAG python3 k5_items.py 2>&1 | grep -v Warn | tail -3
export TAG=$TAG
python3 run_models.py skinmap,findings,acnes,regional 2>&1 | tail -2
python3 run_masks.py 2>&1 | tail -1
python3 ita.py $TAG 2>&1 | tail -1
python3 inpaint.py 2>&1 | tail -1
python3 features.py --dino 2>&1 | tail -2
python3 features2.py 2>&1 | tail -1
echo DONE
