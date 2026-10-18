// Numeric-only legacy record tests. Real photo transaction acceptance is covered
// by test_skin_atomic_deletion.py and test_skin_photo_history.py in real Chrome.
const path=require('path');
const file=path.resolve('apps/vehicle-app/src/utils/skinPhotoHistory.ts');
require.cache[file]={id:file,filename:file,loaded:true,exports:{
 SKIN_PHOTO_DELETE_PENDING:'attune_skin_photo_delete_v1',
 recoverSkinPhotoDeletion:async()=>{},
 deleteSkinPhotosWithRecords:async(_id,apply,_rollback,finalize)=>{apply();finalize();}
}};
