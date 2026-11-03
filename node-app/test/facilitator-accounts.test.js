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
import {provisionFacilitatorAccount,ownFacilitator,ownCard,updateOwnProfile} from '../src/facilitator-accounts.js';
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
 const edit=await request('/my/profile/edit/');assert.equal(edit.status,200);assert.ok(edit.text.includes('Public display consent'));assert.ok(!edit.text.includes('name="mobile"'));
 const missingCsrf=csrf;csrf='bad';assert.equal((await request('/my/profile/edit/',{revision:1})).status,403);csrf=missingCsrf;
 assert.equal((await request('/my/card/preview/')).status,200);assert.ok((await ownCard(db,cfg,owner)).bytes.length>100);
 assert.equal((await request('/my/card/',{format:'pdf'})).status,200);
 const saved=await request('/my/profile/edit/',{revision:1,occupation:'Journalist',years_experience:'2',languages:'Malayalam',public_email:'on'});assert.equal(saved.location,'/my/?updated=1');
 const updated=await request('/my/?updated=1');assert.ok(updated.text.includes('Profile updated successfully'));assert.ok(updated.text.includes('Journalist'));assert.ok(updated.text.indexOf('My ID card')<updated.text.indexOf('Profile details'));assert.ok(updated.text.includes('/my/card/preview/#toolbar=0'));

 const reset=await provisionFacilitatorAccount(db,'admin','one',{action:'reset',revision:2,account_revision:2,reason:'Facilitator forgot password.'});assert.equal(reset.username,credentials.username);assert.equal((await loadUser(db,owner)).must_change,1);assert.equal((await request('/my/')).location,'/accounts/login/');
 await assert.rejects(provisionFacilitatorAccount(db,'admin','one',{action:'reset',revision:2,account_revision:2,reason:'Stale reset'}));
 }finally{if(server)await new Promise(resolve=>server.close(resolve));await db.close();}});

test('self profile updates validate safe fields, preserve identity and cards and audit changes',async()=>{
 const db=await setup(),cfg=config({});
 try{
 await cardAction(db,cfg,'admin','one',{action:'issue',revision:1,reason:'Issue test card'});
 const credentials=await provisionFacilitatorAccount(db,'admin','one',{...allocation,revision:2});
 const owner=(await db.all('SELECT user_id FROM gmf_facilitator_accounts WHERE facilitator_id=?',['one']))[0].user_id;
 await changePassword(db,owner,{current_password:credentials.password,password:'New-personal-password-123'});
 const original=(await ownCard(db,cfg,owner)).card;
 const input={revision:1,occupation:'Reporter',qualification:'Degree',current_organization:'Media',designation:'Writer',media_experience:'Local reporting',years_experience:'5',languages:['Malayalam'],skills:[],equipment:[],facebook:'https://example.org/profile',public_mobile:'on'};
 await updateOwnProfile(db,owner,input);
 const profile=await ownFacilitator(db,owner);
 assert.equal(profile.application.data[3].occupation,'Reporter');
 assert.equal(profile.application.data[4].facebook,input.facebook);
 assert.equal(profile.application.data.consent.public_mobile,true);
 assert.equal(profile.application.data.consent.public_email,false);
 assert.equal(profile.application.number,'APP-one');assert.equal(profile.f.number,'GS-MF-TVM-one');
 const current=(await ownCard(db,cfg,owner)).card;assert.equal(current.number,original.number);assert.equal(current.pdf_hash,original.pdf_hash);
 const audit=JSON.parse((await db.all("SELECT changes FROM gmf_audit_details WHERE id IN (SELECT id FROM gmf_audit WHERE action='facilitator.profile_updated')"))[0].changes);
 assert.equal(audit.after[3].occupation,'Reporter');assert.deepEqual(audit.before[3],{});
 await assert.rejects(updateOwnProfile(db,owner,input),e=>e.status===409);
 for(const key of ['full_name','mobile','email','panchayat','blood_group','facilitator_id'])await assert.rejects(updateOwnProfile(db,owner,{...input,revision:2,[key]:'forged'}),/Only professional/);
 await assert.rejects(updateOwnProfile(db,owner,{...input,revision:2,facebook:'javascript:alert(1)'}),/HTTP/);
 await assert.rejects(updateOwnProfile(db,owner,{...input,revision:2,languages:['Invalid']}),/valid/);
 await assert.rejects(updateOwnProfile(db,'admin',input),e=>e.status===403);
 await db.run("INSERT INTO gmf_approved_corrections(id,application_id,app_revision,facilitator_revision,original_payload,payload,changed,created_at) VALUES ('pending','one',2,2,'{}','{}','[]',0)");
 await assert.rejects(updateOwnProfile(db,owner,{...input,revision:2}),/correction is pending/);
 await db.run("UPDATE gmf_approved_corrections SET state='CANCELLED' WHERE id='pending'");
 await updateOwnProfile(db,owner,{...input,revision:2,public_mobile:undefined});
 assert.equal((await ownFacilitator(db,owner)).application.data.consent.public_mobile,false);
 await db.run("UPDATE gmf_facilitators SET status='SUSPENDED' WHERE id='one'");
 await assert.rejects(updateOwnProfile(db,owner,{...input,revision:3}),e=>e.status===403);
 }finally{await db.close();}
});
