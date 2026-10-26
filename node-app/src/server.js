import 'dotenv/config';
import {config} from './config.js';
import {database} from './database.js';
import {createApp} from './app.js';
import {schemaVersion,migrate} from './schema.js';
try{
 const cfg=config(),db=await database(cfg);
 let versions=await db.all('SELECT MAX(version) AS version FROM gmf_schema');
 // Version 7 only adds correction staging and card revision tables; existing records are untouched.
 if(versions[0]?.version===6&&schemaVersion===7){await migrate(db);versions=await db.all('SELECT MAX(version) AS version FROM gmf_schema');}
 if(versions[0]?.version!==schemaVersion)throw Error('Run database migration first');
 const app=await createApp(db,cfg);const server=app.listen(cfg.port,cfg.production?'0.0.0.0':'127.0.0.1',()=>console.log(`Gramaswaraj listening on port ${cfg.port}`));
 for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>server.close(async()=>{await db.close();process.exit(0);}));
}catch{console.error('Startup failed. Check configuration and run db:migrate first.');process.exitCode=1;}
