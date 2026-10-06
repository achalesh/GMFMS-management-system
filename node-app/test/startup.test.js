import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {database} from '../src/database.js';
import {migrate} from '../src/schema.js';

test('CommonJS hosting launcher can require the release entry and start the ESM server',async()=>{
 const directory=await mkdtemp(path.join(tmpdir(),'gmf-startup-'));
 const sqlite=path.join(directory,'test.sqlite');
 try{
  const db=await database({sqlite});try{await migrate(db);}finally{await db.close();}
  const entry=fileURLToPath(new URL('../scripts/release-start.js',import.meta.url));
  const result=spawnSync(process.execPath,['-e',`const log=console.log;console.log=(...args)=>{log(...args);if(String(args[0]).includes('Gramaswaraj listening'))setTimeout(()=>process.exit(0),100);};require(${JSON.stringify(entry)});`],{
   cwd:fileURLToPath(new URL('..',import.meta.url)),encoding:'utf8',timeout:30000,
   env:{...process.env,NODE_ENV:'development',PORT:'0',MYSQL_URL:'',SQLITE_PATH:sqlite,RUN_MIGRATIONS:'false',BOOTSTRAP_ADMIN:'false'}
  });
  assert.equal(result.status,0,result.stderr);assert.match(result.stdout,/Gramaswaraj listening on port 0/);
  assert.doesNotMatch(result.stderr,/ERR_REQUIRE_ASYNC_MODULE|Startup failed/);
 }finally{await rm(directory,{recursive:true,force:true});}
});
