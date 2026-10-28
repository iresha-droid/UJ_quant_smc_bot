PAWRS Drive Connection and Bootstrap

1. Purpose

This document provides the common connection and bootstrap instructions for an authorized agent starting in a new workspace who needs access to the shared PAWRS Google Drive.

The purpose is limited to:

- Configure the authorized PAWRS Drive connection.
- Establish the "pawrs-user" remote.
- Run the PAWRS bootstrap command.
- Confirm whether the connection and checkpoint discovery succeeded.
- Locate the governance documentation that controls all subsequent work.

The connection details and bootstrap command below reflect the configuration documented and confirmed during the project's prior work. They must not be replaced with guessed values or unrelated Drive credentials.

2. PAWRS Drive Connection Details

Use these settings for the shared PAWRS Drive connection:

Setting| Confirmed value
PAWRS credential input for a fresh environment| "PAWRS_SERVICE_ACCOUNT_JSON"
Rclone remote| "pawrs-user:"
PAWRS data prefix| "PAWRS/v1/"
Google Drive scope| "drive"
Configured PAWRS root folder ID| "1c13t6mb6r7AE8n0HLErTRLYQsgKDuL_J"
Private PAWRS rclone configuration| "~/.local/state/pawrs/rclone.conf"

The scope and root folder ID above are the values recorded for the existing authorized PAWRS Drive configuration. Use them only when connecting to that same PAWRS Drive. Do not assume they apply to a different Drive or account.

The root folder ID is configuration information, not a credential. The service-account JSON credential is secret and must never be included in this document.

3. Configure Access in a Fresh Workspace

A new agent environment must have authorized access to the PAWRS credential before bootstrap can connect to the shared Drive.

1. Confirm that the agent is authorized to access the project's PAWRS Drive.

2. Check whether the private PAWRS configuration already exists at:
   
   "~/.local/state/pawrs/rclone.conf"

3. If the configuration already exists, do not display its contents, delete it, or replace it merely because environment settings differ. The existing private configuration may take precedence over environment values.

4. If this is a genuinely fresh environment without the existing private configuration, make the authorized service-account JSON credential available through the environment's approved secret-management mechanism under:
   
   "PAWRS_SERVICE_ACCOUNT_JSON"

5. Supply the confirmed non-secret configuration values through the approved environment configuration mechanism if the implementation requires them:
   
   - "PAWRS_GOOGLE_DRIVE_SCOPE"
   - "PAWRS_GOOGLE_ROOT_FOLDER_ID"

6. Never place the JSON credential in a shell command, source file, Git history, issue, screenshot, log, or report.

7. Do not invent a credential, request a replacement credential without authorization, or guess a missing root folder ID or scope.

The credential owner must authorize and provide access to the secret for each agent environment that needs it. Naming the secret in this document does not automatically grant access to it.

4. Bootstrap Command

Run the bootstrap command from the intended PAWRS workspace.

General command

python3 -m pawrs bootstrap --workspace "$PWD"

The command above assumes the current working directory is the intended workspace.

Explicit workspace example

python3 -m pawrs bootstrap --workspace /workspaces/Cha-cop

For any other agent or workspace, replace the example path with the actual workspace path. Do not assume that every agent uses the same Codespaces directory.

5. What Bootstrap Confirms

Bootstrap initializes or uses the PAWRS configuration, checks access through the "pawrs-user" remote, and searches the PAWRS checkpoint location for available valid checkpoints.

After running it, read the output from that specific run.

Record:

- Whether PAWRS Drive access succeeded.
- The number of valid checkpoints found.
- The number of invalid or incomplete checkpoints found.
- Any error or unresolved connection requirement reported.

Do not carry checkpoint counts forward from an earlier agent, workspace, or bootstrap run.

Important: Successful bootstrap does not itself restore a checkpoint. It also does not prove that automatic checkpoint creation, continuous watcher operation, or checkpoint persistence has been verified.

If authentication fails, required configuration is missing, or the intended PAWRS Drive cannot be established, stop and report the exact blocker. Do not switch to another Drive or invent an alternative connection.

6. Obsolete Connection Instructions

The following older variables are not the current connection method documented for the inspected PAWRS implementation:

- "PAWRS_RCLONE_TOKEN"
- "PAWRS_GOOGLE_CLIENT_ID"
- "PAWRS_GOOGLE_CLIENT_SECRET"

Do not use those older instructions as a fallback for the current implementation.

The following credential and connection route belongs to the separate Original Drive used for task-output/report files, not the PAWRS checkpoint connection:

- "RCLONE_GDRIVE_CONFIG_TOKEN"
- "RCLONE_DRIVE_BOOTSTRAP_HANDOFF.md"
- "dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/"

Never interchange the Original Drive and PAWRS Drive credentials, remotes, or destinations.

PAWRS checkpoint data belongs under "pawrs-user:" and the "PAWRS/v1/" prefix. The Original Drive route must be used only for its separately authorized purpose.

7. After Connection: Follow the Governance Documents

This document covers connection and bootstrap only.

Once PAWRS Drive access has been established:

1. Locate and read the project's designated governance folder and its authoritative instructions.
2. Follow the relevant governance documents for checkpoint recovery, checkpoint creation, handoff, continuation, persistence, and any other subsequent operation.
3. Use the procedures and approved destinations specified by those documents.
4. Do not infer that bootstrap authorization automatically authorizes a write, checkpoint creation, deletion, restore, or other Drive modification.
5. If the required governance document is missing, inaccessible, or unclear, stop and report the issue instead of inventing a procedure.

Do not use this bootstrap document as a substitute for the governance documents.

8. Security Rules

- Use only an authorized PAWRS credential.
- Never expose secrets or private rclone configuration contents.
- Do not delete or overwrite an existing private PAWRS configuration as a troubleshooting shortcut.
- Do not guess credentials, scopes, root folder IDs, or remote names.
- Do not use the Original Drive as a PAWRS fallback.
- Do not claim that bootstrap, checkpoint creation, upload, read-back, or recovery succeeded unless the actual operation's output supports that claim.

Final Rule

Establish the authorized "pawrs-user:" connection, run the documented bootstrap command, record the actual result, and then follow the governance documents stored on PAWRS Drive for all subsequent work.