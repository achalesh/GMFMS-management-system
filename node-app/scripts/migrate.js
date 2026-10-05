import 'dotenv/config';
import {config} from '../src/config.js';
import {database} from '../src/database.js';
import {migrate} from '../src/schema.js';
import {seed} from '../src/seed.js';
const db=await database(config());try{await migrate(db);await seed(db);console.log('Schema and Kerala directory ready.');}finally{await db.close();}
