from __future__ import annotations

import json
from pathlib import Path

from .mission import VerificationResult


SIDE_EFFECTING_TOOLS = {
    'remember_fact', 'add_note', 'add_todo', 'complete_todo', 'add_reminder',
    'index_local_text_file', 'index_document',
    'open_url', 'open_app', 'open_local_path', 'browser_search',
    'type_text', 'press_key', 'hotkey', 'click_screen',
    'write_local_text_file', 'gmail_send', 'calendar_create',
}

PARTIAL_VERIFICATION_TOOLS = {
    'open_url', 'open_app', 'open_local_path', 'browser_search',
    'type_text', 'press_key', 'hotkey', 'click_screen',
}


def _base(event: dict, name: str, *, side_effecting: bool) -> dict:
    return {
        'name': name,
        'audit_id': event.get('audit_id'),
        'side_effecting': side_effecting,
    }


class VerificationEngine:
    def verify_tool_event(self, event: dict) -> dict:
        name = str(event.get('name', ''))
        args = event.get('args') if isinstance(event.get('args'), dict) else {}
        raw = event.get('output', '')
        side_effecting = name in SIDE_EFFECTING_TOOLS
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            payload = {'ok': False, 'error': 'Tool returned non-JSON output.'}

        if not isinstance(payload, dict) or payload.get('ok') is not True:
            error = payload.get('error', 'Tool did not report success.') if isinstance(payload, dict) else 'Invalid tool output.'
            return _base(event, name, side_effecting=side_effecting) | {
                'verified': False,
                'status': 'FAILED',
                'evidence': str(error)[:1000],
            }

        result = payload.get('result')

        if name == 'write_local_text_file':
            return self._verify_file_write(event, name, args, result)
        if name == 'run_project_tests':
            code = result.get('returncode') if isinstance(result, dict) else None
            return _base(event, name, side_effecting=False) | {
                'verified': code == 0,
                'status': 'VERIFIED' if code == 0 else 'FAILED',
                'evidence': {'returncode': code},
            }
        if name == 'gmail_send':
            message_id = result.get('id') if isinstance(result, dict) else None
            return _base(event, name, side_effecting=True) | {
                'verified': bool(message_id),
                'status': 'VERIFIED' if message_id else 'UNVERIFIED',
                'evidence': {'message_id': message_id, 'provider_acknowledgement': bool(message_id)},
            }
        if name == 'calendar_create':
            event_id = result.get('id') if isinstance(result, dict) else None
            return _base(event, name, side_effecting=True) | {
                'verified': bool(event_id),
                'status': 'VERIFIED' if event_id else 'UNVERIFIED',
                'evidence': {'event_id': event_id, 'provider_acknowledgement': bool(event_id)},
            }
        if name in PARTIAL_VERIFICATION_TOOLS:
            return _base(event, name, side_effecting=True) | {
                'verified': False,
                'status': 'ACKNOWLEDGED_NOT_OBSERVED',
                'evidence': result,
            }

        return _base(event, name, side_effecting=side_effecting) | {
            'verified': True,
            'status': 'VERIFIED',
            'evidence': result,
        }

    @staticmethod
    def _verify_file_write(event: dict, name: str, args: dict, result) -> dict:
        path_value = result.get('path') if isinstance(result, dict) else None
        expected = str(args.get('content', ''))
        if not path_value:
            return _base(event, name, side_effecting=True) | {
                'verified': False,
                'status': 'UNVERIFIED',
                'evidence': 'Write result did not contain a path.',
            }
        path = Path(str(path_value))
        try:
            actual = path.read_text(encoding='utf-8')
            verified = actual == expected
            evidence = {
                'path': str(path),
                'exists': path.exists(),
                'characters': len(actual),
                'content_match': verified,
            }
        except Exception as exc:
            verified = False
            evidence = {'path': str(path), 'verification_error': f'{type(exc).__name__}: {exc}'}
        return _base(event, name, side_effecting=True) | {
            'verified': verified,
            'status': 'VERIFIED' if verified else 'FAILED',
            'evidence': evidence,
        }

    def verify_step(self, result_text: str, tool_events: list[dict]) -> VerificationResult:
        if not tool_events:
            ok = bool(result_text.strip())
            return VerificationResult(
                verified=ok,
                status='VERIFIED_MODEL_OUTPUT' if ok else 'FAILED',
                summary='Model produced a step result with no external tool action.' if ok else 'No step result was produced.',
                evidence=[{'type': 'model_output', 'characters': len(result_text)}] if ok else [],
            )

        checks = [self.verify_tool_event(event) for event in tool_events]
        hard_failures = [item for item in checks if item['status'] == 'FAILED']
        unverified = [item for item in checks if not item['verified'] and item['status'] != 'FAILED']
        verified = not hard_failures and not unverified
        if hard_failures:
            status = 'FAILED'
            summary = f'{len(hard_failures)} tool action(s) failed verification.'
        elif unverified:
            status = 'PARTIAL'
            summary = f'{len(unverified)} action(s) were acknowledged but could not be independently observed.'
        else:
            status = 'VERIFIED'
            summary = f'All {len(checks)} tool action(s) produced verification evidence.'
        return VerificationResult(
            verified=verified,
            status=status,
            summary=summary,
            evidence=checks,
            unverified_actions=[item['name'] for item in unverified],
        )

    @staticmethod
    def has_unsafe_retry_risk(tool_events: list[dict]) -> bool:
        return any(str(event.get('name', '')) in SIDE_EFFECTING_TOOLS for event in tool_events)
