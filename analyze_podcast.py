#!/usr/bin/env python3
"""
Science Fictions Podcast Episode Analyzer

Finds all instances where Stuart and Tom suggest doing a future episode on a topic.
Uses Whisper for transcription and Claude for semantic analysis.
"""

import json
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
import feedparser
import requests
import whisper
from anthropic import Anthropic

# Configuration
TEST_MODE = False  # Set to False to process all episodes
TEST_EPISODES_COUNT = 3  # Number of episodes to process in test mode


class PodcastAnalyzer:
    def __init__(self, config_path: str = "config.json"):
        """Initialize the analyzer with configuration."""
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Setup directories
        self.downloads_dir = Path(self.config['downloads_dir'])
        self.transcripts_dir = Path(self.config['transcripts_dir'])
        self.results_dir = Path(self.config['results_dir'])

        for directory in [self.downloads_dir, self.transcripts_dir, self.results_dir]:
            directory.mkdir(exist_ok=True)

        # Initialize services
        self.anthropic = Anthropic(api_key=self.config['anthropic_api_key'])
        self.whisper_model = None  # Lazy load

        # Progress tracking
        self.progress_file = self.results_dir / "progress.json"
        self.progress = self._load_progress()

    def _load_progress(self) -> Dict:
        """Load progress from file to allow resuming."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'episodes_parsed': [],
            'episodes_transcribed': [],
            'episodes_analyzed': [],
            'results': []
        }

    def _save_progress(self):
        """Save current progress to file."""
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def parse_rss_feed(self) -> List[Dict]:
        """Parse RSS feed and extract episode metadata."""
        print("Parsing RSS feed...")
        response = requests.get(self.config['rss_feed_url'])
        feed = feedparser.parse(response.content)

        episodes = []
        for entry in feed.entries:
            # Extract episode number from title
            episode_num = self._extract_episode_number(entry.title)

            # Get audio URL
            audio_url = None
            if 'enclosures' in entry and entry.enclosures:
                audio_url = entry.enclosures[0].get('href')

            episode = {
                'title': entry.title,
                'episode_number': episode_num,
                'published': entry.published,
                'audio_url': audio_url,
                'link': entry.link
            }
            episodes.append(episode)

        print(f"Found {len(episodes)} episodes")

        # Keep episodes in RSS feed order (most recent first - as provided by the feed)
        # Don't sort, as RSS feeds are already in reverse chronological order

        if TEST_MODE:
            print(f"TEST MODE: Processing only {TEST_EPISODES_COUNT} episodes")
            episodes = episodes[:TEST_EPISODES_COUNT]

        return episodes

    def _extract_episode_number(self, title: str):
        """Extract episode number from title.

        Returns:
            int for regular episodes (e.g., "Episode 25" -> 25)
            str for paid episodes (e.g., "Paid-only episode 25" -> "P25")
            None for episodes without numbers
        """
        # Check for paid-only episodes first
        match = re.search(r'Paid-only episode (\d+)', title, re.IGNORECASE)
        if match:
            return f"P{match.group(1)}"

        # Check for regular episodes
        match = re.search(r'Episode (\d+)', title, re.IGNORECASE)
        if match:
            return int(match.group(1))

        return None

    def download_episode(self, episode: Dict) -> Optional[Path]:
        """Download episode audio file if not already downloaded."""
        if not episode['audio_url']:
            print(f"  No audio URL for {episode['title']}")
            return None

        # Create filename from episode number and title
        safe_title = re.sub(r'[^\w\s-]', '', episode['title']).strip()
        safe_title = re.sub(r'[-\s]+', '-', safe_title)[:50]  # Limit length

        # Use episode number if available, otherwise just use title
        if episode['episode_number'] is not None:
            ep_num = episode['episode_number']
            # Format as 003 for integers, use as-is for strings like "P25"
            if isinstance(ep_num, int):
                filename = f"{ep_num:03d}_{safe_title}.mp3"
            else:
                filename = f"{ep_num}_{safe_title}.mp3"
        else:
            filename = f"{safe_title}.mp3"

        filepath = self.downloads_dir / filename

        if filepath.exists():
            print(f"  Audio already downloaded: {filename}")
            return filepath

        # Fallback: check for old naming scheme (paid-only episodes were previously
        # saved with just the number, e.g., "025" instead of "P25")
        if isinstance(episode['episode_number'], str) and episode['episode_number'].startswith('P'):
            old_num = int(episode['episode_number'][1:])  # Extract number from "P25"
            old_filename = f"{old_num:03d}_{safe_title}.mp3"
            old_path = self.downloads_dir / old_filename
            if old_path.exists():
                print(f"  Audio found with old naming scheme: {old_filename}")
                return old_path

        print(f"  Downloading: {filename}")
        try:
            response = requests.get(episode['audio_url'], stream=True)
            response.raise_for_status()

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"  Downloaded: {filename}")
            return filepath

        except Exception as e:
            print(f"  Error downloading {filename}: {e}")
            return None

    def transcribe_episode(self, episode: Dict, audio_path: Path) -> Optional[Dict]:
        """Transcribe episode using Whisper."""
        # Check if transcript already exists
        # Create safe filename - use episode number if available, otherwise use sanitized title
        if episode['episode_number'] is not None:
            ep_num = episode['episode_number']
            # Format as 003 for integers, use as-is for strings like "P25"
            if isinstance(ep_num, int):
                transcript_filename = f"{ep_num:03d}_transcript.json"
            else:
                transcript_filename = f"{ep_num}_transcript.json"
        else:
            # Use sanitized title for episodes without numbers
            safe_title = re.sub(r'[^\w\s-]', '', episode['title']).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)[:50]
            transcript_filename = f"{safe_title}_transcript.json"

        transcript_path = self.transcripts_dir / transcript_filename

        # Check for transcript with new naming scheme
        if transcript_path.exists():
            print(f"  Transcript already exists: {transcript_filename}")
            with open(transcript_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Fallback: check for old naming scheme (paid-only episodes were previously
        # saved with just the number, e.g., "025" instead of "P25")
        if isinstance(episode['episode_number'], str) and episode['episode_number'].startswith('P'):
            old_num = int(episode['episode_number'][1:])  # Extract number from "P25"
            old_filename = f"{old_num:03d}_transcript.json"
            old_path = self.transcripts_dir / old_filename
            if old_path.exists():
                print(f"  Found transcript with old naming scheme: {old_filename}")
                with open(old_path, 'r', encoding='utf-8') as f:
                    return json.load(f)

        # Lazy load Whisper model
        if self.whisper_model is None:
            print(f"Loading Whisper model '{self.config['whisper_model']}'...")
            self.whisper_model = whisper.load_model(self.config['whisper_model'])

        print(f"  Transcribing: {audio_path.name} (this may take a while...)")
        try:
            result = self.whisper_model.transcribe(
                str(audio_path),
                verbose=False,
                word_timestamps=True
            )

            # Save transcript
            with open(transcript_path, 'w') as f:
                json.dump(result, f, indent=2)

            print(f"  Transcription complete: {transcript_filename}")
            return result

        except Exception as e:
            print(f"  Error transcribing {audio_path.name}: {e}")
            return None

    def analyze_with_claude(self, episode: Dict, transcript: Dict) -> List[Dict]:
        """Use Claude to find instances of future episode suggestions."""
        print(f"  Analyzing with Claude...")

        # Get full text
        full_text = transcript['text']

        # Prepare prompt for Claude
        prompt = f"""You are analyzing a transcript from the Science Fictions podcast hosted by Stuart Ritchie and Tom Chivers.

Your task is to identify ALL instances where the hosts suggest they should do a future episode on a specific topic. This includes any phrasing like:
- "we should do an episode on X"
- "that would make a great episode"
- "we need to cover X"
- "remind me to talk about X"
- "X deserves its own episode"
- "we should discuss X in a future episode"
- Or any other variation where they're proposing a future episode topic

For EACH instance you find, provide:
1. The approximate timestamp or location in the transcript
2. A brief summary of what topic they want to cover
3. The exact quote (or close paraphrase) of what they said

Here's the transcript:

{full_text}

Please respond in JSON format with an array of findings:
[
  {{
    "topic": "brief description of the topic",
    "quote": "the actual words they said",
    "context": "a sentence or two of context around the quote"
  }}
]

If you find no instances, return an empty array: []"""

        try:
            message = self.anthropic.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse Claude's response
            response_text = message.content[0].text

            # Extract JSON from response
            # Claude might wrap it in markdown code blocks
            json_match = re.search(r'```json\s*(\[.*?\])\s*```', response_text, re.DOTALL)
            if json_match:
                findings_json = json_match.group(1)
            else:
                # Try to find JSON array directly
                json_match = re.search(r'(\[.*\])', response_text, re.DOTALL)
                if json_match:
                    findings_json = json_match.group(1)
                else:
                    findings_json = "[]"

            findings = json.loads(findings_json)

            # Enhance findings with episode metadata and timestamps
            enhanced_findings = []
            for finding in findings:
                # Try to find the quote in the transcript to get timestamp
                timestamp = self._find_timestamp(transcript, finding.get('quote', ''))

                enhanced_findings.append({
                    'episode_number': episode['episode_number'],
                    'episode_title': episode['title'],
                    'timestamp': timestamp,
                    'topic': finding.get('topic', 'Unknown'),
                    'quote': finding.get('quote', ''),
                    'context': finding.get('context', '')
                })

            print(f"  Found {len(enhanced_findings)} instance(s)")
            return enhanced_findings

        except Exception as e:
            print(f"  Error analyzing with Claude: {e}")
            return []

    def _find_timestamp(self, transcript: Dict, quote: str) -> str:
        """Find timestamp for a quote in the transcript."""
        if not quote or 'segments' not in transcript:
            return "Unknown"

        # Search through segments to find matching text
        quote_lower = quote.lower()[:50]  # First 50 chars for matching

        for segment in transcript['segments']:
            segment_text = segment['text'].lower()
            if quote_lower in segment_text or segment_text in quote_lower:
                # Found it! Return timestamp
                start_time = segment['start']
                return self._format_timestamp(start_time)

        return "Unknown"

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

    def process_episodes(self, episodes: List[Dict]):
        """Main processing loop for all episodes."""
        all_findings = []

        for i, episode in enumerate(episodes, 1):
            print(f"\n[{i}/{len(episodes)}] Processing: {episode['title']}")

            # Download
            audio_path = self.download_episode(episode)
            if not audio_path:
                continue

            # Transcribe
            transcript = self.transcribe_episode(episode, audio_path)
            if not transcript:
                continue

            # Analyze
            findings = self.analyze_with_claude(episode, transcript)
            all_findings.extend(findings)

            # Save progress
            self.progress['results'] = all_findings
            self._save_progress()

        return all_findings

    def generate_report(self, findings: List[Dict]):
        """Generate output report in CSV and Markdown formats."""
        print("\nGenerating reports...")

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

        # Generate CSV
        csv_path = self.results_dir / "future_episodes.csv"
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
        md_path = self.results_dir / "future_episodes.md"
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


def main():
    """Main entry point."""
    print("Science Fictions Podcast Episode Analyzer")
    print("=" * 50)

    # Check for config file
    if not Path("config.json").exists():
        print("\nERROR: config.json not found!")
        print("Please copy config.example.json to config.json and fill in your details.")
        return

    # Run analyzer
    analyzer = PodcastAnalyzer()

    # Parse feed
    episodes = analyzer.parse_rss_feed()

    # Process episodes
    findings = analyzer.process_episodes(episodes)

    # Generate report
    analyzer.generate_report(findings)

    print("\n" + "=" * 50)
    print("Analysis complete!")


if __name__ == "__main__":
    main()
