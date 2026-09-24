// Publish only the browser assets. Device projects, settings, logs and keys
// cannot enter the Vercel output through this explicit file allowlist.
import {mkdir, copyFile, rm, writeFile} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const output=path.join(root,"web-dist");
await rm(output,{recursive:true,force:true});
await mkdir(output,{recursive:true});
for(const name of ["index.html","app.js","app.css","favicon.svg"])
  await copyFile(path.join(root,"sparkle_coder","ui",name),path.join(output,name));
await writeFile(path.join(output,"robots.txt"),"User-agent: *\nDisallow: /\n");
console.log("Built SPARKLE CODER website: 4 browser assets and robots.txt. Connect a local engine to use projects.");
