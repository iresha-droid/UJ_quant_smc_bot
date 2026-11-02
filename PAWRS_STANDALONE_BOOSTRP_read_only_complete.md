# PAWRS Standalone Bootstrap

මෙම ලේඛනය අලුත් Codespaces workspace එකකට පැමිණෙන Agent කෙනෙකුට පෙර
workspace, Agent session, PAWRS application code හෝ internal Python modules
මත රඳා නොසිට PAWRS Drive සම්බන්ධතාව සකස් කිරීමට අවශ්‍ය උපදෙස් සපයයි.
මෙහි පහතින් ඇතුළත් script සහ README මෙම Bootstrap අදියරේ read-only
අවශ්‍යතාවයට ගැළපෙන ලෙස සකස් කර ඇත.

## ස්ථිර Service Account සහ folder mapping

- Service Account: `pawrs-drive-access@pawrs-drive-access.iam.gserviceaccount.com`
- Codespaces secret: `PAWRS_SERVICE_ACCOUNT_JSON`
- `PAWRS_GOVERNANCE_READ_ONLY` — Folder ID
  `1BryLbWUNvLVzoYtN19HHDgD9Lpryylvr` — Viewer (metadata සහ Read/List පමණයි).
- `PAWRS_CHECKPOINT_DATA` — Folder ID
  `1C08XJJY-QtHG_T-wGWPPDMuMXSExvJVJ` — Editor.

මෙම IDs ස්ථිර mapping එකයි; ඒවා වෙනස් කිරීම හෝ වෙනත් folder එකක්
අනුමාන කිරීම නොකරන්න.


## PAWRS Drive සහ Original Dedicated Drive අතර අනිවාර්ය වෙන් කිරීම

මෙම Bootstrap එක සම්බන්ධ වන්නේ **PAWRS Drive** එකට පමණි:

- Authentication සඳහා `PAWRS_SERVICE_ACCOUNT_JSON` සහ ඉහත සඳහන්
  Service Account එක පමණක් භාවිත කරන්න.
- Governance සහ Checkpoint සඳහා ඉහත ස්ථිර Folder IDs දෙක පමණක් භාවිත කරන්න.
- මෙම අදියරේ `rclone`, `RCLONE_GDRIVE_CONFIG_TOKEN`,
  `RCLONE_DRIVE_BOOTSTRAP_HANDOFF.md`, Drive-root discovery හෝ වෙනත්
  Google Drive account එකක් භාවිත නොකරන්න.

**Original Dedicated Drive** එක වෙනම කාර්යයකට පමණි. එයට ප්‍රවේශ විය යුත්තේ
`RCLONE_GDRIVE_CONFIG_TOKEN` සහ `RCLONE_DRIVE_BOOTSTRAP_HANDOFF.md`
හරහා පමණක් වන අතර, task response files සඳහා නියමිත destination එක
`dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/` වේ.

PAWRS Drive credentials/folders සහ Original Dedicated Drive credentials/
destination එකිනෙකට အစားထုံး කළ හැකි ඒවා නොවේ. එක් Drive එකකට අදාළ
credential, connection හෝ folder path එක අනෙක් Drive එකට භාවිත නොකරන්න.

## අලුත් Codespace එකක Bootstrap ක්‍රියාපටිපාටිය

1. අලුත් Codespaces workspace එකක් විවෘත කරන්න. පෙර workspace files හෝ
   configuration අවශ්‍ය නැහැ.
2. මෙම `PAWRS_STANDALONE_BOOSTRP.md` ලේඛනය Agent/workspace එකට ලබාදෙන්න.
   මෙහි පහත සම්පූර්ණ script එක ඇත.
3. පහත `pawrs_drive_bootstrap.py` code block එකේ සියලුම code lines,
   delimiters හැර, `drive-bootstrap/pawrs_drive_bootstrap.py` නමින් සුරකින්න.
   වෙනත් source file එකක් අවශ්‍ය නැහැ.
4. Codespaces secret එක `PAWRS_SERVICE_ACCOUNT_JSON` ලෙස ලබාදී තිබේදැයි
   value එක නොපෙන්වා පරීක්ෂා කරන්න:

   ```sh
   python3 -c "import os; print('PAWRS_SERVICE_ACCOUNT_JSON: ' + ('set' if os.environ.get('PAWRS_SERVICE_ACCOUNT_JSON') else 'MISSING'))"
   ```

   `MISSING` නම් GitHub → repository **Settings → Secrets and variables →
   Codespaces** වෙතින් secret එක සකසා Codespace එක නැවත ආරම්භ කරන්න. JSON
   අගය terminal, source, log හෝ chat එකකට paste/print නොකරන්න.
5. මුල් README එකට අනුව dependency එක ස්ථාපනය කරන්න:

   ```sh
   python3 -m pip install --user 'google-auth[requests]'
   ```

6. Bootstrap script එක ක්‍රියාත්මක කරන්න:

   ```sh
   python3 drive-bootstrap/pawrs_drive_bootstrap.py
   ```

7. Output එකේ service-account authentication, folder metadata සහ folder
   දෙකෙහි `Read/List` ප්‍රතිඵල වෙන වෙනම බලන්න. Script එක `drive.readonly`
   scope එක භාවිත කරන අතර කිසිදු Write Test එකක් සිදු නොකරයි.
8. Governance folder එකේ files/folders Agent හට පෙනෙන බව
   `PAWRS_GOVERNANCE_READ_ONLY Read/List (N direct items): PASS` ප්‍රතිඵලයෙන්
   තහවුරු කරන්න. Script එක item count එක පමණක් පෙන්වයි; filenames හෝ
   Governance rules අන්තර්ගතය පෙන්වන්නේ නැහැ.
9. Governance rules කියවීමට පහත “Governance rules කියවීම” පියවර භාවිත
   කරන්න. Folder එකට create/update/delete කිසිවක් නොකරන්න.

### Governance rules කියවීම

Bootstrap output එකෙන් metadata සහ Read/List සාර්ථක බව තහවුරු කළ පසු,
පහත read-only snippet එක ධාවනය කරන්න. එය Governance folder එකේ files
ලැයිස්තුගත කර නාම, MIME type සහ IDs පෙන්වයි. එම listing එකෙන් Agent/owner
විසින් තහවුරු කළ rules file ID එක පමණක් `RULE_FILE_ID` ලෙස යොදන්න; ID එකක්
අනුමාන නොකරන්න.

```sh
RULE_FILE_ID='PASTE_VERIFIED_GOVERNANCE_RULE_FILE_ID_HERE' python3 - <<'PY'
import io
import json
import os

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account

info = json.loads(os.environ["PAWRS_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(
    info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
)
credentials.refresh(Request())
session = AuthorizedSession(credentials)

folder_id = "1BryLbWUNvLVzoYtN19HHDgD9Lpryylvr"
files = []
page_token = None

# Retrieve every page; never assume the first 1,000 items are the full listing.
while True:
    params = {
        "q": f"'{folder_id}' in parents and trashed = false",
        "pageSize": 1000,
        "fields": "nextPageToken,files(id,name,mimeType)",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    if page_token:
        params["pageToken"] = page_token

    response = session.get(
        "https://www.googleapis.com/drive/v3/files",
        params=params,
        timeout=60,
    )
    response.raise_for_status()
    page = response.json()
    if not isinstance(page, dict) or not isinstance(page.get("files", []), list):
        raise SystemExit("Invalid Governance folder listing response")

    files.extend(page.get("files", []))
    page_token = page.get("nextPageToken")
    if not page_token:
        break

for item in files:
    print(f"{item['name']}\\t{item['mimeType']}\\t{item['id']}")

rule_id = os.environ["RULE_FILE_ID"]
selected = next((item for item in files if item["id"] == rule_id), None)
if selected is None:
    raise SystemExit("RULE_FILE_ID is not in the complete Governance folder listing")

mime_type = selected["mimeType"]
if mime_type == "application/vnd.google-apps.document":
    content_response = session.get(
        f"https://www.googleapis.com/drive/v3/files/{rule_id}/export",
        params={"mimeType": "text/plain"},
        timeout=60,
    )
    content_response.raise_for_status()
    print(content_response.content.decode("utf-8-sig"))
elif mime_type == "application/pdf":
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit(
            "This Governance file is a PDF. Install the optional reader with: "
            "python3 -m pip install --user pypdf"
        )
    content_response = session.get(
        f"https://www.googleapis.com/drive/v3/files/{rule_id}",
        params={"alt": "media", "supportsAllDrives": "true"},
        timeout=60,
    )
    content_response.raise_for_status()
    reader = PdfReader(io.BytesIO(content_response.content))
    for page_number, page in enumerate(reader.pages, start=1):
        print(f"\\n--- PDF page {page_number} ---")
        print(page.extract_text() or "[No extractable text on this page]")
elif mime_type.startswith("text/") or mime_type in {
    "application/json",
    "application/xml",
}:
    content_response = session.get(
        f"https://www.googleapis.com/drive/v3/files/{rule_id}",
        params={"alt": "media", "supportsAllDrives": "true"},
        timeout=60,
    )
    content_response.raise_for_status()
    print(content_response.content.decode("utf-8-sig"))
else:
    raise SystemExit(
        f"Unsupported Governance MIME type: {mime_type}. "
        "Do not treat this as an access failure; use an approved read-only "
        "reader for this exact format before considering the rules read."
    )
PY
```

මෙම snippet එක Governance folder එකේ සියලුම listing pages ලබාගෙන,
තහවුරු කළ File ID එක සම්පූර්ණ listing එක තුළ සොයයි. එය Google Docs,
PDF සහ UTF-8 text/JSON/XML files කියවයි. PDF එකක් නම් පමණක් optional
`pypdf` dependency එක අවශ්‍ය වේ:

```sh
python3 -m pip install --user pypdf
```

වෙනත් MIME type එකක් හමුවුවහොත් snippet එක එය පැහැදිලිව unsupported ලෙස
දක්වයි. එය Drive access අසාර්ථක බවක් නොවේ; එම format එකට අනුමත read-only
reader එකක් භාවිත කර Rules අන්තර්ගතය සම්පූර්ණයෙන් කියවූ පසුව පමණක්
Governance Rules කියවීම සාර්ථක බව තහවුරු කරන්න. Secret හෝ token
කිසිවිටෙක print නොකරන්න.

## Bootstrap අවසන් වන සීමාව

Standalone Bootstrap එක සාර්ථකව අවසන් වන්නේ මේ සියල්ල තහවුරු වූ විට පමණි:

1. Secret JSON valid අතර `client_email` නිවැරදි Service Account එකට ගැළපීම සහ
   Google Drive API token authentication සාර්ථක වීම.
2. Folder IDs දෙකම නියමිත names සහ Drive folder MIME type සමඟ හඳුනාගැනීම.
3. Governance Read/List සාර්ථක වීම; එහි files සහ authorized Governance
   rules Agent හට පෙනී කියවිය හැකි වීම.
4. Checkpoint metadata සහ Read/List සාර්ථක වී folder එකට සම්බන්ධ විය හැකි බව
   තහවුරු වීම.

මෙම අදියරේ `Viewer`/`Editor` write capability පරීක්ෂා කිරීම අවශ්‍ය නොවේ.
`drive.readonly` scope එක යටතේ Bootstrap එකෙන් තහවුරු කරන්නේ metadata සහ
Read/List access පමණි. Checkpoint Create/Write/Update/Delete පරීක්ෂණ කිසිවක්
සිදු නොකළ යුතුය.

මෙම සීමාවට ළඟා වූ විට Bootstrap කාර්යය අවසන්ය. PAWRS application code
ස්ථාපනය කිරීම, recovery ZIP extract කිරීම හෝ PAWRS functionality පරීක්ෂා
කිරීම මෙම අදියරේ නොකරන්න.

මෙම Bootstrap script එක `https://www.googleapis.com/auth/drive.readonly`
scope එක පමණක් භාවිත කරයි. එය Authentication, fixed folder metadata සහ
Read/List පමණක් පරීක්ෂා කරයි. Checkpoint folder එකට file එකක් Create,
Upload, Update, Read-back හෝ Delete කිරීමට කිසිදු උත්සාහයක් නොකරයි.
Checkpoint Write capability පරීක්ෂා කිරීම මෙම අදියරේ කොටසක් නොවේ.
Script එකේ `Overall Read-only Bootstrap: PASS` යන්නෙන් අදහස් වන්නේ
Bootstrap සඳහා නියමිත read-only checks සියල්ල සාර්ථක බවයි.

## වෙනම ඊළඟ අදියර: recovery package

Bootstrap සාර්ථක වී Governance rules කියවූ පසුව පමණක් recovery අදියර වෙනම
ආරම්භ වේ. එහි පසුකාලීන command එක දැනට ඇති authorized PAWRS Drive API
connection එක භාවිත කර Governance rules කියවා, ඒවා අනුව recovery package
ZIP එක හඳුනාගෙන Codespaces workspace එකට ලබාගෙන extract කළ යුතුය. මෙම
ලේඛනය එම අදියරේ command එකක් අනුමාන නොකරයි: නිවැරදි ZIP path සහ command
Governance rules කියවූ පසු තීරණය කළ යුතුය. ZIP එක download/restore කිරීම
Bootstrap කොටසක් නොවේ.

## Standalone read-only Bootstrap files

පහත Python script සහ README මෙම Bootstrap එකේ අවශ්‍යතාවයට ගැළපෙන ලෙස
read-only ක්‍රියාකාරිත්වයට සකස් කර ඇත. ඒවායේ පැරණි Write Test කොටස්
ඉවත් කර ඇත.

### `drive-bootstrap/pawrs_drive_bootstrap.py`

<!-- BEGIN PAWRS READ-ONLY DRIVE BOOTSTRAP PYTHON -->
```python
#!/usr/bin/env python3
"""Verify read-only access to the fixed PAWRS Drive folders."""

import json
import os
import sys

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account

DRIVE_API = "https://www.googleapis.com/drive/v3"
SERVICE_ACCOUNT = "pawrs-drive-access@pawrs-drive-access.iam.gserviceaccount.com"
FOLDERS = (
    ("PAWRS_GOVERNANCE_READ_ONLY", "1BryLbWUNvLVzoYtN19HHDgD9Lpryylvr"),
    ("PAWRS_CHECKPOINT_DATA", "1C08XJJY-QtHG_T-wGWPPDMuMXSExvJVJ"),
)
FOLDER_MIME = "application/vnd.google-apps.folder"
READ_ONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def fail(message):
    print(f"FAIL: {message}")
    return 1


def list_children(session, folder_id):
    items = []
    page_token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "pageSize": 1000,
            "fields": "nextPageToken,files(id,name,mimeType)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        response = session.get(f"{DRIVE_API}/files", params=params, timeout=60)
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, dict) or not isinstance(page.get("files", []), list):
            raise ValueError("Invalid Drive file-list response")
        items.extend(page.get("files", []))
        page_token = page.get("nextPageToken")
        if not page_token:
            return items


def main():
    secret = os.environ.get("PAWRS_SERVICE_ACCOUNT_JSON")
    if not secret:
        return fail("PAWRS_SERVICE_ACCOUNT_JSON is not set")

    try:
        info = json.loads(secret)
    except (TypeError, ValueError):
        return fail("PAWRS_SERVICE_ACCOUNT_JSON is not valid JSON")

    if (
        not isinstance(info, dict)
        or info.get("type") != "service_account"
        or info.get("client_email") != SERVICE_ACCOUNT
        or not isinstance(info.get("private_key"), str)
        or not info["private_key"]
    ):
        return fail("Service Account identity or JSON is invalid")

    try:
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=[READ_ONLY_SCOPE]
        )
        credentials.refresh(Request())
        session = AuthorizedSession(credentials)
    except (GoogleAuthError, KeyError, TypeError, ValueError):
        return fail("Google Drive read-only authentication failed")

    print(f"Service Account authentication (read-only): PASS ({SERVICE_ACCOUNT})")
    all_passed = True

    for name, folder_id in FOLDERS:
        try:
            response = session.get(
                f"{DRIVE_API}/files/{folder_id}",
                params={
                    "fields": "id,name,mimeType",
                    "supportsAllDrives": "true",
                },
                timeout=60,
            )
            response.raise_for_status()
            metadata = response.json()
            if (
                metadata.get("id") != folder_id
                or metadata.get("name") != name
                or metadata.get("mimeType") != FOLDER_MIME
            ):
                print(f"{name} metadata: FAIL (fixed ID/name/folder type mismatch)")
                all_passed = False
                continue
            print(f"{name} metadata: PASS")

            children = list_children(session, folder_id)
            print(f"{name} Read/List ({len(children)} direct items): PASS")
        except Exception as error:
            # Avoid printing request headers, credential objects, or secret values.
            status = getattr(getattr(error, "response", None), "status_code", None)
            detail = f"HTTP {status}" if status else type(error).__name__
            print(f"{name} Read/List: FAIL ({detail})")
            all_passed = False

    print(f"Overall Read-only Bootstrap: {'PASS' if all_passed else 'FAIL'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
```
<!-- END PAWRS READ-ONLY DRIVE BOOTSTRAP PYTHON -->

### `drive-bootstrap/README.md`

<!-- BEGIN PAWRS READ-ONLY DRIVE BOOTSTRAP README -->
````markdown
# PAWRS Google Drive read-only bootstrap

This standalone script authenticates with `PAWRS_SERVICE_ACCOUNT_JSON` and
uses the Google Drive API directly. It does not need PAWRS source code, a
previous workspace, rclone, or Drive-root discovery.

| Folder | Fixed ID | Bootstrap access required |
|---|---|---|
| `PAWRS_GOVERNANCE_READ_ONLY` | `1BryLbWUNvLVzoYtN19HHDgD9Lpryylvr` | Read metadata and Read/List |
| `PAWRS_CHECKPOINT_DATA` | `1C08XJJY-QtHG_T-wGWPPDMuMXSExvJVJ` | Read metadata and Read/List |

Expected service account:
`pawrs-drive-access@pawrs-drive-access.iam.gserviceaccount.com`.

## New Codespace setup

1. In GitHub, open **Settings → Secrets and variables → Codespaces** and add
   `PAWRS_SERVICE_ACCOUNT_JSON` with the service-account JSON value. Never
   put the JSON in a command, workspace file, log, or chat.
2. Save the script as `drive-bootstrap/pawrs_drive_bootstrap.py`.
3. Install the only direct Python dependency and run the script:

   ```sh
   python3 -m pip install --user 'google-auth[requests]'
   python3 drive-bootstrap/pawrs_drive_bootstrap.py
   ```

The script validates the JSON and exact service-account identity, obtains a
Drive API access token using the `drive.readonly` scope, checks both fixed
IDs' exact names and folder MIME types, and lists every page of each folder's
direct children. The separate Governance reader supports Google Docs and
UTF-8 text/JSON/XML files. For PDF Governance rules, install the optional
`pypdf` reader with `python3 -m pip install --user pypdf`.

This bootstrap performs read-only operations only. It does not create,
upload, update, read back, or delete any file. It does not verify Editor
write capability or prove that Checkpoint writes work. Those are outside the
Bootstrap phase.

Exit status `0` and `Overall Read-only Bootstrap: PASS` mean authentication,
fixed-folder metadata checks, and Read/List checks passed for both folders.
Otherwise, the script exits nonzero and reports the failed step.
````
<!-- END PAWRS READ-ONLY DRIVE BOOTSTRAP README -->
