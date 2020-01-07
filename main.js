const fs = require("fs");
const path = require("path");
var franc = require("franc");
var langs = require("langs");
var cheerio = require("cheerio");
const convert3To1 = require("iso-639-3-to-1");

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
const ROOT = "/Users/peterbe/stumptown-renderer/content/files";
// const LOCALES = ["sv-SE", "es"];
const LOCALES = [];
// const LOCALES = ["en-US"];
// const LOCALES = ["sv-SE"];

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
  const results = [];
  getRootFolders().forEach(filepath => {
    let wasEn = 0;
    let right = 0;
    let wrong = 0;
    const correct = path.basename(filepath).split("-")[0];
    walker(filepath, (folder, files) => {
      if (files.includes("index.html") && files.includes("index.yaml")) {
        if (EXCLUDE_ARCHIVED) {
          const rel = folder.replace(filepath, "");
          if (
            rel.startsWith("/Achive/") ||
            rel.startsWith("/User:") ||
            rel.startsWith("/Talk:") ||
            rel.startsWith("/User_talk:") ||
            rel.startsWith("/Template_talk:") ||
            rel.startsWith("/Project_talk:") ||
            rel.startsWith("/Experiment:")
          ) {
            return;
          }
        }
        // console.log(folder);
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
        // console.log(plain.trim());
        // console.log("\n----------------------------------------------\n\n");
        if (plain.length < 250) {
          // console.log(`SKIP (${plain.length.toLocaleString()})`);
          // console.log(plain);
          return;
        }

        let prob = franc(plain);
        prob = convert3To1(prob) || prob;
        // Scottish ~== English
        if (prob === "sco") {
          prob = "en";
        }
        if (correct === prob) {
          right++;
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
          // console.log({ prob });
          // console.log("\n----------------------------------------------\n\n");
          wrong++;
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
      wrong
    });
    // console.log({ wasEn, right, wrong });
    // return { wasEn, right, wrong };
    totalRight += right;
    totalWrong += wrong;
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
  const p = (100 * totalRight) / (totalRight + totalWrong);
  console.log(
    `right ${p.toFixed(
      1
    )}% of the time (${totalRight.toLocaleString()} right. ${totalWrong.toLocaleString()} wrong)`
  );
  console.log(`(${(totalRight + totalWrong).toLocaleString()} documents)`);
}
run();
