#!/usr/bin/env python3
"""Calculator only. Rates must come from dated AWS pricing evidence, never defaults."""
import argparse
import json

def estimate(g6, m8i, ebs_gb_month, hours, sessions=25, storage_gb=250, ipv4_hour=.005):
    if any(x < 0 for x in (g6,m8i,ebs_gb_month,hours,sessions,storage_gb,ipv4_hour)):
        raise ValueError('Costs and usage must be nonnegative')
    fixed = storage_gb*ebs_gb_month + 2*730*ipv4_hour
    return {'currency':'USD','compute_hourly':g6+m8i,
            'active_hourly_including_ipv4':g6+m8i+2*ipv4_hour,
            'session_compute':hours*(g6+m8i),
            'monthly_compute':sessions*hours*(g6+m8i),
            'monthly_retained_ebs_and_two_eips':fixed,
            'monthly_subtotal':sessions*hours*(g6+m8i)+fixed,
            'excluded':'VAT, internet egress, snapshots, provider APIs, excess EBS IOPS/throughput; no NAT/ALB planned'}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['g6','m8i','ebs-gb-month','hours']:
        p.add_argument('--'+name,type=float,required=True)
    a=p.parse_args()
    print(json.dumps(estimate(a.g6,a.m8i,a.ebs_gb_month,a.hours),indent=2))
