# PAWRS Google Drive Connection and Bootstrap Guide

## 1. Purpose

This document defines the standard procedure for connecting PAWRS to its dedicated Google Drive storage and bootstrapping PAWRS in any supported workspace.

The procedure must be independent of any specific repository, agent, or workspace. An agent operating in a new workspace must be able to establish the PAWRS connection and initialize the available PAWRS state without depending on local configuration or files from a previous workspace.

This document covers:

- PAWRS authentication and connection configuration.
- Identification of the PAWRS Google Drive folders.
- PAWRS bootstrap.
- Verification of connection and bootstrap results.
- Strict separation between the PAWRS Drive and the Original Drive.
- Failure reporting and owner-guided resolution.

Checkpoint creation, persistence, recovery, and agent handoff must follow the applicable PAWRS governance documents.

## 2. Dedicated PAWRS Google Drive

PAWRS uses its dedicated Google Drive connection:

```
"pawrs-user:"
```

The required folder structure is:

<mark><code>Google Drive (pawrs-user:)<br>├── PAWRS_GOVERNANCE_READ_ONLY/<br>└── PAWRS_CHECKPOINT_DATA/</code></mark>

These folders have distinct purposes.

### 2.1 PAWRS_GOVERNANCE_READ_ONLY/

This folder contains the authoritative PAWRS governance and operational documents.

After connecting to Google Drive, the agent must locate and read the applicable documents in this folder before performing operations governed by those documents.

The folder must be treated as read-only unless an explicitly authorized procedure states otherwise.

### 2.2 PAWRS_CHECKPOINT_DATA/

This folder contains PAWRS checkpoint and recovery data.

Agents must access and modify this data only in accordance with the applicable PAWRS governance documents and authorized procedures.

A successful connection does not independently authorize an agent to create, overwrite, delete, or restore checkpoint data.

## 3. Authentication and Configuration

PAWRS must use its dedicated Google Drive authentication and configuration mechanism.

The required authentication secret for a fresh environment is:

```
"PAWRS_SERVICE_ACCOUNT_JSON"
```

The following configuration values may also be required by the PAWRS implementation:

<mark><code>PAWRS_GOOGLE_DRIVE_SCOPE=drive<br>PAWRS_GOOGLE_ROOT_FOLDER_ID=1c13t6mb6r7AE8n0HLErTRLYQsgKDuL_J</code></mark>

Use the configuration supported by the current PAWRS implementation. Do not assume that secrets or local configuration from another workspace are automatically available.

A private rclone configuration may be located at:

```
"~/.local/state/pawrs/rclone.conf"
```

Follow the implementation's configuration-resolution rules when establishing the connection.

### 3.1 Credential Security

- Obtain the required authentication secret from the authorized secret or environment configuration.
- Never print, disclose, commit, or include credentials in source files, logs, reports, checkpoints, or handoff messages.
- Do not invent credentials or substitute an unrelated authentication mechanism.
- If a required secret or configuration value is unavailable, report the missing prerequisite without exposing sensitive information.

## 4. Workspace-Independent Bootstrap

The bootstrap procedure must work in the current supported workspace, regardless of which repository or agent is using it.

**Step 1 — Inspect the Current Workspace**

Identify the current workspace root and inspect the available PAWRS implementation and its documentation.

Use the actual workspace in which the agent is operating. Do not assume a fixed repository name or workspace path.

Preserve existing work and configuration.

**Step 2 — Verify Prerequisites**

Confirm that:

- The PAWRS implementation is available.
- Required dependencies are installed.
- The authorized "PAWRS_SERVICE_ACCOUNT_JSON" secret is available.
- Required configuration values are available through the supported configuration mechanism.
- The dedicated PAWRS Drive connection can be initialized.

Do not expose credentials while checking these prerequisites.

**Step 3 — Establish the Drive Connection**

Initialize or configure the dedicated "pawrs-user:" connection using the supported PAWRS implementation.

Verify that the connection can access the expected PAWRS folders.

If the connection fails, follow the mandatory failure-handling rules in Section 5. Do not switch to another Drive connection.

**Step 4 — Run Bootstrap**

From the current workspace, run the supported PAWRS bootstrap command:

<mark><code>python3 -m pawrs bootstrap --workspace "$PWD"</code></mark>

The "$PWD" variable identifies the current working directory. This allows the command to use the current workspace without hard-coding a repository-specific path.

**Step 5 — Verify Bootstrap Results**

Inspect the actual bootstrap output and verify what the process accomplished.

Where supported by the implementation, confirm that:

- The dedicated PAWRS connection was used.
- The expected Google Drive folders were located.
- Applicable governance documents were discovered.
- Available checkpoint data was inspected according to the bootstrap procedure.
- Errors or missing prerequisites were reported accurately.

If no valid checkpoints are found, report that result. Do not invent checkpoints or claim that recovery succeeded.

**Step 6 — Read Governance Instructions**

After establishing the connection and completing bootstrap, locate and read the applicable documents in:

```
"pawrs-user:/PAWRS_GOVERNANCE_READ_ONLY/"
```

Follow those documents for checkpoint creation, persistence, recovery, and agent handoff.

If a required document is missing or inaccessible, report the issue rather than inventing a procedure.

## 5. Strict Drive Separation and Failure Handling

PAWRS and the Original Drive are two separate Google Drive connections with different purposes. Agents must keep these connections strictly separate.

### 5.1 PAWRS Drive

Connection:

```
"pawrs-user:"
```

Purpose:

- Accessing authoritative PAWRS governance documents.
- Storing and accessing PAWRS checkpoint and recovery data.
- Supporting PAWRS persistence and agent-to-agent recovery according to the applicable governance documents.

The PAWRS folder structure is:

<mark><code>Google Drive (pawrs-user:)<br>├── PAWRS_GOVERNANCE_READ_ONLY/<br>└── PAWRS_CHECKPOINT_DATA/</code></mark>

### 5.2 Original Drive

The Original Drive connection and authentication must follow:

```
"RCLONE_DRIVE_BOOTSTRAP_HANDOFF.md"
```

It uses its separately configured connection and authentication mechanism.

Its task-response destination is:

```
"dedicated-drive:UJ_quant_smc_bot_BACKUP/NEW_TASK_OUTPUTS/"
```

This connection is for the documented Original Drive task-response purpose. It must not be substituted for the PAWRS connection.

### 5.3 Mandatory Separation Rules

1. Never confuse the PAWRS Drive connection with the Original Drive connection.
2. Never use the Original Drive as a fallback when the PAWRS Drive connection fails.
3. Never use the PAWRS Drive as a fallback when the Original Drive connection fails.
4. Never substitute one connection's credentials, configuration, folders, or storage destination for those of the other connection.
5. Never store PAWRS checkpoints in the Original Drive task-response folder as an undocumented workaround.
6. Never use the PAWRS checkpoint folder as a substitute for the Original Drive task-response destination.
7. Never silently switch to another Drive, authentication mechanism, or storage location when the required connection fails.

### 5.4 Required Response When PAWRS Connection Fails

If the PAWRS Drive connection cannot be established, or access to either required PAWRS folder fails:

1. Stop the affected PAWRS operation immediately.
2. Do not attempt to use the Original Drive as a fallback.
3. Do not create or select an alternative storage location.
4. Do not bypass the failed connection or continue with operations that require PAWRS access.
5. Record the exact operation that failed and the relevant non-sensitive error output.
6. Identify the failure reason as precisely as the available evidence allows, such as missing credentials, invalid configuration, connectivity failure, permission denial, or missing folders.
7. Report the failure and its exact known cause to the owner.
8. Ask the owner for instructions and wait for the owner's guidance before attempting a remedy or resuming the blocked operation.

If the cause cannot yet be established, explicitly say that the cause is undetermined and provide the available diagnostic evidence. Do not guess or claim an unverified cause.

### 5.5 Required Response When Original Drive Connection Fails

If the Original Drive connection fails:

1. Stop the affected Original Drive operation.
2. Do not use the PAWRS Drive as a fallback.
3. Report the exact known failure reason and relevant non-sensitive diagnostic information to the owner.
4. Ask for instructions and wait for the owner's guidance before attempting an alternative remedy or resuming the blocked operation.

### 5.6 Credential and Diagnostic Safety

Failure reports must never include:

- Service-account JSON.
- Authentication tokens or secrets.
- Private credentials.
- Other sensitive authentication material.

Provide enough non-sensitive diagnostic information for the owner to understand and investigate the failure.

A failed Drive connection must result in stopping the affected operation, reporting the known failure reason to the owner, and waiting for instructions. It must never trigger automatic or undocumented failover to the other Drive.

## 6. Verification and Operational Boundaries

A successful Drive connection or bootstrap command does not, by itself, prove that the entire PAWRS persistence and recovery system is operational.

The following capabilities must be verified separately when required:

- Automatic checkpoint creation.
- File-change monitoring.
- Checkpoint upload and storage verification.
- Recovery from stored checkpoints.
- Agent-to-agent handoff across independent workspaces.
- Persistence across workspace restarts.

Do not claim that any capability is active unless it has been verified through the implementation's supported checks or tests.

Avoid unnecessary write operations during connection verification. Any operation that uploads, overwrites, or deletes data must be authorized by the applicable procedure.

## 7. General Failure Handling

If authentication, connection, folder discovery, or bootstrap fails:

1. Preserve the current workspace and its existing work.
2. Record the command executed and relevant non-sensitive error output.
3. Identify the failure category and the exact known cause, if established.
4. Do not expose credentials.
5. Do not invent an alternative storage location or authentication mechanism.
6. Do not switch to the other Drive connection.
7. Do not claim successful persistence or recovery without evidence.
8. Report the failure to the owner and request instructions.
9. Wait for the owner's guidance before attempting a remedy or resuming the blocked operation.

Resume only after the issue has been addressed in accordance with the owner's instructions and the applicable governance procedures.

## 8. Scope

This document defines the PAWRS Google Drive connection and bootstrap procedure.

It is independent of any particular repository, agent, or workspace path.

It does not replace the authoritative PAWRS governance documents and does not independently authorize checkpoint creation, deletion, restoration, or modification of governance rules.

After bootstrap, agents must follow the applicable documents in "PAWRS_GOVERNANCE_READ_ONLY/" for persistence, checkpoint, recovery, and handoff operations.

## 9. Authoritative Folder Structure

The PAWRS Google Drive structure is:

<mark><code>Google Drive (pawrs-user:)<br>├── PAWRS_GOVERNANCE_READ_ONLY/<br>└── PAWRS_CHECKPOINT_DATA/</code></mark>

All PAWRS connection and bootstrap operations must use the dedicated PAWRS connection and the applicable configuration and procedures defined in this document and the authoritative PAWRS governance documents.

Drive connection failures must be handled according to Section 5. Agents must stop the affected operation, report the failure to the owner, and wait for instructions instead of switching to the other Drive.
