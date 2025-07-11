#!/usr/bin/env python
"""Generate summary report for trip detection test runs"""
import json
from pathlib import Path
from datetime import datetime

def generate_test_summary():
    """Generate a summary report of all test runs"""
    test_data_dir = Path(__file__).parent / "test_data"
    
    # Try both log files
    test_log_paths = [
        test_data_dir / "optimized_test_runs.jsonl",
        test_data_dir / "test_runs.jsonl"
    ]
    
    # Find which log file exists
    test_log_path = None
    for path in test_log_paths:
        if path.exists():
            test_log_path = path
            print(f"Using log file: {path.name}")
            break
    
    if not test_log_path:
        print("No test log file found (tried test_runs.jsonl and optimized_test_runs.jsonl)")
        return
    
    # Read all test entries
    entries = []
    with open(test_log_path, 'r') as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except:
                continue
    
    if not entries:
        print("No test entries found")
        return
    
    # Generate summary
    summary = {
        "total_runs": len(entries),
        "successful_runs": sum(1 for e in entries if e.get('success', False)),
        "failed_runs": sum(1 for e in entries if not e.get('success', False)),
        "total_cost": sum(e.get('cost_usd', 0) for e in entries),
        "total_tokens": sum(e.get('total_tokens', 0) for e in entries),
        "by_provider": {},
        "timestamp": datetime.now().isoformat()
    }
    
    # Group by provider and model
    for entry in entries:
        provider = entry.get('provider', 'unknown')
        model_tier = entry.get('model_tier', 'unknown')
        key = f"{provider}_{model_tier}"
        
        if key not in summary['by_provider']:
            summary['by_provider'][key] = {
                'runs': 0,
                'successful': 0,
                'total_cost': 0,
                'total_tokens': 0,
                'total_time': 0,
                'response_times': [],
                'input_tokens': [],
                'output_tokens': [],
                'input_chars': [],
                'output_chars': []
            }
        
        stats = summary['by_provider'][key]
        stats['runs'] += 1
        if entry.get('success', False):
            stats['successful'] += 1
        stats['total_cost'] += entry.get('cost_usd', 0)
        stats['total_tokens'] += entry.get('total_tokens', 0)
        response_time = entry.get('response_time_seconds', 0)
        if response_time > 0:
            stats['total_time'] += response_time
            stats['response_times'].append(response_time)
        stats['input_tokens'].append(entry.get('input_tokens', 0))
        stats['output_tokens'].append(entry.get('output_tokens', 0))
        stats['input_chars'].append(entry.get('input_char_count', 0))
        stats['output_chars'].append(entry.get('output_char_count', 0))
    
    # Calculate averages
    for key, stats in summary['by_provider'].items():
        if stats['runs'] > 0:
            stats['avg_input_tokens'] = sum(stats['input_tokens']) / len(stats['input_tokens'])
            stats['avg_output_tokens'] = sum(stats['output_tokens']) / len(stats['output_tokens'])
            stats['avg_input_chars'] = sum(stats['input_chars']) / len(stats['input_chars'])
            stats['avg_output_chars'] = sum(stats['output_chars']) / len(stats['output_chars'])
            stats['avg_cost_per_run'] = stats['total_cost'] / stats['runs']
            stats['token_char_ratio_input'] = stats['avg_input_tokens'] / stats['avg_input_chars'] if stats['avg_input_chars'] > 0 else 0
            stats['token_char_ratio_output'] = stats['avg_output_tokens'] / stats['avg_output_chars'] if stats['avg_output_chars'] > 0 else 0
            
            # Calculate time averages
            if stats['response_times']:
                stats['avg_response_time'] = sum(stats['response_times']) / len(stats['response_times'])
                stats['min_response_time'] = min(stats['response_times'])
                stats['max_response_time'] = max(stats['response_times'])
            else:
                stats['avg_response_time'] = 0
                stats['min_response_time'] = 0
                stats['max_response_time'] = 0
            
            # Remove raw lists from final output
            del stats['input_tokens']
            del stats['output_tokens']
            del stats['input_chars']
            del stats['output_chars']
            del stats['response_times']
    
    # Save summary
    summary_path = test_log_path.parent / "test_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    print("\n=== Trip Detection Test Run Summary ===")
    print(f"Generated at: {summary['timestamp']}")
    print(f"\nTotal test runs: {summary['total_runs']}")
    print(f"Successful: {summary['successful_runs']}")
    print(f"Failed: {summary['failed_runs']}")
    print(f"Total cost: ${summary['total_cost']:.4f}")
    print(f"Total tokens: {summary['total_tokens']:,}")
    
    print("\n=== Providers Tested ===")
    providers_tested = sorted(set(key.split('_')[0] for key in summary['by_provider'].keys()))
    print(f"Providers: {', '.join(providers_tested)}")
    print(f"Total combinations: {len(summary['by_provider'])}")
    
    print("\n=== By Provider/Model ===")
    for key, stats in sorted(summary['by_provider'].items()):
        print(f"\n{key}:")
        print(f"  Runs: {stats['runs']} (Success: {stats['successful']})")
        print(f"  Total cost: ${stats['total_cost']:.4f}")
        print(f"  Avg cost/run: ${stats.get('avg_cost_per_run', 0):.4f}")
        print(f"  Avg response time: {stats.get('avg_response_time', 0):.2f}s (min: {stats.get('min_response_time', 0):.2f}s, max: {stats.get('max_response_time', 0):.2f}s)")
        print(f"  Avg input: {stats['avg_input_chars']:.0f} chars / {stats['avg_input_tokens']:.0f} tokens")
        print(f"  Avg output: {stats['avg_output_chars']:.0f} chars / {stats['avg_output_tokens']:.0f} tokens")
        print(f"  Token/char ratio: {stats['token_char_ratio_input']:.3f} (input) / {stats['token_char_ratio_output']:.3f} (output)")
    
    print(f"\n=== Cost Comparison ===")
    # Sort by cost
    cost_sorted = sorted(
        [(k, v['avg_cost_per_run']) for k, v in summary['by_provider'].items()],
        key=lambda x: x[1]
    )
    
    # Separate local (zero cost) and API providers
    local_providers = [(k, v) for k, v in cost_sorted if v == 0.0]
    api_providers = [(k, v) for k, v in cost_sorted if v > 0.0]
    
    if local_providers:
        print("Local providers (zero cost):")
        for provider, cost in local_providers:
            print(f"  {provider}: $0.0000 per run")
    
    if api_providers:
        if local_providers:
            print("\nAPI providers:")
        cheapest_api = api_providers[0]
        print(f"Cheapest API: {cheapest_api[0]} at ${cheapest_api[1]:.4f} per run")
        
        for provider, cost in api_providers[1:]:
            ratio = cost / cheapest_api[1] if cheapest_api[1] > 0 else 0
            print(f"{provider}: ${cost:.4f} per run ({ratio:.1f}x more expensive than {cheapest_api[0]})")
    
    print(f"\n=== Runtime Comparison ===")
    # Sort by average response time
    time_sorted = sorted(
        [(k, v.get('avg_response_time', 0)) for k, v in summary['by_provider'].items() if v.get('avg_response_time', 0) > 0],
        key=lambda x: x[1]
    )
    
    if time_sorted:
        fastest = time_sorted[0]
        print(f"Fastest: {fastest[0]} at {fastest[1]:.2f}s average")
        
        for provider, avg_time in time_sorted[1:]:
            ratio = avg_time / fastest[1] if fastest[1] > 0 else 0
            print(f"{provider}: {avg_time:.2f}s average ({ratio:.1f}x slower than {fastest[0]})")
    
    # Group by provider type for runtime analysis
    print(f"\n=== Runtime by Provider Type ===")
    local_times = [(k, v) for k, v in time_sorted if any(local in k for local in ['gemma3', 'deepseek', 'ollama'])]
    api_times = [(k, v) for k, v in time_sorted if not any(local in k for local in ['gemma3', 'deepseek', 'ollama'])]
    
    if local_times:
        avg_local = sum(t[1] for t in local_times) / len(local_times)
        print(f"Local providers average: {avg_local:.2f}s")
        for provider, avg_time in sorted(local_times, key=lambda x: x[1]):
            print(f"  {provider}: {avg_time:.2f}s")
    
    if api_times:
        avg_api = sum(t[1] for t in api_times) / len(api_times)
        print(f"\nAPI providers average: {avg_api:.2f}s")
        for provider, avg_time in sorted(api_times, key=lambda x: x[1]):
            print(f"  {provider}: {avg_time:.2f}s")
    
    print(f"\nSummary saved to: {summary_path}")

if __name__ == "__main__":
    generate_test_summary()