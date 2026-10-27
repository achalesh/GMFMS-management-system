import 'dotenv/config';
import {config} from './config.js';
import {database} from './database.js';
import {createApp} from './app.js';
import {schemaVersion,migrate} from './schema.js';
try{
 const cfg=config(),db=await database(cfg);
 let versions=await db.all('SELECT MAX(version) AS version FROM gmf_schema');
 // Versions 7 and 8 only add correction/card history and facilitator account tables.
 if([6,7].includes(versions[0]?.version)&&schemaVersion===8){await migrate(db);versions=await db.all('SELECT MAX(version) AS version FROM gmf_schema');}
 if(versions[0]?.version!==schemaVersion)throw Error('Run database migration first');
 const app=await createApp(db,cfg);const server=app.listen(cfg.port,cfg.production?'0.0.0.0':'127.0.0.1',()=>console.log(`Gramaswaraj listening on port ${cfg.port}`));
 for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>server.close(async()=>{await db.close();process.exit(0);}));
}catch{console.error('Startup failed. Check configuration and run db:migrate first.');process.exitCode=1;}
