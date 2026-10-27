import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {database} from '../src/database.js';
import {migrate} from '../src/schema.js';

test('CommonJS hosting launcher can require the release entry and start the ESM server and safely upgrade schema 6',async()=>{
 const directory=await mkdtemp(path.join(tmpdir(),'gmf-startup-'));
 const sqlite=path.join(directory,'test.sqlite');
 try{
  const db=await database({sqlite});try{await migrate(db);await db.run('DROP TABLE gmf_facilitator_accounts');await db.run('DROP TABLE gmf_approved_corrections');await db.run('DROP TABLE gmf_card_revisions');await db.run('DELETE FROM gmf_schema WHERE version>=7');await db.run('INSERT OR IGNORE INTO gmf_schema(version) VALUES (6)');await db.run("UPDATE gmf_settings SET payload=? WHERE id='organization'",[JSON.stringify({short_name:'Preserved organization'})]);}finally{await db.close();}
  const entry=fileURLToPath(new URL('../scripts/release-start.js',import.meta.url));
  const result=spawnSync(process.execPath,['-e',`const log=console.log;console.log=(...args)=>{log(...args);if(String(args[0]).includes('Gramaswaraj listening'))setTimeout(()=>process.exit(0),100);};require(${JSON.stringify(entry)});`],{
   cwd:fileURLToPath(new URL('..',import.meta.url)),encoding:'utf8',timeout:30000,
   env:{...process.env,NODE_ENV:'development',PORT:'0',MYSQL_URL:'',SQLITE_PATH:sqlite,RUN_MIGRATIONS:'false',BOOTSTRAP_ADMIN:'false'}
  });
  assert.equal(result.status,0,result.stderr);assert.match(result.stdout,/Gramaswaraj listening on port 0/);
  assert.doesNotMatch(result.stderr,/ERR_REQUIRE_ASYNC_MODULE|Startup failed/);
  const upgraded=await database({sqlite});try{assert.equal((await upgraded.all('SELECT MAX(version) AS n FROM gmf_schema'))[0].n,8);assert.equal(JSON.parse((await upgraded.all("SELECT payload FROM gmf_settings WHERE id='organization'"))[0].payload).short_name,'Preserved organization');assert.equal((await upgraded.all('SELECT COUNT(*) AS n FROM gmf_approved_corrections'))[0].n,0);}finally{await upgraded.close();}
 }finally{await rm(directory,{recursive:true,force:true});}
});
