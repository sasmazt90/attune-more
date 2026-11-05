"""Keep a journey's machine exit status consistent with its saved evidence."""


def finalize_report(report):
    checks = report.get('checks', [])
    passed = (report.get('status') == 'PASS' and bool(checks)
              and all(check.get('passed') is True for check in checks)
              and not report.get('errors') and not report.get('failure'))
    if not passed and report.get('status') != 'ERROR':
        report['status'] = 'FAIL'
    return 0 if passed else 1
