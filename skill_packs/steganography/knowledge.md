# Steganography Knowledge Base

## LSB (Least Significant Bit) Steganography
- **PNG/BMP**: Modify LSB of each RGB channel; 3 bits per pixel
- **Detection**: Visual artefacts in colour channels, statistical anomalies
- **Extraction**: `zsteg` (automated LSB detection), `StegSolve` (bit plane analysis)
- **Common patterns**: LSB on all channels, LSB on blue channel only, palette-based

## Metadata Analysis
- **EXIF**: Camera model, GPS coordinates, timestamps, software
- **Tool**: `exiftool` for comprehensive metadata extraction
- **Hidden fields**: Comment fields, copyright notices, user comments
- **Thumbnail**: Embedded thumbnail may differ from main image

## File Carving
- **Appended data**: File size vs declared size difference (`binwalk`, `foremost`)
- **Zip bombs**: Multiple files appended after image data
- **Tool**: `binwalk -Me <file>` — scan and extract embedded files recursively

## Common Steganography Techniques
- **Text whitespace**: Hidden message in trailing spaces/tabs (stegsnow)
- **Audio spectrogram**: Message visible as image in audio frequency plot (Sonic Visualiser)
- **Polyglot files**: Valid as multiple formats (e.g., PNG+ZIP)
- **Font/PDF**: Hidden data in font files, PDF annotations, unused objects
- **Network**: Data hidden in packet timing, unused header fields (IP identification)

## Extraction Workflow
1. Run `strings` on the file — look for unusual text or base64
2. Check file size vs expected; examine hex dump for appended data
3. Run `binwalk` to detect embedded archives
4. Extract EXIF with `exiftool`
5. Test LSB extraction with `zsteg` on images
6. Check spectrogram for audio files
7. Try known passwords with `steghide extract -sf <file>`
