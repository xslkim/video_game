// A single offline script also runs on Android TV's original Chromium 39.
const fs = require("node:fs");
const path = require("node:path");
const babel = require("@babel/core");
const browserify = require("browserify");
const {Readable} = require("node:stream");
const sources = ["audio.js", "render.js", "game.js"].map(name =>
  fs.readFileSync(path.join(__dirname, "web", name), "utf8"));
const js = babel.transformSync(sources.join("\n"), {
  babelrc: false, configFile: false, comments: false, sourceType: "script",
  presets: [[require("@babel/preset-env"), {targets: {chrome: "39"}, modules: "commonjs"}]]
}).code;
const entry = Readable.from(["require('core-js/stable');\n" + js]);
entry.file = path.join(__dirname, "game-entry.js");
browserify(entry, {basedir: __dirname}).bundle((err, result) => {
  if (err) throw err;
  fs.writeFileSync(process.argv[2], result);
});
