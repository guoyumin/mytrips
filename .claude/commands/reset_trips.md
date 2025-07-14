---
allowed-tools: Bash
description: Reset trip detection status for all emails and clear all trips
---

Reset trip detection status and clear all trips from the database:

!curl -X POST http://localhost:8000/api/trips/detection/reset -H "Content-Type: application/json"