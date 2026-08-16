import tempfile
import unittest
from pathlib import Path

from jarvis.security.audit import AuditStore
from jarvis.skills import SkillProposalStatus, SkillRegistry, WorkflowLearningEngine


class V75SkillSystemTests(unittest.TestCase):
    def test_gap_creates_complete_but_inactive_skill_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = SkillRegistry(Path(tmp) / 'jarvis.db')
            proposal = registry.propose_from_gap({
                'id': 'GAP-1',
                'capability': 'Excel Automation',
                'title': 'Excel Analysis Automation',
                'description': 'Repeated spreadsheet analysis needs a reusable skill.',
                'recommended_action': 'Build and verify an Excel analysis skill.',
                'evidence': ['workflow repeated 4 times'],
                'severity': 'MEDIUM',
                'permissions': ['FILE_READ', 'FILE_WRITE'],
            })
            valid, reasons = proposal.manifest.validate()
            self.assertTrue(valid, reasons)
            self.assertEqual(proposal.status, SkillProposalStatus.PROPOSED)
            self.assertEqual(proposal.manifest.slug, 'excel_automation')
            self.assertTrue(proposal.manifest.implementation.startswith('skills/excel_automation/'))
            self.assertTrue(proposal.manifest.tests)
            self.assertTrue(proposal.manifest.documentation)
            self.assertTrue(proposal.manifest.evaluation)
            self.assertEqual(registry.get(proposal.id).status, SkillProposalStatus.PROPOSED)

    def test_repeated_safe_tool_sequence_creates_proposal_not_automation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'jarvis.db'
            audit = AuditStore(path)
            for session in ('S1', 'S2', 'S3'):
                for tool in ('search_local_files', 'read_document', 'search_knowledge'):
                    audit.record(
                        mission_id=None, session_id=session, request_summary='repeat analysis',
                        tool_name=tool, risk_level='MEDIUM', capabilities=['FILE_READ'],
                        args={'safe': True}, approval_status='AUTO_ALLOWED',
                        execution_status='SUCCESS', latency_ms=10,
                    )
            engine = WorkflowLearningEngine(path, audit_store=audit)
            workflows = engine.detect(min_occurrences=3, persist=True)
            exact = [item for item in workflows if item.tools == ('search_local_files', 'read_document', 'search_knowledge')]
            self.assertEqual(len(exact), 1)
            self.assertIn('Create reusable workflow skill', exact[0].proposal_text)
            history = engine.recent(10)
            self.assertTrue(history)
            self.assertTrue(all(item['status'] == 'PROPOSED' for item in history))

    def test_sensitive_side_effect_sequence_is_not_auto_learned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'jarvis.db'
            audit = AuditStore(path)
            for index in range(3):
                audit.record(
                    mission_id=None, session_id=f'S{index}', request_summary='send email',
                    tool_name='gmail_send', risk_level='HIGH', capabilities=['EMAIL_SEND'],
                    args={'to': 'redacted@example.com'}, approval_status='ALLOW_ONCE',
                    execution_status='SUCCESS', latency_ms=10,
                )
                audit.record(
                    mission_id=None, session_id=f'S{index}', request_summary='followup',
                    tool_name='search_web', risk_level='LOW', capabilities=['WEB_READ'],
                    args={'q': 'x'}, approval_status='AUTO_ALLOWED',
                    execution_status='SUCCESS', latency_ms=10,
                )
            workflows = WorkflowLearningEngine(path, audit_store=audit).detect(persist=False)
            self.assertFalse(any('gmail_send' in item.tools for item in workflows))


if __name__ == '__main__':
    unittest.main()
