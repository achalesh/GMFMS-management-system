import {test} from 'node:test';
import assert from 'node:assert/strict';
import {database} from '../src/database.js';
import {config} from '../src/config.js';
import {migrate} from '../src/schema.js';
import {accountAction,changePassword,updateSettings} from '../src/administration.js';
import {settings,organizationDefaults} from '../src/settings.js';
import {loadUser,can} from '../src/policies.js';
import {hashPassword} from '../src/security.js';
test('account permissions, revision checks, forced password change and session invalidation',async()=>{
 const db=await database({...config({}),sqlite:':memory:'});try{
 await migrate(db);await db.run('INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES (?,?,?,?,1)',['admin','admin','admin@example.invalid',await hashPassword('administrator-test-123')]);
 const id=await accountAction(db,'admin',{action:'create',username:'staff',email:'staff@example.invalid',password:'temporary-password-123',reason:'Test account'});
 assert.equal((await loadUser(db,id)).must_change,1);
 await assert.rejects(accountAction(db,id,{action:'active',user_id:'admin',revision:1,reason:'Denied'}),e=>e.status===403);
 await assert.rejects(accountAction(db,'admin',{action:'active',user_id:'admin',revision:1,reason:'Self disable'}));
 await accountAction(db,'admin',{action:'assign',user_id:id,revision:1,role:'VIEWER',scope:'STATE',reason:'Viewer access'});
 assert(can(await loadUser(db,id),'facilitators.view'));
 await assert.rejects(accountAction(db,'admin',{action:'active',user_id:id,revision:1,reason:'Stale'}),e=>e.status===409);
 await db.run('INSERT INTO gmf_sessions(id,payload,expires_at) VALUES (?,?,?)',['staff-session',JSON.stringify({userId:id}),Date.now()+100000]);
 await assert.rejects(changePassword(db,id,{current_password:'incorrect',password:'new-password-12345'}));
 await changePassword(db,id,{current_password:'temporary-password-123',password:'new-password-12345'});
 assert.equal((await loadUser(db,id)).must_change,0);assert.equal((await db.all('SELECT id FROM gmf_sessions')).length,0);
 assert(!JSON.stringify(await db.all('SELECT changes FROM gmf_audit_details')).includes('password-123'));
 // Removing the only manager's assignment must roll back.
 await db.run('UPDATE gmf_users SET superuser=0 WHERE id=?',['admin']);
 await db.run('INSERT INTO gmf_scopes(id,user_id,role,scope) VALUES (?,?,?,?)',['manager','admin','SUPER_ADMIN','STATE']);
 await assert.rejects(accountAction(db,'admin',{action:'remove',user_id:'admin',revision:1,assignment_id:'manager',reason:'Last manager'}));
 assert(can(await loadUser(db,'admin'),'accounts.manage'));
 }finally{await db.close();}
});
test('settings restrict access, validate document codes and reject stale edits',async()=>{
 const db=await database({...config({}),sqlite:':memory:'});try{
 await migrate(db);await db.run('INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES (?,?,?,?,1)',['admin','admin','admin@example.invalid','unused']);
 const input={...organizationDefaults,revision:1,reason:'Organization update',short_name:'Test Brand'};
 await updateSettings(db,'admin','organization',input);assert.equal((await settings(db,'organization')).data.short_name,'Test Brand');
 await assert.rejects(updateSettings(db,'admin','organization',input),e=>e.status===409);
 await assert.rejects(updateSettings(db,'admin','system',{revision:1,reason:'Invalid document',prefix:'GS-MF',validity_days:365,consent_version:'1.0',required_documents:['unknown']}));
 await updateSettings(db,'admin','system',{revision:1,reason:'Close registration',prefix:'GS-MF',validity_days:365,consent_version:'1.0'});
 assert.equal((await settings(db,'system')).data.registration_open,false);
 }finally{await db.close();}
});
