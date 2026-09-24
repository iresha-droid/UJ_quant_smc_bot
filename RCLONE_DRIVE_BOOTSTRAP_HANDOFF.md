# Rclone + Dedicated Google Drive Bootstrap Handoff

## Purpose
This document records the validated fresh-Codespace bootstrap path for accessing the project's Dedicated Google Drive source of truth.

It is a handoff/instruction document only. It contains no credentials and does not depend on the historical installation path used by an earlier Codespace.

## Zero-start facts
A fresh Codespace using the Universal devcontainer image may not have rclone installed.

The five required Codespaces secrets are expected to be supplied manually:
- B2_APPLICATION_KEY
- B2_BUCKET
- B2_ENDPOINT_URL
- B2_KEY_ID
- RCLONE_GDRIVE_CONFIG_TOKEN

The value of RCLONE_GDRIVE_CONFIG_TOKEN must never be printed, logged, displayed, committed, or included in this file.

## Validated rclone path
1. Obtain rclone v1.75.1 from the official rclone download source.
2. Verify the downloaded archive against the official SHA256 checksum.
3. Extract the binary and ensure it has executable permission.
4. Use the existing RCLONE_GDRIVE_CONFIG_TOKEN secret as the Google Drive OAuth token.
5. Create a temporary rclone configuration with a remote named dedicated-drive.
6. The remote type is drive.
7. Put the OAuth JSON into the Drive backend's token configuration field.
8. Perform a read-only connectivity test with: rclone lsd dedicated-drive:
9. Do not upload, copy, sync, rename, delete, or otherwise modify anything in Google Drive during bootstrap validation.

## Exact validated result
- rclone version: v1.75.1
- official archive checksum: verified
- temporary configuration: succeeded
- dedicated-drive authentication: succeeded
- rclone lsd dedicated-drive: succeeded

The validated fresh-environment test used a temporary config only; it did not require or recover the unknown historical installation path of rclone.

## Important configuration detail
The OAuth credential belongs in the Google Drive backend's token field.
Do not use config_token for this Drive remote.

The existing OAuth token was validated as JSON containing the documented OAuth fields, including access_token, refresh_token, token_type, and expiry. Never expose their values.

## Official documentation
- https://rclone.org/install/
- https://rclone.org/downloads/
- https://rclone.org/drive/
- https://rclone.org/commands/rclone_config/

## Security requirements
- Never print or echo RCLONE_GDRIVE_CONFIG_TOKEN.
- Never commit the OAuth token or generated rclone config.
- Never place credentials in this handoff file.
- Prefer a temporary isolated config for initial validation.
- Keep the first Drive test read-only.
- Do not rely on the unknown historical source/path of the old Codespace's rclone binary.

## Future fresh-agent instruction
For a new zero-start Codespace, follow the official rclone documentation, use the validated v1.75.1 release path above, and reproduce the temporary dedicated-drive configuration and read-only rclone lsd dedicated-drive: test before establishing any persistent project-specific setup.

This document records the proven bootstrap contract; it does not authorize repository changes, backtests, synchronization, or changes to protected production files.