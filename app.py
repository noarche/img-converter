#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path
from tqdm import tqdm
import shutil
from colorama import Fore, Style, init

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

def run_ffmpeg(cmd):
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return result.returncode, result.stderr.decode(errors="ignore")

def ffmpeg_convert(input_path, output_path, fmt):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------- WEBP ----------
    if fmt == 'webp':
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),

            '-c:v', 'libwebp',

            # Improved visually lossless settings
            '-qscale:v', '90',
            '-compression_level', '6',
            '-preset', 'photo',
            '-lossless', '0',
            '-near_lossless', '60',
            '-alpha_quality', '90',
            '-metadata', 'none',

            str(output_path)
        ]

        code, err = run_ffmpeg(cmd)

        if code != 0:
            return False, err

    # ---------- AVIF ----------
    elif fmt == 'avif':
        # Try SVT-AV1 first
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),

            '-c:v', 'libsvtav1',

            # Improved visually lossless settings
            '-crf', '22',
            '-preset', '4',
            '-b:v', '0',
            '-pix_fmt', 'yuv420p',
            '-svtav1-params', 'tune=0',
            '-map_metadata', '-1',

            str(output_path)
        ]

        code, err = run_ffmpeg(cmd)

        # fallback to libaom if SVT fails
        if code != 0:
            cmd = [
                'ffmpeg', '-y', '-i', str(input_path),

                '-c:v', 'libaom-av1',
                '-crf', '24',
                '-b:v', '0',
                '-cpu-used', '4',
                '-row-mt', '1',
                '-pix_fmt', 'yuv420p',

                str(output_path)
            ]
            code, err = run_ffmpeg(cmd)

            if code != 0:
                return False, err

    else:
        return False, "Invalid format"

    # ---------- VALIDATE OUTPUT ----------
    if not output_path.exists():
        return False, "Output file not created"

    size = output_path.stat().st_size

    if size == 0:
        try:
            output_path.unlink()
        except:
            pass
        return False, "Output file is 0 bytes"

    if size < 100:  # sanity check
        return False, f"Suspiciously small file ({size} bytes)"

    return True, None

def preserve_file_attributes(src, dst):
    try:
        shutil.copystat(src, dst)
    except Exception:
        pass

def collect_images(path):
    path = Path(path)
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
  python batch_convert.py

Features:
  - Converts images to WebP or AVIF
  - Preserves folder structure
  - Detects FFmpeg failures
  - Prevents 0-byte outputs
  - Falls back to safe codecs automatically
""")
    sys.exit(0)

# ==========================
# Main
# ==========================
def main():
    if '-h' in sys.argv or '--help' in sys.argv:
        print_help()

    print(f"{Fore.CYAN}{Style.BRIGHT}=== Batch Image Converter (WebP / AVIF) ===\n{Style.RESET_ALL}")

    source = input(f"{Fore.YELLOW}Enter path to directory or image file: {Style.RESET_ALL}").strip()
    source_path = Path(source)

    if not source_path.exists():
        print(f"{Fore.RED}Path does not exist!{Style.RESET_ALL}")
        sys.exit(1)

    fmt = ''
    while fmt not in ['webp','avif']:
        fmt = input(f"{Fore.YELLOW}Convert to WebP or AVIF? [webp/avif]: {Style.RESET_ALL}").strip().lower()

    dest_dir = input(f"{Fore.YELLOW}Enter output folder (leave empty to replace originals): {Style.RESET_ALL}").strip()

    replace_original = False
    if not dest_dir:
        print(f"{Fore.RED}WARNING: Originals will be replaced!{Style.RESET_ALL}")
        replace_original = True
        dest_path = None
    else:
        dest_path = Path(dest_dir)
        dest_path.mkdir(parents=True, exist_ok=True)

    images = collect_images(source_path)

    if not images:
        print(f"{Fore.RED}No images found.{Style.RESET_ALL}")
        sys.exit(0)

    total_files = len(images)
    orig_total_size = sum(f.stat().st_size for f in images)

    converted_count = 0
    converted_total_size = 0
    failed = 0

    print(f"\n{Fore.GREEN}Converting {total_files} images to {fmt.upper()}...\n{Style.RESET_ALL}")

    for img_path in tqdm(images, desc=f"{Fore.MAGENTA}Progress{Style.RESET_ALL}", unit="img"):

        try:
            base_path = source_path if source_path.is_dir() else source_path.parent
            rel_path = img_path.relative_to(base_path)
        except ValueError:
            rel_path = Path(img_path.name)

        if replace_original:
            new_file = img_path.with_suffix(f".{fmt}")
        else:
            new_file = (dest_path / rel_path).with_suffix(f".{fmt}")
            new_file.parent.mkdir(parents=True, exist_ok=True)

        success, err = ffmpeg_convert(img_path, new_file, fmt)

        if not success:
            failed += 1
            print(f"{Fore.RED}FAILED: {img_path}\n{err}{Style.RESET_ALL}")
            continue

        preserve_file_attributes(img_path, new_file)

        converted_count += 1
        converted_total_size += new_file.stat().st_size

        if replace_original:
            try:
                img_path.unlink()
            except Exception as e:
                print(f"{Fore.RED}Could not delete original: {e}{Style.RESET_ALL}")

    saved_bytes = orig_total_size - converted_total_size
    saved_percent = (saved_bytes / orig_total_size * 100) if orig_total_size else 0

    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== DONE ==={Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Images found:     {Fore.WHITE}{total_files}")
    print(f"{Fore.GREEN}Converted:        {Fore.WHITE}{converted_count}")
    print(f"{Fore.RED}Failed:           {Fore.WHITE}{failed}")
    print(f"{Fore.YELLOW}Original size:    {Fore.WHITE}{human_readable(orig_total_size)}")
    print(f"{Fore.YELLOW}Converted size:   {Fore.WHITE}{human_readable(converted_total_size)}")
    print(f"{Fore.GREEN}Space saved:      {Fore.WHITE}{human_readable(saved_bytes)} ({saved_percent:.2f}%)\n")

if __name__ == "__main__":
    main()