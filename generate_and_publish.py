"""Generate a thumbnail via fal.ai, upload as cover, then publish a draft.

Usage:
    python generate_and_publish.py <post_id> "<image prompt>" [--send-email]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import requests

from substack_mcp.client import SubstackClient


def generate_image_fal(prompt: str, fal_key: str) -> bytes:
    """Generate an image via fal.ai flux-schnell and return PNG bytes."""
    headers = {
        "Authorization": f"Key {fal_key}",
        "Content-Type": "application/json",
    }

    submit = requests.post(
        "https://queue.fal.run/fal-ai/flux/schnell",
        headers=headers,
        json={
            "prompt": prompt,
            "image_size": "landscape_16_9",
            "num_inference_steps": 4,
            "num_images": 1,
            "enable_safety_checker": True,
        },
        timeout=60,
    )
    submit.raise_for_status()
    job = submit.json()
    request_id = job["request_id"]
    status_url = job["status_url"]
    response_url = job["response_url"]

    deadline = time.time() + 120
    while time.time() < deadline:
        st = requests.get(status_url, headers=headers, timeout=15).json()
        if st.get("status") == "COMPLETED":
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"FAL job {request_id} timed out")

    result = requests.get(response_url, headers=headers, timeout=30).json()
    images = result.get("images") or []
    if not images:
        raise RuntimeError(f"No images returned: {result}")
    image_url = images[0]["url"]

    img = requests.get(image_url, timeout=60)
    img.raise_for_status()
    return img.content


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("post_id")
    parser.add_argument("prompt", help="Image generation prompt")
    parser.add_argument("--send-email", action="store_true")
    args = parser.parse_args()

    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        print("error: FAL_KEY env var not set", file=sys.stderr)
        return 1

    client = SubstackClient.from_env()

    print(f"[1/4] Generating image with FAL...", flush=True)
    img_bytes = generate_image_fal(args.prompt, fal_key)

    tmp = Path(tempfile.gettempdir()) / f"substack_cover_{args.post_id}.png"
    tmp.write_bytes(img_bytes)
    print(f"      Saved: {tmp} ({len(img_bytes)} bytes)", flush=True)

    print(f"[2/4] Uploading image to Substack CDN...", flush=True)
    upload = client.upload_image(str(tmp))
    cover_url = upload["url"]
    print(f"      Cover URL: {cover_url}", flush=True)

    print(f"[3/4] Setting as cover image for post {args.post_id}...", flush=True)
    client.set_cover_image(args.post_id, cover_url)

    print(f"[4/4] Publishing post {args.post_id}...", flush=True)
    result = client.publish_draft(
        post_id=args.post_id,
        send_email=args.send_email,
        share_automatically=False,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    try:
        tmp.unlink()
    except OSError:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
