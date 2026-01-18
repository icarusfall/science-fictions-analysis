#!/usr/bin/env python3
"""
Quick script to regenerate reports from existing progress.json
"""

import json
from pathlib import Path

def generate_report():
    # Load existing results
    progress_path = Path("results/progress.json")
    with open(progress_path, 'r', encoding='utf-8') as f:
        progress = json.load(f)

    findings = progress.get('results', [])
    print(f"Loaded {len(findings)} findings from progress.json")

    # Sort by episode number (handling int, str like "P25", and None)
    def sort_key(x):
        ep_num = x['episode_number']
        if ep_num is None:
            return (2, 0)  # None goes last
        elif isinstance(ep_num, str):
            # "P25" -> (1, 25) - paid episodes after regular, sorted by number
            return (1, int(ep_num[1:]))
        else:
            return (0, ep_num)  # Regular episodes first

    findings.sort(key=sort_key, reverse=True)

    results_dir = Path("results")

    # Generate CSV
    csv_path = results_dir / "future_episodes.csv"
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write("Episode Number,Episode Title,Timestamp,Topic Summary,Context\n")
        for finding in findings:
            # Escape CSV fields
            title = finding['episode_title'].replace('"', '""')
            topic = finding['topic'].replace('"', '""')
            context = finding['context'].replace('"', '""')

            f.write(f'{finding["episode_number"]},"{title}",{finding["timestamp"]},"{topic}","{context}"\n')

    print(f"CSV report saved to: {csv_path}")

    # Generate Markdown
    md_path = results_dir / "future_episodes.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Science Fictions: Future Episode Suggestions\n\n")
        f.write(f"Total instances found: {len(findings)}\n\n")
        f.write("| Episode # | Episode Title | Timestamp | Topic Summary | Context |\n")
        f.write("|-----------|---------------|-----------|---------------|----------|\n")

        for finding in findings:
            # Escape markdown special chars
            title = finding['episode_title'].replace('|', '\\|')
            topic = finding['topic'].replace('|', '\\|')
            context = finding['context'].replace('|', '\\|').replace('\n', ' ')

            f.write(f"| {finding['episode_number']} | {title} | {finding['timestamp']} | {topic} | {context} |\n")

    print(f"Markdown report saved to: {md_path}")
    print(f"\nTotal findings: {len(findings)}")

if __name__ == "__main__":
    generate_report()
