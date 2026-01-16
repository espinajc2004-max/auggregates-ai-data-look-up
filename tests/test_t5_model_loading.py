"""
Test T5 Model Loading and Basic SQL Generation
"""
import sys
import os
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.stage2.t5_sql_generator import T5SQLGenerator


@pytest.fixture(scope="module")
def generator():
    """Fixture to load T5 model once for all tests."""
    model_path = "./ml/models/t5_text_to_sql"
    gen = T5SQLGenerator(model_path)
    if gen.is_available():
        return gen
    else:
        pytest.skip("T5 model not available")


def test_model_loading(generator):
    """Test if T5 model loads successfully."""
    print("=" * 60)
    print("TEST 1: Model Loading")
    print("=" * 60)
    
    assert generator is not None
    assert generator.is_available()
    print("✅ Model loaded successfully!")
    print(f"   Device: {generator.device}")
    print(f"   Model path: ./ml/models/t5_text_to_sql")


def test_simple_query(generator):
    """Test simple SQL generation."""
    print("\n" + "=" * 60)
    print("TEST 2: Simple Query Generation")
    print("=" * 60)
    
    test_queries = [
        "find fuel in expenses",
        "how much cement expenses",
        "how many projects",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        
        result = generator.generate_sql(
            query=query,
            schema={},
            intent="search",
            entities={}
        )
        
        assert result is not None
        if result.success:
            print(f"✅ SQL Generated:")
            print(f"   {result.sql}")
            print(f"   Confidence: {result.confidence:.2f}")
            print(f"   Time: {result.execution_time_ms}ms")
        else:
            print(f"❌ Generation failed: {result.error}")


def test_complex_query(generator):
    """Test complex SQL generation."""
    print("\n" + "=" * 60)
    print("TEST 3: Complex Query Generation")
    print("=" * 60)
    
    query = "how much gcash payment in francis gays"
    print(f"\nQuery: {query}")
    
    result = generator.generate_sql(
        query=query,
        schema={},
        intent="analytics",
        entities={"method": "GCASH", "project": "francis gays"}
    )
    
    assert result is not None
    if result.success:
        print(f"✅ SQL Generated:")
        print(f"   {result.sql}")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Time: {result.execution_time_ms}ms")
    else:
        print(f"❌ Generation failed: {result.error}")
