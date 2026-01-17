# Science Fictions Podcast Episode Analyzer

This tool analyzes all episodes of the Science Fictions podcast to find instances where Stuart and Tom say "we should do an episode on that" (or similar phrases), logging what topics they mentioned for future episodes.

Created in response to Stuart and Tom's challenge to listeners on the podcast!

## How It Works

1. **Parses the RSS feed** to get all episode metadata
2. **Downloads audio files** (MP3s) for each episode
3. **Transcribes audio** using OpenAI's Whisper (runs locally, free)
4. **Analyzes transcripts** using Claude AI to semantically detect when hosts suggest future episode topics
5. **Generates a report** with episode details, timestamps, topics, and context

## Why Whisper?

While Substack does provide transcripts for podcast episodes, they are access-controlled via CDN-level authentication that cannot be bypassed with simple cookie-based auth. Whisper transcription is therefore necessary, but it has several advantages:

- **Free** - Runs entirely on your local machine
- **Accurate** - Whisper is state-of-the-art speech recognition
- **Private** - Your audio never leaves your computer
- **Reusable** - Transcripts are saved locally for future analysis

## Features

- **Semantic understanding** - Uses Claude's AI to catch all variations of "we should do an episode on X", not just keyword matching
- **Exact timestamps** - Whisper provides word-level timestamps
- **Context included** - Extracts the surrounding conversation for each mention
- **Progress saving** - Can stop and resume anytime
- **Cached transcripts** - Re-analyze with different prompts without re-transcribing

## Setup

### Prerequisites

- Python 3.8 or higher
- ffmpeg (required by Whisper for audio processing)
- An Anthropic API key (for Claude)
- A paid Science Fictions podcast subscription (for the private RSS feed)

### Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/science-fictions-analysis.git
cd science-fictions-analysis
```

2. Install ffmpeg:

**Windows:**
```bash
# Using Chocolatey
choco install ffmpeg

# Or using winget
winget install Gyan.FFmpeg

# Or download manually from: https://www.gyan.dev/ffmpeg/builds/
```

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg  # Ubuntu/Debian
sudo yum install ffmpeg  # CentOS/RHEL
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Create your config file:
```bash
cp config.example.json config.json
```

5. Edit `config.json` and add:
   - Your private RSS feed URL (from your Substack subscription)
   - Your Anthropic API key (get one at https://console.anthropic.com/)

### Configuration

The `config.json` file supports these options:

```json
{
  "rss_feed_url": "YOUR_PRIVATE_RSS_FEED_URL",
  "anthropic_api_key": "YOUR_ANTHROPIC_API_KEY",
  "whisper_model": "base",
  "downloads_dir": "downloads",
  "transcripts_dir": "transcripts",
  "results_dir": "results"
}
```

**Whisper model options:**
- `tiny` - Fastest, least accurate
- `base` - Good balance (recommended)
- `small` - More accurate, slower
- `medium` - Very accurate, quite slow
- `large` - Best accuracy, slowest

## Usage

Run the analysis:

```bash
python analyze_podcast.py
```

The script will:
1. Parse the RSS feed
2. Download all episodes
3. Transcribe them (this takes time - several hours for all episodes)
4. Analyze with Claude
5. Generate results in `results/future_episodes.csv` and `results/future_episodes.md`

### Testing First

To test with just a few episodes first, edit the script and set:
```python
TEST_MODE = True
TEST_EPISODES_COUNT = 3
```

## Output

The script generates two files in the `results/` directory:

1. **future_episodes.csv** - Spreadsheet format
2. **future_episodes.md** - Markdown table

Columns:
- Episode Number
- Episode Title
- Timestamp
- Topic Summary
- Context (30s transcript)

## Performance

Processing all episodes takes time, but it's worth it:

- **Transcription**: ~7-8 minutes per episode with the `base` model
  - All 133 episodes: ~10-15 hours total
  - The `medium` model is more accurate but takes ~15-20 hours total
- **Claude analysis**: ~30 seconds per episode (~30 minutes total)
- **Total runtime**: Plan to run overnight or over a weekend

The script saves progress after each episode, so you can stop and resume anytime. Transcripts are cached, so re-running the analysis (with different prompts or settings) only takes the Claude analysis time (~30 minutes).

## Example Results

In testing on Episode 93 ("Many analysts"), the tool found 3 instances where Stuart and Tom suggested future episodes:

| Topic | Context |
|-------|---------|
| Linguistics and football cliches | Tom discussing the Football Cliches podcast and how interesting it is linguistically |
| fMRI research and its problems | After discussing fMRI problems, Stuart suggests a whole episode on fMRI |
| Adversarial collaborations | Stuart suggesting this as a way to address ideological bias in research |

The semantic analysis successfully catches these even when they don't use the exact phrase "we should do an episode on that"!

## Privacy & Security

Your `config.json` file contains:
- Your private RSS feed URL (unique to your subscription)
- Your Anthropic API key

This file is gitignored and will not be committed to the repository. **Never share your config.json publicly** - it gives access to your paid subscription and API credits.

## Credits

Created in response to Stuart and Tom's challenge to listeners to catalog all the times they've said "we should do an episode on that."

Built with:
- [OpenAI Whisper](https://github.com/openai/whisper) - State-of-the-art speech recognition
- [Claude by Anthropic](https://www.anthropic.com/claude) - Semantic analysis and topic extraction
- Python, feedparser, and a lot of patience

Special thanks to Stuart Ritchie (who works at Anthropic!) and Tom Chivers for creating an excellent podcast about science, skepticism, and the replication crisis.
