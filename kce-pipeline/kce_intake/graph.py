"""Microsoft Graph, delegated, read-only: list messages, list attachments,
download one attachment. Sign-in is MSAL device code; the token cache lives in
the per-user state folder (DPAPI-protected on Windows), never under OneDrive.

Only `Mail.Read` is requested. Files are written to the OneDrive-synced folder
on disk, so no Files/Sites write permission is needed."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Iterator

from .config import Config
from .state import iso

log = logging.getLogger("kce_intake.graph")

GRAPH = "https://graph.microsoft.com/v1.0"
AUTHORITY = "https://login.microsoftonline.com/{tenant}"
MESSAGE_SELECT = "id,subject,receivedDateTime,sender,from,hasAttachments,internetMessageId,body"


class NotLoggedIn(RuntimeError):
    pass


class GraphClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client_id = cfg.graph.get("clientId") or ""
        self.tenant = cfg.graph.get("tenantId") or "common"
        self.scopes = list(cfg.graph.get("scopes") or ["Mail.Read"])
        self._app = None
        self._session = None

    # ---- auth ------------------------------------------------------------
    def _cache(self):
        import msal  # lazy: the rest of the package works without it

        cache = msal.SerializableTokenCache()
        try:
            from msal_extensions import FilePersistence, PersistedTokenCache, build_encrypted_persistence

            path = str(self.cfg.token_cache_path)
            try:
                persistence = build_encrypted_persistence(path)
            except Exception:  # noqa: BLE001 - no DPAPI/keyring on this box
                persistence = FilePersistence(path)
            return PersistedTokenCache(persistence)
        except ImportError:
            return cache

    def app(self):
        if self._app is None:
            import msal

            if not self.client_id or self.client_id.startswith("<"):
                raise NotLoggedIn("config/intake.json → graph.clientId is not set (see README: app registration)")
            self._app = msal.PublicClientApplication(
                self.client_id,
                authority=AUTHORITY.format(tenant=self.tenant),
                token_cache=self._cache(),
            )
        return self._app

    def login(self) -> str:
        """Interactive device-code sign-in. Returns the signed-in account name."""
        app = self.app()
        flow = app.initiate_device_flow(scopes=self.scopes)
        if "user_code" not in flow:
            raise RuntimeError(f"device flow failed: {flow.get('error_description', flow)}")
        print(flow["message"], flush=True)
        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"sign-in failed: {result.get('error_description', result)}")
        account = (result.get("id_token_claims") or {}).get("preferred_username", "?")
        log.info("signed in as %s", account)
        return account

    def token(self) -> str:
        app = self.app()
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(self.scopes, account=accounts[0])
            if result and "access_token" in result:
                return result["access_token"]
        raise NotLoggedIn("no cached sign-in; run:  py -m kce_intake login")

    def whoami(self) -> str:
        accounts = self.app().get_accounts()
        return accounts[0].get("username", "?") if accounts else "(not signed in)"

    # ---- http ------------------------------------------------------------
    def _get(self, url: str, *, params: dict | None = None, headers: dict | None = None, raw: bool = False):
        import requests

        if self._session is None:
            self._session = requests.Session()
        hdrs = {"Authorization": f"Bearer {self.token()}"}
        if headers:
            hdrs.update(headers)
        for attempt in range(5):
            resp = self._session.get(url, params=params, headers=hdrs, timeout=120)
            if resp.status_code in (429, 503, 504) and attempt < 4:
                wait = float(resp.headers.get("Retry-After", 2 ** attempt))
                log.warning("graph %s → %s, retrying in %.0fs", url.split("?")[0], resp.status_code, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.content if raw else resp.json()
        raise RuntimeError("graph: gave up after retries")

    def _paged(self, url: str, params: dict | None, headers: dict | None = None) -> Iterator[dict]:
        page = self._get(url, params=params, headers=headers)
        while True:
            for item in page.get("value", []):
                yield item
            nxt = page.get("@odata.nextLink")
            if not nxt:
                return
            page = self._get(nxt, headers=headers)

    # ---- MailClient protocol -------------------------------------------
    def list_messages_since(self, since: datetime) -> Iterator[dict]:
        params = {
            "$filter": f"receivedDateTime ge {iso(since)} and hasAttachments eq true",  # orderby property must lead the filter or Graph returns InefficientFilter
            "$select": MESSAGE_SELECT,
            "$orderby": "receivedDateTime asc",
            "$top": "50",
        }
        headers = {"Prefer": 'outlook.body-content-type="text"'}
        for msg in self._paged(f"{GRAPH}/me/messages", params, headers):
            sender = ((msg.get("sender") or msg.get("from") or {}).get("emailAddress") or {})
            yield {
                "id": msg["id"],
                "subject": msg.get("subject") or "",
                "receivedDateTime": msg.get("receivedDateTime"),
                "sender": sender.get("address") or "",
                "senderName": sender.get("name") or "",
                "internetMessageId": msg.get("internetMessageId"),
                "bodyText": (msg.get("body") or {}).get("content") or "",
            }

    def list_attachments(self, message_id: str) -> list[dict]:
        params = {"$select": "id,name,contentType,size,isInline"}
        out = []
        for att in self._paged(f"{GRAPH}/me/messages/{message_id}/attachments", params):
            out.append({
                "id": att["id"],
                "name": att.get("name") or "",
                "contentType": att.get("contentType") or "",
                "size": att.get("size") or 0,
                "isInline": bool(att.get("isInline")),
                "odataType": att.get("@odata.type") or "",
            })
        return out

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        return self._get(f"{GRAPH}/me/messages/{message_id}/attachments/{attachment_id}/$value", raw=True)
