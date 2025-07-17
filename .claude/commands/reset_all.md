---
allowed-tools: Bash
description: Reset all emails from database
---

Reset all emails and email contents from database.

!curl -X POST http://localhost:8000/api/emails/reset-all -H "Content-Type: application/json"