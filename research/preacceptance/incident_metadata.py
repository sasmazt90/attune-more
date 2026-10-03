"""Only existing content-free incident records; no media/transcript/log reads."""
import datetime, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PRODUCT=ROOT.parent/'attune-live-test';OUT=ROOT/'research/preacceptance'
records=['audit-results/live-provider/results.json','audit-results/incident-source-metadata.json','docs/live-provider-incident-review.md','audit-results/uat-closure-20261003/admin-evidence-needed.json']
invalid=json.loads((PRODUCT/records[0]).read_text(encoding='utf-8'))
assert invalid['status']=='INVALID_TEST_SOURCE'
proof={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':{p:hashlib.sha256((PRODUCT/p).read_bytes()).hexdigest() for p in records},
    'incident':{'status':invalid['status'],'retainedConversationCount':invalid['providerRequests'],'providerTypes':invalid['providerTypes'],
        'ttsCount':3,'ttsCountSource':'existing incident-review document; not a complete transport ledger',
        'summaryCount':None,'totalProviderRequests':None,'utcInterval':None,'organizationId':None,'projectId':None,'requestIds':[],
        'timeEvidence':'No preserved event timestamp; artifact filesystem dates are not event timestamps',
        'endpoints':['/v1/chat/completions','/v1/audio/speech'],'absoluteHostAtIncident':None,
        'endpointEvidence':'Existing incident-review document and API implementation; complete event request ledger missing',
        'rawTranscriptRetained':invalid['rawTranscriptRetained']},
    'eventTimeControls':{'dataSharing':None,'zeroDataRetention':None,'modifiedAbuseMonitoring':None,'residency':None},
    'providerDeletionRecord':None,'providerSupportRecord':None,
    'nativeSpeechService':{'providerIdentity':None,'endpoint':None,'retentionOrDeletionEvidence':None,
        'scope':'Browser-native STT audio egress is distinct from OpenAI transcript/TTS requests; no preserved transport ledger identifies its provider'},
    'accountReadOnlyAccess':{'dashboardOpened':True,'browserReadAttempts':2,'browserReadResult':'trusted Node process exited unexpectedly; kernel reset',
        'adminCredentialAvailable':False,'ordinaryModelsGETDoesNotGrantAdministration':True},
    'providerSideStatus':'UNVERIFIED','localDeletionIsProviderDeletion':False,'rawContentRead':False,'rawContentReuploaded':False,'providerMessagesSent':0,'accountSettingsChanged':False,'providerDeletionRequested':False,
    'laterRunEvidenceExcluded':['20261003-approved-02','20261003-approved-03','controlled-text','20261003-uat-01'],
    'laterRunExclusionReason':'These are separate authorized runs; their request IDs/timing do not identify the invalid microphone incident',
    'currentReadonlyRequestExcluded':'c464a52b-f229-4786-84b2-8eb857807a52 identifies current GET /v1/models only',
    'oldKeyRevocation':'USER_REPORTED_NOT_ADMIN_VERIFIED','currentKeyId':None,'oldKeyId':None,'oldVersusCurrentKeyMetadataLink':None}
(OUT/'incident-evidence.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps({'incidentStatus':proof['providerSideStatus'],'requestIdsAvailable':0,'utcIntervalAvailable':False,'organizationProjectKnown':False,'providerContactSent':False,'rawContentReuploaded':False}))
