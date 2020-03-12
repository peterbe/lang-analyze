import random
import re
import concurrent.futures
import json
import time
from pathlib import Path

import bleach
import yaml
from guess_language import guess_language
from pyquery import PyQuery as pq

ACCEPTED_LOCALES = (
    "en-US",  # English
    "ar",  # Arabic
    "bg",  # Bulgarian
    "bm",  # Bambara
    "bn",  # Bengali
    "ca",  # Catalan
    "de",  # German
    "el",  # Greek
    "es",  # Spanish
    "fa",  # Persian
    "fi",  # Finnish
    "fr",  # French
    "he",  # Hebrew
    "hi-IN",  # Hindi (India)
    "hu",  # Hungarian
    "id",  # Indonesian
    "it",  # Italian
    "ja",  # Japanese
    "kab",  # Kabyle
    "ko",  # Korean
    "ms",  # Malay
    "my",  # Burmese
    "nl",  # Dutch
    "pl",  # Polish
    "pt-PT",  # Portuguese (Portugal)
    "pt-BR",  # Portuguese (Brazil)
    "ru",  # Russian
    "sv-SE",  # Swedish (Sweden)
    "th",  # Thai
    "tr",  # Turkish
    "uk",  # Ukranian
    "vi",  # Vietnamese
    "zh-CN",  # Chinese (China)
    "zh-TW",  # Chinese (Taiwan, Province of China)
)

_proper_locales = {x.lower(): x for x in ACCEPTED_LOCALES}


def run(root, destination, locales, include_archive=False, dry_run=False):
    if not destination.is_dir() and not dry_run:
        destination.mkdir()

    root_folders = [
        x
        for x in root.iterdir()
        if x.name in locales or not locales and x.name != "en-us"
    ]

    all = []
    futures = []
    t0 = time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        for folder in root_folders:
            futures.append(
                executor.submit(
                    process_folder,
                    folder,
                    destination,
                    include_archive=include_archive,
                    dry_run=dry_run,
                )
            )
        for future in concurrent.futures.as_completed(futures):
            all.append(future.result())
    t1 = time.time()

    print("")
    print("Ordered by wrongs...")
    all.sort(key=lambda x: x["p"])

    took_total = 0
    for each in all:
        locale = each["locale"]
        wrongs = each["wrongs"]
        rights = each["rights"]
        took_total += each["took"]
        p = each["p"]
        print(
            locale.ljust(10),
            f"{wrongs:,} of {wrongs+rights:,} ({p:.1f}%s) are wrong probably.",
        )
    print()
    print(f"Took {t1 - t0:.1f}s  ({took_total:.1f}s summed individually)")

    with open("/tmp/all-suspects.json", "w") as f:
        json.dump(all, f, indent=2)


def process_folder(folder, destination, include_archive, dry_run):
    actual_locale = _proper_locales.get(folder.name, folder.name)
    locale = folder.name.split("-")[0]
    wrongs = rights = 0
    suspects = []
    every_possible_slugs = []
    t0 = time.time()
    for file in folder.glob("**/index.html"):
        with open(file.parent / "index.yaml") as f:
            metadata = yaml.safe_load(f)

        slug = metadata["slug"]
        every_possible_slugs.append(metadata["slug"])

        if not include_archive:
            if any([slug.lower().startswith(s) for s in ("archive", "mozilla", "mdn")]):
                continue

        # DON'T do `d = pq(filename=file)` since I think that messed up unicode.
        with open(file) as f:
            html = f.read()
        d = pq(html)

        d(
            "pre,code,#Quick_Links,div.bc-data,div.hidden,"
            "table.standard-table,li:empty,p:empty,div:empty,"
            "#compat-desktop,#compat-mobile,table.compat-table,"
            "div.blockIndicator.warning,span.inlineIndicator,"
            ".overheadIndicator,.translationInProgress,"
            ".blockIndicator.experimental,div.prevnext"
        ).remove()
        # What happens a LOT is that in some documents, the only thing
        # that has tranlated are the <h2> headings. That's nice but if that's
        # the only thing that's been translated, then it's misleading.
        # E.g. https://developer.mozilla.org/bm/docs/Web/JavaScript/Reference/Errors/Property_access_denied
        d("h2").remove()
        if "glossary" in slug:
            d(".multiColumnList").remove()
        # One more time
        d("li:empty,p:empty,div:empty,dt:empty").remove()
        text = d.html()
        if not text:
            print(file, "NO TEXT!!")
            continue
        text = bleach.clean(text, tags=[], strip=True)

        # Remove any all-caps words
        # all_caps_words = re.findall(r"\b[A-Z][A-Z]+\b", text)
        text = re.sub(r"\b[A-Z][A-Z]+\b", "", text)

        # Basic cleaning
        text = text.replace("&gt;", ">").replace("&lt;", "<")

        lines = [
            x.strip() for x in text.splitlines() if x.strip() and len(x.strip()) > 1
        ]
        if len(lines) > 20:

            first_half = lines[: len(lines) // 2]
            second_half = lines[len(lines) // 2 :]
            first_text = "\n".join(first_half)
            second_text = "\n".join(second_half)
            first_guessed = guess_language(first_text)
            second_guessed = guess_language(second_text)

            wrong = False
            if locale.lower() != first_guessed.lower():
                wrong = True
                guessed = first_guessed
            elif locale.lower() != second_guessed.lower():
                wrong = True
                guessed = second_guessed

            # if (locale.lower() != first_guessed.lower()) != (
            #     locale.lower() != second_guessed.lower()
            # ):
            #     print("DISAGREEDMENT", locale, first_guessed, second_guessed)
            #     # print(repr(slug))
            #     if random.random() > 0.5:
            #         print(f"  {file} ".center(100, "-"))
            #         text = "\n".join(lines)
            #         print(text)
            #         print()
            #         print(len(lines), "LINES")

            #         print("_" * 180)
            #         print((locale, guessed))

        else:
            text = "\n".join(lines)
            guessed = guess_language(text)
            wrong = locale.lower() != guessed.lower()

        if wrong:
            wrongs += 1

            suspects.append(
                {
                    "folder": str(folder),
                    "locale": actual_locale,
                    "guessed": guessed,
                    "slug": slug,
                    "metadata": metadata,
                }
            )
        else:
            rights += 1

        # # print(repr(slug))
        # if random.random() > 0.99:
        #     print(f"  {file} ".center(100, "-"))
        #     print(text)
        #     print()
        #     print(len(lines), "LINES")

        #     print("_" * 100)
        #     print((locale, guessed))

    t1 = time.time()
    p = 100 * wrongs / (wrongs + rights)
    print(
        locale,
        f"{wrongs:,} of {wrongs+rights:,} ({p:.1f}%s) are wrong probably - {t1 - t0:.1f}s",
    )

    if suspects and not dry_run:
        suspect_destination = destination / f"{actual_locale}.json"
        for suspect in suspects:
            # If there is any other slug that starts with this
            # then this is NOT a leaf
            leaf = True
            for s in every_possible_slugs:
                if s.startswith(suspect["slug"]) and s != suspect["slug"]:
                    leaf = False
                    break
            suspect["leaf"] = leaf
        with open(suspect_destination, "w") as f:
            json.dump(suspects, f, indent=2)

    return {
        "locale": locale,
        "wrongs": wrongs,
        "p": p,
        "rights": rights,
        "took": t1 - t0,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("contentdir", help="where are the content files are")
    parser.add_argument("destinationdir", help="where the suspects end up")
    parser.add_argument(
        "--include-archive", help="include archive", action="store_true", default=False
    )
    parser.add_argument(
        "--dry-run",
        help="dry run, don't actually write .json files",
        action="store_true",
        default=False,
    )
    parser.add_argument("locale", help="specific locales", nargs="*")
    args = parser.parse_args()
    run(
        Path(args.contentdir),
        Path(args.destinationdir),
        args.locale,
        include_archive=args.include_archive,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main())
