#!/usr/bin/env python3
"""
Analyze Single Line Diagram images using AI Vision API.
This is Step 2 of the OCR pipeline for electrical schematics.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: google-genai library is not installed.")
    print("Please install it using: pip install google-genai")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


# The analysis prompt for the AI
ANALYSIS_PROMPT = """You are an expert Electrical Engineer analyzing a Single Line Diagram (SLD).

Your Goal:

Extract accurate cable specifications for every circuit column AND classify the direction of electricity flow.

Visual Guide:

Locate the Circuit Column: Identified by the number at the bottom (e.g., 1, 2, 3).

Locate the Terminal Block: This is the horizontal row labeled "X..." (e.g., X03, X101) located just above the bottom text descriptions.

Locate the Cable Size: A number like "1,5" or "2,5" usually found below the terminals.

Locate the Description: Read the text at the very bottom of the column to understand the circuit's function.

Classification Rules for "connection_type":

Analyze the text description to determine the direction of power:

SUPPLY: Text contains "Zuleitung", "Einspeisung", "Supply", "Incoming" (Power entering the panel).

INTERNAL: Text contains "Überspannungsschutz", "SPD", "Potentialausgleich", "Surge" (Wiring that stays inside the panel/room).

LOAD: Text contains "Steckdosen", "Beleuchtung", "Licht", "Motor", "Reserve", "Trafo", "Heizung", or specific device names.

Note: If a circuit leaves the panel to connect to an external control/monitoring device (e.g., "Phasenausfallrelais", "Remote Control", "BMS"), classify it as LOAD because the wiring leaves the enclosure.

Extraction Rules for "cable_spec":

To determine the full cable string, analyze the terminals and text.

Step A (Find Cross-Section): Extract the number (e.g., "1,5" = 1.5mm²).

Step B (Count Cores): Count the terminals in the block for that specific circuit.

3x: (L, N, PE) or (1, N, PE).

5x: (L1, L2, L3, N, PE) or (1, 2, 3, N, PE).

Other: Exact count of terminals (e.g., 4 slots = "4x").

Step C (Check for Multiple Cables):

Split Cables: If a single circuit (column) has multiple separate terminal blocks (e.g., one block labeled X101 with 5 pins and another adjacent block labeled X1 with 5 pins), verify if they represent separate cables. If yes, sum them (e.g., "2x(5x1.5mm²)").

Complex Control: If a device (like a relay or monitor) has wires going to terminals X... and separate wires going to a different external destination, account for all outgoing cables.

Step D (Exceptions):

Text Override: If the text explicitly states a cable type (e.g., "NAYCWY 4x240"), use the text description instead of counting terminals.

Output Format:

Return ONLY a valid JSON array. Do not include any markdown formatting, code blocks, or explanatory text. Just the raw JSON array.

Example format:

[
  {
    "circuit": "1",
    "connection_type": "SUPPLY",
    "breaker": "1S1",
    "cable_spec": "4x240/120mm²",
    "destination": "Zuleitung NAYCWY..."
  },
  {
    "circuit": "3",
    "connection_type": "LOAD",
    "breaker": "1F3",
    "cable_spec": "2x(5x1.5mm²)",
    "destination": "Phasenausfallrelais (Control & Sense)"
  },
  {
    "circuit": "18",
    "connection_type": "LOAD",
    "breaker": "03F01",
    "cable_spec": "7x2.5",
    "destination": "Lichtschiene..."
  }
]"""




def extract_json_from_response(response_text: str) -> List[Dict[str, Any]]:
    """
    Extract JSON from AI response, handling markdown code blocks if present.
    """
    # Remove markdown code blocks if present
    response_text = response_text.strip()
    
    # Try to find JSON array
    if response_text.startswith("```"):
        # Remove markdown code block markers
        lines = response_text.split("\n")
        # Remove first and last line if they are code block markers
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        response_text = "\n".join(lines)
    
    # Try to find JSON array boundaries
    start_idx = response_text.find("[")
    end_idx = response_text.rfind("]")
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = response_text[start_idx:end_idx + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse JSON, trying full response: {e}")
    
    # Fallback: try parsing the whole response
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not parse JSON from response: {e}")
        print(f"Response preview: {response_text[:500]}")
        return []


def analyze_image_with_ai(
    client: genai.Client,
    model_name: str,
    image_path: Path,
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    Analyze a single image using Google Gemini Vision API.
    
    Args:
        client: Gemini client instance
        model_name: Name of the model to use
        image_path: Path to the image file
        max_retries: Maximum number of retry attempts
        
    Returns:
        List of extracted circuit data dictionaries
    """
    # Read image file
    with open(image_path, "rb") as f:
        image_content = f.read()
    
    # Prepare the API call
    for attempt in range(max_retries):
        try:
            # Use the same API format as test.py
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    # Pass the detailed analysis prompt
                    ANALYSIS_PROMPT,
                    # Pass the image using from_bytes (same as test.py)
                    types.Part.from_bytes(
                        data=image_content,
                        mime_type="image/png"
                    ),
                ]
            )
            
            # Extract response text
            response_text = response.text
            
            # Parse JSON from response
            results = extract_json_from_response(response_text)
            
            return results
            
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Exponential backoff
                print(f"  ⚠ Attempt {attempt + 1} failed: {e}")
                print(f"  Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"  ❌ Failed after {max_retries} attempts: {e}")
                return []


def process_single_image(
    api_key: str,
    model_name: str,
    image_path: Path,
    page_num: int,
    total_pages: int
) -> tuple[int, Path, List[Dict[str, Any]]]:
    """
    Helper function to process a single image (for parallel execution).
    Creates its own client instance to ensure thread safety.
    
    Returns:
        Tuple of (page_num, image_path, results)
    """
    print(f"[STARTING] Processing page {page_num}/{total_pages}: {image_path.name}")
    
    # Create a new client instance for this thread to ensure thread safety
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"  ❌ Page {page_num}: Failed to create client: {e}")
        return (page_num, image_path, [])
    
    results = analyze_image_with_ai(client, model_name, image_path)
    
    if results:
        # Add page number to each result for tracking
        for result in results:
            result["page"] = page_num
            result["source_image"] = image_path.name
        print(f"  ✓ Page {page_num}: Extracted {len(results)} circuit(s)")
    else:
        print(f"  ⚠ Page {page_num}: No circuits extracted")
    
    print(f"[COMPLETED] Page {page_num}/{total_pages}: {image_path.name}")
    return (page_num, image_path, results)


def process_all_images(
    input_dir: Path = Path("input_images"),
    output_file: Path = Path("results.json"),
    api_key: str = None,
    model_name: str = "gemini-2.0-flash",
    max_workers: int = 5
) -> List[Dict[str, Any]]:
    """
    Process all images in the input directory and save to a single results.json file.
    Uses parallel processing to speed up API calls.
    
    Args:
        input_dir: Directory containing input images
        output_file: Path to save the combined results JSON file
        api_key: Google API key (if None, reads from GOOGLE_API_KEY env var)
        model_name: Model to use (default: gemini-2.0-flash). Options: gemini-2.0-flash, gemini-3-pro-preview
        max_workers: Maximum number of concurrent API requests (default: 5)
        
    Returns:
        List of all extracted circuit data dictionaries
    """
    # Initialize Google Gemini client
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("ERROR: Google API key not found.")
            print("Please set GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable or pass it as argument.")
            print("You can get an API key from: https://aistudio.google.com/app/apikey")
            sys.exit(1)
    
    # Initialize the client (new API: pass api_key directly to Client)
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"ERROR: Failed to initialize Gemini client: {e}")
        sys.exit(1)
    
    # Get all image files
    image_files = sorted(input_dir.glob("page_*.png"))
    
    if not image_files:
        print(f"ERROR: No images found in {input_dir}")
        sys.exit(1)
    
    print(f"Found {len(image_files)} image(s) to process")
    print(f"Using model: {model_name}")
    print(f"Parallel workers: {max_workers}")
    print(f"Output file: {output_file}")
    print("="*60)
    
    all_results = []
    start_time = time.time()
    
    # Process images in parallel using ThreadPoolExecutor
    # Each thread will create its own client instance for thread safety
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks - pass api_key instead of client
        print(f"Submitting {len(image_files)} task(s) to thread pool (max {max_workers} concurrent)...")
        future_to_image = {}
        for i, image_path in enumerate(image_files):
            future = executor.submit(
                process_single_image,
                api_key,
                model_name,
                image_path,
                i + 1,
                len(image_files)
            )
            future_to_image[future] = (i + 1, image_path)
        
        print(f"✓ All {len(future_to_image)} task(s) queued. Up to {max_workers} will run concurrently.\n")
        print("Tasks will start as workers become available...\n")
        
        # Collect results as they complete
        page_results = {}
        completed_count = 0
        for future in as_completed(future_to_image):
            try:
                page_num, image_path, results = future.result()
                page_results[page_num] = results
                completed_count += 1
                print(f"  [Progress: {completed_count}/{len(image_files)} pages completed]")
            except Exception as e:
                page_num, image_path = future_to_image[future]
                print(f"  ❌ Page {page_num} ({image_path.name}) failed: {e}")
                page_results[page_num] = []
                completed_count += 1
    
    # Sort results by page number to maintain order
    for page_num in sorted(page_results.keys()):
        all_results.extend(page_results[page_num])
    
    elapsed_time = time.time() - start_time
    
    # Save all results to a single JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*60)
    print(f"SUCCESS: Processed {len(image_files)} page(s) in {elapsed_time:.1f} seconds")
    print(f"Total circuits extracted: {len(all_results)}")
    print(f"Results saved to: {output_file}")
    print("="*60)
    
    return all_results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze Single Line Diagram images using AI Vision"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="input_images",
        help="Directory containing input images (default: input_images)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results.json",
        help="Output JSON file path (default: results.json)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Google API key (or set GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.0-flash",
        choices=["gemini-2.0-flash", "gemini-3-pro-preview"],
        help="Model to use (default: gemini-2.0-flash)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Maximum number of concurrent API requests (default: 5). Increase for faster processing, but be mindful of API rate limits."
    )
    
    args = parser.parse_args()
    
    process_all_images(
        input_dir=Path(args.input_dir),
        output_file=Path(args.output),
        api_key=args.api_key,
        model_name=args.model,
        max_workers=args.max_workers
    )

