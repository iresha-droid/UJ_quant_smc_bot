# NEW TASK INVENTORY DECISION NOTES

## 1. Introduction

This document defines the required workflow for an agent handling a new user-assigned task. It exists to keep each new task independent, protect the original project and its inventory, and make deliverables easy for the user to retrieve from a temporary Codespace.

Read this document before starting a new task. Follow it together with the user's latest explicit instructions. The user's current task defines the scope of work.

## 2. Mandatory Instructions

- Work only on the task the user has currently assigned.
- Do not assume that you should continue, resume, or complete work performed by a previous agent.
- Do not change the original project's code, inventory, recovery files, or unrelated documents unless the user explicitly authorizes that change.
- Do not claim a file was created, tested, downloaded, committed, or pushed unless that action has actually been verified.
- Protect existing work. Before any destructive operation, check what it affects and obtain user approval when the action goes beyond an already explicit instruction.
- If instructions conflict or the correct repository, branch, or target is uncertain, stop and ask a focused clarification instead of guessing.

## 3. Handoff and Startup Instructions

At the start of each new task:

1. Read this document.
2. Read and understand the user's latest task request and any constraints supplied with it.
3. Identify the required deliverables, format, and acceptance criteria.
4. Establish an isolated temporary working environment when appropriate and consistent with the user's latest explicit instructions. The agent is responsible for setting up its working environment; do not ask the user to provision a Codespace unless a genuine permission or account limitation makes that necessary.
5. Confirm the active repository and branch. If the user explicitly names the current repository/workspace as the task target, follow that specific instruction; do not switch repositories or create an unnecessary separate Codespace.
6. Keep task outputs separate from the original project unless the user's explicit task specifically authorizes work in that project.
7. Begin the current task from its stated requirements. Do not treat previous agents' unfinished work as an instruction to continue it, unless the user explicitly asks to resume, retrieve, or continue specified prior work.

## 4. How to Use This Document

Use this document as the common operating guide for new tasks. It is not, by itself, a task queue or permission to modify the main project. The user's latest explicit task instruction defines the scope and can expressly authorize work in a named repository or continuation/retrieval of specified prior work.

The workflow is: understand the current request, use an appropriate workspace consistent with the user's explicit instructions, create the requested deliverables, validate them, and tell the user how to retrieve them. When the user assigns another new task, follow that request independently unless the user explicitly asks to resume, retrieve, or continue specified prior work.

## 5. Working Environment

- Use a separate temporary Codespace/workspace by default when suitable. However, if the user's latest explicit instruction names the current repository/workspace as the target, work there within the authorized scope; this specific instruction takes precedence over the general isolation preference.
- The user expects the agent to set up an appropriate environment rather than requiring the user to create it manually, unless a genuine permission or account limitation prevents this.
- A Codespace has its own filesystem. The local staging directory described below exists inside that Codespace and is not shared across different Codespaces. A Drive folder with the same path/name is a separate remote location; never treat the local directory as proof that the Drive upload succeeded.
- Do not commit or push task deliverables to any repository. A change to this guide or another repository file is allowed only when the user explicitly authorizes that specific file change.
- If a genuine access, permission, or safety limitation prevents the requested work, explain the precise limitation before making any out-of-scope change.

## 6. File Creation and Saving

Use this common local staging directory inside the task's Codespace:

`/workspaces/new-task-output/`

Create the directory if it does not already exist. A task-specific subdirectory may be used to organize multiple deliverables, for example `/workspaces/new-task-output/<task-name>/`.

- Save requested output files there first, using clear, descriptive filenames and the formats requested by the user.
- The local Codespace staging directory `/workspaces/new-task-output/` and the user's remote original-Drive destination `dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/` are different locations and do not have the same path. A local file is not saved to Drive until the remote upload and verification described in Section 13 succeed.
- Do not use a fixed filename for reports unless the user specifies one. Choose a descriptive name based on the selected task/command/response, adding a timestamp or unique suffix when needed to avoid collisions.
- Do not overwrite an existing file unless the user explicitly requests an update and the target has been verified as the intended file.
- Check that each expected local output file exists, is readable, and contains the complete intended content before reporting completion.
- Keep output files outside the original repository's tracked project files and inventory.


## 7. Delivering Results from Codespaces

When the task is complete:

1. List each deliverable by filename and its full path.
2. Tell the user how to download the files from the Codespace using the available interface.
3. Verify that the files exist and are readable before claiming they are ready.
4. If possible, provide concise verification details relevant to the task.
5. Do not claim that the user has downloaded or received a file until the user confirms it.
6. If the user requested persistent Drive delivery, also report the verified original-Drive destination and integrity-check results as specified in Section 13.

Codespace storage is not a permanent backup. Uncommitted files can become unavailable if a Codespace is deleted or its storage is lost. For a requested persistent report, do not rely on local storage alone; complete and verify the Drive upload before reporting it as saved there.

## 8. Completion

A task is complete when the current user request has been fulfilled, the requested outputs have been validated, and the user has been given their paths and download instructions.

Do not automatically start another task, continue previous agents' work, or create a follow-on workflow. Wait for the user's next instruction.

## 9. Failure Handling

If the Codespace cannot be created or accessed, permissions are insufficient, credits run out, execution stops, or an output file cannot be generated:

- State what succeeded, what failed, and what remains incomplete.
- Preserve existing work and any recoverable outputs.
- Do not report success based on an attempted action alone.
- Do not make unapproved changes to the original repository to work around the problem.
- Give the user the smallest practical next step needed to proceed.

## 10. Protect the Inventory and Main Project

- This guide must remain outside the project's inventory.
- Do not add this guide or temporary task deliverables to the project inventory or change its item count.
- Do not modify inventory manifests, recovery systems, source-of-truth files, or unrelated project files as part of an ordinary new task.
- Do not place task output files in the original repository.
- Do not alter existing commits or rewrite Git history unless the user explicitly requests it.
- If the user requests a change that could affect the inventory or main project, explain the scope and obtain clarification or approval where needed.

## 11. Pre-Start Checklist

Before beginning work, confirm:

- [ ] I read this guide.
- [ ] I understand the user's latest task and deliverables.
- [ ] I am not assuming that I should continue an earlier agent's task.
- [ ] I have identified the correct working environment and repository.
- [ ] I have isolated task outputs from the original project.
- [ ] I will use `/workspaces/new-task-output/` for deliverables.
- [ ] I have identified any permissions, safety, or destructive-action concerns.
- [ ] If the user requested persistent report delivery, I have identified the exact response to save, the original-Drive connection, and the destination folder without confusing them with the PAWRS connection.

## 12. Pre-Completion Checklist

Before reporting completion, confirm:

- [ ] The current task's requested work is complete.
- [ ] Expected output files exist in the common output directory and are readable.
- [ ] Outputs have not been committed or pushed to any repository.
- [ ] The original project and inventory were left unchanged unless an explicit instruction authorized a change.
- [ ] The response lists filenames and paths and explains how to download them.
- [ ] Any failure, limitation, or unverified result is stated accurately.
- [ ] I have not started an unrelated or follow-on task.
- [ ] If persistent report delivery was requested, I verified the uploaded report by reading it back and matching its SHA-256 and byte size before reporting success.

## 13. Persistent Agent-Response and Report Delivery via Original Drive

### 13.1 Purpose and User Selection

Use this procedure when the user explicitly asks to save a particular agent response, command result, task report, or other specified response to the user's original Drive. This is especially useful when the response is too long to copy conveniently from chat on a mobile device.

- The user's instruction identifies which command/task/agent response is to be saved. Save the complete response relevant to that selection, not a short summary, unless the user asks for a summary.
- This is a general procedure: the selected command, report content, and filename can vary from task to task. Do not hard-code a single command or filename.
- Do not save every agent response automatically. Use this procedure when the user asks for persistent delivery or when the user's standing instructions clearly require it.
- Do not include unrelated responses, terminal logs, credentials, OAuth tokens, or unrelated workspace content in the report.
- If the requested response cannot be identified from the conversation/context, ask one focused clarification. Do not ask again for information already stated clearly.

### 13.2 Mandatory Drive/Token/Function Isolation (Fail-Closed Rule)

The two Drive connections are separate security boundaries with different permitted purposes. The agent MUST choose the connection by the task's purpose and MUST NOT cross over to the other Drive, even if the other connection is available or appears easier to use.

| Credential / connection | Sole permitted purpose | Permitted destination/scope | Forbidden use |
|---|---|---|---|
| `RCLONE_GDRIVE_CONFIG_TOKEN` | Deliver a specific response/report to the user, only when the user requests that delivery | `dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/` only | PAWRS checkpoints, persistence, recovery, handoff state, project snapshots, or any other Drive/folder |
| `PAWRS_RCLONE_TOKEN` | PAWRS automatic persistence, checkpointing, recovery, and agent-to-agent handoff only | The dedicated PAWRS Drive connection and its configured PAWRS scope only | Ordinary user response/report delivery, including the original-Drive destination `dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/` |

These mappings are mandatory and must be treated as separate, non-interchangeable rules:

**HARD COMMAND — EXCLUSIVE USE OF `RCLONE_GDRIVE_CONFIG_TOKEN` FOR ORIGINAL-DRIVE REPORT DELIVERY**

`RCLONE_GDRIVE_CONFIG_TOKEN` MUST be used exclusively to establish the original Dedicated Google Drive connection by following the exact bootstrap procedure in `RCLONE_DRIVE_BOOTSTRAP_HANDOFF.md`, and to save and verify the user-authorized response/report file(s) only in:

`dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/`

The agent MUST read and follow `RCLONE_DRIVE_BOOTSTRAP_HANDOFF.md` before establishing this connection. This is mandatory and MUST NOT be bypassed, improvised, or replaced with another bootstrap method.

This token MUST NOT be used for PAWRS persistence, implementation recovery, checkpoints, handoff state, project snapshots, or any unrelated Drive destination or workflow. Those operations must use their separately authorized credentials and procedures.

If the required bootstrap procedure, token, connection, or exact destination cannot be verified, the agent MUST STOP the affected Drive operation and report the precise blocker. It MUST NOT substitute another account, token, Drive, remote, destination, or improvised connection method.

After saving a report, the agent MUST read it back and verify its SHA-256 hash, byte size, and byte-for-byte integrity against the local source file before reporting success.

1. **Report-delivery task:** use only the original-Drive connection established from `RCLONE_GDRIVE_CONFIG_TOKEN`, and save only to the exact verified destination `dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/`. Before setting up or using this connection, read `RCLONE_DRIVE_BOOTSTRAP_HANDOFF.md` and establish the connection exactly as that document describes; do not reproduce, improvise, or substitute a different bootstrap procedure. Perform only the connection checks permitted by that handoff before report delivery. Do not use `PAWRS_RCLONE_TOKEN`, the PAWRS remote, or any other Drive as a fallback.
2. **PAWRS persistence/recovery task:** use only the PAWRS connection established from `PAWRS_RCLONE_TOKEN`, within its configured PAWRS scope. Do not use `RCLONE_GDRIVE_CONFIG_TOKEN`, the original Drive, or the report-delivery folder for PAWRS state.
3. **No cross-purpose access:** a task may not access a Drive outside the connection and destination explicitly assigned to that task by these rules. Do not browse, list, test, write, read, or delete content in the other Drive merely because its credentials are available.
4. **No guessed remote names or paths:** a secret's name is not necessarily an rclone remote name. Resolve the connection only from safe, non-secret configuration metadata. Never print, log, expose, or include token/secret values in output.
5. **Verify before any operation:** before listing or writing, verify that the selected remote corresponds to the correct token/connection and that the destination is within the permitted scope. Do not infer this merely from a remote name, a matching folder name, or the presence of a secret.
6. **Fail closed:** if the required secret is missing, malformed, inaccessible, ambiguously mapped, or cannot be verified as the correct connection and permitted destination, stop that Drive operation. State exactly what could not be verified. Do not switch to the other Drive, another credential, another remote, or another folder; do not ask the user to accept a silent substitution.
7. **No connection mutation:** do not change either token, credential, root-folder setting, scope, or unrelated remote configuration to make an operation work. Do not print raw configuration containing secrets.
8. **Separate evidence:** report-delivery verification proves only that the requested report was saved to the original Drive. PAWRS persistence/recovery verification proves only the PAWRS operation. Success on one connection does not validate or authorize the other.

For ordinary response/report delivery, the exact original-Drive destination is:

`dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/`

The local Codespace staging directory `/workspaces/new-task-output/` is not this remote Drive folder. A local file does not count as a Drive delivery.

If the original-Drive connection is unavailable, permission is denied, or the exact destination cannot be verified, preserve the local report and report the limitation. Do not select another Drive destination or silently use the PAWRS Drive or any other destination. Do not use `SOURCE_OF_TRUTH/` or the prohibited workaround `tools/publish_repository_recovery.py` to perform report delivery.

### 13.3 Dynamic Filename and Destination Safety

- Save each requested report as a separate file only inside `dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/`.
- Choose a clear, descriptive filename based on the selected command/task/response. Add a timestamp or unique suffix when necessary to prevent collisions. Do not hard-code one report filename for all tasks.
- Preserve existing files. Never overwrite or delete an existing Drive report as an automatic retry.
- Upload only the report the user authorized for this task. Do not upload the project, workspace, logs, or other files under this procedure.
- Keep the report outside the project's source-of-truth snapshot and inventory.

### 13.4 Strict Separation from Project Source of Truth

Every report delivered through this procedure must satisfy all of the following:

- Remain outside `SOURCE_OF_TRUTH/`.
- Remain outside the project's authoritative source snapshot and recovery inventory.
- Never be added to the project inventory or its item count.
- Never be published through the normal repository recovery publisher, `tools/publish_repository_recovery.py`.
- Never require changes to `CURRENT.json`, `PROJECT_SOURCE_OF_TRUTH.json`, inventory manifests, publisher code, or other source-of-truth files.
- Never be committed or pushed to the original project repository solely to make the report downloadable.

The original Drive destination `dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/` is a separate report-delivery location, not part of the authoritative project snapshot.

### 13.5 Mandatory Upload and Integrity Verification

For each report uploaded to the original Drive:

1. Finish generating the report in the isolated task workspace, normally under the local staging directory `/workspaces/new-task-output/`.
2. Confirm the expected local file exists, is readable, and contains the complete selected response/report.
3. Check that the report contains no credentials, OAuth tokens, or unrelated sensitive information.
4. Calculate and record the local file's SHA-256 hash and byte size.
5. Upload only that report to the exact `dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/` destination using the verified original-Drive connection.
6. Download the uploaded file back to a separate temporary verification path. Do not overwrite or modify the original local report during verification.
7. Calculate the downloaded copy's SHA-256 hash and byte size.
8. Compare both copies: the SHA-256 hashes and byte sizes must match exactly, and a byte-for-byte comparison must succeed.
9. Confirm the exact remote path and verify that the intended report is present.
10. Report Drive-delivery success only after all checks pass.

If any integrity check fails, do not declare success. Preserve the local report, investigate the discrepancy, and report the actual status. Do not delete or overwrite an existing remote file as an automatic retry.

### 13.6 User Handoff

After successful verification, tell the user:

- The exact report filename.
- The full original-Drive path.
- The verified byte size.
- The SHA-256 hash.
- Whether the SHA-256, byte-size, and byte-for-byte comparisons passed.
- How to locate and download the file using the available Drive interface.

Do not claim that a clickable direct-download or sharing link exists unless it has actually been retrieved and verified. Do not create or enable public sharing without the user's explicit authorization.

### 13.7 Scope Restrictions and Instruction Precedence

This procedure authorizes saving only the specific agent response/report the user selected. It does not authorize uploading arbitrary project files, changing the authoritative inventory, modifying the normal publisher, or treating temporary reports as source-of-truth artifacts.

Follow the user's latest explicit instructions when they specify the task, repository, selected response, or report destination. The general preference for isolated workspaces does not override an explicit instruction to work in a named repository. Do not infer permission to modify any other file or repository from permission to update this guide or save a report.

If a genuine security, access, permission, or destination ambiguity blocks the requested action, stop only the blocked step, preserve completed work, and report the precise issue. Do not invent a destination or silently use the other Drive connection.
