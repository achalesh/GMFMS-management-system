import 'dotenv/config';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
// Explicit first-release switches. The server also supports the additive schema 6/7-to-8 upgrade.
for(const [flag,file] of [['RUN_MIGRATIONS','migrate.js'],['BOOTSTRAP_ADMIN','create-admin.js']]){
 if(process.env[flag]==='true'){
  const result=spawnSync(process.execPath,[fileURLToPath(new URL(file,import.meta.url))],{stdio:'inherit',env:process.env});
  if(result.status!==0)process.exit(result.status||1);
 }
}
delete process.env.ADMIN_PASSWORD;
// Hostinger's LiteSpeed launcher requires this entry synchronously.
// Keep the asynchronous ESM server behind a dynamic import, with no top-level await here.
import('../src/server.js').catch(()=>{
 console.error('Server module failed to load. Check deployment dependencies and configuration.');
 process.exitCode=1;
});
