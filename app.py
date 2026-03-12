#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path
from tqdm import tqdm
import shutil
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# ==========================
# Helper functions
# ==========================
def human_readable(size_bytes):
    for unit in ['B','KB','MB','GB','TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def ffmpeg_convert(input_path, output_path, fmt):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == 'webp':
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),
            '-c:v', 'libwebp',
            '-qscale:v', '80',
            '-compression_level', '6',
            '-preset', 'photo',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]
    elif fmt == 'avif':
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),
            '-c:v', 'libaom-av1',
            '-crf', '32',
            '-b:v', '0',
            '-pix_fmt', 'yuv420p',
            '-cpu-used', '4',
            '-map_metadata', '-1',
            str(output_path)
        ]
    else:
        raise ValueError("Format must be 'webp' or 'avif'")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def preserve_file_attributes(src, dst):
    try:
        shutil.copystat(src, dst)
    except Exception:
        pass

def collect_images(path):
    path = Path(path)
    # Exclude webp/avif as sources to avoid recompressing
    exts = ['.jpg','.jpeg','.png','.bmp','.tiff','.tif']
    files = []
    if path.is_file() and path.suffix.lower() in exts:
        files.append(path)
    elif path.is_dir():
        for f in path.rglob('*'):
            if f.suffix.lower() in exts:
                files.append(f)
    return files

def print_help():
    print(f"""
{Fore.CYAN}{Style.BRIGHT}Batch Image Converter Help{Style.RESET_ALL}

Usage:
  python batch_convert.py [options]

Options:
  -h, --help     Show this help message

How it works:
  1. Prompts for a source file or directory (recursively searches directories).
  2. Prompts for output format: WebP or AVIF.
  3. Prompts for a destination folder to save converted images.
     If left empty, images will replace originals automatically.
  4. Keeps folder structure and original file attributes.
  5. Shows progress bar, ETA, total size, and space saved.

  Benefits of Output Formats:
  {Fore.YELLOW}WebP{Style.RESET_ALL}:
    - Smaller files than JPEG while preserving quality.
    - Supports transparency and animation.
    - Very fast encoding/decoding and widely supported.

  {Fore.YELLOW}AVIF{Style.RESET_ALL}:
    - Superior compression (smaller than WebP for high-quality images).
    - High image quality with support for HDR and transparency.
    - Slower encoding, but excellent for archival or web delivery.

Why some formats are not used as sources:
  - The script ignores existing WebP/AVIF files because:
    1. Converting them again reduces quality due to lossy recompression.
    2. AVIF/WebP sources are usually already optimized in size.
    3. Avoids unnecessary processing and keeps conversion efficient.

Tips:
  - Resize large images before converting for extra space savings.
  - Use WebP for wide compatibility, AVIF for maximum compression.
  - Use lossless sources (PNG/TIFF) for best AVIF quality.

Example Run:
  python batch_convert.py
""")
    sys.exit(0)

# ==========================
# Main
# ==========================
def main():
    # Check for help argument
    if '-h' in sys.argv or '--help' in sys.argv:
        print_help()

    print(f"{Fore.CYAN}{Style.BRIGHT}=== Batch Image Converter (WebP / AVIF) ===\n{Style.RESET_ALL}")

    source = input(f"{Fore.YELLOW}Enter path to directory or image file: {Style.RESET_ALL}").strip()
    source_path = Path(source)
    if not source_path.exists():
        print(f"{Fore.RED}Path does not exist!{Style.RESET_ALL}")
        sys.exit(1)

    fmt = ''
    while fmt.lower() not in ['webp','avif']:
        fmt = input(f"{Fore.YELLOW}Convert to WebP or AVIF? [webp/avif]: {Style.RESET_ALL}").strip().lower()

    dest_dir = input(f"{Fore.YELLOW}Enter path to save converted images (leave empty to replace originals): {Style.RESET_ALL}").strip()
    replace_original = False
    if not dest_dir:
        print(f"{Fore.RED}WARNING: This will replace the original images with the converted files!{Style.RESET_ALL}")
        replace_original = True
        dest_path = None
    else:
        dest_path = Path(dest_dir)
        dest_path.mkdir(parents=True, exist_ok=True)

    images = collect_images(source_path)
    total_files = len(images)
    if total_files == 0:
        print(f"{Fore.RED}No images found to convert.{Style.RESET_ALL}")
        sys.exit(0)

    orig_total_size = sum(f.stat().st_size for f in images)
    converted_count = 0
    converted_total_size = 0

    print(f"\n{Fore.GREEN}Converting {total_files} images to {fmt.upper()}...\n{Style.RESET_ALL}")

    for img_path in tqdm(images, desc=f"{Fore.MAGENTA}Progress{Style.RESET_ALL}", unit="img"):
        try:
            rel_path = img_path.relative_to(source_path) if source_path.is_dir() else img_path.name
        except ValueError:
            rel_path = img_path.name

        if replace_original:
            new_file = img_path.with_suffix(f".{fmt}")
        else:
            new_file = dest_path / rel_path
            new_file = new_file.with_suffix(f".{fmt}")
            new_file.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg_convert(img_path, new_file, fmt)
        preserve_file_attributes(img_path, new_file)

        if new_file.exists():
            converted_count += 1
            converted_total_size += new_file.stat().st_size
            if replace_original:
                try:
                    img_path.unlink()  # delete original
                except Exception as e:
                    print(f"{Fore.RED}Failed to delete original {img_path}: {e}{Style.RESET_ALL}")

    saved_bytes = orig_total_size - converted_total_size
    saved_percent = (saved_bytes / orig_total_size) * 100 if orig_total_size > 0 else 0

    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== Conversion Complete ==={Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Images found:        {Fore.WHITE}{total_files}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Images converted:    {Fore.WHITE}{converted_count}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Original size:       {Fore.WHITE}{human_readable(orig_total_size)}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Converted size:      {Fore.WHITE}{human_readable(converted_total_size)}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Space saved:         {Fore.WHITE}{human_readable(saved_bytes)} ({saved_percent:.2f}%){Style.RESET_ALL}\n")

if __name__ == "__main__":
    main()