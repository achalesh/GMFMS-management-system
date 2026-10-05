import {test} from 'node:test';
import assert from 'node:assert/strict';
import {database} from '../src/database.js';
import {migrate} from '../src/schema.js';
import {seed} from '../src/seed.js';
import {hashPassword,verifyPassword,validCsrf,budget} from '../src/security.js';
import {config} from '../src/config.js';
import {can} from '../src/policies.js';
import {createApp} from '../src/app.js';
test('password hashing, malformed CSRF and production configuration',async()=>{
 const hash=await hashPassword('test-password-123');assert(await verifyPassword('test-password-123',hash));assert.equal(await verifyPassword('wrong',hash),false);assert.equal(validCsrf({csrf:'a'},'a'.repeat(64)),false);assert.throws(()=>config({NODE_ENV:'production'}));
});
test('jurisdiction does not combine privileges across assignments',()=>{
 const user={active:1,scopes:[{active:1,role:'DISTRICT_ADMIN',scope:'DISTRICT',district_code:'A',district_active:1,state_active:1},{active:1,role:'VIEWER',scope:'STATE'}]};
 assert(can(user,'applications.approve',{district_code:'A'}));assert.equal(can(user,'applications.approve',{district_code:'B'}),false);assert.equal(can({...user,active:0},'locations.view'),false);
});
test('login, rotation, persistence, directory, CSRF, account disabling and throttling',async()=>{
 const cfg={...config({}),sqlite:':memory:'};const db=await database(cfg);let server;
 try{
 await migrate(db);await seed(db);await seed(db);
 for(const [table,count] of [['districts',14],['blocks',152],['panchayats',941]])assert.equal((await db.all(`SELECT COUNT(*) AS n FROM gmf_${table}`))[0].n,count);
 await db.run('INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES (?,?,?,?,1)',['test','tester','test@example.invalid',await hashPassword('test-password-123')]);
 const app=await createApp(db,cfg);server=app.listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));const base=`http://127.0.0.1:${server.address().port}`;cfg.origin=base;
 let cookie='';async function request(url,options={}){const r=await fetch(base+url,{redirect:'manual',...options,headers:{cookie,...options.headers}});const next=r.headers.get('set-cookie');if(next)cookie=next.split(';')[0];return r;}
 assert.equal((await request('/locations/')).status,302);
 const html=await(await request('/accounts/login/')).text();let csrf=html.match(/name="csrf" value="([a-f0-9]+)"/)[1];const old=cookie;
 const post=(body)=>({method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams(body)});
 assert.equal((await request('/accounts/login/',post({username:'tester',password:'test-password-123'}))).status,403);
 assert.equal((await request('/accounts/login/',post({csrf,username:'tester',password:'test-password-123'}))).status,302);assert.notEqual(cookie,old);
 const home=await(await request('/')).text();assert.match(home,/941/);csrf=home.match(/name="csrf" value="([a-f0-9]+)"/)[1];
 assert.match(await(await request('/locations/?q=Varkala')).text(),/Varkala/);
 assert.equal((await request('/.env')).status,404);assert.equal((await request('/accounts/logout/')).status,404);
 assert.equal((await request('/accounts/logout/',post({csrf}))).status,302);assert.equal((await request('/')).status,302);
 const login=await(await request('/accounts/login/')).text();csrf=login.match(/name="csrf" value="([a-f0-9]+)"/)[1];await request('/accounts/login/',post({csrf,username:'tester',password:'test-password-123'}));await db.run('UPDATE gmf_users SET active=0 WHERE id=?',['test']);assert.equal((await request('/')).status,302);
 assert(await budget(db,'secret','test','identity',1));assert.equal(await budget(db,'secret','test','identity',1),false);
 }finally{if(server)await new Promise(r=>server.close(r));await db.close();}
});
