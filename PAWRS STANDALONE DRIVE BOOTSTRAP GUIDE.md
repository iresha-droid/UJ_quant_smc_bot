PAWRS Standalone Drive Bootstrap Guide

1. Purpose

This document is the first and only PAWRS bootstrap artifact an agent needs before receiving the PAWRS source-code ZIP.

The agent must use this guide to establish and verify access to the authorized PAWRS Google Drive location without first needing:

- The PAWRS Python package.
- A PAWRS Git repository.
- A previously configured PAWRS workspace.
- A different agent's workspace.
- An alternative Drive connection or storage location.

After Drive access has been established and verified, the user may provide the PAWRS ZIP. The agent can then inspect the package and continue the PAWRS setup.

2. Mandatory access boundaries

The authorized PAWRS remote is:

"pawrs-user:"

The bootstrap process must use the PAWRS service-account authentication mechanism and the PAWRS-specific configuration described below.

Required environment variables:

- "PAWRS_SERVICE_ACCOUNT_JSON"
- "PAWRS_GOOGLE_DRIVE_SCOPE"
- "PAWRS_GOOGLE_ROOT_FOLDER_ID"

The authorized service-account identity is:

"pawrs-drive-access@pawrs-drive-access.iam.gserviceaccount.com"

The service account must already have permission to access the designated Drive folder.

Do not substitute another Drive remote, another credential mechanism, another repository, or an alternate storage location.

3. First-run procedure for a new agent

The agent must perform the following steps in order.

Step 1 — Inspect the environment

Check whether Python 3 and "rclone" are available.

If either is missing, install or enable it using the workspace's permitted installation mechanism. Do not install the PAWRS package as a prerequisite.

Check whether the three required environment variables are available. Do not print their values, private keys, tokens, or other secret material to logs.

Step 2 — Obtain missing access configuration

If the required credentials or configuration are absent, stop before attempting authentication.

Ask the user or authorized workspace administrator to provide the missing values through a secure mechanism:

- Provide the service-account JSON through the workspace's secret-management facility.
- Provide the Drive scope through a protected workspace variable.
- Provide the authorized Drive root-folder ID through a protected workspace variable.

For GitHub Codespaces, the user or administrator can configure the applicable Codespaces secrets and variables in the repository or organization settings, subject to their access permissions.

The agent must not ask the user to paste private keys into public files, source code, commits, issue comments, or ordinary logs.

A document cannot independently create a missing private key, grant Google Drive permissions, or retrieve a secret that the workspace does not expose. If access configuration cannot be supplied securely, report precisely which prerequisite is missing and wait for it to be supplied. Do not switch to another Drive.

Step 3 — Validate the service-account identity

Validate the supplied JSON in memory or through a securely created temporary file.

Confirm that:

- The JSON is valid.
- Its credential type is "service_account".
- Its service-account email matches the authorized identity specified in this guide.
- The required private-key and project fields exist.
- The Drive scope and root-folder ID are present.

Never display the JSON or private key in the terminal.

Reject unexpected credential identities. Do not silently accept a different account.

Step 4 — Create a temporary authentication configuration

Use a temporary directory accessible only to the current user.

Create the service-account credential file and temporary "rclone" configuration with restrictive permissions. Use the supplied PAWRS scope and root-folder configuration to construct the "pawrs-user:" remote.

Do not write credentials into the repository, PAWRS ZIP, bootstrap guide, source files, or Git history.

Do not overwrite an unrelated existing "rclone" configuration.

Ensure temporary files are removed when the bootstrap operation finishes, including when the operation fails.

Step 5 — Verify the authorized Drive connection

Use the temporary configuration to execute a listing operation against:

"pawrs-user:"

The operation must succeed using the authorized service account and the configured Drive root.

A successful configuration-file creation is not proof of a working connection. The remote listing must actually succeed.

Do not display secret values in command output.

Step 6 — Report the result

If the remote listing succeeds, report:

- "pawrs-user=available"
- "drive_access_check=passed"
- The verified service-account identity.
- Whether the required configuration is available for subsequent workspace operations.
- Whether write access has been separately verified.

If the listing fails, report a sanitized error category and the next corrective action. Do not claim that the connection succeeded.

A successful listing verifies access to the remote. It does not, by itself, prove that uploads, checkpoint creation, or recovery work.

4. Standalone bootstrap script

The bootstrap implementation must be independent of the PAWRS package. It must not import "pawrs", "pawrs.storage", or any other PAWRS module because the ZIP has not yet been supplied.

The script must implement the following operations directly:

1. Validate the runtime and required environment variables.
2. Validate the authorized service-account identity.
3. Validate the scope and root-folder configuration.
4. Create a private temporary directory.
5. Create a temporary service-account file and "rclone" configuration.
6. Execute an actual "rclone lsf pawrs-user:" operation using that configuration.
7. Return a clear success or sanitized failure result.
8. Remove temporary credentials and configuration in a "finally" cleanup operation.

The script must not persist private keys or secrets in the repository. It must not fall back to a different Drive if the authorized remote fails.

The implementation must use the actual installed "rclone" configuration format and supported flags. It must not report success merely because the script passed syntax validation.

5. Receiving the PAWRS ZIP

Only after the bootstrap connection has been verified should the agent request or receive the PAWRS ZIP.

Once received:

1. Inspect the ZIP manifest and file list.
2. Validate the archive before extraction.
3. Extract it into the intended workspace without overwriting unrelated files.
4. Inspect the included PAWRS implementation and its documented configuration requirements.
5. Compare the package's authentication and storage implementation against this guide.
6. Reuse the authorized "pawrs-user:" access boundary.
7. Report any mismatch before changing the implementation.

The agent must not assume that the PAWRS Python package is already installed.

6. Security and recovery requirements

- Never print credentials or private keys.
- Never commit secrets.
- Never silently switch to an alternative Drive.
- Never claim that access is verified when only configuration creation succeeded.
- Never claim upload, write access, checkpoint creation, or recovery has been tested unless the relevant operation actually succeeded.
- Do not modify unrelated project files during bootstrap.
- Keep temporary authentication material separate from persistent PAWRS checkpoint data.
- Clean up temporary credentials and configuration on both success and failure.

7. Completion criteria

The standalone bootstrap is complete only when:

- The runtime prerequisites have been checked.
- The authorized service-account identity has been validated.
- The required Drive scope and root-folder configuration have been validated.
- The "pawrs-user:" remote has been accessed successfully.
- The result has been reported without exposing secrets.
- Temporary authentication files have been cleaned up.

At that point, the agent can receive the PAWRS ZIP and continue with package installation, checkpoint discovery, persistence verification, and recovery setup.

Important distinction: this guide contains the procedure for bootstrapping PAWRS Drive access before the source-code ZIP arrives. It does not manufacture credentials or permissions. Those must be supplied through the authorized secure configuration mechanism when the new workspace does not already have them.