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

**Pipeline:** Phi-3-mini-4k-instruct → T5-text2sql → Supabase

**Endpoint:** `POST /api/chat/hybrid`

```json
{
  "query": "pakita fuel expenses sa project alpha"
}
```
