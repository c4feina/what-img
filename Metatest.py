"""
Extractor de metadata imagenes - pa subir algo al github jeje
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    print("Error: Pillow no está instalado. Ejecuta: pip install Pillow")
    sys.exit(1)

def get_basic_info(img: Image.Image, filepath: str) -> dict:
    #Información basiquita
    stat = os.stat(filepath)
    return {
        "archivo": os.path.basename(filepath),
        "ruta": os.path.abspath(filepath),
        "formato": img.format,
        "modo_color": img.mode,
        "ancho_px": img.width,
        "alto_px": img.height,
        "tamaño_bytes": stat.st_size,
        "tamaño_kb": round(stat.st_size / 1024, 2),
        "fecha_modificacion": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def decode_gps(gps_data: dict) -> dict:
    #Convierte los datos gps a coordenadas simples
    decoded = {}
    for key, val in gps_data.items():
        tag_name = GPSTAGS.get(key, str(key))
        decoded[tag_name] = val

    result = {}
    try:
        lat = decoded.get("GPSLatitude")
        lat_ref = decoded.get("GPSLatitudeRef", "N")
        lon = decoded.get("GPSLongitude")
        lon_ref = decoded.get("GPSLongitudeRef", "E")

        if lat and lon:
            def to_degrees(val):
                d, m, s = float(val[0]), float(val[1]), float(val[2])
                return d + m / 60 + s / 3600

            lat_dd = to_degrees(lat) * (-1 if lat_ref == "S" else 1)
            lon_dd = to_degrees(lon) * (-1 if lon_ref == "W" else 1)
            result["latitud"] = round(lat_dd, 7)
            result["longitud"] = round(lon_dd, 7)
            result["maps_url"] = f"https://maps.google.com/?q={lat_dd},{lon_dd}"
    except Exception:
        pass

    result.update(decoded)
    return result


def get_exif_data(img: Image.Image) -> dict:
    exif_raw = img._getexif() if hasattr(img, "_getexif") else None
    if not exif_raw:
        return {}

    exif = {}
    gps_raw = {}

    for tag_id, value in exif_raw.items():
        tag_name = TAGS.get(tag_id, str(tag_id))

        if tag_name == "GPSInfo":
            gps_raw = value
            continue

        # Convertir bytes a string para serialización
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8", errors="replace")
            except Exception:
                value = str(value)

        exif[tag_name] = value

    if gps_raw:
        exif["GPS"] = decode_gps(gps_raw)

    return exif


def extract_metadata(filepath: str) -> dict:
    #Funcion principal
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

    img = Image.open(filepath)

    metadata = {
        "info_basica": get_basic_info(img, filepath),
        "exif": get_exif_data(img),
    }
    extra = {k: str(v) for k, v in img.info.items()
             if k.lower() not in ("exif",) and isinstance(v, (str, int, float, tuple))}
    if extra:
        metadata["info_extra"] = extra

    img.close()
    return metadata

def print_metadata(metadata: dict, verbose: bool = False) -> None:
    #Imprime los metadatos 
    sep = "─" * 60

    # Info basica
    print(f"\n{sep}")
    print("  INFORMACIÓN BÁSICA")
    print(sep)
    for k, v in metadata["info_basica"].items():
        print(f"  {k:<25} {v}")

    exif = metadata.get("exif", {})
    if exif:
        print(f"\n{sep}")
        print("  METADATOS EXIF")
        print(sep)

        # Tags más relevantes primero
        priority = [
            "Make", "Model", "Software", "DateTime", "DateTimeOriginal",
            "ExposureTime", "FNumber", "ISOSpeedRatings", "FocalLength",
            "Flash", "WhiteBalance", "Orientation", "GPS",
        ]
        shown = set()

        for tag in priority:
            if tag in exif:
                val = exif[tag]
                if isinstance(val, dict):
                    print(f"\n  {tag}:")
                    for k, v in val.items():
                        print(f"    {k:<25} {v}")
                else:
                    print(f"  {tag:<25} {val}")
                shown.add(tag)

        if verbose:
            print(f"\n  {'— Todos los tags —':^56}")
            for tag, val in exif.items():
                if tag not in shown:
                    if isinstance(val, dict):
                        print(f"\n  {tag}:")
                        for k, v in val.items():
                            print(f"    {k:<25} {v}")
                    else:
                        print(f"  {tag:<25} {val}")
    else:
        print("\n  Sin datos EXIF disponibles.")

    extra = metadata.get("info_extra", {})
    if extra and verbose:
        print(f"\n{sep}")
        print("  INFO ADICIONAL (PNG/GIF/etc.)")
        print(sep)
        for k, v in extra.items():
            print(f"  {k:<25} {v}")

    print(f"\n{sep}\n")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extrae metadatos EXIF y básicos de imágenes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python image_metadata_extractor.py foto.jpg
  python image_metadata_extractor.py foto.jpg --verbose
  python image_metadata_extractor.py foto.jpg --json
  python image_metadata_extractor.py foto.jpg --output resultado.json
  python image_metadata_extractor.py *.jpg --json
        """,
    )
    parser.add_argument("imagenes", nargs="+", help="Una o más imágenes a analizar")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Mostrar todos los tags EXIF (no solo los principales)")
    parser.add_argument("-j", "--json", action="store_true",
                        help="Salida en formato JSON")
    parser.add_argument("-o", "--output", metavar="ARCHIVO",
                        help="Guardar resultado JSON en un archivo")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    results = {}
    errors = {}

    for filepath in args.imagenes:
        try:
            metadata = extract_metadata(filepath)
            results[filepath] = metadata
            if not args.json and not args.output:
                print(f"\n{'='*60}")
                print(f"  {filepath}")
                print_metadata(metadata, verbose=args.verbose)
        except Exception as e:
            errors[filepath] = str(e)
            print(f"[ERROR] {filepath}: {e}", file=sys.stderr)

    if args.json or args.output:
        output_data = {"resultados": results}
        if errors:
            output_data["errores"] = errors

        json_str = json.dumps(output_data, ensure_ascii=False, indent=2, default=str)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_str)
            print(f"Resultado guardado en: {args.output}")
        else:
            print(json_str)


if __name__ == "__main__":
    main()