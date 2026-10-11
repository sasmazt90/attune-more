"""Source-coordinate development metrics; unknown pixels never become negatives.

Selection is a development comparison, not a product acceptance decision.
Thresholds and selection rule must be frozen before evaluating a holdout.
"""
import collections
import cv2
import numpy as np

VERSION = 'source-scope-mask-development-v2'
RULE = dict(version=VERSION, threshold=0.5,
            targetScore='source-macro labelled-positive recall minus source-macro reviewed-negative FPR',
            requiredEvidence=['labelled positive source', 'reviewed negative support source'],
            globalScore='equal target macro score, only when every target has required evidence',
            missingMetrics='null; no ranking without both positive and negative evidence',
            productAcceptance='unchanged separate frozen acceptance; development ranking is not promotion')


def mean(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


class SourceScopes:
    def __init__(self):
        self.sources = {}

    def add(self, row, prediction, truth, support):
        """truth/support belong to this target, unpadded native tile, bool arrays."""
        a, b, c, d = row['rect']; w, h = row['sourceNativeSize']
        key = (row['sha256'], row['target'])
        if key not in self.sources:
            self.sources[key] = dict(group=row['group'], tileIDs=[],
                pred=np.zeros((h, w), bool), positive=np.zeros((h, w), bool),
                partial=np.zeros((h, w), bool), full=np.zeros((h, w), bool),
                negativeReview=np.zeros((h, w), bool))
        s = self.sources[key]
        if s['group'] != row['group'] or s['pred'].shape != (h, w):
            raise ValueError('SOURCE_IDENTITY_OR_SIZE_CONFLICT')
        p, y, k = [np.asarray(v, bool)[:d-b, :c-a] for v in (prediction, truth, support)]
        if any(v.shape != (d-b, c-a) for v in (p, y, k)) or np.any(y & ~k):
            raise ValueError('INVALID_NATIVE_TRUTH_SUPPORT')
        s['tileIDs'].append(row['id'])
        region = np.s_[b:d, a:c]
        s['pred'][region] |= p
        s['positive'][region] |= y
        reviewed = row.get('wholeValidSkinROIEngineeringReviewed') is True or row.get('wholeValidSkinExpertReviewed') is True
        negative_reviewed = row.get('engineeringNegativeROIReviewed') is True and not y.any()
        # completeROI alone is not an assertion that all unlabelled skin was reviewed.
        if row.get('completeROI') and (reviewed or negative_reviewed):
            s['full'][region] |= k
            if negative_reviewed:s['negativeReview'][region] |= k
        else:
            s['partial'][region] |= y

    def finish(self, targets):
        rows = collections.defaultdict(list)
        for (digest, target), s in sorted(self.sources.items()):
            p, y, full = s['pred'], s['positive'], s['full']
            if np.any(y & s['negativeReview']):
                raise ValueError('REVIEWED_NEGATIVE_CONFLICTS_WITH_LABELLED_POSITIVE')
            partial = s['partial'] & ~full
            neg = full & ~y
            pos = full & y
            tp = int((p & pos).sum()); fp = int((p & neg).sum()); fn = int((~p & pos).sum())
            components = cv2.connectedComponents((p & neg).astype(np.uint8), connectivity=8)[0] - 1
            rows[target].append(dict(sha256=digest, group=s['group'], tileCount=len(s['tileIDs']),
                tileIDs=s['tileIDs'], labelledPositivePixels=int(y.sum()),
                positiveRecall=float(p[y].mean()) if y.any() else None,
                missedLabelledPixels=int((y & ~p).sum()),
                partialPositivePixels=int(partial.sum()),
                partialPositiveRecall=float(p[partial].mean()) if partial.any() else None,
                reviewedPositivePixels=int(pos.sum()), reviewedNegativePixels=int(neg.sum()),
                Dice=2*tp/(2*tp+fp+fn) if pos.any() else None,
                IoU=tp/(tp+fp+fn) if pos.any() else None,
                precision=tp/(tp+fp) if pos.any() and tp+fp else None,
                fullROIRecall=tp/(tp+fn) if pos.any() else None,
                negativeFPR=fp/int(neg.sum()) if neg.any() else None,
                falseComponentsOnReviewedNegative=int(components) if neg.any() else None,
                predictedUnknownPixels=int((p & ~(y | full)).sum()),
                wholePhotoHealthy=False, expertLabels=False))
        return self.summarize(rows,targets)

    @staticmethod
    def summarize(rows,targets):
        result = {}
        for t in targets:
            rs = rows[t]
            recall = mean([r['positiveRecall'] for r in rs]); fpr = mean([r['negativeFPR'] for r in rs])
            usable = recall is not None and fpr is not None
            result[t] = dict(positiveRecall=recall, negativeFPR=fpr,
                partialPositiveRecall=mean([r['partialPositiveRecall'] for r in rs]),
                Dice=mean([r['Dice'] for r in rs]), IoU=mean([r['IoU'] for r in rs]),
                precision=mean([r['precision'] for r in rs]), fullROIRecall=mean([r['fullROIRecall'] for r in rs]),
                positiveSources=sum(r['labelledPositivePixels']>0 for r in rs),
                reviewedFullPositiveSources=sum(r['reviewedPositivePixels']>0 for r in rs),
                reviewedNegativeSupportSources=sum(r['reviewedNegativePixels']>0 for r in rs),
                reviewedNegativeOnlySources=sum(r['reviewedNegativePixels']>0 and r['labelledPositivePixels']==0 for r in rs),
                missedLabelledPixels=sum(r['missedLabelledPixels'] for r in rs),
                falseComponentsOnReviewedNegative=sum(r['falseComponentsOnReviewedNegative'] or 0 for r in rs),
                rankingUsable=usable, developmentScore=recall-fpr if usable else None,
                rankingReason='positive capture and reviewed negative suppression both measured' if usable else 'missing positive or reviewed negative evidence; no rank',
                productMaskLocalizationProven=False, scope='source-group development; engineering reviews; unknown outside excluded', rows=rs)
        return result


def global_score(metrics, targets):
    values = [metrics[t]['developmentScore'] for t in targets]
    return mean(values) if all(v is not None for v in values) else None
