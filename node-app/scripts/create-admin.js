import 'dotenv/config';
import {randomUUID} from 'node:crypto';
import {config} from '../src/config.js';
import {database} from '../src/database.js';
import {hashPassword} from '../src/security.js';
const username=(process.env.ADMIN_USERNAME||'').trim().toLowerCase(),email=(process.env.ADMIN_EMAIL||'').trim();
if(!/^[a-z0-9_.-]{3,150}$/.test(username)||!/^\S+@\S+\.\S+$/.test(email)||email.length>254)throw Error('Provide ADMIN_USERNAME and ADMIN_EMAIL');
const hash=await hashPassword(process.env.ADMIN_PASSWORD);delete process.env.ADMIN_PASSWORD;
const db=await database(config());try{await db.transaction(async tx=>{const id=randomUUID();await tx.run('INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES (?,?,?,?,1)',[id,username,email,hash]);await tx.run('INSERT INTO gmf_audit(id,user_id,action,created_at) VALUES (?,?,?,?)',[randomUUID(),id,'admin.created',Date.now()]);});console.log('Administrator created.');}finally{await db.close();}
