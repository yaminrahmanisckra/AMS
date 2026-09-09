# Phase 1.5 — Private uploads (FILE-01 / FILE-02)

Sensitive files leave `public_html` and are served only through authenticated (or admission) routes.

## 1. Create private directory (SSH / Terminal)

```bash
mkdir -p ~/ams_private_uploads/{user_photos,user_signatures,admission_exam}
chmod 700 ~/ams_private_uploads
```

## 2. Copy existing files (do not delete yet)

From the app root (e.g. `~/public_html/ams`):

```bash
SRC=~/public_html/ams/static/uploads
DST=~/ams_private_uploads

# Copy only if the source folder exists
[ -d "$SRC/user_photos" ] && rsync -a "$SRC/user_photos/" "$DST/user_photos/"
[ -d "$SRC/user_signatures" ] && rsync -a "$SRC/user_signatures/" "$DST/user_signatures/"
[ -d "$SRC/admission_exam" ] && rsync -a "$SRC/admission_exam/" "$DST/admission_exam/"
```

Dual-read keeps working for old DB paths like `/static/uploads/user_photos/…` after this copy.

## 3. cPanel environment

Python App → Environment variables:

| Name | Value |
|------|--------|
| `PRIVATE_UPLOAD_DIR` | `/home/kulawams/ams_private_uploads` |

(Adjust home username if different.)

## 4. Deploy code + Restart

Upload the updated app files, then **Restart** the Python App.

Confirm:

- Profile photo / signature still load when logged in (`/media/users/<id>/photo` etc.)
- Direct URL `/static/uploads/user_photos/…` returns **404** (`.htaccess`)
- New profile uploads appear under `~/ams_private_uploads/user_photos/`

## 5. Optional later cleanup

After a few days of verified serving:

1. Optional DB rewrite (basename-preserving dual-read is enough until then):
   ```bash
   cd ~/public_html/ams && python scripts/security/rewrite_private_upload_paths.py --dry-run
   ```
2. Only then remove copies under `static/uploads/user_photos`, `user_signatures`, `admission_exam` (keep a backup zip first).
