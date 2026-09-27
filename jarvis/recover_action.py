"""Operator-only reconciliation CLI. Never exposed as a model tool."""
import argparse
from .agent.effects import EffectLedger
from .config import settings


def main():
    parser = argparse.ArgumentParser(description='Inspect the real action before resolving uncertainty; this does not retry it.')
    parser.add_argument('id', nargs='?')
    parser.add_argument('--observed', choices=['observed_applied', 'observed_not_applied'])
    args = parser.parse_args()
    ledger = EffectLedger(settings.db_path)
    if args.id and args.observed:
        ledger.resolve(args.id, args.observed)
        from .security.audit import AuditStore
        AuditStore(settings.db_path).record(mission_id=None, session_id=None, request_summary='Operator reconciled a prior action', tool_name='operator_effect_reconciliation', risk_level='HIGH',
            capabilities=[], args={'intent_id': args.id, 'observation': args.observed}, approval_status='OPERATOR_CLI', execution_status='SUCCESS')
    else:
        for item in ledger.unresolved():
            print(item['id'], item['tool'], item['state'])


if __name__ == '__main__':
    main()
