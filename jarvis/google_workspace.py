from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from .config import ROOT


SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.events',
]


class GoogleWorkspaceUnavailable(RuntimeError):
    pass


class GoogleWorkspace:
    """Optional user-authorized Gmail + Google Calendar integration.

    No Google credentials are bundled in the public project. The operator must create a
    Google OAuth Desktop client, provide its JSON file locally, and consent in a browser.
    """

    def __init__(self, credentials_file: str | Path | None = None, token_file: str | Path | None = None):
        self.credentials_file = Path(credentials_file or (ROOT / 'google_credentials.json')).expanduser().resolve()
        self.token_file = Path(token_file or (ROOT / 'data' / 'google_token.json')).expanduser().resolve()
        self._creds = None
        self._gmail = None
        self._calendar = None

    @staticmethod
    def _imports():
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except Exception as exc:
            raise GoogleWorkspaceUnavailable(
                'Google Workspace packages are not installed. Run setup_google.ps1 first.'
            ) from exc
        return Request, Credentials, InstalledAppFlow, build

    def configured(self) -> dict:
        return {
            'credentials_file': str(self.credentials_file),
            'credentials_exists': self.credentials_file.is_file(),
            'token_file': str(self.token_file),
            'token_exists': self.token_file.is_file(),
            'scopes': list(SCOPES),
        }

    def authorize(self):
        Request, Credentials, InstalledAppFlow, _build = self._imports()
        creds = None
        if self.token_file.is_file():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_file.is_file():
                    raise FileNotFoundError(
                        f'Google OAuth Desktop credentials not found: {self.credentials_file}. '
                        'Download the OAuth client JSON from Google Cloud and save it with this filename.'
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), SCOPES)
                creds = flow.run_local_server(port=0)
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(creds.to_json(), encoding='utf-8')
        self._creds = creds
        return creds

    def _service(self, api: str):
        _Request, _Credentials, _Flow, build = self._imports()
        creds = self._creds or self.authorize()
        if api == 'gmail':
            if self._gmail is None:
                self._gmail = build('gmail', 'v1', credentials=creds, cache_discovery=False)
            return self._gmail
        if api == 'calendar':
            if self._calendar is None:
                self._calendar = build('calendar', 'v3', credentials=creds, cache_discovery=False)
            return self._calendar
        raise ValueError(api)

    @staticmethod
    def _headers(message: dict) -> dict[str, str]:
        headers = message.get('payload', {}).get('headers', [])
        return {str(item.get('name', '')).lower(): str(item.get('value', '')) for item in headers}

    def gmail_search(self, query: str, max_results: int = 10) -> list[dict]:
        service = self._service('gmail')
        result = service.users().messages().list(
            userId='me', q=query.strip(), maxResults=max(1, min(int(max_results), 25))
        ).execute()
        rows: list[dict] = []
        for item in result.get('messages', []):
            msg = service.users().messages().get(
                userId='me', id=item['id'], format='metadata',
                metadataHeaders=['From', 'To', 'Subject', 'Date'],
            ).execute()
            headers = self._headers(msg)
            rows.append({
                'id': msg.get('id'),
                'thread_id': msg.get('threadId'),
                'from': headers.get('from', ''),
                'to': headers.get('to', ''),
                'subject': headers.get('subject', ''),
                'date': headers.get('date', ''),
                'snippet': msg.get('snippet', ''),
            })
        return rows

    def gmail_send(self, to: str, subject: str, body: str) -> dict:
        if not to.strip() or '@' not in to:
            raise ValueError('A valid recipient email is required.')
        service = self._service('gmail')
        message = EmailMessage()
        message.set_content(body)
        message['To'] = to.strip()
        message['Subject'] = subject.strip()[:998]
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = service.users().messages().send(userId='me', body={'raw': encoded}).execute()
        return {'id': result.get('id'), 'thread_id': result.get('threadId'), 'to': to, 'subject': subject}

    def calendar_upcoming(self, max_results: int = 10) -> list[dict]:
        service = self._service('calendar')
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=max(1, min(int(max_results), 50)),
            singleEvents=True,
            orderBy='startTime',
        ).execute()
        rows = []
        for event in result.get('items', []):
            start = event.get('start', {})
            end = event.get('end', {})
            rows.append({
                'id': event.get('id'),
                'summary': event.get('summary', '(No title)'),
                'start': start.get('dateTime', start.get('date', '')),
                'end': end.get('dateTime', end.get('date', '')),
                'location': event.get('location', ''),
                'html_link': event.get('htmlLink', ''),
            })
        return rows

    def calendar_create(
        self,
        summary: str,
        start: str,
        end: str,
        timezone_name: str = 'Asia/Kolkata',
        description: str = '',
    ) -> dict:
        # Validate date-time strings early; Google still remains the final validator.
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        if end_dt <= start_dt:
            raise ValueError('Calendar event end must be after start.')
        service = self._service('calendar')
        event = {
            'summary': summary.strip()[:1024] or 'JARVIS event',
            'description': description.strip()[:8000],
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': timezone_name},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': timezone_name},
        }
        created = service.events().insert(calendarId='primary', body=event).execute()
        return {
            'id': created.get('id'),
            'summary': created.get('summary'),
            'start': created.get('start', {}),
            'end': created.get('end', {}),
            'html_link': created.get('htmlLink', ''),
        }
