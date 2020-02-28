import concurrent.futures
import json
import time
from pathlib import Path

import bleach
import yaml
from guess_language import guess_language
from pyquery import PyQuery as pq


def run(root, destination, locales, include_archive=False):
    if not destination.is_dir():
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
                    process_folder, folder, destination, include_archive=include_archive
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


def process_folder(folder, destination, include_archive):
    locale = folder.name.split("-")[0]
    wrongs = rights = 0
    suspects = []
    every_possible_slugs = []
    t0 = time.time()
    for file in folder.glob("**/index.html"):
        with open(file.parent / "index.yaml") as f:
            metadata = yaml.safe_load(f)

        actual_locale = metadata["locale"]
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
            ".blockIndicator.experimental"
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

        lines = [
            x.strip() for x in text.splitlines() if x.strip() and len(x.strip()) > 1
        ]
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

        # # import random
        # # print(repr(slug))
        # if "Property_access_denied" in slug:
        #     print(f"  {file} ".center(100, "-"))
        #     print(text)

        #     print("_" * 100)
        #     print((locale, guessed))

    t1 = time.time()
    p = 100 * wrongs / (wrongs + rights)
    print(
        locale,
        f"{wrongs:,} of {wrongs+rights:,} ({p:.1f}%s) are wrong probably - {t1 - t0:.1f}s",
    )

    if suspects:
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
    parser.add_argument("locale", help="specific locales", nargs="*")
    args = parser.parse_args()
    run(
        Path(args.contentdir),
        Path(args.destinationdir),
        args.locale,
        args.include_archive,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main())
