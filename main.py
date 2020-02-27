import json
import time
from pathlib import Path

import yaml
import bleach
from pyquery import PyQuery as pq
from guess_language import guess_language


def run(root, destination, locales, include_archive=False):
    if not destination.is_dir():
        destination.mkdir()

    root_folders = [
        x
        for x in root.iterdir()
        if x.name in locales or not locales and x.name != "en-us"
    ]

    all = []
    for folder in root_folders:
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
                if any(
                    [slug.lower().startswith(s) for s in ("archive", "mozilla", "mdn")]
                ):
                    continue

            # DON'T do `d = pq(filename=file)` since I think that messed up unicode.
            with open(file) as f:
                html = f.read()
            d = pq(html)

            d(
                "pre,code,#Quick_Links,div.bc-data,div.hidden,"
                "table.standard-table,li:empty,p:empty,div:empty,"
                "#compat-desktop,#compat-mobile,table.compat-table,"
                "div.blockIndicator.warning,span.inlineIndicator"
            ).remove()
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

            # # print((locale, guessed))
            # import random

            # if random.random() > 0.999 and wrong:
            #     print(f"  {file} ".center(100, "-"))
            #     print(text)

            #     print("_" * 100)

        t1 = time.time()
        p = 100 * wrongs / (wrongs + rights)
        print(
            locale,
            f"{wrongs:,} of {wrongs+rights:,} ({p:.1f}%s) are wrong probably - {t1 - t0:.1f}s",
        )

        all.append({"locale": locale, "wrongs": wrongs, "p": p, "rights": rights})

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

    print("\n")
    print("Ordered by wrongs...")
    all.sort(key=lambda x: x["p"])

    for each in all:
        locale = each["locale"]
        wrongs = each["wrongs"]
        rights = each["rights"]
        p = each["p"]
        print(
            locale.ljust(10),
            f"{wrongs:,} of {wrongs+rights:,} ({p:.1f}%s) are wrong probably",
        )


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
