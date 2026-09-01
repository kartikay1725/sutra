# SUTRA Backup & Restore Operational Manual

## Executive Overview
This document specifies automated backup and verified restore workflows for SUTRA's PostgreSQL 17 database and bare Git repositories.

---

## 1. Database Backup & Restore

### Backup Execution
```powershell
./scripts/db_backup.ps1 -BackupPath "./backups/sutra_backup.sql"
```

### Restore Execution & Verification
```powershell
./scripts/db_restore.ps1 -BackupPath "./backups/sutra_backup.sql"
python scripts/production_db_audit.py
```

---

## 2. Git Repository Storage Backup & Restore

### Storage Directory Tarball
```bash
tar -czvf sutra_git_storage_backup.tar.gz ./data/repositories
```

### Storage Directory Restore
```bash
tar -xzvf sutra_git_storage_backup.tar.gz -C /var/sutra/data
```
