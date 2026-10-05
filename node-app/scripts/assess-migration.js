import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {assessSnapshot} from '../src/migration-assessment.js';
const directory=process.argv[2];
if(!directory)throw Error('Provide the private snapshot directory');
try{
 const report=assessSnapshot(await readFile(path.join(directory,'snapshot.json')),JSON.parse(await readFile(path.join(directory,'reconciliation.json'),'utf8')));
 await writeFile(path.join(directory,'assessment.json'),JSON.stringify(report,null,2),{flag:'wx',mode:0o600});
 console.log(`Snapshot and artifacts verified. ${report.blockers.length} migration mapping blockers recorded. No source or target database modified.`);
}catch{console.error('Migration assessment failed. Check snapshot integrity and choose a directory without an existing assessment. Private record values are not logged.');process.exitCode=1;}
