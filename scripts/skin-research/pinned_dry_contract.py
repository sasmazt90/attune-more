"""Explicit user-pinned delivery identities; old admission remains reproducible."""
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def contract():
    parser=argparse.ArgumentParser();parser.add_argument('--package',choices=['v1','v2'],default='v1');v=parser.parse_args().package
    if v=='v1':
        return dict(version=v,commit='1db3cfdddbdcb0846b9219865d31cc5547413296',base='audit-results/cdc-delivery-20261014',out=ROOT/'audit-results/dryness-integration-20261014',hashes={'dryness/calibrated-source-group-head.json':'a668840c2cd568bf91a03ad274a0def97c1185bb22f7856a9c504eeb01571c72','dryness/dryness-head-comparison.json':'a946e65c2a10d8d5e1d374296cb19239e806029167c440cf0e00ec4a6939b75b','cdc_skin_adapters.py':'711e8e8695cb89a89a2de45cc2d684798599106421e443a31625f0f94e75154a'})
    return dict(version=v,commit='1b2ee037d1d835fcd29a8f5bf78eb99d034632dd',base='audit-results/cdc-delivery-20261014-v2',out=ROOT/'audit-results/dryness-integration-v2-20261014',hashes={'dryness/calibrated-source-group-head.json':'7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1','dryness/dryness-head-comparison.json':'58bf9b425a0cf1c496d845abfa1d4f1916996a61122b135c5142b98c7938a3ea','cdc_skin_adapters.py':'7804e14be721717966a3efa05b90c40d7f7bd7d9cce5a865c10476f812613cf1','sagging/instant_appearance.py':'ff888ce2793df6cb867c314ca3f940c0979219271a9be79acf18bfcaac14cb76'})
