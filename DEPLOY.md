# Deploy to Hugging Face Spaces

## Steps

1. **Create a new Space** at https://huggingface.co/new-space
   - SDK: **Docker**
   - Hardware: **T4 GPU** (needed for Mistral 4-bit)

2. **Push this repo** to the Space:
   ```bash
   git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
   git push hf main
   ```

3. **Set Secrets** in Space Settings → Variables and Secrets:
   | Key | Value |
   |-----|-------|
   | `SUPABASE_URL` | your supabase url |
   | `SUPABASE_KEY` | your supabase anon key |
   | `MISTRAL_MODEL` | `mistralai/Mistral-7B-Instruct-v0.2` |
   | `MISTRAL_QUANTIZATION` | `4bit` |
   | `T5_MODEL_PATH` | `gaussalgo/T5-LM-Large-text2sql-spider` |
   | `ALLOWED_TABLES` | `ai_documents,Project,conversations` |

4. **Connect frontend** to:
   ```
   https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/api
   ```

## Test endpoint
```bash
curl -X POST https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/api/chat/hybrid \
  -H "Content-Type: application/json" \
  -d '{"query": "pakita fuel expenses"}'
```
