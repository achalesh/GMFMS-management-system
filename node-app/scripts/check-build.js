import {readdir,readFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import ejs from 'ejs';
for(const dir of ['src','scripts','test'])for(const f of await readdir(dir))if(f.endsWith('.js'))execFileSync(process.execPath,['--check',`${dir}/${f}`]);
for(const f of await readdir('views'))if(f.endsWith('.ejs'))ejs.compile(await readFile(`views/${f}`,'utf8'));
console.log('JavaScript and templates validated.');
