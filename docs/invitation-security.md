# Invitation security hardening

Project invitation handling now enforces stricter token safety and lifecycle controls.

## Security controls

* Invite tokens are stored as SHA-256 hashes at rest.
* Acceptance enforces bounded TTL via `EDMP_INVITE_TTL_MINUTES` (clamped safety range).
* Acceptance attempts are bounded via `EDMP_INVITE_MAX_ATTEMPTS`; overflow revokes the invite.

## New lifecycle APIs

* `POST /api/v1/projects/invitations/{invitation_id}/revoke`
  * immediately revokes non-accepted invites.
* `POST /api/v1/projects/invitations/{invitation_id}/resend`
  * rotates token, resets attempt counters, renews expiry, and issues a fresh one-time link.

## Acceptance behavior

* Revoked invites are rejected with `invitation_revoked`.
* Expired invites are rejected with `invitation_expired`.
* Attempt overflow is rejected with `invitation_attempt_limit_exceeded`.
