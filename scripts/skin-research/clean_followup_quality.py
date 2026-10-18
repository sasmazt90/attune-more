"""Hash-bound objective development-photo review; no model outcomes used.

All 2169 previously eligible development type images were inspected in full
source contact sheets. Ambiguous retouching/makeup alone is not an exclusion.
This is engineering photo quality review, not clinical/skin-type relabelling.
"""
import collections,json
import cv2,numpy as np
from diagnose_followup import NEW,OLD,write
from prepare_focused_data import sha

# Indices refer ONLY to the pinned quality/index.json, never class/prediction.
DECISIONS={
 'superimposed-text-advertisement-or-diagram': '''18 33 39 48 81 86 90 91 99 116 117 120 135 136 137 161 163 171 177 180 191 196 231 253 254 255 261 262 278 279 280 285 286 287 303 312 313 319 342 343 346 347 348 362 363 364 376 377 395 396 402 417 418 432 433 436 438 439 440 464 472 477 478 479 489 490 500 508 509 556 568 571 595 600 662 691 692 693 713 726 765 786 787 813 849 850 851 861 862 867 871 872 894 895 898 899 911 912 918 919 930 948 949 959 960 961 962 1004 1015 1020 1021 1027 1028 1029 1031 1032 1041 1052 1064 1065 1066 1067 1071 1074 1077 1083 1084 1087 1105 1109 1110 1124 1155 1156 1165 1173 1174 1175 1176 1189 1190 1197 1198 1219 1220 1221 1233 1234 1250 1256 1287 1305 1306 1342 1343 1350 1359 1366 1367 1370 1371 1381 1402 1407 1420 1431 1432 1438 1439 1440 1443 1444 1465 1469 1476 1477 1486 1487 1520 1521 1530 1535 1554 1576 1577 1578 1589 1590 1619 1620 1638 1654 1655 1674 1690 1691 1692 1713 1722 1739 1742 1759 1772 1778 1780 1787 1790 1791 1801 1810 1811 1816 1820 1827 1917 1918 1931 1946 1951 1954 1955 1956 1968 1974 1985 1993 1998 2003 2009 2010 2026 2042 2046 2047 2048 2054 2055 2056 2066 2067 2084 2104 2109 2110 2163''',
 'opaque-occlusion-sunglasses-or-clipped-source': '''30 35 44 56 96 131 133 189 209 249 250 268 270 271 274 325 357 383 405 623 624 637 638 639 641 728 807 835 836 837 865 968 1033 1127 1128 1247 1265 1266 1278 1279 1333 1347 1349 1354 1355 1374 1461 1471 1472 1608 1641 1711 1712 1728 1738 1750 1754 1784 1803 1843 1844 1845 1888 1895 1935 1961 2024 2103 2126 2127 2161''',
 'visible-cosmetic-mask-cream-or-application': '''15 17 41 57 64 67 68 72 127 144 149 184 185 190 192 193 222 223 229 230 233 235 236 257 258 263 281 314 321 322 324 358 372 388 389 390 419 420 421 422 441 445 446 460 461 462 465 466 467 468 469 471 485 486 488 494 495 502 503 523 524 525 526 530 531 532 535 536 548 549 550 551 564 577 578 586 587 591 592 593 597 625 626 636 649 650 656 667 668 669 701 711 740 741 742 763 764 778 779 782 783 808 812 820 833 834 876 877 885 886 908 939 940 941 942 943 944 951 976 980 988 989 990 1024 1025 1050 1051 1082 1108 1112 1116 1117 1141 1142 1143 1144 1145 1169 1177 1185 1248 1251 1252 1258 1259 1285 1296 1297 1301 1302 1307 1308 1314 1320 1339 1340 1341 1351 1368 1369 1385 1387 1388 1389 1399 1400 1401 1403 1404 1408 1412 1413 1414 1415 1416 1417 1418 1421 1422 1433 1434 1436 1437 1454 1463 1485 1488 1489 1490 1491 1494 1499 1500 1510 1520 1536 1537 1546 1550 1553 1556 1568 1569 1570 1574 1575 1579 1580 1581 1591 1607 1610 1611 1612 1639 1640 1651 1652 1653 1675 1681 1682 1696 1697 1698 1716 1717 1719 1721 1729 1746 1748 1762 1763 1764 1773 1774 1775 1779 1785 1788 1789 1792 1793 1794 1797 1808 1809 1813 1835 1856 1859 1867 1868 1872 1877 1887 1896 1898 1901 1902 1919 1923 1932 1937 1941 1949 1970 1980 1981 1986 1994 2001 2033 2051 2061 2064 2068 2074 2081 2086 2090 2091 2096 2098 2107 2114 2116 2121 2125 2152 2160 2167 2168''',
 'monochrome-or-clearly-stylized-heavy-processing': '''12 29 31 37 42 78 95 102 123 124 128 143 148 154 173 226 282 328 329 365 366 381 382 399 400 401 403 406 407 411 473 474 491 534 537 538 574 575 576 608 609 614 615 618 629 631 632 635 678 679 680 750 776 784 785 802 803 843 844 858 875 900 913 915 916 917 929 937 956 973 987 993 994 1002 1003 1011 1012 1013 1022 1026 1076 1078 1079 1080 1081 1085 1086 1100 1101 1118 1136 1137 1157 1166 1167 1181 1183 1196 1223 1224 1225 1280 1281 1294 1295 1377 1378 1406 1427 1445 1446 1460 1506 1507 1511 1512 1525 1526 1527 1528 1531 1532 1560 1563 1564 1571 1572 1593 1594 1595 1615 1616 1617 1622 1623 1624 1627 1628 1658 1659 1664 1665 1666 1685 1686 1687 1705 1718 1727 1732 1733 1758 1768 1769 1782 1798 1832 1837 1838 1884 1890 1899 1900 1909 1922 1929 1930 1942 1943 1948 1967 1973 1976 1983 1995 2007 2029 2044 2050 2058 2059 2078 2079 2115 2135 2136 2141 2142 2147 2151 2166'''
}
def impulse(crop):
    # Unlike v1, colored/non-extreme corruption and full source are inspected.
    med=cv2.medianBlur(crop,3);delta=np.max(np.abs(crop.astype(np.int16)-med.astype(np.int16)),2)
    n,l,st,_=cv2.connectedComponentsWithStats((delta>65).astype(np.uint8));areas=st[:,cv2.CC_STAT_AREA]
    return float(((l>0)&(areas[l]<=3)).mean())

def padding_impulse(source):
    """Sparse bright islands in flat black source padding, outside anatomy.

    Original face-only fraction missed low-density corruption added across a
    rotated/padded source. Require flat outer rows/columns, eroded padding,
    >=12 isolated islands and >=4 spatial cells. Hair/eye texture alone cannot
    satisfy this condition; no photo class or model output is consulted.
    """
    # Actual Roboflow JPEG padding is RGB 10..12, not mathematical zero.
    median=cv2.medianBlur(source,3);dark=np.max(median,2)<24
    padding=np.zeros(dark.shape,bool)
    padding[dark.mean(1)>.98,:]=True;padding[:,dark.mean(0)>.98]=True
    padding=cv2.erode((padding&dark).astype(np.uint8),np.ones((5,5),np.uint8))>0
    if not padding.any():return dict(pixels=0,paddingPixels=0,fraction=0.,occupiedCells=0,confirmedNumericPattern=False)
    delta=np.max(source.astype(np.int16)-median.astype(np.int16),2)
    count,labels,stats,_=cv2.connectedComponentsWithStats(((delta>40)&padding).astype(np.uint8))
    points=(labels>0)&(stats[:,cv2.CC_STAT_AREA][labels]<=3);pixels=int(points.sum());area=int(padding.sum())
    cells=set((int(y*4/source.shape[0]),int(x*4/source.shape[1])) for y,x in np.argwhere(points))
    fraction=pixels/max(1,area)
    return dict(pixels=pixels,paddingPixels=area,fraction=fraction,occupiedCells=len(cells),confirmedNumericPattern=pixels>=12 and fraction>=.0003 and len(cells)>=4)
def main():
    cv2.setNumThreads(1)
    assert sha(NEW/'quality/index.json')=='3aea955591fe099f45c816022384dd39a7224ef40ffb183013ad5fa3059536ce','REVIEW_INDEX_CHANGED'
    m=json.loads((OLD/'learning-manifest.json').read_text());index=json.loads((NEW/'quality/index.json').read_text());decisions={}
    for reason,ids in DECISIONS.items():
        for i in map(int,ids.split()):decisions.setdefault(index[i]['group'],set()).add(reason)
    evidence=[];dev=[];cache_path=NEW/'quality/source-metrics-cache-v2.json'
    cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
    previous={r['sha256']:r for r in json.loads((NEW/'development-manifest.json').read_text())['rows']} if (NEW/'development-manifest.json').exists() else {}
    for index_row,r in enumerate(m['rows']):
        if r['split']=='test':continue # old final cannot participate in new selection
        reasons=sorted(decisions.get(r['group'],[]))
        if r.get('typeEligible') or r.get('degreeEligible'):
            key=r['sha256']+json.dumps(r['crop']);saved=cache.get(key)
            if saved is None:
                bgr=cv2.imread(r['absolutePath']);a,b,c,d=r['crop'];prior=previous.get(r['sha256'],{})
                if prior.get('crop')==r['crop'] and 'followupImpulseFraction' in prior:
                    face=prior['followupImpulseFraction'];whole=prior['followupFullSourceImpulseFraction']
                else:face=impulse(bgr[b:d,a:c]);whole=impulse(bgr)
                saved=dict(face=face,whole=whole,padding=padding_impulse(bgr));cache[key]=saved
            face=saved['face'];whole=saved['whole']
            # Conservative flag, visibly checked below; not a prediction gate.
            r['followupImpulseFraction']=face;r['followupFullSourceImpulseFraction']=whole
            # High-frequency hair, beard, iris and patterned backgrounds also
            # exceed this flag. It cannot independently exclude a source.
            # Native-scale review of five extra flags found natural edges.
            r['followupImpulseReviewRequired']=face>.004
            padding=saved['padding'];r['followupPaddingImpulse']=padding
            if padding['confirmedNumericPattern']:reasons.append('isolated-bright-impulses-in-flat-source-padding')
        if reasons:
            r['typeEligible']=False;r['degreeEligible']=False
            evidence.append(dict(sha256=r['sha256'],group=r['group'],path=r['path'],reasons=reasons,sourceReviewOnly=True,labelChanged=False))
        dev.append(r)
        if index_row%100==0:write('quality/source-metrics-cache-v2.json',cache)
    write('quality/source-metrics-cache-v2.json',cache)
    write('quality/decisions.json',dict(indexSHA256=sha(NEW/'quality/index.json'),reviewedDevelopmentTypePhotos=len(index),allContactSheetsReviewed=True,clinicalAnnotation=False,modelPredictionNotUsed=True,oldFinalImagesNotInspected=True,scope='existing development source families only',reasons=dict(collections.Counter(reason for e in evidence for reason in e['reasons'])),excluded=evidence))
    write('development-manifest.json',{**{k:v for k,v in m.items() if k!='rows'},'rows':dev,'parentManifestSHA256':sha(OLD/'learning-manifest.json'),'finalAvailable':False,'oldFinalRowsExcluded':True,'qualityReviewSHA256':sha(NEW/'quality/decisions.json')})
    print(json.dumps(dict(type=collections.Counter(r['split'] for r in dev if r.get('typeEligible')),degrees=collections.Counter(r['split'] for r in dev if r.get('degreeEligible')),excluded=len(evidence)),indent=2),flush=True)
if __name__=='__main__':main()
