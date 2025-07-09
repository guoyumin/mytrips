#!/usr/bin/env python
"""Analyze model comparison results"""
import json
from pathlib import Path

def analyze_comparison():
    # Load the comparison report
    report_path = Path(__file__).parent / "test_data" / "model_comparison_report.json"
    with open(report_path, 'r') as f:
        data = json.load(f)
    
    results = data['results']
    summary = data['summary']
    
    print("\n" + "="*80)
    print("MODEL COMPARISON ANALYSIS")
    print("="*80 + "\n")
    
    # 1. Cost Analysis
    print("1. COST ANALYSIS (per run average)")
    print("-" * 40)
    costs = []
    for model, stats in summary.items():
        avg_cost = stats['total_cost'] / stats['successes'] if stats['successes'] > 0 else 0
        costs.append((model, avg_cost))
    
    costs.sort(key=lambda x: x[1])
    baseline = costs[0][1]
    
    for model, cost in costs:
        if cost == baseline:
            print(f"{model:<20} ${cost:.6f} (baseline)")
        else:
            ratio = cost / baseline
            print(f"{model:<20} ${cost:.6f} ({ratio:.1f}x more expensive)")
    
    # 2. Speed Analysis
    print("\n2. SPEED ANALYSIS (per run average)")
    print("-" * 40)
    speeds = []
    for model, stats in summary.items():
        avg_time = stats['total_time'] / stats['successes'] if stats['successes'] > 0 else 0
        speeds.append((model, avg_time))
    
    speeds.sort(key=lambda x: x[1])
    
    for model, time in speeds:
        print(f"{model:<20} {time:.1f}s")
    
    # 3. Quality Consistency Analysis
    print("\n3. QUALITY CONSISTENCY ANALYSIS")
    print("-" * 40)
    
    for test_name, test_results in results.items():
        print(f"\n{test_name}:")
        
        # Check trip count consistency
        trip_counts = {}
        for model, result in test_results.items():
            if result['success']:
                count = result['trips_count']
                trip_counts[model] = count
        
        unique_counts = set(trip_counts.values())
        if len(unique_counts) == 1:
            print(f"  ✓ All models agree on trip count: {list(unique_counts)[0]}")
        else:
            print(f"  ⚠ Models disagree on trip count:")
            for model, count in trip_counts.items():
                print(f"    - {model}: {count} trips")
        
        # Check destinations
        destinations = {}
        for model, result in test_results.items():
            if result['success'] and result['trips_count'] > 0:
                dests = [trip['destination'] for trip in result['trips']]
                destinations[model] = dests
        
        all_dests = set()
        for dests in destinations.values():
            all_dests.update(dests)
        
        if len(all_dests) > 0:
            print(f"  Destinations detected: {', '.join(sorted(all_dests))}")
    
    # 4. Token Usage Analysis
    print("\n4. TOKEN USAGE ANALYSIS")
    print("-" * 40)
    
    # Calculate average tokens per test
    token_usage = {}
    for test_name, test_results in results.items():
        for model, result in test_results.items():
            if result['success']:
                if model not in token_usage:
                    token_usage[model] = {'input': 0, 'output': 0, 'count': 0}
                token_usage[model]['input'] += result['input_tokens']
                token_usage[model]['output'] += result['output_tokens']
                token_usage[model]['count'] += 1
    
    print(f"{'Model':<20} {'Avg Input':<12} {'Avg Output':<12} {'Total Avg':<12}")
    print("-" * 56)
    for model in sorted(token_usage.keys()):
        usage = token_usage[model]
        avg_input = usage['input'] / usage['count']
        avg_output = usage['output'] / usage['count']
        avg_total = avg_input + avg_output
        print(f"{model:<20} {int(avg_input):<12} {int(avg_output):<12} {int(avg_total):<12}")
    
    # 5. Cost-Performance Ratio
    print("\n5. COST-PERFORMANCE RANKING")
    print("-" * 40)
    print("(Lower score is better - balances cost and speed)")
    
    scores = []
    for model, stats in summary.items():
        avg_cost = stats['total_cost'] / stats['successes'] if stats['successes'] > 0 else 0
        avg_time = stats['total_time'] / stats['successes'] if stats['successes'] > 0 else 0
        # Normalize cost (multiply by 1000 to make it comparable to seconds)
        score = (avg_cost * 1000) + avg_time
        scores.append((model, score, avg_cost, avg_time))
    
    scores.sort(key=lambda x: x[1])
    
    for model, score, cost, time in scores:
        print(f"{model:<20} Score: {score:.1f} (${cost:.4f}, {time:.1f}s)")
    
    # 5. Recommendations
    print("\n5. RECOMMENDATIONS")
    print("-" * 40)
    
    # Best for cost
    cheapest = costs[0]
    print(f"Best for cost: {cheapest[0]} at ${cheapest[1]:.6f} per run")
    
    # Best for speed
    fastest = speeds[0]
    print(f"Best for speed: {fastest[0]} at {fastest[1]:.1f}s per run")
    
    # Best balance
    best_balance = scores[0]
    print(f"Best balance: {best_balance[0]} (score: {best_balance[1]:.1f})")
    
    # Token efficiency
    print("\n6. TOKEN USAGE COMPARISON")
    print("-" * 40)
    
    # Calculate average tokens per test
    token_usage = {}
    for test_name, test_results in results.items():
        for model, result in test_results.items():
            if result['success']:
                if model not in token_usage:
                    token_usage[model] = {'input': 0, 'output': 0, 'count': 0}
                token_usage[model]['input'] += result['input_tokens']
                token_usage[model]['output'] += result['output_tokens']
                token_usage[model]['count'] += 1
    
    for model, usage in sorted(token_usage.items()):
        avg_input = usage['input'] / usage['count']
        avg_output = usage['output'] / usage['count']
        print(f"{model:<20} Avg: {avg_input:.0f} in / {avg_output:.0f} out")

if __name__ == "__main__":
    analyze_comparison()