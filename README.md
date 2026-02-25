---
title: AU-Ggregates AI API
emoji: 🏗️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# AU-Ggregates AI API

AI-powered data lookup for AU-Ggregates CRM.

**Pipeline:** Mistral-7B-Instruct-v0.2 → T5-LM-Large-text2sql-spider → Supabase

**Endpoint:** `POST /api/chat/hybrid`

```json
{
  "query": "pakita fuel expenses sa project alpha"
}
```
