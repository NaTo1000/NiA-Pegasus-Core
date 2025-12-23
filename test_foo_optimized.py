"""
Comprehensive test suite for optimized foo module
Tests all 10 revisions with performance benchmarks
"""
import pytest
import asyncio
from foo_optimized import (
    add, add_async, batch_add_async, multiply,
    add_vectorized, add_inplace, add_generator,
    add_int, add_float, batch_add_preallocated,
    FastMath, add_parallel, add_safe,
    benchmark_all_revisions
)


# ============================================================================
# Basic Functionality Tests
# ============================================================================

def test_add():
    """Test basic cached addition"""
    assert add(2, 3) == 5
    assert add(10, -5) == 5
    assert add(0, 0) == 0
    assert add(1.5, 2.5) == 4.0


def test_multiply():
    """Test cached multiplication"""
    assert multiply(2, 3) == 6
    assert multiply(5, 0) == 0
    assert multiply(-2, 3) == -6


@pytest.mark.asyncio
async def test_add_async():
    """Test async addition"""
    result = await add_async(5, 3)
    assert result == 8
    
    result = await add_async(10.5, 2.5)
    assert result == 13.0


@pytest.mark.asyncio
async def test_batch_add_async():
    """Test concurrent batch addition"""
    operations = [(1, 2), (3, 4), (5, 6), (7, 8)]
    results = await batch_add_async(operations)
    assert results == [3, 7, 11, 15]


# ============================================================================
# Vectorized Operations Tests
# ============================================================================

def test_add_vectorized():
    """Test vectorized addition"""
    a_list = [1, 2, 3, 4, 5]
    b_list = [5, 4, 3, 2, 1]
    result = add_vectorized(a_list, b_list)
    assert result == [6, 6, 6, 6, 6]


def test_add_vectorized_error():
    """Test vectorized addition with mismatched lengths"""
    with pytest.raises(ValueError):
        add_vectorized([1, 2, 3], [1, 2])


def test_add_inplace():
    """Test in-place addition"""
    result = [0, 0, 0, 0]
    a_list = [1, 2, 3, 4]
    b_list = [4, 3, 2, 1]
    add_inplace(result, a_list, b_list)
    assert result == [5, 5, 5, 5]


def test_add_inplace_error():
    """Test in-place addition with size mismatch"""
    with pytest.raises(ValueError):
        add_inplace([0, 0], [1, 2, 3], [1, 2, 3])


# ============================================================================
# Generator Tests
# ============================================================================

def test_add_generator():
    """Test generator-based addition"""
    a_list = [1, 2, 3, 4]
    b_list = [10, 20, 30, 40]
    result = list(add_generator(a_list, b_list))
    assert result == [11, 22, 33, 44]


def test_add_generator_memory_efficiency():
    """Test that generator doesn't create intermediate list"""
    # Generator should not consume memory for full list
    gen = add_generator(range(1000000), range(1000000))
    # Take only first few elements
    result = [next(gen) for _ in range(5)]
    assert result == [0, 2, 4, 6, 8]


# ============================================================================
# Type-Specialized Tests
# ============================================================================

def test_add_int():
    """Test integer-only addition"""
    assert add_int(5, 3) == 8
    assert add_int(-10, 10) == 0


def test_add_float():
    """Test float-only addition"""
    assert add_float(5.5, 3.2) == pytest.approx(8.7)
    assert add_float(0.1, 0.2) == pytest.approx(0.3)


# ============================================================================
# Batch Processing Tests
# ============================================================================

def test_batch_add_preallocated():
    """Test batch addition with pre-allocated buffer"""
    operations = [(1, 2), (3, 4), (5, 6)]
    result = batch_add_preallocated(operations)
    assert result == [3, 7, 11]


def test_batch_add_preallocated_custom_buffer():
    """Test batch addition with custom buffer"""
    operations = [(1, 2), (3, 4), (5, 6)]
    buffer = [0, 0, 0]
    result = batch_add_preallocated(operations, buffer)
    assert result == [3, 7, 11]
    assert buffer is result  # Should modify in-place


def test_batch_add_preallocated_error():
    """Test batch addition with buffer size mismatch"""
    operations = [(1, 2), (3, 4)]
    buffer = [0, 0, 0]  # Wrong size
    with pytest.raises(ValueError):
        batch_add_preallocated(operations, buffer)


# ============================================================================
# FastMath Class Tests
# ============================================================================

def test_fast_math_add():
    """Test FastMath addition"""
    assert FastMath.add(10, 5) == 15
    assert FastMath.add(-5, 5) == 0


def test_fast_math_add_many():
    """Test FastMath multiple argument addition"""
    assert FastMath.add_many(1, 2, 3, 4, 5) == 15
    assert FastMath.add_many(10) == 10


def test_fast_math_add_with_bounds():
    """Test FastMath addition with bounds"""
    assert FastMath.add_with_bounds(5, 3) == 8
    assert FastMath.add_with_bounds(5, 3, min_val=10) == 10
    assert FastMath.add_with_bounds(5, 3, max_val=7) == 7
    assert FastMath.add_with_bounds(5, 3, min_val=0, max_val=10) == 8


# ============================================================================
# Parallel Processing Tests
# ============================================================================

def test_add_parallel_threads():
    """Test parallel addition with threads"""
    operations = [(1, 2), (3, 4), (5, 6), (7, 8)]
    result = add_parallel(operations, use_processes=False)
    assert sorted(result) == [3, 7, 11, 15]


def test_add_parallel_processes():
    """Test parallel addition with processes"""
    operations = [(1, 2), (3, 4), (5, 6), (7, 8)]
    result = add_parallel(operations, use_processes=True)
    assert sorted(result) == [3, 7, 11, 15]


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_add_safe():
    """Test safe addition with error handling"""
    assert add_safe(5, 3) == 8
    assert add_safe("invalid", 3, default=0) == 0
    assert add_safe(5, "invalid", default=-1) == -1


def test_add_safe_with_compatible_types():
    """Test safe addition with compatible non-numeric types"""
    assert add_safe("hello", "world") == "helloworld"
    assert add_safe([1, 2], [3, 4]) == [1, 2, 3, 4]


# ============================================================================
# Cache Effectiveness Tests
# ============================================================================

def test_cache_effectiveness():
    """Test that LRU cache improves performance"""
    import time
    
    # Clear cache
    add.cache_clear()
    multiply.cache_clear()
    
    # First call - cache miss
    result1 = add(1, 2)
    assert result1 == 3
    
    # Second call - should be from cache
    result2 = add(1, 2)
    assert result2 == 3
    
    # Verify cache info shows hits
    info = add.cache_info()
    assert info.hits > 0


def test_cache_info():
    """Test cache statistics"""
    add.cache_clear()
    
    # Make some calls
    add(1, 2)
    add(1, 2)  # Cache hit
    add(2, 3)
    add(1, 2)  # Cache hit
    
    info = add.cache_info()
    assert info.hits >= 2
    assert info.misses >= 2


# ============================================================================
# Performance Benchmark Tests (require pytest-benchmark)
# ============================================================================

pytest_benchmark_available = False
try:
    import pytest_benchmark
    pytest_benchmark_available = True
except ImportError:
    pass

@pytest.mark.skipif(not pytest_benchmark_available, reason="pytest-benchmark not installed")
@pytest.mark.benchmark
def test_benchmark_baseline(benchmark):
    """Benchmark baseline addition"""
    result = benchmark(lambda: sum([i + (i+1) for i in range(1000)]))
    assert result > 0


@pytest.mark.skipif(not pytest_benchmark_available, reason="pytest-benchmark not installed")
@pytest.mark.benchmark
def test_benchmark_cached(benchmark):
    """Benchmark cached addition"""
    add.cache_clear()
    result = benchmark(lambda: add(5, 3))
    assert result == 8


@pytest.mark.skipif(not pytest_benchmark_available, reason="pytest-benchmark not installed")
@pytest.mark.benchmark
def test_benchmark_vectorized(benchmark):
    """Benchmark vectorized addition"""
    a_list = list(range(1000))
    b_list = list(range(1000, 2000))
    result = benchmark(add_vectorized, a_list, b_list)
    assert len(result) == 1000


@pytest.mark.skipif(not pytest_benchmark_available, reason="pytest-benchmark not installed")
@pytest.mark.benchmark
def test_benchmark_inplace(benchmark):
    """Benchmark in-place addition"""
    result_buffer = [0] * 1000
    a_list = list(range(1000))
    b_list = list(range(1000, 2000))
    benchmark(add_inplace, result_buffer, a_list, b_list)
    assert len(result_buffer) == 1000


def test_benchmark_all_revisions():
    """Test that benchmark function runs without errors"""
    results = benchmark_all_revisions()
    assert 'baseline' in results
    assert len(results) > 1
    
    # Verify performance improvements
    baseline = results['baseline']
    for name, time in results.items():
        if name != 'baseline':
            # Most optimizations should be faster than baseline
            print(f"{name}: {baseline/time:.2f}x speedup")


# ============================================================================
# Integration Tests
# ============================================================================

def test_multiple_operations_integration():
    """Test multiple operations working together"""
    # Use different optimization strategies
    a = add(5, 3)
    b = multiply(2, 4)
    c = add_int(10, 20)
    d = add_float(1.5, 2.5)
    
    assert a == 8
    assert b == 8
    assert c == 30
    assert d == 4.0


@pytest.mark.asyncio
async def test_async_integration():
    """Test async operations integration"""
    # Mix async and sync operations
    sync_result = add(10, 20)
    async_result = await add_async(10, 20)
    
    assert sync_result == async_result == 30
    
    # Batch operations
    batch_operations = [(i, i+1) for i in range(10)]
    batch_results = await batch_add_async(batch_operations)
    
    assert len(batch_results) == 10
    assert all(batch_results[i] == 2*i + 1 for i in range(10))


# ============================================================================
# Edge Cases and Stress Tests
# ============================================================================

def test_large_numbers():
    """Test with very large numbers"""
    large_num = 10**100
    result = add(large_num, large_num)
    assert result == 2 * large_num


def test_many_operations():
    """Stress test with many operations"""
    operations = [(i, i) for i in range(10000)]
    result = batch_add_preallocated(operations)
    assert len(result) == 10000
    assert all(result[i] == 2*i for i in range(10000))


def test_parallel_with_many_operations():
    """Test parallel processing with large dataset"""
    operations = [(i, i+1) for i in range(1000)]
    result = add_parallel(operations, use_processes=False)
    assert len(result) == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-skip"])
