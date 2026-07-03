#!/usr/bin/env python3
"""Scrape YouTube channels and Tumblr for facts content."""
import requests
import re
import json
import html

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def clean_text(text):
    """Clean HTML entities and whitespace."""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def scrape_youtube_channel(channel_url, max_videos=20):
    """Scrape video titles and descriptions from a YouTube channel."""
    results = []
    
    # Ensure we hit the /videos tab
    if not channel_url.endswith('/videos'):
        channel_url = channel_url.rstrip('/') + '/videos'
    
    try:
        r = requests.get(channel_url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        text = r.text
        
        print(f"  Status: {r.status_code}, Size: {len(text)} bytes")
        
        # Extract from ytInitialData JSON embedded in page
        # Pattern 1: ytInitialData = {...}
        data_match = re.search(r'window\[["\']ytInitialData["\']\]\s*=\s*({.*?});', text, re.DOTALL)
        if data_match:
            try:
                data = json.loads(data_match.group(1))
                # Navigate to video list
                contents = data
                for key in ['contents', 'twoColumnBrowseResultsRenderer', 'tabs']:
                    if isinstance(contents, dict):
                        contents = contents.get(key, contents)
                # Try to find video renderers
                vid_items = []
                tab_contents = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
                for tab in tab_contents:
                    if isinstance(tab, dict):
                        tab_vids = tab.get('tabRenderer', {}).get('content', {}).get('richGridRenderer', {}).get('contents', [])
                        vid_items.extend(tab_vids)
                print(f"  Found {len(vid_items)} video items from ytInitialData")
            except:
                print("  Failed to parse ytInitialData")
                vid_items = []
        else:
            vid_items = []
        
        # Pattern 2: regex for videoIds and titles directly
        video_ids = re.findall(r'"videoId"\s*:\s*"([A-Za-z0-9_-]{11})"', text)
        # Deduplicate preserving order
        seen = set()
        video_ids_unique = []
        for vid in video_ids:
            if vid not in seen:
                seen.add(vid)
                video_ids_unique.append(vid)
        
        video_ids = video_ids_unique
        print(f"  Found {len(video_ids)} unique videoIds via regex")
        
        # Try to get titles from simpleText
        title_matches = re.findall(r'"title"\s*:\s*\{[^}]*"simpleText"\s*:\s*"([^"]+)"', text)
        print(f"  Found {len(title_matches)} titles via simpleText")
        
        # Also try runs.text pattern
        if not title_matches:
            title_matches = re.findall(r'"runs":\[{"text":"([^"]+)"', text)
            print(f"  Found {len(title_matches)} titles via runs.text")
        
        # Pair videoIds with titles
        for i, vid in enumerate(video_ids[:max_videos]):
            title = title_matches[i] if i < len(title_matches) else f"Video {vid}"
            results.append({"id": vid, "title": clean_text(title)})
        
    except Exception as e:
        print(f"  Error scraping channel: {e}")
    
    return results

def get_video_details(video_id):
    """Get description of a single video from its watch page."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        text = r.text
        
        # Extract description from meta tags
        desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', text)
        if desc_match:
            return clean_text(desc_match.group(1))
        
        # Try JSON embedded data
        data_match = re.search(r'window\[["\']ytInitialPlayerResponse["\']\]\s*=\s*({.*?});', text, re.DOTALL)
        if data_match:
            try:
                data = json.loads(data_match.group(1))
                desc = data.get('playerOverlays', {}).get('playerOverlayRenderer', {}).get('description', '')
                if desc:
                    return clean_text(desc)
            except:
                pass
        
        return ""
    except:
        return ""

def scrape_tumblr(blog_url, max_posts=20):
    """Scrape posts from a Tumblr blog."""
    results = []
    try:
        r = requests.get(blog_url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        text = r.text
        
        # Try to find post content
        # Tumblr often uses JSON in data attributes or embedded scripts
        # Look for post titles and text
        post_texts = re.findall(r'"text":"([^"]+)"', text)
        post_titles = re.findall(r'"title":"([^"]+)"', text)
        
        # Also look for regular HTML content
        soup = None
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, 'html.parser')
            articles = soup.find_all(['article', 'div'], class_=re.compile(r'post|entry', re.I))
            for art in articles[:max_posts]:
                title_el = art.find(['h1', 'h2', 'h3', 'h4'])
                title = title_el.get_text(strip=True) if title_el else ""
                body_els = art.find_all('p')
                body = ' '.join(p.get_text(strip=True) for p in body_els)
                if title or body:
                    results.append({"title": title, "text": body[:500]})
        except:
            pass
        
        if post_texts:
            for i, txt in enumerate(post_texts[:max_posts]):
                title = post_titles[i] if i < len(post_titles) else ""
                results.append({"title": clean_text(title), "text": clean_text(txt)})
        
        print(f"  Found {len(results)} Tumblr posts")
        
    except Exception as e:
        print(f"  Error scraping Tumblr: {e}")
    
    return results


if __name__ == "__main__":
    results = {}
    
    print("=== Scraping Channel 1: UCBwMQht541r-bxpy-wPSLpw ===")
    ch1 = scrape_youtube_channel("https://www.youtube.com/channel/UCBwMQht541r-bxpy-wPSLpw")
    results["channel1"] = ch1
    
    print("\n=== Scraping Channel 2: @aleks-x2y9p ===")
    ch2 = scrape_youtube_channel("https://www.youtube.com/@aleks-x2y9p")
    results["channel2"] = ch2
    
    print("\n=== Scraping Tumblr: kort0881 ===")
    tb = scrape_tumblr("https://www.tumblr.com/blog/kort0881")
    results["tumblr"] = tb
    
    # Save raw results
    with open("raw_scrape.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== SAVED ===")
    print(f"Channel 1 videos: {len(ch1)}")
    for v in ch1[:3]:
        print(f"  {v['id']}: {v['title'][:80]}")
    print(f"Channel 2 videos: {len(ch2)}")
    for v in ch2[:3]:
        print(f"  {v['id']}: {v['title'][:80]}")
    print(f"Tumblr posts: {len(tb)}")
    for p in tb[:3]:
        print(f"  Title: {p.get('title','')[:80]}")
