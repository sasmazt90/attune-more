# ACNE-DET permission request — prepared, not sent

Recipient: maintainers of INno-Vation/Decoupled-Sequential-Detection-Head.
Use the repository's published contact channel; no address is inferred.

Subject: ACNE-DET image/annotation access and commercial research permission

Hello,

We are developing TOGG Attune, a local health appearance assessment application.
We would like to evaluate and fine-tune a lesion detector on ACNE-DET. The output
would be visible lesion candidates in source image coordinates, rather than a
diagnosis or a disease severity score derived from model confidence.

We checked your Apache-2.0 repository and the linked Baidu share
https://pan.baidu.com/s/19fv9itHcpjAQCbBxIzvb2Q (published access code: foa7).
The share is visible, but opening/downloading the archive did not expose its
contents in our browser. Could you provide an authorized direct archive or an
alternative public mirror, including the archive's license and permission files?

Please confirm separately whether the images and annotations may be used for:

- commercial model development, training, validation and evaluation;
- cropping, tiling and annotation corrections, with modification notices;
- distribution and commercial use of derived model weights;
- distribution of example images or annotations, if any, with the required
  attribution and license terms (we will otherwise keep them private).

Please identify attribution, notice, share-alike, redistribution or other
restrictions, and whether the permission covers the original photographs and
annotations rather than only the repository's code. If different files have
different rights, please identify their scope. We do not intend to identify or
re-identify depicted people or link them to personal metadata.

We would also appreciate the official split information, annotation schema,
source resolution and any known derivative-image grouping needed to prevent
train/validation/test leakage. We will not infer unknown subject relationships.

Thank you.

## Current evidence and next step

Repository revision: `8f189bba3e72594bed724669af3fea556faeda78`.
The public share displayed 393.3 MB, permanent validity and upload date
2024-01-31. Archive/download clicks did not surface contents or a download in
the recorded browser session. This proves neither a login requirement nor
commercial data permission. The Apache code license is not extended to data.
Local evidence: `audit-results/all-health-20261010/sources/acne-det-*.json/png`.

No message has been sent. Sending requires the user's explicit authorization.
Once an authorized archive and its rights are available, inspect its internal
licenses, prepare derivative-disjoint annotated splits, repeat the bounded
learning-chain and validation procedure, then use a fresh protected test only
if validation clears the declared acceptance criteria.
