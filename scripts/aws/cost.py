#!/usr/bin/env python3
"""Calculator only. Dated rates and observed public-IP counts must be supplied."""
import argparse
import json
import math


def estimate(g6, m8i, ebs_gb_month, hours, *, ipv4_hour, retained_ipv4_count, active_ipv4_count,
             sessions=25, storage_gb=270):
    values=(g6,m8i,ebs_gb_month,hours,sessions,storage_gb,ipv4_hour,retained_ipv4_count,active_ipv4_count)
    if any(not math.isfinite(x) or x < 0 for x in values) or sessions*hours > 730:
        raise ValueError('Finite nonnegative rates/usage required; monthly active hours cannot exceed 730')
    if retained_ipv4_count > active_ipv4_count or any(int(x)!=x for x in (retained_ipv4_count,active_ipv4_count,sessions)):
        raise ValueError('IP/session counts must be integers and retained IPs cannot exceed active IPs')
    fixed=storage_gb*ebs_gb_month + retained_ipv4_count*730*ipv4_hour
    incremental_ip=(active_ipv4_count-retained_ipv4_count)*ipv4_hour
    return {'currency':'USD','compute_hourly':g6+m8i,
            'active_hourly_including_ipv4':g6+m8i+active_ipv4_count*ipv4_hour,
            'session_compute':hours*(g6+m8i),
            'session_incremental_compute_and_ipv4':hours*(g6+m8i+incremental_ip),
            'monthly_compute':sessions*hours*(g6+m8i),
            'monthly_retained_ebs_and_ipv4':fixed,
            'monthly_subtotal':sessions*hours*(g6+m8i+incremental_ip)+fixed,
            'storage_gb':storage_gb,
            'excluded':'VAT, internet egress, snapshots, provider APIs, excess EBS IOPS/throughput, existing NAT/endpoints or other account resources. Inventory and price evidence required.'}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['g6','m8i','ebs-gb-month','hours','ipv4-hour']:
        p.add_argument('--'+name,type=float,required=True)
    for name in ['retained-ipv4-count','active-ipv4-count']:
        p.add_argument('--'+name,type=int,required=True)
    p.add_argument('--storage-gb',type=int,default=270)
    p.add_argument('--sessions',type=int,default=25)
    a=p.parse_args()
    print(json.dumps(estimate(**vars(a)),indent=2))
