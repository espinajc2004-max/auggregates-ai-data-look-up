# LoRA Advanced Query Understanding - Design Document

## Architecture Overview

```
User Query
    ↓
┌─────────────────────────────────────┐
│   Query Preprocessing               │
│   - Normalize text                  │
│   - Detect language (EN/TL)         │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│   Parallel Processing               │
│                                     │
│   ┌──────────────┐  ┌────────────┐ │
│   │ Pattern      │  │ LoRA       │ │
│   │ Matching     │  │ Model      │ │
│   │ (Fast)       │  │ (Smart)    │ │
│   └──────────────┘  └────────────┘ │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│   Confidence-Based Selection        │
│   - LoRA confidence > 0.7: Use LoRA │
│   - Else: Use pattern matching      │
│   - Log both for comparison         │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│   Query Execution                   │
│   - Execute on database             │
│   - Return results                  │
└─────────────────────────────────────┘
```

## Component Design

### 1. LoRA Model Service (`app/services/lora_query_service.py`)

```python
class LoRAQueryService:
    """
    LoRA-based query understanding service.
    Handles typo correction, complex queries, and natural language variations.
    """
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.confidence_threshold = 0.7
        
    def load_model(self, model_path: str):
        """Load LoRA fine-tuned model"""
        
    def understand_query(self, query: str) -> QueryUnderstanding:
        """
        Analyze query using LoRA model.
        
        Returns:
            QueryUnderstanding with:
            - corrected_query: Typo-corrected version
            - intent: search/count/list/sum
            - entities: Extracted entities
            - boolean_logic: Parsed boolean expression
            - confidence: Model confidence (0-1)
        """
        
    def correct_typos(self, query: str) -> Tuple[str, float]:
        """Correct typos in query"""
        
    def parse_boolean_logic(self, query: str) -> BooleanExpression:
        """Parse complex boolean expressions"""
        
    def disambiguate_implicit(self, query: str, context: Dict) -> str:
        """Disambiguate implicit queries using context"""
```

### 2. Hybrid Query Processor (`app/services/hybrid_query_processor.py`)

```python
class HybridQueryProcessor:
    """
    Combines pattern matching and LoRA for best results.
    """
    
    def __init__(self):
        self.pattern_detector = MultiQueryDetector()
        self.lora_service = LoRAQueryService()
        
    async def process_query(self, query: str, context: Dict = None) -> ProcessedQuery:
        """
        Process query using both pattern matching and LoRA.
        
        Flow:
        1. Run pattern matching (fast)
        2. Run LoRA in parallel (smart)
        3. Compare confidence scores
        4. Select best result
        5. Log both for A/B testing
        """
        
        # Run both in parallel
        pattern_result = self.pattern_detector.detect(query)
        lora_result = await self.lora_service.understand_query(query)
        
        # Select based on confidence
        if lora_result.confidence > self.confidence_threshold:
            selected = lora_result
            method = "lora"
        else:
            selected = pattern_result
            method = "pattern"
            
        # Log for comparison
        self._log_comparison(query, pattern_result, lora_result, selected, method)
        
        return selected
```

### 3. Training Data Generator (`ml/training/lora_query_dataset_generator.py`)

```python
class QueryDatasetGenerator:
    """
    Generate training data for LoRA model.
    """
    
    def generate_typo_examples(self, base_queries: List[str]) -> List[Dict]:
        """Generate queries with common typos"""
        
    def generate_complex_boolean(self) -> List[Dict]:
        """Generate complex boolean query examples"""
        
    def generate_natural_variations(self, base_queries: List[str]) -> List[Dict]:
        """Generate natural language variations"""
        
    def generate_implicit_queries(self) -> List[Dict]:
        """Generate implicit query examples"""
        
    def generate_contextual_queries(self) -> List[Dict]:
        """Generate contextual query examples"""
```

## Data Models

### QueryUnderstanding
```python
@dataclass
class QueryUnderstanding:
    original_query: str
    corrected_query: str
    intent: str  # search, count, list, sum
    entities: List[str]  # Extracted search terms
    boolean_logic: Optional[BooleanExpression]
    confidence: float  # 0-1
    method: str  # "pattern" or "lora"
    corrections: List[Tuple[str, str]]  # [(original, corrected)]
```

### BooleanExpression
```python
@dataclass
class BooleanExpression:
    operator: str  # AND, OR, NOT
    operands: List[Union[str, BooleanExpression]]
    
    def to_sql(self) -> str:
        """Convert to SQL WHERE clause"""
        
    def to_multi_query(self) -> List[str]:
        """Convert to list of sub-queries"""
```

## Training Pipeline

### 1. Dataset Generation
```bash
# Generate 10,000 training examples
python ml/training/generate_lora_query_dataset.py \
    --output ml/training/lora_query_dataset.jsonl \
    --num-examples 10000 \
    --include-typos \
    --include-complex \
    --include-variations
```

### 2. Model Training
```bash
# Train LoRA model
python ml/training/train_lora_query_model.py \
    --dataset ml/training/lora_query_dataset.jsonl \
    --base-model gpt2 \
    --lora-rank 16 \
    --epochs 3 \
    --output ml/models/lora_query_v1
```

### 3. Model Evaluation
```bash
# Evaluate on test set
python ml/training/evaluate_lora_model.py \
    --model ml/models/lora_query_v1 \
    --test-data ml/training/lora_query_test.jsonl \
    --metrics accuracy,f1,precision,recall
```

## Integration Points

### 1. Chat V2 Endpoint
```python
# In app/api/routes/chat_v2.py

async def handle_new_query(request: ChatRequest, user_id: str, role: str = None):
    # NEW: Use hybrid processor instead of direct pattern matching
    processor = HybridQueryProcessor()
    
    understanding = await processor.process_query(
        query=request.query,
        context=get_conversation_context(user_id)
    )
    
    # Use understanding.corrected_query for search
    search_term = understanding.corrected_query
    
    # Handle complex boolean logic
    if understanding.boolean_logic:
        results = execute_boolean_query(understanding.boolean_logic, role)
    else:
        results = UniversalHandler.search(search_term, filters={}, role=role)
```

### 2. Monitoring Dashboard
```python
# Track LoRA vs Pattern performance
class QueryMethodMetrics:
    def log_query(self, query: str, method: str, success: bool, latency: float):
        """Log query processing metrics"""
        
    def get_comparison_stats(self) -> Dict:
        """
        Returns:
        {
            "lora": {"accuracy": 0.92, "avg_latency": 150ms},
            "pattern": {"accuracy": 0.85, "avg_latency": 5ms},
            "lora_usage_rate": 0.65
        }
        """
```

## Training Data Format

### Example 1: Typo Correction
```json
{
    "input": "show me gcsh or fule",
    "output": {
        "corrected_query": "show me gcash or fuel",
        "intent": "search",
        "entities": ["gcash", "fuel"],
        "corrections": [["gcsh", "gcash"], ["fule", "fuel"]],
        "confidence": 0.95
    }
}
```

### Example 2: Complex Boolean
```json
{
    "input": "gcash or (fuel and cement)",
    "output": {
        "corrected_query": "gcash or (fuel and cement)",
        "intent": "search",
        "boolean_logic": {
            "operator": "OR",
            "operands": [
                "gcash",
                {
                    "operator": "AND",
                    "operands": ["fuel", "cement"]
                }
            ]
        },
        "confidence": 0.88
    }
}
```

### Example 3: Implicit Query
```json
{
    "input": "show me payments",
    "output": {
        "corrected_query": "show me payment_method",
        "intent": "search",
        "entities": ["payment_method"],
        "disambiguation": {
            "original": "payments",
            "options": ["payment_method", "payment_type"],
            "selected": "payment_method",
            "reason": "Most common usage in context"
        },
        "confidence": 0.72
    }
}
```

## Performance Optimization

### 1. Model Quantization
```python
# Reduce model size by 4x with minimal accuracy loss
from transformers import AutoModelForCausalLM
import torch

model = AutoModelForCausalLM.from_pretrained("ml/models/lora_query_v1")
quantized_model = torch.quantization.quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)
```

### 2. Caching
```python
# Cache LoRA predictions for common queries
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_lora_prediction(query: str) -> QueryUnderstanding:
    return lora_service.understand_query(query)
```

### 3. Async Processing
```python
# Process LoRA in background for non-critical queries
async def process_query_async(query: str):
    # Return pattern matching result immediately
    pattern_result = pattern_detector.detect(query)
    
    # Process LoRA in background
    asyncio.create_task(lora_service.understand_query(query))
    
    return pattern_result
```

## Testing Strategy

### 1. Unit Tests
- Test typo correction accuracy
- Test boolean logic parsing
- Test confidence scoring
- Test fallback mechanism

### 2. Integration Tests
- Test hybrid processor selection logic
- Test end-to-end query flow
- Test performance under load
- Test graceful degradation

### 3. A/B Testing
- 50% users get LoRA
- 50% users get pattern matching
- Compare success rates
- Measure user satisfaction

## Rollout Plan

### Phase 1: Shadow Mode (Week 1)
- LoRA runs in parallel but doesn't affect results
- Log predictions for analysis
- Compare with pattern matching

### Phase 2: Canary Release (Week 2)
- 10% of users get LoRA
- Monitor error rates and latency
- Collect user feedback

### Phase 3: Gradual Rollout (Week 3-4)
- Increase to 25%, 50%, 75%, 100%
- Monitor metrics at each stage
- Rollback if issues detected

### Phase 4: Full Production (Week 5+)
- 100% users on LoRA
- Pattern matching as fallback
- Continuous monitoring

## Monitoring and Alerts

### Key Metrics
1. LoRA confidence distribution
2. Pattern vs LoRA selection rate
3. Query success rate by method
4. Average latency by method
5. Typo correction accuracy
6. User satisfaction scores

### Alerts
- LoRA confidence < 0.5 for > 20% of queries
- LoRA latency > 500ms
- Error rate > 5%
- Model serving failures

## Future Enhancements

### Phase 5: Advanced Features
1. Multi-turn conversation understanding
2. Entity linking to database schema
3. Query suggestion and autocomplete
4. Personalized query understanding
5. Real-time learning from user feedback

### Phase 6: Multi-Language Support
1. Extend beyond English/Tagalog
2. Cross-language query understanding
3. Translation-aware search

## Success Criteria

### Must Have
- ✅ Typo correction accuracy > 85%
- ✅ Complex query support > 80%
- ✅ Inference latency < 200ms
- ✅ No degradation in simple query performance

### Nice to Have
- Implicit query disambiguation > 75%
- Contextual understanding > 70%
- User satisfaction increase > 20%
- A/B test shows LoRA outperforms pattern matching

## Risks and Mitigations

### Technical Risks
1. **Model size too large**: Use quantization and pruning
2. **Inference too slow**: Use caching and async processing
3. **Accuracy not good enough**: Collect more training data

### Business Risks
1. **User confusion from corrections**: Show corrections clearly
2. **Increased infrastructure cost**: Optimize model size
3. **Maintenance burden**: Automate retraining pipeline

## Conclusion

This LoRA implementation will significantly enhance query understanding while maintaining backward compatibility with the existing pattern-based system. The hybrid approach ensures we get the best of both worlds: speed from pattern matching and intelligence from LoRA.
