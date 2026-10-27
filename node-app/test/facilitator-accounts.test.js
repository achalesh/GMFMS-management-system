import {test} from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {database} from '../src/database.js';
import {migrate} from '../src/schema.js';
import {seed} from '../src/seed.js';
import {config} from '../src/config.js';
import {hashPassword,verifyPassword} from '../src/security.js';
import {loadUser,can} from '../src/policies.js';
import {accountAction,changePassword} from '../src/administration.js';
import {provisionFacilitatorAccount,ownFacilitator,ownCard} from '../src/facilitator-accounts.js';
import {cardAction,hash} from '../src/cards.js';
import {createApp} from '../src/app.js';
async function setup(){const db=await database({sqlite:':memory:'});await migrate(db);await seed(db);
 await db.run("INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES ('admin','admin','admin@example.invalid',?,1)",[await hashPassword('Admin-password-123')]);
 const photo=await sharp({create:{width:200,height:300,channels:3,background:'#888'}}).jpeg().toBuffer();
 for(const [id,name,mobile,role] of [['one','First Facilitator','9876543210','PRIMARY'],['two','Other Facilitator','9876543211','ASSISTANT']]){
 await db.run('INSERT INTO gmf_applications(id,number,panchayat_code,payload,full_name,normalized_name,mobile,email,status,submitted_at) VALUES (?,?,?,?,?,?,?,?,?,?)',[id,'APP-'+id,'G01071',JSON.stringify({2:{full_name:name,mobile,address:'Private address '+id},3:{},4:{}}),name,name,mobile,'','APPROVED',0]);
 await db.run('INSERT INTO gmf_uploads(owner_id,slot,mime,body,sha256) VALUES (?,?,?,?,?)',[id,'photo','image/jpeg',photo.toString('base64'),hash(photo)]);
 await db.run('INSERT INTO gmf_facilitators(id,application_id,number,panchayat_code,full_name,role,valid_until,primary_key,approved_by,approved_at) VALUES (?,?,?,?,?,?,?,?,?,?)',[id,id,'GS-MF-TVM-'+id,'G01071',name,role,'2099-01-01',role==='PRIMARY'?'G01071':null,'admin',0]);}
 return db;}
const allocation={action:'create',username:'gs-mf-tvm-one',revision:1,email:'',reason:'Allocate personal facilitator access.'};
test('facilitator account allocation is restricted, one-to-one, hashed and has no staff privileges',async()=>{const db=await setup();try{
 const credentials=await provisionFacilitatorAccount(db,'admin','one',allocation),row=(await db.all('SELECT * FROM gmf_users WHERE username=?',[credentials.username]))[0];
 assert.ok(await verifyPassword(credentials.password,row.password_hash));assert.notEqual(row.password_hash,credentials.password);const user=await loadUser(db,row.id);assert.equal(user.must_change,1);assert.equal(user.facilitator_id,'one');assert.equal(can(user,'applications.view'),false);assert.equal(can(user,'accounts.manage'),false);assert.equal((await db.all('SELECT COUNT(*) AS n FROM gmf_scopes WHERE user_id=?',[row.id]))[0].n,0);
 await assert.rejects(ownFacilitator(db,row.id),/temporary password/);assert.ok(!JSON.stringify(await db.all('SELECT * FROM gmf_audit_details')).includes(credentials.password));
 await assert.rejects(provisionFacilitatorAccount(db,'admin','one',allocation));await assert.rejects(provisionFacilitatorAccount(db,row.id,'two',{...allocation,username:'stolen'}));
 await assert.rejects(accountAction(db,'admin',{action:'assign',user_id:row.id,revision:1,role:'VIEWER',scope:'STATE',reason:'Should be blocked'}));
 await db.run("UPDATE gmf_facilitators SET status='SUSPENDED' WHERE id='two'");await assert.rejects(provisionFacilitatorAccount(db,'admin','two',{...allocation,username:'two-user'}));
 }finally{await db.close();}});

test('temporary login forces password change; personal portal denies other records and reset ends sessions',async()=>{const db=await setup(),cfg=config({});let server;try{
 await cardAction(db,cfg,'admin','one',{action:'issue',revision:1,reason:'Issue test card'});
 const credentials=await provisionFacilitatorAccount(db,'admin','one',{...allocation,revision:2});const owner=(await db.all('SELECT user_id FROM gmf_facilitator_accounts WHERE facilitator_id=?',['one']))[0].user_id;
 const app=await createApp(db,cfg);server=app.listen(0,'127.0.0.1');await new Promise(resolve=>server.once('listening',resolve));const base=`http://127.0.0.1:${server.address().port}`;
 let cookie='',csrf='';async function request(path,body){const options={redirect:'manual',headers:{cookie}};if(body){options.method='POST';options.headers['content-type']='application/x-www-form-urlencoded';options.body=new URLSearchParams({csrf,...body});}const response=await fetch(base+path,options);if(response.headers.get('set-cookie'))cookie=response.headers.get('set-cookie').split(';')[0];const text=await response.text();csrf=text.match(/name="csrf" value="([a-f0-9]+)"/)?.[1]||csrf;return {status:response.status,location:response.headers.get('location'),text,headers:response.headers};}
 await request('/accounts/login/');assert.equal((await request('/accounts/login/',{username:credentials.username,password:credentials.password})).status,302);
 for(const path of ['/','/my/','/my/card/preview/','/applications/','/register/'])assert.equal((await request(path)).location,'/accounts/password/');
 assert.ok((await request('/accounts/password/')).text.includes('must change your temporary password'));
 const permanent='My-permanent-password-123';assert.equal((await request('/accounts/password/',{current_password:credentials.password,password:permanent,confirm_password:permanent})).location,'/accounts/login/');assert.equal((await loadUser(db,owner)).must_change,0);
 await request('/accounts/login/');assert.equal((await request('/accounts/login/',{username:credentials.username,password:credentials.password})).status,401);assert.equal((await request('/accounts/login/',{username:credentials.username,password:permanent})).status,302);
 assert.equal((await request('/')).location,'/my/');const profile=await request('/my/?facilitator_id=two');assert.equal(profile.status,200);assert.ok(profile.text.includes('First Facilitator'));assert.ok(!profile.text.includes('Other Facilitator'));assert.ok(!profile.text.includes('Dashboard'));
 for(const path of ['/applications/two/','/reports/','/facilitators/two/login/','/administration/'])assert.equal((await request(path)).location,'/my/');
 assert.equal((await request('/my/card/preview/')).status,200);assert.ok((await ownCard(db,cfg,owner)).bytes.length>100);
 assert.equal((await request('/my/card/',{format:'pdf'})).status,200);
 const reset=await provisionFacilitatorAccount(db,'admin','one',{action:'reset',revision:2,account_revision:2,reason:'Facilitator forgot password.'});assert.equal(reset.username,credentials.username);assert.equal((await loadUser(db,owner)).must_change,1);assert.equal((await request('/my/')).location,'/accounts/login/');
 await assert.rejects(provisionFacilitatorAccount(db,'admin','one',{action:'reset',revision:2,account_revision:2,reason:'Stale reset'}));
 }finally{if(server)await new Promise(resolve=>server.close(resolve));await db.close();}});
