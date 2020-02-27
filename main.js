const fs = require("fs");
const path = require("path");
const franc = require("franc");
const langs = require("langs");
const cheerio = require("cheerio");
const yaml = require("js-yaml");
const convert3To1 = require("iso-639-3-to-1");
// const csv = require("@fast-csv/format");

// const iso63931_to_iso63933 = {};
const iso63933_to_name = {};
langs.all().forEach(each => {
  iso63933_to_name[each["1"]] = each.name;
});

function walker(root, callback) {
  const files = fs.readdirSync(root);
  for (const name of files) {
    const filepath = path.join(root, name);
    const isDirectory = fs.statSync(filepath).isDirectory();
    if (isDirectory) {
      callback(
        filepath,
        fs.readdirSync(filepath).filter(name => {
          return !fs.statSync(path.join(filepath, name)).isDirectory();
        })
      );
      // Now go deeper
      walker(filepath, callback);
    }
  }
}

const EXCLUDE_ARCHIVED = true;
const ROOT = process.argv[2];
if (!fs.statSync(ROOT).isDirectory()) {
  throw new Error(`${ROOT} is not a directory`);
}
const DESTINATION = path.resolve(process.argv[3]);
if (!fs.existsSync(DESTINATION)) {
  fs.mkdirSync(DESTINATION, { recursive: true });
} else if (!fs.statSync(DESTINATION).isDirectory()) {
  throw new Error(`${DESTINATION} is not a directory`);
}

const LOCALES = process.argv.slice(4).map(x => x.toLowerCase());

function getRootFolders() {
  const files = fs.readdirSync(ROOT);
  const folders = [];
  for (const name of files) {
    const filepath = path.join(ROOT, name);
    const isDirectory = fs.statSync(filepath).isDirectory();
    if (isDirectory && (!LOCALES.length || LOCALES.includes(name))) {
      folders.push(filepath);
    }
  }
  return folders;
}

function run() {
  let totalRight = 0;
  let totalWrong = 0;
  let totalMaybe = 0;
  const results = [];
  const suspects = [];
  getRootFolders().forEach(filepath => {
    let wasEn = 0;
    let right = 0;
    let maybe = 0;
    let wrong = 0;
    const locale = path.basename(filepath);
    const correct = locale.split("-")[0];
    walker(filepath, (folder, files) => {
      if (files.includes("index.html") && files.includes("index.yaml")) {
        const rel = folder.replace(filepath, "");
        if (EXCLUDE_ARCHIVED) {
          const start = rel.split("/")[1];
          if (["archive", "mozilla", "mdn"].includes(start)) {
            return;
          }
        }
        // if (rel !== "/web/api/htmlelement/offsetwidth") return;

        const html = fs.readFileSync(path.join(folder, "index.html"), "utf8");
        const $ = cheerio.load(`<div id="_body">${html}</div>`);
        $(
          "pre,code,#Quick_Links,div.bc-data,div.hidden,table.standard-table,h2,a,li:empty,p:empty"
        ).remove();
        $("li:empty,p:empty").remove();
        $("ul:empty").remove();
        // console.log(filepath, folder);
        // console.log(html);
        // console.log(
        //   "============================================================="
        // );
        // console.log(
        //   $("#_body")
        //     .html()
        //     .trim()
        // );
        const plain = $.html({ decodeEntities: false })
          .replace(/(<([^>]+)>)/gi, "")
          .trim();
        // console.log(plain);
        // console.log(plain.trim());
        // console.log("\n----------------------------------------------\n\n");
        if (plain.length < 250) {
          // console.log(`SKIP (${plain.length.toLocaleString()})`);
          // console.log(plain);
          return;
        }

        let probAll = franc.all(plain);
        let prob = probAll[0][0];
        let firstP = probAll[0][1];
        prob = convert3To1(prob) || prob;
        // Scottish ~== English
        if (prob === "sco") {
          prob = "en";
        }
        let secondP = null;
        if (correct !== prob) {
          // So, what percentage did we get for the same locale
          const selfProb = probAll.filter(x => {
            return correct === (convert3To1(x[0]) || x[0]);
          });
          if (selfProb && selfProb.length) {
            secondP = selfProb[0][1];
          }
          // try {
          //   secondP = selfProb[0][1];
          // } catch (ex) {
          //   console.log({ correct });
          //   console.log(probAll);
          //   throw ex;
          // }
        }

        if (correct === prob) {
          right++;
        } else if (secondP && secondP > 0.99) {
          maybe++;
        } else {
          // console.log(folder);
          // console.log(
          //   "============================================================="
          // );
          // console.log(
          //   $("#_body")
          //     .html()
          //     .trim()
          // );
          // console.log(plain.trim());
          // console.log(probAll);
          // console.log({ prob });
          // console.log("\n----------------------------------------------\n\n");
          wrong++;
          suspects.push({
            folder,
            prob,
            locale,
            secondP,
            firstP
          });
          if (prob === "en" && correct !== "en") {
            wasEn++;
          }
        }
        // const probs = franc.all(plain);
        // // console.log(probs.slice(0, 3));
        // for (const prob of probs.slice(0, 3)) {
        //   console.log(`${convert3To1(prob[0]) || prob[0]}\t${prob[1]}`);
        // }

        // const $ = cheerio.load(`<div id="_body">${html}</div>`);

        // $("*").each(function() {
        //   $(this).replaceWith($(this).html());
        // });
        // const plain = $.html();
        // console.log(plain);
        // // console.log(
        // //   $("*")
        // //     .unwrap()
        // //     .html()
        // // );
        // throw new Error("stop");
      }
    });

    const name = iso63933_to_name[correct] || correct;
    const p = (100 * right) / (right + wrong);
    console.log(
      `${correct}: right ${p.toFixed(
        1
      )}% of the time (${right.toLocaleString()} right. ${wrong.toLocaleString()} wrong) ${name}`
    );
    results.push({
      locale: correct,
      right,
      wrong,
      maybe
    });
    // console.log({ wasEn, right, wrong });
    // return { wasEn, right, wrong };
    totalRight += right;
    totalWrong += wrong;
    totalMaybe += maybe;
  });

  console.log("\nOrdered by wrongs...");
  results
    .sort((a, b) => b.wrong - a.wrong)
    .forEach(({ locale, right, wrong }) => {
      const name = iso63933_to_name[locale] || locale;
      const p = (100 * right) / (right + wrong);
      console.log(
        `${locale.padStart(3)}: right ${p.toFixed(
          1
        )}% of the time (${right.toLocaleString()} right. ${wrong.toLocaleString()} wrong) ${name}`
      );
    });

  console.log("\nIn total...");
  const totalTotal = totalRight + totalWrong + totalMaybe;
  const p = (100 * totalRight) / totalTotal;
  console.log(`right ${p.toFixed(1)}% of the time`);
  const mp = (100 * totalMaybe) / totalTotal;
  console.log(`maybe ${mp.toFixed(1)}% of the time`);
  console.log(
    `${totalRight.toLocaleString()} right. ${totalMaybe.toLocaleString()} maybe. ${totalWrong.toLocaleString()} wrong. `
  );
  console.log(`(${totalTotal.toLocaleString()} documents)`);

  const rows = {};
  for (let suspect of suspects) {
    if (!(suspect.locale in rows)) {
      rows[suspect.locale] = [];
    }
    let metadata = yaml.load(
      fs.readFileSync(path.join(suspect.folder, "index.yaml"))
    );
    if (suspect.firstP < 1) {
      console.log(metadata);
    }
    rows[suspect.locale].push({
      metadata,
      // locale: suspect.locale,
      probably: suspect.prob,
      probability: suspect.firstP
      // secondP: suspect.secondP
    });
  }
  Object.entries(rows).forEach(([locale, suspects]) => {
    // const stream = csv.format({
    //   delimiter: "\t"
    // });
    const filename = `${locale}.json`;
    const filepath = path.join(DESTINATION, filename);
    fs.writeFileSync(filepath, JSON.stringify(suspects, null, 2));
    // const wstream = fs.createWriteStream(filepath);
    // stream.pipe(wstream);

    // stream.write(["LOCALE", "SLUG", "PROBABLY", "SELF-PROBABILITY", "TITLE"]);
    // for (let suspect of suspects) {
    //   stream.write([
    //     // `https://wiki.developer.mozilla.org${suspect.locale}/docs/${suspect.slug}`,
    //     suspect.locale,
    //     suspect.metadata.slug,
    //     suspect.probability,
    //     suspect.secondP,
    //     suspect.metadata.title
    //   ]);
    // }
    // stream.end();
    // wstream.end();
    console.log(`Wrote ${filepath}`);
  });
}
run();
